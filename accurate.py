import csv
import json
import datetime
import random
import logging

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

from tasks.gather import GatherTasks
from tasks.recordset import RecordsetTasks
from tasks.zone import ZoneTasks
from models import Tenant

LOG = logging.getLogger(__name__)

# require a username + password to access the web interface
setup_authentication(CONFIG.username, CONFIG.password)

# send metrics to a graphite server
graphite_client.setup_graphite_communication(
    CONFIG.graphite_host, CONFIG.graphite_port)

# save a report when the test finishes
persistence.setup_persistence()

locust.config.RESET_STATS_AFTER_HATCHING = CONFIG.reset_stats


# use digaas to externally poll the nameserver(s) to record zone propagation
# times through Designate's stack
if CONFIG.use_digaas and not insight.is_slave():
    _digaas_client = digaas_integration.DigaasClient(CONFIG.digaas_endpoint)
    digaas_integration.setup(_digaas_client)

if not insight.is_master():
    # TODO: the tenant id is actually the username. it should be named so.
    SMALL_TENANTS = [Tenant(id=id, api_key=api_key, type=Tenant.SMALL)
                      for id, api_key in CONFIG.small_tenants]
    LARGE_TENANTS = [Tenant(id=id, api_key=api_key, type=Tenant.LARGE)
                     for id, api_key in CONFIG.large_tenants]
    ALL_TENANTS = SMALL_TENANTS + LARGE_TENANTS

    # the greenlet_manager keeps track of greenlets spawned for polling
    # todo: it's hard to ensure cleanup_greenlets gets run before the stats
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
        super(LargeTasks, self).__init__(LARGE_TENANTS, *args, **kwargs)
        self.designate_client = DesignateClient(self.client,
            tenant_id_in_url=CONFIG.tenant_id_in_url)


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
        super(SmallTasks, self).__init__(SMALL_TENANTS, *args, **kwargs)
        self.designate_client = DesignateClient(self.client,
            tenant_id_in_url=CONFIG.tenant_id_in_url)

class AccurateTaskSet(TaskSet):
    """Combines large tenants and small tenants with appropriate weights."""
    tasks = {
        LargeTasks: CONFIG.total_large_weight,
        SmallTasks: CONFIG.total_small_weight,
    }

class GatherShim(GatherTasks):

    done_gathering = locust.events.EventHook()

    tasks = {
        GatherTasks.gather_zones: 1,
        GatherTasks.gather_recordsets: 1,
    }

    def __init__(self, *args, **kwargs):
        super(GatherShim, self).__init__(ALL_TENANTS, *args, **kwargs)

class GatherData(TaskSet):

    tasks = [GatherShim]

    ALREADY_GATHERED = False
    HATCH_COMPLETE_HANDLERS = None

    @classmethod
    def set_already_gathered(cls, val):
        cls.ALREADY_GATHERED = val

    @classmethod
    def has_already_gathered(cls):
        return cls.ALREADY_GATHERED

    def __init__(self, *args, **kwargs):
        super(GatherData, self).__init__(*args, **kwargs)
        self.is_done = False
        self.already_did_it = self.has_already_gathered()

        def _handler():
            self.is_done = True
            self.be_done_if_done()
        GatherShim.done_gathering += _handler

    def on_start(self):
        if not self.has_already_gathered():
            self.disable_hatch_complete_handlers()

    @classmethod
    def disable_hatch_complete_handlers(cls):
        # disable hatch complete handlers to delay the hatch complete event
        if cls.HATCH_COMPLETE_HANDLERS is None:
            cls.HATCH_COMPLETE_HANDLERS = locust.events.hatch_complete._handlers
            locust.events.hatch_complete._handlers = []

    @classmethod
    def restore_hatch_complete_handlers(cls):
        if cls.HATCH_COMPLETE_HANDLERS is not None:
            locust.events.hatch_complete._handlers = cls.HATCH_COMPLETE_HANDLERS
            cls.HATCH_COMPLETE_HANDLERS = None

    def be_done_if_done(self):
        if not self.already_did_it and self.is_done:
            locust.runners.locust_runner.state = locust.runners.STATE_HATCHING
            self.restore_hatch_complete_handlers()
            locust.events.hatch_complete.fire(user_count=locust.runners.locust_runner.user_count)
            self.already_did_it = True


class TaskSwitcher(TaskSet):
    """This is a bit of a hack. This will use one set of tasks for hatching and
    a different set of tasks otherwise. This lets us easily do data preparation
    before the perf test starts using one set of task weights, and then run the
    performance test with the usual set of task weights.
    """

    tasks = []

    regular_tasks = None
    gathering_tasks = None

    def __init__(self, *args, **kwargs):
        super(TaskSwitcher, self).__init__(*args, **kwargs)
        # this is a little awkward, but it works. these must be instances
        # of a class that has the task methods as members.
        if TaskSwitcher.regular_tasks is None:
            TaskSwitcher.regular_tasks = AccurateTaskSet(*args, **kwargs)
        if TaskSwitcher.gathering_tasks is None:
            TaskSwitcher.gathering_tasks = GatherData(*args, **kwargs)

        locust.events.locust_start_hatching._handlers = []

        def on_hatch_complete(user_count):
            GatherData.set_already_gathered(True)
            self.tasks = self.regular_tasks.tasks
        locust.events.hatch_complete += on_hatch_complete

        def on_done_gathering():
            locust.runners.locust_runner.stats.reset_all()
            self.interrupt()
        GatherShim.done_gathering += on_done_gathering

    def on_start(self):
        self.gathering_tasks.on_start()

    def need_to_gather(self):
        if GatherData.has_already_gathered():
            return False
        state = locust.runners.locust_runner.state
        return state in (None, locust.runners.STATE_INIT, locust.runners.STATE_HATCHING)

    def get_next_task(self):
        if self.need_to_gather():
            self.tasks = self.gathering_tasks.tasks
            LOG.info("Using gathering tasks")
        else:
            self.tasks = self.regular_tasks.tasks
            LOG.info("Using regular tasks")
        next_task = super(TaskSwitcher, self).get_next_task()
        return next_task

class Locust(HttpLocust):
    task_set = TaskSwitcher

    min_wait = CONFIG.min_wait
    max_wait = CONFIG.max_wait

    host = CONFIG.designate_host
