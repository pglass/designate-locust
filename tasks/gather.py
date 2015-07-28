from base import BaseTaskSet

from models import Zone, Recordset

import locust.events
import locust.runners

import accurate_config as CONFIG


class PaginationFrontier(object):
    """This is the frontier of "next" links for exploring paginated lists
    across multiple tenants"""

    def __init__(self, tenants):
        self.tenant_list = list(tenants)
        self.next_zone_links = [('/v2/zones', t) for t in self.tenant_list]
        self.next_recordset_links = []

    def add_zone_link(self, link, tenant):
        self.next_zone_links.append((link, tenant))

    def add_recordset_link(self, zone, link, tenant):
        self.next_recordset_links.append((zone, link, tenant))

    def pop_next_zone_link(self):
        if self.next_zone_links:
            return self.next_zone_links.pop(0)
        return None, None

    def pop_next_recordset_link(self):
        if self.next_recordset_links:
            return self.next_recordset_links.pop(0)
        return None, None, None

    def remove_tenant(self, tenant):
        self.tenant_list.remove(tenant)
        self.next_zone_links = [
            x for x in self.next_zone_links if x[-1] != tenant]
        self.next_recordset_links = [
            x for x in self.next_recordset_links if x[-1] != tenant]

    def is_empty(self):
        return (not self.next_zone_links and not self.next_recordset_links) \
            or not self.tenant_list


class GatherTasks(BaseTaskSet):

    frontier = None

    def __init__(self, *args, **kwargs):
        super(GatherTasks, self).__init__(*args, **kwargs)
        self.on_start()

    def on_start(self):
        print "GatherTasks.on_start()"
        print "tenants = {0}".format(self.tenant_list)
        if not GatherTasks.frontier:
            GatherTasks.frontier = PaginationFrontier(self.tenant_list)

    def _get_path_from_full_url(self, link):
        parts = link.split('/v2/')
        return '/v2/' + parts[1]

    def done(self):
        for tenant in self.frontier.tenant_list:
            enough_zones_and_recordsets = tenant.data.exceeds_quotas(
                n_get_zones = CONFIG.n_zones_for_get_per_tenant,
                n_delete_zones = CONFIG.n_zones_for_delete_per_tenant,
                n_get_recordsets = CONFIG.n_recordsets_for_get_per_tenant,
                n_delete_recordsets = CONFIG.n_recordsets_for_delete_per_tenant)

            if enough_zones_and_recordsets:
                print "%s has enough stuff!" % tenant
                self.frontier.remove_tenant(tenant)
                print "Tenants left: {0}".format(self.frontier.tenant_list)

        return self.frontier.is_empty()

    def gather_zones(self):
        if self.done():
            print "we're done! -- %s.done_gathering" % self.__class__.__name__
            self.done_gathering.fire()
            return

        # grab a list zones link from our 'frontier' of links
        link, tenant = self.frontier.pop_next_zone_link()
        if not link:
            return
        link = self._get_path_from_full_url(link)

        headers = {'X-Auth-Project-ID': tenant.id}
        resp = self.client.get(link, headers=headers, name='/v2/zones')
        zones = resp.json()['zones']
        links = resp.json()['links']
        print "%s -- fetched %s zones for tenant %s" % (resp.request.url, len(zones), tenant)
        if 'next' in links:
            self.frontier.add_zone_link(links['next'], tenant)
        else:
            print "no more zone 'next' links to pursue"
        for z in zones:
            zone = Zone(z['id'], z['name'])

            # be sure to avoid storing recordsets on zones we're going to delete
            if len(tenant.data.zones_for_get) <= len(tenant.data.zones_for_delete):
                tenant.data.zones_for_get.append(zone)

                recordset_link = z['links']['self'].strip('/') + '/recordsets'
                self.frontier.add_recordset_link(zone, recordset_link, tenant)
            else:
                tenant.data.zones_for_delete.append(zone)

    def gather_recordsets(self):
        if self.done():
            print "we're done! -- %s.done_gathering" % self.__class__.__name__
            self.done_gathering.fire()
            return

        zone, link, tenant = self.frontier.pop_next_recordset_link()
        if not link:
            return
        link = self._get_path_from_full_url(link)

        headers = {'X-Auth-Project-ID': tenant.id}
        resp = self.client.get(link, headers=headers, name='/v2/zones/{id}/recordsets')
        recordsets = resp.json()['recordsets']
        links = resp.json()['links']

        print "{0} -- fetched {1} recordsets for tenant {2}".format(
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
