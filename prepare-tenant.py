import argparse
import json
import logging

from requests.packages.urllib3 import disable_warnings
disable_warnings()

from locust.clients import HttpSession

from client import DesignateClient
from models import Tenant, Zone, Recordset
from datagen import random_zone_email, randomize, random_ip
from auth_client import AuthClient
from tasks.gather import PaginationFrontier

logging.basicConfig(level=logging.DEBUG)

def parse_args():
    p = argparse.ArgumentParser(description=
        "Create a specific number of zones for a tenant and a specific number "
        "of recordsets per zone. This will try to be intelligent enough to "
        "avoid creating a whole bunch of additional zones")

    p.add_argument("-e", "--endpoint", required=True,
        help="The address of a Designate API (e.g. http://192.168.33.20:9001)")
    p.add_argument("-a", "--auth-endpoint", required=True)
    p.add_argument("-u", "--username", required=True)
    p.add_argument("-k", "--api-key", required=True)
    p.add_argument("-z", "--n-zones", required=True, type=int,
        help="The number of zones this tenant needs to have")
    p.add_argument("-r", "--n-recordsets-per-zone", required=True, type=int,
        help="The number of recordsets each zone should have")
    p.add_argument("--no-tenant-id-in-url", action='store_true',
        help="Don't put the tenant id in the url")
    p.add_argument("--use-project-id-header", action='store_true',
        help="Pass in the X-Auth-Project-ID header")
    p.add_argument("--no-https", action='store_true', help="Don't force https")
    return p.parse_args()

def ensure_https(link, args):
    if not args.no_https and link.startswith('http:'):
        return link.replace('http:', 'https:', 1)
    return link

class TenantPrepper(object):

    def __init__(self, args):
        self.args = args
        self.tenant = Tenant(
            self.args.username,
            self.args.api_key,
            Tenant.SMALL,  # this doesn't mean anything for our purposes
            self.args.auth_endpoint,
        )

        self.tenant.get_token()

        print "%s has token %s" % (self.tenant.id, self.tenant.get_token())

        self.client = DesignateClient(
            client=HttpSession(self.args.endpoint),
            tenant=self.tenant,
            use_project_id=self.args.use_project_id_header,
            tenant_id_in_url=not self.args.no_tenant_id_in_url,
        )

    def run(self):
        # self.increase_quotas()
        zones = self.ensure_zones_are_created()
        recordsets = self.ensure_recordsets_are_created(zones)

    def increase_quotas(self):
        payload = {
            "quota": {
                "zones": 99999999,
                "recordset_records": 99999999,
                "zone_records": 99999999,
                "zone_recordsets": 99999999,
            }
        }
        resp = self.client.patch_quotas(self.tenant.tenant_id, json.dumps(payload))
        check_resp(resp)
        print '%s increased quotas' % self.tenant.tenant_id

    def ensure_zones_are_created(self):
        # try to fetch the number of zones we need
        zones = self.list_zones(limit=self.args.n_zones)
        print "%s has at least %s zones already (need %s total)" % (
            self.tenant.id, len(zones), self.args.n_zones)

        # if we don't have enough zones, create some more
        if len(zones) < self.args.n_zones:
            n_missing_zones = self.args.n_zones - len(zones)
            print "%s is creating %s additional zones" % (
                self.tenant.id, n_missing_zones)
            additional_zones = self.create_zones(number=n_missing_zones)
            zones.extend(additional_zones)

        return zones

    def ensure_recordsets_are_created(self, zones):
        recordsets = []
        for zone in zones:
            records_for_zone = self.ensure_recordsets_are_created_for_zone(zone)
            recordsets.extend(records_for_zone)
        return recordsets

    def ensure_recordsets_are_created_for_zone(self, zone):
        # try to fetch the number of recordsets we want
        recordsets = self.list_a_recordsets(zone, limit=self.args.n_recordsets_per_zone)
        print "%s: zone %s already has at least %s A recordsets (need %s)" % (
            self.tenant.id, zone.name, len(recordsets), self.args.n_recordsets_per_zone)

        # if not enough recordsets, create some more
        if len(recordsets) < self.args.n_recordsets_per_zone:
            n_missing_recordsets = self.args.n_recordsets_per_zone - len(recordsets)
            print "%s is creating %s additional recordsets on zone %s" % (
                self.tenant.id, n_missing_recordsets, zone.name)
            additional_recordsets = self.create_recordsets(zone, number=n_missing_recordsets)
            print 'created %s additional_recordets' % len(additional_recordsets)
            recordsets.extend(additional_recordsets)

        return recordsets

    def create_zones(self, number):
        return [self.create_zone() for _ in xrange(number)]

    def create_zone(self):
        zone_name, email = random_zone_email()
        payload = { "name": zone_name, "email": email, "ttl": 7200 }

        resp = self.client.post_zone(data=json.dumps(payload))
        check_resp(resp)

        zone = Zone(resp.json()['id'], resp.json()['name'])
        print '%s: Created zone %s' % (self.tenant.id, zone.name)
        return zone

    def create_recordsets(self, zone, number):
        return [self.create_recordset(zone) for _ in xrange(number)]

    def create_recordset(self, zone):
        record_name = "{0}.{1}".format(randomize("record"), zone.name)
        payload = { "name" : record_name,
                    "type" : "A",
                    "ttl" : 3600,
                    "records" : [ random_ip() ] }

        resp = self.client.post_recordset(zone.id, data=json.dumps(payload))
        check_resp(resp)

        recordset = Recordset(
            zone = zone,
            id = resp.json()['id'],
            data = resp.json()['records'][0],
            type = resp.json()['type'])
        print '%s: Created recordset %s' % (self.tenant.id, record_name)
        return recordset

    def list_zones(self, limit):
        frontier = PaginationFrontier([self.tenant])
        found_zones = []

        while not frontier.is_empty():
            link, tenant = frontier.pop_next_zone_link()
            if not link:
                return found_zones

            print "%s: GET %s" % (self.tenant.id, link)
            resp = self.client.get(link)
            # print resp.request.headers
            # print resp.request.body
            check_resp(resp)

            zones = resp.json()['zones']
            links = resp.json()['links']

            if 'next' in links:
                if self.args.endpoint.startswith('https:'):
                    next_link = ensure_https(links['next'], self.args)
                else:
                    next_link = links['next']
                frontier.add_zone_link(next_link, tenant)

            for z in zones:
                zone = Zone(z['id'], z['name'])
                found_zones.append(zone)
                if len(found_zones) >= limit:
                    return found_zones

        return found_zones

    def list_a_recordsets(self, zone, limit):
        frontier = PaginationFrontier([self.tenant])
        found_recordsets = []

        initial_link = '/v2/zones/%s/recordsets' % zone.id
        frontier.add_recordset_link(zone, initial_link, self.tenant)

        while not frontier.is_empty():
            zone, link, tenant = frontier.pop_next_recordset_link()
            if not link:
                return found_recordsets

            print "%s: GET %s" % (self.tenant.id, link)
            resp = self.client.get(link)
            # print resp.text
            check_resp(resp)

            recordsets = resp.json()['recordsets']
            links = resp.json()['links']

            if 'next' in links:
                if self.args.endpoint.startswith('https:'):
                    next_link = ensure_https(links['next'], self.args)
                else:
                    next_link = links['next']
                frontier.add_recordset_link(zone, next_link, tenant)

            for r in recordsets:
                if r['type'].upper() != 'A':
                    continue

                recordset = Recordset(zone, r['id'], r['records'][0], r['type'])
                found_recordsets.append(recordset)
                if len(found_recordsets) >= limit:
                    return found_recordsets

        return found_recordsets


def check_resp(resp):
    if not resp.ok:
        raise Exception("Bad response! %s - %s" % (resp, resp.text))


if __name__ == '__main__':
    prepper = TenantPrepper(parse_args())
    prepper.run()
