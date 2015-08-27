import datetime
import logging
import json

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
        client = self.designate_client.as_user(tenant)
        zone = tenant.data.select_zone_for_get()
        if not zone:
            LOG.error("%s has no zones for getting", tenant)
            return
        resp = client.get_zone(zone.id, name='/v2/zones/ID')

    def get_domain_by_name(self):
        """GET /zones?name=<name>"""
        tenant = self.select_random_tenant()
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
        client = self.designate_client.as_user(tenant)
        client.list_zones(name='/v2/zones')

    def export_domain(self):
        """GET /zone/ID, Accept: text/dns"""
        tenant = self.select_random_tenant()
        client = self.designate_client.as_user(tenant)
        zone = tenant.data.select_zone_for_get()
        if not zone:
            LOG.error("%s has no zones for getting", tenant)
            return
        resp = client.export_zone(zone.id, name='/v2/zones/ID - export')

    def create_domain(self):
        """POST /zones"""
        gevent.spawn(
            GreenletManager.get().tracked_greenlet,
            lambda: self._do_create_domain(interval=2),
            timeout=60
        )

    def _do_create_domain(self, interval):
        tenant = self.select_random_tenant()
        client = self.designate_client.as_user(tenant)
        zone_name, email = random_zone_email()
        payload = { "name": zone_name,
                    "email": email,
                    "ttl": 7200 }

        # the with block lets us specify when the request has succeeded.
        # this lets us time how long until an active or error status.
        with client.post_zone(data=json.dumps(payload),
                              name='/v2/zones',
                              catch_response=True) as post_resp:

            if CONFIG.use_digaas and post_resp.ok:
                self.digaas_behaviors.check_zone_create_or_update(post_resp)

            if not post_resp.ok:
                post_resp.failure("Failed with status code %s" % post_resp.status_code)
                return

            api_call = lambda: client.get_zone(
                zone_id=post_resp.json()['id'],
                name='/v2/zones - status of POST /v2/zones')
            self._poll_until_active_or_error(
                api_call=api_call,
                interval=interval,
                status_function=lambda r: r.json()['status'],
                success_function=post_resp.success,
                failure_function=post_resp.failure)

            # if we successfully created the zone, add it to our list
            # todo: add some domains to the delete list
            resp = api_call()
            if resp.ok and resp.json()['status'] == 'ACTIVE':
                zone = Zone(resp.json()['id'], resp.json()['name'])
                LOG.info("%s -- Added zone %s", tenant, zone)
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
        client = self.designate_client.as_user(tenant)
        zone_file = random_zone_file()
        with client.import_zone(data=zone_file,
                                name='/v2/zones/tasks/imports',
                                catch_response=True) as import_resp:

            #print "[%s]: %s\n%s\nResponse:\n%s" % (
            #    import_resp.status_code,
            #    import_resp.request.url,
            #    import_resp.request.body,
            #    import_resp.text)

            # TODO: tell digaas to check the zone name. we need the zone name here.
            # if CONFIG.use_digaas and import_resp.ok:
            #     self.digaas_behaviors.check_zone_create_or_update(import_resp)

            if not import_resp.ok:
                import_resp.failure("Failed with status code %s" % import_resp.status_code)
                return

            api_call = lambda: client.get_zone_import(
                import_id=import_resp.json()['id'],
                name='/v2/zones - status of POST /v2/zones/tasks/imports')

            self._poll_until_active_or_error(
                api_call=api_call,
                interval=interval,
                status_function=lambda r: r.json()['status'],
                success_function=import_resp.success,
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
        client = self.designate_client.as_user(tenant)
        zone = tenant.data.select_zone_for_get()
        if not zone:
            LOG.error("%s has no zones for updating", tenant)
            return
        payload = { "name": zone.name,
                    "email": ("update@" + zone.name).strip('.'),
                    "ttl": random.randint(2400, 7200) }
        with client.patch_zone(
                zone.id,
                data=json.dumps(payload),
                name='/v2/zones/ID',
                catch_response=True) as patch_resp:

            if CONFIG.use_digaas and patch_resp.ok:
                self.digaas_behaviors.check_zone_create_or_update(patch_resp)

            if not patch_resp.ok:
                patch_resp.failure('Failure - got %s status code' % patch_resp.status_code)
                return

            api_call = lambda: client.get_zone(
                zone_id=zone.id,
                name='/v2/zones - status of PATCH /v2/zones/ID')
            self._poll_until_active_or_error(
                api_call=api_call,
                interval=interval,
                status_function=lambda r: r.json()['status'],
                success_function=patch_resp.success,
                failure_function=patch_resp.failure)

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

    def remove_domain(self):
        """DELETE /zones/ID"""
        gevent.spawn(
            GreenletManager.get().tracked_greenlet,
            lambda: self._do_remove_domain(interval=2),
            timeout=60
        )

    def _do_remove_domain(self, interval):
        tenant = self.select_random_tenant()
        client = self.designate_client.as_user(tenant)
        zone = tenant.data.pop_zone_for_delete()
        if not zone:
            LOG.error("%s has no zones for deleting", tenant)
            return

        # digaas uses the start_time when computing the propagation
        # time to the nameserver. We're assuming this time is UTC.
        # Normally, we use the created_at/update_at time returned by the api,
        # but the api doesn't gives us that for a delete
        #
        # IMPORTANT: your locust box must be synchronized to network time,
        # along with your digaas box, or digaas will compute bad durations
        if CONFIG.use_digaas:
            start_time = datetime.datetime.now()

        with client.delete_zone(
                zone.id,
                name='/v2/zones/ID',
                catch_response=True) as del_resp:

            if CONFIG.use_digaas and del_resp.ok:
                self.digaas_behaviors.check_name_removed(zone.name, start_time)

            api_call = lambda: client.get_zone(
                zone.id, catch_response=True,
                name='/v2/zones - status of DELETE /v2/zones/ID')
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
