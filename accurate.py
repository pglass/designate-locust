import csv
import json
import datetime
import random
from collections import namedtuple

from locust import HttpLocust
from locust import TaskSet
from locust import task
from locust.clients import HttpSession
import locust.events
import locust.config

import gevent

import client
import graphite_client
import digaas_integration
import persistence
import insight
import greenlet_manager
from client import DesignateClient
from web import *
from datagen import *
import accurate_config as CONFIG

# require a username + password to access the web interface
setup_authentication(CONFIG.username, CONFIG.password)

# send metrics to a graphite server
graphite_client.setup_graphite_communication(
    CONFIG.graphite_host, CONFIG.graphite_port)

# save a report when the test finishes
persistence.setup_persistence()

locust.config.RESET_STATS_AFTER_HATCHING = CONFIG.reset_stats

ZoneTuple = namedtuple('ZoneTuple', ['tenant', 'api_key', 'id', 'name'])
RecordTuple = namedtuple('RecordTuple', ['tenant', 'api_key', 'zone_id',
                                         'zone_name', 'record_id',
                                         'record_data', 'record_type'])

_client = HttpSession(CONFIG.designate_host)
_designate_client = DesignateClient(_client)
_digaas_client = digaas_integration.DigaasClient(CONFIG.digaas_endpoint)

# use digaas to externally poll the nameserver(s) to record zone propagation
# times through Designate's stack
if CONFIG.use_digaas and not insight.is_slave():
    digaas_integration.setup_digaas_integration(_digaas_client)


def prepare_headers_with_tenant(tenant):
    return { client.ROLE_HEADER: 'admin',
             client.PROJECT_ID_HEADER: tenant }

def get_domains_data(tenants, n):
    # print "Tenants: %s" % tenants
    result = []
    for tenant in tenants:
        # print "Using tenant: %s" % tenant
        resp = _designate_client.list_zones(
            headers=prepare_headers_with_tenant(tenant),
            params={"limit": n},
            name='-- prep data')
        if not resp.ok:
            raise Exception("Failed to list zones for tenant %s" % tenant)
        else:
            for zone in resp.json()['zones']:
                val = ZoneTuple(tenant=tenant, api_key=None, id=zone['id'], name=zone['name'])
                # print val
                result.append(val)
    random.shuffle(result)
    print "Got %s domains for tenants %s" % (len(result), tenants)
    return result

def get_records_data(zone_infos, n, rtype):
    result = []
    for zone_info in zone_infos:
        resp = _designate_client.list_recordsets(
            zone_info.id,
            headers=prepare_headers_with_tenant(zone_info.tenant),
            params={"limit": n, "type": rtype},
            name='-- prep data')
        if not resp.ok:
            raise Exception("Failed to list recordsets for tenant %s" % zone_info.tenant)

        if rtype == 'A' and not len(resp.json()['recordsets']):
            ip = random_ip()
            payload = { "name" : zone_info.name,
                        "type" : "A",
                        "ttl" : 3600,
                        "records" : [ ip ] }
            #print "%s creating A record %s --> %s" % (zone_info.tenant, zone_info.name, ip)
            resp = _designate_client.post_recordset(
                zone_info.id, data=json.dumps(payload),
                headers=prepare_headers_with_tenant(zone_info.tenant),
                name='-- prep data')
            recordset = resp.json()
            record = recordset['records'][0]  # !
            val = RecordTuple(zone_info.tenant, zone_info.api_key, zone_info.id,
                              zone_info.name, recordset['id'], record,
                              recordset['type'])
            result.append(val)
        else:
            #print "%s found %s A records for domain %s" \
                    #% (zone_info.tenant, len(resp.json()['recordsets']), zone_info.id)
            for recordset in resp.json()['recordsets']:
                val = RecordTuple(tenant=zone_info.tenant,
                                  api_key=None,
                                  zone_id=zone_info.id,
                                  zone_name=zone_info.name,
                                  record_id=recordset['id'],
                                  record_data=recordset['records'],
                                  record_type=recordset['type'])
                # print val
                result.append(val)
    print "Got %s records for tenants %s" % (len(result), set([z.tenant for z in zone_infos]))
    return result

def split(L, n):
    result = []
    for i in xrange(n):
        f = i * len(L) / n
        t = (i+1) * len(L) / n
        result.append(L[f:t])
    return result


class TestData(object):

    def __init__(self, tenant_list):
        self.domain_get_data = []
        self.domain_delete_data = []
        self.record_get_data = []
        self.record_delete_data = []
        self.record_update_data = []
        self.tenant_list = list(tenant_list)

    def refresh(self, n_domains_per_tenant, n_records_per_domain):
        """Discard currently stored data and fetch new data from Designate."""
        domain_data = get_domains_data(self.tenant_list, n_domains_per_tenant)

        self.domain_get_data,    \
        self.domain_delete_data, \
        records_domains = split(domain_data, 3)

        # assume precreated NS records for gets (we can't always update these)
        self.record_get_data = get_records_data(records_domains, n_records_per_domain, 'NS')

        # assume precreated A records for deletes and updates
        a_records = get_records_data(records_domains, n_records_per_domain, 'A')

        self.record_update_data, self.record_delete_data = split(a_records, 2)

    def __str__(self):
        return ("TestData[domains=(get: %s, delete: %s), "
                "records=(get: %s, delete: %s, update: %s))"
                % (len(self.domain_get_data), len(self.domain_delete_data),
                   len(self.record_get_data), len(self.record_delete_data),
                   len(self.record_update_data)))

    def pick_zone_for_get(self):
        """Returns a tuple (tenant, api_key, zone_id, zone_name)"""
        return select_random_item(self.domain_get_data)

    def pick_zone_for_delete(self):
        """Returns a tuple (tenant, api_key, zone_id, zone_name)"""
        val = select_random_item(self.domain_delete_data)
        # ensure we don't pick this twice
        if val:
            self.domain_delete_data.remove(val)
        #print "deleted record - %s" % self.test_data
        return val

    def pick_record_for_get(self):
        """Returns a tuple (tenant, api_key, zone_id, zone_name, record_id,
        record_data, record_type)"""
        return select_random_item(self.record_get_data)

    def pick_record_for_update(self):
        return select_random_item(self.record_update_data)

    def pick_record_for_delete(self):
        """Returns a tuple (tenant, api_key, zone_id, zone_name, record_id,
        record_data, record_type)"""
        val = select_random_item(self.record_delete_data)
        if val:
            self.record_delete_data.remove(val)
        #print "deleted record - %s" % self.test_data
        return val

    def pick_random_tenant(self):
        return select_random_item(self.tenant_list)


def refresh_test_data(previous, current):
    if current == locust.runners.STATE_HATCHING:
        print "refreshing test data for large tenants..."
        LARGE_DATA.refresh(CONFIG.n_large_domains_per_tenant, CONFIG.n_large_records_per_domain)
        print "Large: %s" % LARGE_DATA

        print "refreshing test data for small tenants..."
        SMALL_DATA.refresh(CONFIG.n_small_domains_per_tenant, CONFIG.n_small_records_per_domain)
        print "Small: %s" % SMALL_DATA


if not insight.is_master():
    LARGE_DATA = TestData(CONFIG.large_tenants)
    SMALL_DATA = TestData(CONFIG.small_tenants)
    locust.events.state_changed += refresh_test_data

    # the greenlet_manager is used to keep track of greenlets spawned to poll
    # note: it's hard to ensure cleanup_greenlets gets run before the stats
    # are persisted to a file...
    GREENLET_MANAGER = greenlet_manager.GreenletManager()
    # ensure cleanup when the test is stopped
    locust.events.locust_stop_hatching += \
        lambda: GREENLET_MANAGER.cleanup_greenlets()
    # ensure cleanup on interrupts
    locust.events.quitting += \
        lambda: GREENLET_MANAGER.cleanup_greenlets()


class Tasks(TaskSet):

    def __init__(self, test_data, *args, **kwargs):
        super(Tasks, self).__init__(*args, **kwargs)

        self.designate_client = DesignateClient(self.client)

        self.test_data = test_data

        if CONFIG.use_digaas:
            self.digaas_client = digaas_integration.DigaasClient(CONFIG.digaas_endpoint)
            self.digaas_behaviors = digaas_integration.DigaasBehaviors(self.digaas_client, CONFIG)

    def prepare_headers_with_tenant(self, tenant_id=None):
        return { client.ROLE_HEADER: 'admin',
                 client.PROJECT_ID_HEADER: tenant_id or self.test_data.pick_random_tenant() }

    @task
    def get_domain_by_id(self):
        """GET /zones/{id}"""
        zone_info = self.test_data.pick_zone_for_get()
        # print "get_domain_by_id: %s, %s, %s" % (tenant, zone_id, zone_name)
        headers = self.prepare_headers_with_tenant(tenant_id=zone_info.tenant)
        resp = self.designate_client.get_zone(zone_info.id,
                                              name='/v2/zones/{id}',
                                              headers=headers)

    @task
    def get_domain_by_name(self):
        """GET /zones?name=<name>"""
        zone_info = self.test_data.pick_zone_for_get()
        # print "get_domain_by_name: %s, %s, %s" % (tenant, zone_id, zone_name)
        headers = self.prepare_headers_with_tenant(tenant_id=zone_info.tenant)
        resp = self.designate_client.get_zone_by_name(
            zone_name=zone_info.name,
            name='/v2/zones/{id}?name=zoneNAME',
            headers=headers)

    @task
    def list_domains(self):
        """GET /zones"""
        headers = self.prepare_headers_with_tenant()
        self.designate_client.list_zones(name='/v2/zones', headers=headers,
            # at the time of this writing, designate didn't limit by default
            params={'limit': 100})

    @task
    def export_domain(self):
        """GET /zone/{id}, Accept: text/dns"""
        zone_info = self.test_data.pick_zone_for_get()
        # print "export_domain: %s, %s, %s" % (tenant, zone_id, zone_name)
        headers = self.prepare_headers_with_tenant(tenant_id=zone_info.tenant)
        resp = self.designate_client.export_zone(zone_info.id,
                                                 name='/v2/zones/{id} (export)',
                                                 headers=headers)

    @task
    def import_zone(self):
        """POST /zones/tasks/import, Content-type: text/dns"""
        gevent.spawn(GREENLET_MANAGER.tracked_greenlet,
                     lambda: self._do_import_zone(interval=2),
                     timeout=120)

    def _do_import_zone(self, interval):
        zone_file = random_zone_file()
        headers = self.prepare_headers_with_tenant()
        with self.designate_client.import_zone(data=zone_file,
                                               name='/v2/zones/tasks/imports',
                                               headers=headers,
                                               catch_response=True) as import_resp:

            print "[%s]: %s\n%s\nResponse:\n%s" % (
                import_resp.status_code,
                import_resp.request.url,
                import_resp.request.body,
                import_resp.text)

            # TODO: tell digaas to check the zone name. we need the zone name here.
            # if CONFIG.use_digaas and import_resp.ok:
            #     self.digaas_behaviors.check_zone_create_or_update(import_resp)

            if not import_resp.ok:
                import_resp.failure("Failed with status code %s" % import_resp.status_code)
                return

            api_call = lambda: self.designate_client.get_zone_import(
                import_id=import_resp.json()['id'],
                headers=headers,
                name='/v2/zones (status of POST /v2/zones/tasks/imports)')

            self._poll_until_active_or_error(
                api_call=api_call,
                interval=interval,
                status_function=lambda r: r.json()['status'],
                success_function=import_resp.success,
                failure_function=import_resp.failure,
                expected='COMPLETE')

    @task
    def create_domain(self):
        """POST /zones"""
        gevent.spawn(
            GREENLET_MANAGER.tracked_greenlet,
            lambda: self._do_create_domain(interval=2),
            timeout=60
        )

    def _do_create_domain(self, interval):
        zone, email = random_zone_email()
        headers = self.prepare_headers_with_tenant()
        payload = { "name": zone,
                    "email": email,
                    "ttl": 7200 }

        # use the magical with block to let us specify when the request has
        # succeeded. this lets us poll until the status is ACTIVE or ERROR
        with self.designate_client.post_zone(data=json.dumps(payload),
                                             name='/v2/zones',
                                             headers=headers,
                                             catch_response=True) as post_resp:

            if CONFIG.use_digaas and post_resp.ok:
                self.digaas_behaviors.check_zone_create_or_update(post_resp)

            if not post_resp.ok:
                post_resp.failure("Failed with status code %s" % post_resp.status_code)
                return

            api_call = lambda: self.designate_client.get_zone(
                zone_id=post_resp.json()['id'],
                headers=headers,
                name='/v2/zones (status of POST /v2/zones)')
            self._poll_until_active_or_error(
                api_call=api_call,
                interval=interval,
                status_function=lambda r: r.json()['status'],
                success_function=post_resp.success,
                failure_function=post_resp.failure)

    def _poll_until_active_or_error(self, api_call, interval, status_function,
                                    success_function, failure_function,
                                    expected='ACTIVE'):
        # NOTE: this is assumed to be run in a separate greenlet. We use
        # `while True` here, and use gevent to manage a timeout or to kill
        # the greenlet externally.
        while True:
            resp = api_call()
            if resp.ok and status_function(resp) == expected:
                success_function()
                break
            elif resp.ok and status_function(resp) == 'ERROR':
                failure_function("Failed - saw ERROR status")
                break
            gevent.sleep(interval)

    @task
    def modify_domain(self):
        """PATCH /zones/{id}"""
        gevent.spawn(
            GREENLET_MANAGER.tracked_greenlet,
            lambda: self._do_modify_domain(interval=2),
            timeout=60
        )

    def _do_modify_domain(self, interval):
        zone_info = self.test_data.pick_zone_for_get()
        headers = self.prepare_headers_with_tenant(zone_info.tenant)
        payload = { "name": zone_info.name,
                    "email": ("update@" + zone_info.name).strip('.'),
                    "ttl": random.randint(2400, 7200) }
        with self.designate_client.patch_zone(
                zone_info.id, data=json.dumps(payload), headers=headers,
                name='/v2/zones/{id}', catch_response=True) as patch_resp:

            if CONFIG.use_digaas and patch_resp.ok:
                self.digaas_behaviors.check_zone_create_or_update(patch_resp)

            if not patch_resp.ok:
                patch_resp.failure('Failure - got %s status code' % patch_resp.status_code)
                return

            api_call = lambda: self.designate_client.get_zone(
                zone_id=zone_info.id,
                headers=headers,
                name='/v2/zones (status of PATCH /v2/zones/{id})')
            self._poll_until_active_or_error(
                api_call=api_call,
                interval=interval,
                status_function=lambda r: r.json()['status'],
                success_function=patch_resp.success,
                failure_function=patch_resp.failure)

    @task
    def remove_domain(self):
        """DELETE /zones/{id}"""
        gevent.spawn(
            GREENLET_MANAGER.tracked_greenlet,
            lambda: self._do_remove_domain(interval=2),
            timeout=60
        )

    def _do_remove_domain(self, interval):
        zone_info = self.test_data.pick_zone_for_delete()
        if zone_info is None:
            print "remove_domain: got None zone_info"
            return

        headers = self.prepare_headers_with_tenant(zone_info.tenant)

        # digaas uses the start_time when computing the propagation
        # time to the nameserver. We're assuming this time is UTC.
        # Normally, we use the created_at/update_at time returned by the api,
        # but the api doesn't gives us that for a delete
        #
        # IMPORTANT: your locust box must be synchronized to network time,
        # along with your digaas box, or digaas will compute bad durations
        if CONFIG.use_digaas:
            start_time = datetime.datetime.now()

        with self.designate_client.delete_zone(
                zone_info.id, headers=headers, name='/v2/zones/{id}',
                catch_response=True) as del_resp:

            if CONFIG.use_digaas and del_resp.ok:
                self.digaas_behaviors.check_name_removed(zone_info.name, start_time)

            api_call = lambda: self.designate_client.get_zone(
                zone_info.id, headers=headers, catch_response=True,
                name='/v2/zones (status of DELETE /v2/zones/{id})')
            self._poll_until_404(api_call, interval,
                success_function=del_resp.success,
                failure_function=del_resp.failure)

    def _poll_until_404(self, api_call, interval, success_function,
                        failure_function):
        # NOTE: this is assumed to be run in a separate greenlet. We use
        # `while True` here, and use gevent to manage a timeout or to kill
        # the greenlet externally.
        while True:
            with api_call() as resp:
                if resp.status_code == 404:
                    # ensure the 404 isn't marked as a failure in the report
                    resp.success()
                    # mark the original (delete) request as a success
                    success_function()
                    return
            gevent.sleep(interval)

    @task
    def list_records(self):
        """GET /zones/{id}/recordsets"""
        tenant, api_key, zone_id, zone_name = self.test_data.pick_zone_for_get()
        headers = self.prepare_headers_with_tenant(tenant)
        resp = self.designate_client.list_recordsets(
            zone_id, name='/v2/zones/{id}/recordsets', headers=headers,
            # at the time of this writing, designate didn't limit by default
            params={'limit': 100})

    @task
    def get_record(self):
        """GET /zones/{id}/recordsets/recordID"""
        record_info = self.test_data.pick_record_for_get()
        headers = self.prepare_headers_with_tenant(record_info.tenant)
        self.designate_client.get_recordset(
            record_info.zone_id,
            record_info.record_id,
            headers=headers,
            name='/v2/zone/{id}/recordsets/recordID')

    @task
    def create_record(self):
        """POST /zones/{id}/recordsets"""
        gevent.spawn(
            GREENLET_MANAGER.tracked_greenlet,
            lambda: self._do_create_record(interval=2),
            timeout=60
        )

    def _do_create_record(self, interval):
        zone_info = self.test_data.pick_zone_for_get()
        headers = self.prepare_headers_with_tenant(zone_info.tenant)

        a_record_name = "{0}.{1}".format(randomize("record"), zone_info.name)
        payload = { "name" : a_record_name,
                    "type" : "A",
                    "ttl" : 3600,
                    "records" : [ random_ip() ] }

        with self.designate_client.post_recordset(
                zone_info.id,
                data=json.dumps(payload),
                name='/v2/zones/{id}/recordsets',
                headers=headers,
                catch_response=True) as post_resp:

            if CONFIG.use_digaas and post_resp.ok:
                self.digaas_behaviors.check_record_create_or_update(post_resp)

            if not post_resp.ok:
                post_resp.failure("Failed with status code %s" % post_resp.status_code)
                return

            api_call = lambda: self.designate_client.get_recordset(
                zone_id=zone_info.id,
                recordset_id=post_resp.json()['id'],
                headers=headers,
                name='/v2/zones/{id}/recordsets/{id} (POST status check)')
            self._poll_until_active_or_error(
                api_call=api_call,
                interval=interval,
                status_function=lambda r: r.json()['status'],
                success_function=post_resp.success,
                failure_function=post_resp.failure)

    @task
    def modify_record(self):
        gevent.spawn(
            GREENLET_MANAGER.tracked_greenlet,
            lambda: self._do_modify_record(interval=2),
            timeout=60
        )

    def _do_modify_record(self, interval):
        """PATCH /zones/{id}/recordsets/{id}"""
        record_info = self.test_data.pick_record_for_update()
        if not record_info:
            print "modify_record: got None record_info"
            return

        headers = self.prepare_headers_with_tenant(record_info.tenant)
        payload = { "records": [ random_ip() ],
                    "type": "A",
                    # TODO: is using zone_name right?
                    "name": record_info.zone_name,
                    "ttl": random.randint(2400, 7200) }
        with self.designate_client.put_recordset(
                record_info.zone_id,
                record_info.record_id,
                data=json.dumps(payload),
                headers=headers,
                name="/v2/zones/{id}/recordsets/{id}",
                catch_response=True) as put_resp:

            if CONFIG.use_digaas and put_resp.ok:
                self.digaas_behaviors.check_record_create_or_update(put_resp)

            if not put_resp.ok:
                put_resp.failure("Failed with status code %s" % put_resp.status_code)
                return

            api_call = lambda: self.designate_client.get_recordset(
                zone_id=put_resp.json()['zone_id'],
                recordset_id=put_resp.json()['id'],
                headers=headers,
                name='/v2/zones/{id}/recordsets/{id} (PUT status check)')
            self._poll_until_active_or_error(
                api_call=api_call,
                interval=interval,
                status_function=lambda r: r.json()['status'],
                success_function=put_resp.success,
                failure_function=put_resp.failure)

    @task
    def remove_record(self):
        """DELETE /zones/{id}/recordsets/{id}"""
        gevent.spawn(
            GREENLET_MANAGER.tracked_greenlet,
            lambda: self._do_remove_record(interval=2),
            timeout=60
        )

    def _do_remove_record(self, interval):
        record_info = self.test_data.pick_record_for_delete()
        if not record_info:
            print "remove_record: got None record_info"
            return
        headers = self.prepare_headers_with_tenant(record_info.tenant)

        # digaas uses the start_time when computing the propagation
        # time to the nameserver. We're assuming this time is UTC.
        # Normally, we use the created_at/update_at time returned by the api,
        # but the api doesn't gives us that for a delete
        #
        # IMPORTANT: your locust box must be synchronized to network time,
        # along with your digaas box, or digaas will compute bad durations
        if CONFIG.use_digaas:
            start_time = datetime.datetime.now()

        with self.designate_client.delete_recordset(
                record_info.zone_id,
                record_info.record_id,
                name='/v2/zones/{id}/recordsets/{id}',
                headers=headers,
                catch_response=True) as del_resp:

            if CONFIG.use_digaas and del_resp.ok:
                self.digaas_behaviors.check_name_removed(record_info.zone_name, start_time)

            if not del_resp.ok:
                del_resp.failure("Failed with status_code %s" % del_resp.status_code)
                return

            api_call = lambda: self.designate_client.get_recordset(
                record_info.zone_id,
                record_info.record_id,
                headers=headers,
                name='/v2/zones/{id}/recordsets/{id} (DELETE status check)',
                catch_response=True)
            self._poll_until_404(
                api_call=api_call,
                interval=interval,
                success_function=del_resp.success,
                failure_function=del_resp.failure)


class LargeTasks(Tasks):

    tasks = {
        Tasks.get_domain_by_id:   CONFIG.large_weights.get_domain_by_id,
        Tasks.get_domain_by_name: CONFIG.large_weights.get_domain_by_name,
        Tasks.list_domains:       CONFIG.large_weights.list_domain,
        Tasks.import_zone:        CONFIG.large_weights.import_zone,
        Tasks.export_domain:      CONFIG.large_weights.export_domain,
        Tasks.create_domain:      CONFIG.large_weights.create_domain,
        Tasks.modify_domain:      CONFIG.large_weights.modify_domain,
        Tasks.remove_domain:      CONFIG.large_weights.remove_domain,
        Tasks.list_records:       CONFIG.large_weights.list_records,
        Tasks.get_record:         CONFIG.large_weights.get_record,
        Tasks.create_record:      CONFIG.large_weights.create_record,
        Tasks.remove_record:      CONFIG.large_weights.remove_record,
        Tasks.modify_record:      CONFIG.large_weights.modify_record,
    }

    def __init__(self, *args, **kwargs):
        super(LargeTasks, self).__init__(LARGE_DATA, *args, **kwargs)
        self.designate_client = DesignateClient(self.client)


class SmallTasks(Tasks):

    tasks = {
        Tasks.get_domain_by_id:   CONFIG.small_weights.get_domain_by_id,
        Tasks.get_domain_by_name: CONFIG.small_weights.get_domain_by_name,
        Tasks.list_domains:       CONFIG.small_weights.list_domain,
        Tasks.import_zone:        CONFIG.small_weights.import_zone,
        Tasks.export_domain:      CONFIG.small_weights.export_domain,
        Tasks.create_domain:      CONFIG.small_weights.create_domain,
        Tasks.modify_domain:      CONFIG.small_weights.modify_domain,
        Tasks.remove_domain:      CONFIG.small_weights.remove_domain,
        Tasks.list_records:       CONFIG.small_weights.list_records,
        Tasks.get_record:         CONFIG.small_weights.get_record,
        Tasks.create_record:      CONFIG.small_weights.create_record,
        Tasks.remove_record:      CONFIG.small_weights.remove_record,
        Tasks.modify_record:      CONFIG.small_weights.modify_record,
    }

    def __init__(self, *args, **kwargs):
        super(SmallTasks, self).__init__(SMALL_DATA, *args, **kwargs)
        self.designate_client = DesignateClient(self.client)


class AccurateTaskSet(TaskSet):
    """Combines large tenants and small tenants with appropriate weights."""
    tasks = {
        LargeTasks: CONFIG.total_large_weight,
        SmallTasks: CONFIG.total_small_weight,
    }

class Locust(HttpLocust):
    task_set = AccurateTaskSet

    min_wait = CONFIG.min_wait
    max_wait = CONFIG.max_wait

    host = CONFIG.designate_host

