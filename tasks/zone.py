import datetime
import logging
import json
import time

from locust import TaskSet
import gevent

from base import BaseTaskSet
from models import Zone
from datagen import *
from greenlet_manager import GreenletManager
import accurate_config as CONFIG

LOG = logging.getLogger(__name__)


class ZoneTasks(BaseTaskSet):

    def get_domain_by_id(self):
        """GET /zones/ID"""
        tenant = self.select_random_tenant()
        if not tenant:
            return
        client = self.designate_client.as_user(tenant)
        zone = tenant.data.select_zone_for_get()
        if not zone:
            LOG.error("%s has no zones for getting", tenant)
            return
        resp = client.get_zone(zone.id, name='/v2/zones/ID')

    def get_domain_by_name(self):
        """GET /zones?name=<name>"""
        tenant = self.select_random_tenant()
        if not tenant:
            return
        client = self.designate_client.as_user(tenant)
        zone = tenant.data.select_zone_for_get()
        if not zone:
            LOG.error("%s has no zones for getting", tenant)
            return
        resp = client.get_zone_by_name(
            zone_name=zone.name,
            name='/v2/zones/ID?name=zoneNAME')

    def list_domains(self):
        """GET /zones"""
        tenant = self.select_random_tenant()
        if not tenant:
            return
        client = self.designate_client.as_user(tenant)
        client.list_zones(name='/v2/zones')

    def export_domain(self):
        """This runs the entire export domain sequence:

            1. POST /zones/ID/tasks/export
            2. GET /zones/tasks/exports/ID (poll for COMPLETED)
            3. GET /zones/tasks/export (Accept: text/dns)
        """
        gevent.spawn(
            GreenletManager.get().tracked_greenlet,
            lambda: self._do_export_domain(interval=2),
            timeout=60
        )


    def _do_export_domain(self, interval):
        tenant = self.select_random_tenant()
        if not tenant:
            return
        client = self.designate_client.as_user(tenant)
        zone = tenant.data.select_zone_for_get()
        if not zone:
            LOG.error("%s has no zones for getting", tenant)
            return

        # this is asynchronous
        start_time = time.time()
        with client.post_zone_export(zone.id,
                                     name='/v2/zones/ID/tasks/export',
                                     catch_response=True) as post_resp:

            if not post_resp.ok:
                post_resp.failure("Failed with status code %s" % post_resp.status_code)
                return

            export_id = post_resp.json()['id']
            api_call = lambda: client.get_zone_export(
                export_id=export_id,
                name='/v2/zones/tasks/exports/ID',
            )

            self._poll_until_active_or_error(
                api_call=api_call,
                interval=interval,
                status_function=lambda r: r.json()['status'],
                success_function=lambda: self.async_success(start_time, post_resp),
                failure_function=post_resp.failure,
                expected='COMPLETE',
            )

            export_resp = client.get_exported_zone_file(
                export_id=export_id,
                name='/v2/zones/tasks/exports/ID/export',
            )

    def create_domain(self):
        """POST /zones"""
        gevent.spawn(
            GreenletManager.get().tracked_greenlet,
            lambda: self._do_create_domain(interval=2),
            timeout=60
        )

    def _do_create_domain(self, interval):
        tenant = self.select_random_tenant()
        if not tenant:
            return
        client = self.designate_client.as_user(tenant)
        zone_name, email = random_zone_email()
        payload = { "name": zone_name,
                    "email": email,
                    "ttl": 7200 }

        # the with block lets us specify when the request has succeeded.
        # this lets us time how long until an active or error status.
        start_time = time.time()
        post_resp = client.post_zone(
            data=json.dumps(payload), name='/v2/zones'
        )
        if not post_resp.ok:
            return
        if CONFIG.use_digaas:
            self.digaas_behaviors.observe_zone_create(post_resp, start_time)

        api_call = lambda: client.get_zone(
            zone_id=post_resp.json()['id'],
            name='/v2/zones/ID - status check')

        self._poll_until_active_or_error(
            api_call=api_call,
            interval=interval,
            status_function=lambda r: r.json()['status'],
            success_function=lambda: self.async_success(
                post_resp, start_time, '/v2/zones - async'
            ),
            failure_function=lambda msg: self.async_failure(
                post_resp, start_time, '/v2/zones - async', msg
            ),
        )

        # if we successfully created the zone, add it to our list
        # todo: add some domains to the delete list
        resp = api_call()
        if resp.ok and resp.json()['status'] == 'ACTIVE':
            zone = Zone(resp.json()['id'], resp.json()['name'])
            # LOG.info("%s -- Added zone %s", tenant, zone)
            tenant.data.zones_for_delete.append(zone)

    def import_zone(self):
        """POST /zones/tasks/import, Content-type: text/dns"""
        gevent.spawn(
            GreenletManager.get().tracked_greenlet,
            lambda: self._do_import_zone(interval=2),
            timeout=120
        )

    def _do_import_zone(self, interval):
        tenant = self.select_random_tenant()
        if not tenant:
            return
        client = self.designate_client.as_user(tenant)
        zone_file = random_zone_file()
        start_time = time.time()
        with client.import_zone(data=zone_file.get_zone_file_text(),
                                name='/v2/zones/tasks/imports',
                                catch_response=True) as import_resp:

            if CONFIG.use_digaas and import_resp.ok:
                self.digaas_behaviors.observe_zone_create(
                    import_resp, start_time, name=zone_file.zone_name,
                )

            if not import_resp.ok:
                import_resp.failure("Failed with status code %s" % import_resp.status_code)
                return

            api_call = lambda: client.get_zone_import(
                import_id=import_resp.json()['id'],
                name='/v2/zones/ID - status check')

            self._poll_until_active_or_error(
                api_call=api_call,
                interval=interval,
                status_function=lambda r: r.json()['status'],
                success_function=lambda: self.async_success(start_time, import_resp),
                failure_function=import_resp.failure,
                expected='COMPLETE')

    def modify_domain(self):
        """PATCH /zones/ID"""
        gevent.spawn(
            GreenletManager.get().tracked_greenlet,
            lambda: self._do_modify_domain(interval=2),
            timeout=60
        )

    def _do_modify_domain(self, interval):
        tenant = self.select_random_tenant()
        if not tenant:
            return
        client = self.designate_client.as_user(tenant)
        zone = tenant.data.select_zone_for_get()
        if not zone:
            LOG.error("%s has no zones for updating", tenant)
            return
        payload = { "name": zone.name,
                    "email": ("update@" + zone.name).strip('.'),
                    "ttl": random.randint(2400, 7200) }
        start_time = time.time()
        patch_resp = client.patch_zone(
            zone.id,
            data=json.dumps(payload),
            name='/v2/zones/ID',
        )
        if not patch_resp.ok:
            return
        if CONFIG.use_digaas:
            self.digaas_behaviors.observe_zone_update(patch_resp, start_time)

        api_call = lambda: client.get_zone(
            zone_id=zone.id,
            name='/v2/zones/ID - status check')
        self._poll_until_active_or_error(
            api_call=api_call,
            interval=interval,
            status_function=lambda r: r.json()['status'],
            success_function=lambda: self.async_success(
                patch_resp, start_time, '/v2/zones - async'
            ),
            failure_function=lambda msg: self.async_failure(
                patch_resp, start_time, '/v2/zones - async', msg
            ),
        )

    def remove_domain(self):
        """DELETE /zones/ID"""
        gevent.spawn(
            GreenletManager.get().tracked_greenlet,
            lambda: self._do_remove_domain(interval=2),
            timeout=60
        )

    def _do_remove_domain(self, interval):
        tenant = self.select_random_tenant()
        if not tenant:
            return
        client = self.designate_client.as_user(tenant)
        zone = tenant.data.pop_zone_for_delete()
        if not zone:
            LOG.error("%s has no zones for deleting", tenant)
            return

        start_time = time.time()
        with client.delete_zone(
                zone.id,
                name='/v2/zones/ID',
                catch_response=True) as del_resp:

            if CONFIG.use_digaas and del_resp.ok:
                self.digaas_behaviors.observe_zone_delete(zone.name, start_time)

            api_call = lambda: client.get_zone(
                zone.id, catch_response=True,
                name='/v2/zones/ID - status check',
                no_log_request=True)
            self._poll_until_404(api_call, interval,
                success_function=lambda: self.async_success(start_time, del_resp),
                failure_function=del_resp.failure)
