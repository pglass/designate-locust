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

    def list_recordsets_cross_zone(self):
        tenant = self.select_random_tenant()
        if not tenant:
            return
        client = self.designate_client.as_user(tenant)
        client.list_recordsets_cross_zone(
            name="/v2/recordsets")

    def get_recordset_cross_zone(self):
        tenant = self.select_random_tenant()
        if not tenant:
            return
        client = self.designate_client.as_user(tenant)
        recordset = tenant.data.select_recordset_for_get()
        if not recordset:
            return
        client.get_recordset_cross_zone(
            recordset.id,
            name="/v2/recordsets/ID")

    def filter_recordsets_by_data(self):
        tenant = self.select_random_tenant()
        if not tenant:
            return
        client = self.designate_client.as_user(tenant)

        # use a filter like `data=*1*` but randomize the number
        n = random.randrange(0, 10)
        client.list_recordsets_cross_zone(
            params={'data': "*%s*" % n},
            name="/v2/recordsets?data=")

    def list_records(self):
        """GET /zones/ID/recordsets"""
        tenant = self.select_random_tenant()
        if not tenant:
            return
        client = self.designate_client.as_user(tenant)
        recordset = tenant.data.select_recordset_for_get()
        if not recordset:
            LOG.error("%s has no zones for getting", tenant)
            return
        client.list_recordsets(
            recordset.zone.id,
            name='/v2/zones/ID/recordsets')

    def filter_recordsets_by_name_left_wildcard(self):
        tenant = self.select_random_tenant()
        if not tenant:
            return
        client = self.designate_client.as_user(tenant)

        zone = tenant.data.select_zone_for_get()
        if zone is None:
            LOG.warning("don't know of any zones to list recordsets with")
            return

        client.list_recordsets(
            zone.id,
            params={'name': '*.com.'},
            name='/v2/zones/ID/recordsets?name=')

    def filter_recordsets_by_name_right_wildcard(self):
        tenant = self.select_random_tenant()
        if not tenant:
            return
        client = self.designate_client.as_user(tenant)

        zone = tenant.data.select_zone_for_get()
        if zone is None:
            LOG.warning("don't know of any zones to list recordsets with")
            return

        client.list_recordsets(
            zone.id,
            params={'name': 'record*'},
            name='/v2/zones/ID/recordsets?name=record*')

    def filter_recordsets_by_name_double_wildcard(self):
        tenant = self.select_random_tenant()
        if not tenant:
            return
        client = self.designate_client.as_user(tenant)

        zone = tenant.data.select_zone_for_get()
        if zone is None:
            LOG.warning("don't know of any zones to list recordsets with")
            return

        client.list_recordsets(
            zone.id,
            params={'name': '*zone*'},
            name='/v2/zones/ID/recordsets?name=*zone*')

    def get_record(self):
        """GET /zones/ID/recordsets/ID"""
        tenant = self.select_random_tenant()
        if not tenant:
            return
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
            lambda: self._do_create_record(),
        )

    def _do_create_record(self):
        tenant = self.select_random_tenant()
        if not tenant:
            return
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
        post_resp = client.post_recordset(
            zone.id,
            data=json.dumps(payload),
            name='/v2/zones/ID/recordsets',
        )

        if not post_resp.ok:
            return

        if CONFIG.use_digaas:
            # we need the zone's serial to confidently poll for the update.
            # the recordset doesn't have the serial. instead, grab the zone
            # and use whatever serial we get. this is not perfect - digaas may
            # record slightly longer propagation times than actual.
            get_zone = client.get_zone(zone.id, name='/v2/zones/ID')
            if not get_zone.ok:
                LOG.error(
                    "Failed to fetch zone %s to grab serial. We need the "
                    "serial for digaas to poll for the recordset create",
                    zone.id
                )
            else:
                self.digaas_behaviors.observe_zone_update(get_zone, start_time)

        api_call = lambda: client.get_recordset(
            zone_id=zone.id,
            recordset_id=post_resp.json()['id'],
            name='/v2/zones/ID/recordsets/ID - status check')
        self._poll_until_active_or_error(
            api_call=api_call,
            status_function=lambda r: r.json()['status'],
            success_function=lambda: self.async_success(
                post_resp, start_time, '/v2/zones/ID/recordsets - async',
            ),
            failure_function=lambda msg: self.async_failure(
                post_resp, start_time, '/v2/zones/ID/recordsets - async', msg
            ),
        )

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
            lambda: self._do_modify_record(),
        )

    def _do_modify_record(self):
        """PATCH /zones/ID/recordsets/ID"""
        tenant = self.select_random_tenant()
        if not tenant:
            return
        client = self.designate_client.as_user(tenant)
        recordset = tenant.data.select_recordset_for_get()
        if not recordset:
            LOG.error("%s has no recordsets for updating", tenant)
            return

        payload = { "records": [ datagen.random_ip() ],
                    "ttl": random.randint(2400, 7200) }
        start_time = time.time()
        put_resp = client.put_recordset(
            recordset.zone.id,
            recordset.id,
            data=json.dumps(payload),
            name="/v2/zones/ID/recordsets/ID",
        )

        if not put_resp.ok:
            return
        if CONFIG.use_digaas:
            get_zone = client.get_zone(recordset.zone.id, name='/v2/zones/ID')
            if not get_zone.ok:
                LOG.error(
                    "Failed to fetch zone %s to grab serial. We need the "
                    "serial for digaas to poll for the recordset update",
                    zone.id
                )
            else:
                self.digaas_behaviors.observe_zone_update(get_zone, start_time)

        api_call = lambda: client.get_recordset(
            zone_id=put_resp.json()['zone_id'],
            recordset_id=put_resp.json()['id'],
            name='/v2/zones/ID/recordsets/ID - status check')
        self._poll_until_active_or_error(
            api_call=api_call,
            status_function=lambda r: r.json()['status'],
            success_function=lambda: self.async_success(
                put_resp, start_time, '/v2/zones/ID/recordsets/ID - async',
            ),
            failure_function=lambda msg: self.async_failure(
                put_resp, start_time, '/v2/zones/ID/recordsets/ID - async', msg
            ),
        )

    def remove_record(self):
        """DELETE /zones/ID/recordsets/ID"""
        gevent.spawn(
            GreenletManager.get().tracked_greenlet,
            lambda: self._do_remove_record(),
        )

    def _do_remove_record(self):
        tenant = self.select_random_tenant()
        if not tenant:
            return
        client = self.designate_client.as_user(tenant)
        recordset = tenant.data.pop_recordset_for_delete()
        if not recordset:
            LOG.error("%s has no recordsets for deleting", tenant)
            return

        start_time = time.time()
        del_resp = client.delete_recordset(
            recordset.zone.id,
            recordset.id,
            name='/v2/zones/ID/recordsets/ID',
        )

        if not del_resp.ok:
            return
        if CONFIG.use_digaas:
            get_zone = client.get_zone(recordset.zone.id, name='/v2/zones/ID')
            if not get_zone.ok:
                LOG.error(
                    "Failed to fetch zone %s to grab serial. We need the "
                    "serial for digaas to poll for the recordset create",
                    zone.id
                )
            else:
                self.digaas_behaviors.observe_zone_update(get_zone, start_time)

        api_call = lambda: client.get_recordset(
            recordset.zone.id,
            recordset.id,
            name='/v2/zones/ID/recordsets/ID - status check',
            catch_response=True,
            no_log_request=True)

        self._poll_until_404(
            api_call=api_call,
            success_function=lambda: self.async_success(
                del_resp, start_time, '/v2/zones/ID/recordsets/ID - async',
            ),
            failure_function=lambda msg: self.async_failure(
                del_resp, start_time, '/v2/zones/ID/recordsets/ID - async', msg
            ),
        )
