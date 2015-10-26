import logging
import urlparse

import locust.events
import locust.runners

from base import BaseTaskSet
from models import Zone, Recordset
from paginator import PaginationFrontier
import accurate_config as CONFIG

LOG = logging.getLogger(__name__)


class GatherTasks(BaseTaskSet):

    frontier = None

    def _log_tenants(self):
        LOG.info("---- tenants -----")
        for t in self.tenant_list:
            LOG.info(str(t))

    def on_start(self):
        LOG.debug("GatherTasks.on_start()")
        self._log_tenants()
        if not GatherTasks.frontier:
            GatherTasks.frontier = PaginationFrontier(self.tenant_list)

    def done(self):
        for tenant in self.frontier.tenant_list:
            enough_zones_and_recordsets = tenant.data.exceeds_quotas(
                n_get_zones = CONFIG.n_zones_for_get_per_tenant,
                n_delete_zones = CONFIG.n_zones_for_delete_per_tenant,
                n_get_recordsets = CONFIG.n_recordsets_for_get_per_tenant,
                n_delete_recordsets = CONFIG.n_recordsets_for_delete_per_tenant)

            if enough_zones_and_recordsets:
                LOG.info("%s has enough stuff!" % tenant)
                self.frontier.remove_tenant(tenant)
                LOG.debug("Tenants left: {0}".format(self.frontier.tenant_list))

        return self.frontier.is_empty()

    def gather_zones(self):
        if self.done():
            LOG.debug("we're done!")
            self.done_gathering.fire()
            return

        # grab a list zones link from our 'frontier' of links
        link, tenant = self.frontier.pop_next_zone_link()
        if not link:
            return
        # we want to be careful to retain the 'marker=<uuid>' that's used to
        # grab different pages of a paginated list
        path, params = self.frontier.parse_url(link)
        params['sort_key'] = 'id'

        client = self.designate_client.as_user(tenant)
        resp = client.get(path, name='/v2/zones', params=params)
        if not resp.ok:
            LOG.error("failed to list zones while gathering zones")
            return

        zones = resp.json()['zones']
        links = resp.json()['links']
        LOG.info("%s -- fetched %s zones for tenant %s",
                 resp.request.url, len(zones), tenant)
        if 'next' in links:
            self.frontier.add_zone_link(links['next'], tenant)
        else:
            LOG.debug("no more zone 'next' links to pursue")
        for z in zones:
            zone = Zone(z['id'], z['name'])

            # be sure to avoid storing recordsets on zones we're going to delete
            if len(tenant.data.zones_for_get) <= len(tenant.data.zones_for_delete):
                tenant.data.zones_for_get.append(zone)

                path, _ = self.frontier.parse_url(z['links']['self'])
                recordset_link = "{0}/recordsets".format(path)
                self.frontier.add_recordset_link(zone, recordset_link, tenant)
            else:
                tenant.data.zones_for_delete.append(zone)

    def gather_recordsets(self):
        if self.done():
            LOG.debug("we're done!")
            self.done_gathering.fire()
            return

        zone, link, tenant = self.frontier.pop_next_recordset_link()
        if not link:
            return
        path, params = self.frontier.parse_url(link)
        params['sort_key'] = 'id'

        client = self.designate_client.as_user(tenant)
        resp = client.get(path, name='/v2/zones/ID/recordsets', params=params)
        if not resp.ok:
            LOG.error("failed to list recordsets while gathering recordsets")
            return

        recordsets = resp.json()['recordsets']
        links = resp.json()['links']

        LOG.info("%s -- fetched %s recordsets for tenant %s",
                resp.request.url, len(recordsets), tenant)
        if 'next' in links:
            self.frontier.add_recordset_link(zone, links['next'], tenant)

        for r in recordsets:
            if r['type'] != 'A':
                continue

            # we're assuming only one record per recordset.
            # this is guaranteed as long we're in control of data creation
            recordset = Recordset(zone, r['id'], r['records'][0], r['type'])

            if len(tenant.data.recordsets_for_get) <= len(tenant.data.recordsets_for_delete):
                tenant.data.recordsets_for_get.append(recordset)
            else:
                tenant.data.recordsets_for_delete.append(recordset)
