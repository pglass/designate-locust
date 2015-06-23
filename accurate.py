import csv
import json
import datetime
import random

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
from greenlet_manager import GreenletManager
from client import DesignateClient
from web import *
from datagen import *
import accurate_config as CONFIG

from prep.model import TestData
from prep.callback import refresh_test_data
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

_client = HttpSession(CONFIG.designate_host)
_designate_client = DesignateClient(_client)
_digaas_client = digaas_integration.DigaasClient(CONFIG.digaas_endpoint)

# use digaas to externally poll the nameserver(s) to record zone propagation
# times through Designate's stack
if CONFIG.use_digaas and not insight.is_slave():
    digaas_integration.setup_digaas_integration(_digaas_client)

if not insight.is_master():
    LARGE_DATA = TestData(CONFIG.large_tenants)
    SMALL_DATA = TestData(CONFIG.small_tenants)
    locust.events.state_changed += lambda previous, current: \
        refresh_test_data(previous, current, LARGE_DATA, SMALL_DATA)

    # the greenlet_manager keeps track of greenlets spawned for polling
    # note: it's hard to ensure cleanup_greenlets gets run before the stats
    # are persisted to a file...

    # ensure cleanup when the test is stopped
    locust.events.locust_stop_hatching += \
        lambda: GreenletManager.get().cleanup_greenlets()
    # ensure cleanup on interrupts
    locust.events.quitting += \
        lambda: GreenletManager.get().cleanup_greenlets()

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

