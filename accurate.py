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

import redis

import client
import graphite_client
import persistence
from client import DesignateClient
from web import *
from datagen import *
from redis_buf import RedisBuffer
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

def _prepare_headers_w_tenant(tenant):
    return { client.ROLE_HEADER: 'admin',
             client.PROJECT_ID_HEADER: tenant }

def get_domains_data(tenants, n):
    # print "Tenants: %s" % tenants
    result = []
    for tenant in tenants:
        # print "Using tenant: %s" % tenant
        resp = _designate_client.list_zones(
            headers=_prepare_headers_w_tenant(tenant),
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
            headers=_prepare_headers_w_tenant(zone_info.tenant),
            params={"limit": n, "type": rtype},
            name='-- prep data')
        if not resp.ok:
            raise Exception("Failed to list recordsets for tenant %s" % zone_info.tenant)

        if rtype == 'A' and not len(resp.json()['recordsets']):
            ip = random_ip()
            payload = {"recordset" : {"name" : zone_info.name,
                                      "type" : "A",
                                      "ttl" : 3600,
                                      "records" : [ ip ] }}
            headers = _prepare_headers_w_tenant(zone_info.tenant)
            #print "%s creating A record %s --> %s" % (zone_info.tenant, zone_info.name, ip)
            resp = _designate_client.post_recordset(
                zone_info.id, data=json.dumps(payload),
                headers=_prepare_headers_w_tenant(zone_info.tenant),
                name='-- prep data')
            recordset = resp.json()['recordset']
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

LARGE_DATA = TestData(CONFIG.large_tenants)
SMALL_DATA = TestData(CONFIG.small_tenants)

def refresh_test_data(previous, current):
    if current == locust.runners.STATE_HATCHING:
        print "refreshing test data for large tenants..."
        LARGE_DATA.refresh(CONFIG.n_large_domains_per_tenant, CONFIG.n_large_records_per_domain)
        print "Large: %s" % LARGE_DATA

        print "refreshing test data for small tenants..."
        SMALL_DATA.refresh(CONFIG.n_small_domains_per_tenant, CONFIG.n_small_records_per_domain)
        print "Small: %s" % SMALL_DATA

locust.events.state_changed += refresh_test_data


class Tasks(TaskSet):

    def __init__(self, test_data, *args, **kwargs):
        super(Tasks, self).__init__(*args, **kwargs)

        self.designate_client = DesignateClient(self.client)

        self.test_data = test_data

        self._use_redis = CONFIG.use_redis
        if self._use_redis:
            # initialize redis client
            self.redis_client = redis.StrictRedis(
                host=CONFIG.redis_host,
                port=CONFIG.redis_port,
                password=CONFIG.redis_password,
                db=0)
            # ping redis to ensure the connection is good (fail fast)
            self.redis_client.ping()

            self.buffer = RedisBuffer(client=self.redis_client)

            # ensure cleanup when the test is stopped
            locust.events.locust_stop_hatching += lambda: self.buffer.flush()
            # ensure cleanup on interrupts
            locust.events.quitting += lambda: self.buffer.flush()




    def pick_zone_for_get(self):
        """Returns a tuple (tenant, api_key, zone_id, zone_name)"""
        return select_random_item(self.test_data.domain_get_data)

    def pick_zone_for_delete(self):
        """Returns a tuple (tenant, api_key, zone_id, zone_name)"""
        val = select_random_item(self.test_data.domain_delete_data)
        # ensure we don't pick this twice
        if val:
            self.test_data.domain_delete_data.remove(val)
        #print "deleted record - %s" % self.test_data
        return val

    def pick_record_for_get(self):
        """Returns a tuple (tenant, api_key, zone_id, zone_name, record_id,
        record_data, record_type)"""
        return select_random_item(self.test_data.record_get_data)

    def pick_record_for_update(self):
        return select_random_item(self.test_data.record_update_data)

    def pick_record_for_delete(self):
        """Returns a tuple (tenant, api_key, zone_id, zone_name, record_id,
        record_data, record_type)"""
        val = select_random_item(self.test_data.record_delete_data)
        if val:
            self.test_data.record_delete_data.remove(val)
        #print "deleted record - %s" % self.test_data
        return val

    def _random_tenant(self):
        return select_random_item(self.test_data.tenant_list)

    def _prepare_headers_w_tenant(self, tenant_id=None):
        return { client.ROLE_HEADER: 'admin',
                 client.PROJECT_ID_HEADER: tenant_id or self._random_tenant() }

    @task
    def get_domain_by_id(self):
        """GET /zones/zoneID"""
        zone_info = self.pick_zone_for_get()
        # print "get_domain_by_id: %s, %s, %s" % (tenant, zone_id, zone_name)
        headers = self._prepare_headers_w_tenant(tenant_id=zone_info.tenant)
        resp = self.designate_client.get_zone(zone_info.id,
                                              name='/v2/zones/zoneID',
                                              headers=headers)

    @task
    def get_domain_by_name(self):
        """GET /zones?name=<name>"""
        zone_info = self.pick_zone_for_get()
        # print "get_domain_by_name: %s, %s, %s" % (tenant, zone_id, zone_name)
        headers = self._prepare_headers_w_tenant(tenant_id=zone_info.tenant)
        resp = self.designate_client.get_zone_by_name(
            zone_name=zone_info.name,
            name='/v2/zones/zoneID?name=zoneNAME',
            headers=headers)

    @task
    def list_domains(self):
        """GET /zones"""
        headers = self._prepare_headers_w_tenant()
        self.designate_client.list_zones(name='/v2/zones', headers=headers)

    @task
    def export_domain(self):
        """GET /zone/zoneID, Accept: text/dns"""
        zone_info = self.pick_zone_for_get()
        # print "export_domain: %s, %s, %s" % (tenant, zone_id, zone_name)
        headers = self._prepare_headers_w_tenant(tenant_id=zone_info.tenant)
        resp = self.designate_client.export_zone(zone_info.id,
                                                 name='/v2/zones/zoneID (export)',
                                                 headers=headers)

    @task
    def create_domain(self):
        """POST /zones"""
        zone, email = random_zone_email()
        headers = self._prepare_headers_w_tenant()
        payload = {"zone": { "name": zone,
                             "email": email,
                             "ttl": 7200 }}
        response = self.designate_client.post_zone(data=json.dumps(payload),
                                                   name='/v2/zones',
                                                   headers=headers)
        if self._use_redis and response.ok:
            self.buffer.append((self.buffer.CREATE, response))

    @task
    def modify_domain(self):
        """PATCH /zones/zoneID"""
        zone_info = self.pick_zone_for_get()
        headers = self._prepare_headers_w_tenant(zone_info.tenant)
        payload = { "zone": { "name": zone_info.name,
                              "email": ("update@" + zone_info.name).strip('.'),
                              "ttl": random.randint(2400, 7200) }}
        resp = self.designate_client.patch_zone(zone_info.id,
                                                data=json.dumps(payload),
                                                headers=headers,
                                                name='/v2/zones/zoneID')
        if self._use_redis and resp.ok:
            self.buffer.append((self.buffer.UPDATE, resp))

    @task
    def remove_domain(self):
        """DELETE /zones/zoneID"""
        zone_info = self.pick_zone_for_delete()
        if zone_info is None:
            print "remove_domain: got None zone_info"
            return

        headers = self._prepare_headers_w_tenant(zone_info.tenant)
        self.designate_client.delete_zone(zone_info.id,
                                          headers=headers,
                                          name='/v2/zones/zoneID')

    @task
    def list_records(self):
        """GET /zones/zoneID/recordsets"""
        tenant, api_key, zone_id, zone_name = self.pick_zone_for_get()
        headers=self._prepare_headers_w_tenant(tenant)
        resp = self.designate_client.list_recordsets(
            zone_id, name='/v2/zones/zoneID/recordsets', headers=headers)

    @task
    def get_record(self):
        """GET /zones/zoneID/recordsets/recordID"""
        record_info = self.pick_record_for_get()
        headers = self._prepare_headers_w_tenant(record_info.tenant)
        self.designate_client.get_recordset(
            record_info.zone_id,
            record_info.record_id,
            headers=headers,
            name='/v2/zone/zoneID/recordsets/recordID')

    @task
    def create_record(self):
        """POST /zones/zoneID/recordsets"""
        zone_info = self.pick_zone_for_get()
        headers = self._prepare_headers_w_tenant(zone_info.tenant)

        a_record_name = "{0}.{1}".format(randomize("record"), zone_info.name)
        payload = {"recordset" : {"name" : a_record_name,
                                  "type" : "A",
                                  "ttl" : 3600,
                                  "records" : [ random_ip() ] }}

        recordset_resp = self.designate_client.post_recordset(
            zone_info.id,
            data=json.dumps(payload),
            name='/v2/zones/zoneID/recordsets',
            headers=headers)
        if self._use_redis and recordset_resp.ok:
            zone_resp = self.designate_client.get_zone(zone_info.id,
                                                       name='/v2/zones/zoneID',
                                                       headers=headers)
            if zone_resp.ok:
                self.buffer.append((self.buffer.UPDATE, zone_resp))

    @task
    def modify_record(self):
        """PATCH /zones/zoneID/recordsets/recordsetID"""
        record_info = self.pick_record_for_update()
        if not record_info:
            print "modify_record: got None record_info"
            return
        headers = self._prepare_headers_w_tenant(record_info.tenant)
        payload = { "recordset": { "records": [ random_ip() ],
                                   "type": "A",
                                   "name": record_info.zone_name,
                                   "ttl": random.randint(2400, 7200) }}
        resp = self.designate_client.put_recordset(
            record_info.zone_id,
            record_info.record_id,
            data=json.dumps(payload),
            headers=headers,
            name='/v2/zones/zoneID/recordsets/recordsetID')
        if self._use_redis and resp.ok:
            zone_resp = self.designate_client.get_zone(record_info.zone_id,
                                                       name='/v2/zones/zoneID',
                                                       headers=headers)
            if zone_resp.ok:
                self.buffer.append((self.buffer.UPDATE, zone_resp))

    @task
    def remove_record(self):
        """DELETE /zones/zoneID/recordsets"""
        record_info = self.pick_record_for_delete()
        if not record_info:
            print "remove_record: got None record_info"
            return
        headers = self._prepare_headers_w_tenant(record_info.tenant)
        resp = self.designate_client.delete_recordset(
            record_info.zone_id,
            record_info.record_id,
            name='/v2/zones/zoneID/recordsets',
            headers=headers)
        if self._use_redis and resp.ok:
            zone_resp = self.designate_client.get_zone(record_info.zone_id,
                                                       name='/v2/zones/zoneID',
                                                       headers=headers)
            if zone_resp.ok:
                self.buffer.append((self.buffer.UPDATE, zone_resp))


class LargeTasks(Tasks):

    tasks = {
        Tasks.get_domain_by_id:   CONFIG.large_weights.get_domain_by_id,
        Tasks.get_domain_by_name: CONFIG.large_weights.get_domain_by_name,
        Tasks.list_domains:       CONFIG.large_weights.list_domain,
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

