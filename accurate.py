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

from tasks.recordset import RecordsetTasks
from tasks.zone import ZoneTasks

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

class LargeTasks(ZoneTasks, RecordsetTasks):

    tasks = {
        ZoneTasks.get_domain_by_id:   CONFIG.large_weights.get_domain_by_id,
        ZoneTasks.get_domain_by_name: CONFIG.large_weights.get_domain_by_name,
        ZoneTasks.list_domains:       CONFIG.large_weights.list_domain,
        ZoneTasks.import_zone:        CONFIG.large_weights.import_zone,
        ZoneTasks.export_domain:      CONFIG.large_weights.export_domain,
        ZoneTasks.create_domain:      CONFIG.large_weights.create_domain,
        ZoneTasks.modify_domain:      CONFIG.large_weights.modify_domain,
        ZoneTasks.remove_domain:      CONFIG.large_weights.remove_domain,
        RecordsetTasks.list_records:  CONFIG.large_weights.list_records,
        RecordsetTasks.get_record:    CONFIG.large_weights.get_record,
        RecordsetTasks.create_record: CONFIG.large_weights.create_record,
        RecordsetTasks.remove_record: CONFIG.large_weights.remove_record,
        RecordsetTasks.modify_record: CONFIG.large_weights.modify_record,
    }

    def __init__(self, *args, **kwargs):
        super(LargeTasks, self).__init__(LARGE_DATA, *args, **kwargs)
        self.designate_client = DesignateClient(self.client)


class SmallTasks(ZoneTasks, RecordsetTasks):

    tasks = {
        ZoneTasks.get_domain_by_id:   CONFIG.small_weights.get_domain_by_id,
        ZoneTasks.get_domain_by_name: CONFIG.small_weights.get_domain_by_name,
        ZoneTasks.list_domains:       CONFIG.small_weights.list_domain,
        ZoneTasks.import_zone:        CONFIG.small_weights.import_zone,
        ZoneTasks.export_domain:      CONFIG.small_weights.export_domain,
        ZoneTasks.create_domain:      CONFIG.small_weights.create_domain,
        ZoneTasks.modify_domain:      CONFIG.small_weights.modify_domain,
        ZoneTasks.remove_domain:      CONFIG.small_weights.remove_domain,
        RecordsetTasks.list_records:  CONFIG.small_weights.list_records,
        RecordsetTasks.get_record:    CONFIG.small_weights.get_record,
        RecordsetTasks.create_record: CONFIG.small_weights.create_record,
        RecordsetTasks.remove_record: CONFIG.small_weights.remove_record,
        RecordsetTasks.modify_record: CONFIG.small_weights.modify_record,
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

