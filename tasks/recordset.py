import datetime
import json
import logging
import random
import time

from locust import TaskSet
import gevent

from base import BaseTaskSet
import datagen
from greenlet_manager import GreenletManager
import accurate_config as CONFIG
from models import Recordset

LOG = logging.getLogger(__name__)


class RecordsetTasks(BaseTaskSet):

    def list_records(self):
        """GET /zones/ID/recordsets"""
        tenant = self.select_random_tenant()
        client = self.designate_client.as_user(tenant)
        recordset = tenant.data.select_recordset_for_get()
        if not recordset:
            LOG.error("%s has no zones for getting", tenant)
            return
        client.list_recordsets(
            recordset.zone.id,
            name='/v2/zones/ID/recordsets')

    def get_record(self):
        """GET /zones/ID/recordsets/ID"""
        tenant = self.select_random_tenant()
        client = self.designate_client.as_user(tenant)
        recordset = tenant.data.select_recordset_for_get()
        if not recordset:
            LOG.error("%s has no zones for getting", tenant)
            return
        client.get_recordset(
            recordset.zone.id,
            recordset.id,
            name='/v2/zone/ID/recordsets/ID')

    def create_record(self):
        """POST /zones/ID/recordsets"""
        gevent.spawn(
            GreenletManager.get().tracked_greenlet,
            lambda: self._do_create_record(interval=2),
            timeout=60
        )

    def _do_create_record(self, interval):
        tenant = self.select_random_tenant()
        client = self.designate_client.as_user(tenant)
        zone = tenant.data.select_zone_for_get()
        if zone is None:
            LOG.warning("don't know of any zones to create records on")
            return

        record_name = "{0}.{1}".format(datagen.randomize("record"), zone.name)
        payload = { "name" : record_name,
                    "type" : "A",
                    "ttl" : 3600,
                    "records" : [ datagen.random_ip() ] }

        start_time = time.time()
        with client.post_recordset(
                zone.id,
                data=json.dumps(payload),
                name='/v2/zones/ID/recordsets',
                catch_response=True) as post_resp:
            client._log_if_bad_request(post_resp)

            if CONFIG.use_digaas and post_resp.ok:
                self.digaas_behaviors.check_record_create_or_update(post_resp, start_time)

            if not post_resp.ok:
                post_resp.failure("Failed with status code %s" % post_resp.status_code)
                return

            api_call = lambda: client.get_recordset(
                zone_id=zone.id,
                recordset_id=post_resp.json()['id'],
                name='/v2/zones/ID/recordsets/ID - status check')
            self._poll_until_active_or_error(
                api_call=api_call,
                interval=interval,
                status_function=lambda r: r.json()['status'],
                success_function=lambda: self.async_success(start_time, post_resp),
                failure_function=post_resp.failure)

            # if we successfully created the recordset, add it to our list
            resp = api_call()
            if resp.ok and resp.json()['status'] == 'ACTIVE':
                recordset = Recordset(
                    zone = zone,
                    id = resp.json()['id'],
                    data = resp.json()['records'][0],
                    type = resp.json()['type'])

                # add to the list of things for deleting, to help us not run
                # out of zones to delete
                LOG.info("%s -- Added recordset %s", tenant, recordset)
                tenant.data.recordsets_for_delete.append(recordset)
                LOG.info("have %s records", tenant.data.recordset_count())

    def modify_record(self):
        gevent.spawn(
            GreenletManager.get().tracked_greenlet,
            lambda: self._do_modify_record(interval=2),
            timeout=60
        )

    def _do_modify_record(self, interval):
        """PATCH /zones/ID/recordsets/ID"""
        tenant = self.select_random_tenant()
        client = self.designate_client.as_user(tenant)
        recordset = tenant.data.select_recordset_for_get()
        if not recordset:
            LOG.error("%s has no recordsets for updating", tenant)
            return

        payload = { "records": [ datagen.random_ip() ],
                    "ttl": random.randint(2400, 7200) }
        start_time = time.time()
        with client.put_recordset(
                recordset.zone.id,
                recordset.id,
                data=json.dumps(payload),
                name="/v2/zones/ID/recordsets/ID",
                catch_response=True) as put_resp:

            if CONFIG.use_digaas and put_resp.ok:
                self.digaas_behaviors.check_record_create_or_update(put_resp, start_time)

            if not put_resp.ok:
                put_resp.failure("Failed with status code %s" % put_resp.status_code)
                LOG.error("Failed, update recordset response %s" % put_resp)
                LOG.error("  %s %s", put_resp.request.method, put_resp.request.url)
                LOG.error("  %s", put_resp.request.body)
                LOG.error("  %s", put_resp.request.headers)
                LOG.error("  %s", put_resp.headers)
                LOG.error("  %s", put_resp.text)
                return

            api_call = lambda: client.get_recordset(
                zone_id=put_resp.json()['zone_id'],
                recordset_id=put_resp.json()['id'],
                name='/v2/zones/ID/recordsets/ID - status check')
            self._poll_until_active_or_error(
                api_call=api_call,
                interval=interval,
                status_function=lambda r: r.json()['status'],
                success_function=lambda: self.async_success(start_time, put_resp),
                failure_function=put_resp.failure)

    def remove_record(self):
        """DELETE /zones/ID/recordsets/ID"""
        gevent.spawn(
            GreenletManager.get().tracked_greenlet,
            lambda: self._do_remove_record(interval=2),
            timeout=60
        )

    def _do_remove_record(self, interval):
        tenant = self.select_random_tenant()
        client = self.designate_client.as_user(tenant)
        recordset = tenant.data.pop_recordset_for_delete()
        if not recordset:
            LOG.error("%s has no recordsets for updating", tenant)
            return

        start_time = time.time()
        with client.delete_recordset(
                recordset.zone.id,
                recordset.id,
                name='/v2/zones/ID/recordsets/ID',
                catch_response=True) as del_resp:
            print 'DELETED recordset %s' % recordset.id

            if CONFIG.use_digaas and del_resp.ok:
                self.digaas_behaviors.check_name_removed(recordset.zone.name, start_time)

            if not del_resp.ok:
                del_resp.failure("Failed with status_code %s" % del_resp.status_code)
                return

            api_call = lambda: client.get_recordset(
                recordset.zone.id,
                recordset.id,
                name='/v2/zones/ID/recordsets/ID - status check',
                catch_response=True,
                no_log_request=True)

            self._poll_until_404(
                api_call=api_call,
                interval=interval,
                success_function=lambda: self.async_success(start_time, del_resp),
                failure_function=del_resp.failure)
