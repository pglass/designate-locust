"""
This script precreates a bunch of data prior to running the test.
It spits out four csv files:
    domains.dat       - domains for GET requests
    domainsdelete.dat - domains for DELETE requests
    records.dat       - records for GET requests
    recordsdelete.dat - records for DELETE requests
These are csv-formatted files. The domains files have the following columns:
    username, apikey, domainid, domainname
The records files have the following columns:
    username, apikey, domainid, domainname, recordid, recorddata, recordtype

This reuses the HTTP client from our Locust test code, which means this script
needs DesignateClient and locust.client.HttpSession.
"""

import argparse
import json
import random
import sys

import requests

from locust.clients import HttpSession
import client
from client import DesignateClient

def get_api_key(tenant):
    return 'API_KEY'

def prepare_headers(tenant):
    return { client.ROLE_HEADER: 'admin',
             client.PROJECT_ID_HEADER: tenant }

def random_ip():
    return ".".join(str(random.randint(0, 255)) for _ in range(4))

def randomize(string, n):
    """Append a random n-digit number to the given string"""
    return "{0}{1}".format(string, random.randint(10 ** (n - 1), 10 ** n - 1))

def random_zone_email(name='random_zone', user='rando'):
    name = randomize(name, n=30)
    zone = "{0}.com.".format(name)
    email = "{0}@{1}".format(user, zone).strip('.')
    return zone, email

def parse_args():
    p = argparse.ArgumentParser(
        description="Generates data prior to running a test")
    p.add_argument("-e", "--endpoint", required=True,
        help="The address of a Designate API (e.g. http://192.168.33.20:9001)")

    p.add_argument("-n", "--n-tenants", required=True, type=int,
        help="The numbers of tenants to use")
    p.add_argument("-p", "--n-domains-per-tenant", required=True, type=int,
        help="The number of domains to create per tenant. The actual number "
             "created per tenant will be 2x this amount. This number of 'GET' "
             "domains is created per tenant. Then, this number of 'DELETE' "
             "domains is created per tenant.")
    return p.parse_args()

ARGS = parse_args()
TENANTS = ["T{0}".format(i + 1) for i in xrange(ARGS.n_tenants)]
CLIENT = DesignateClient(HttpSession(ARGS.endpoint))

# since we print out lots of stuff, make sure we can print a message at the
# end to remind the user an error occurred
ERR_FLAG = False
def error(msg):
    global ERR_FLAG
    ERR_FLAG = True
    print msg

def increase_quotas():
    payload = { "quota": { "zones": 999999999,
                           "recordset_records": 999999999,
                           "zone_records": 999999999,
                           "zone_recordsets": 999999999}}
    for tenant in TENANTS:
        print "Increasing quotas for tenant {0}".format(tenant)
        headers = prepare_headers(tenant)
        CLIENT.patch_quotas(tenant=tenant,
                            data=json.dumps(payload),
                            headers=headers)

def create_domains(n_per_tenant, prefix='domain'):
    """
    Create n_per_tenant domains under each tenant in TENANTS.
    Each zone created has a name that starts with the given prefix.

    return a list of tuples (tenant, api_key, zone_id, zone_name)
    """
    result = []
    for tenant in TENANTS:
        for _ in xrange(n_per_tenant):
            zone, email = random_zone_email(name=prefix)
            payload = { "name": zone,
                        "email": email,
                        "ttl": 7200 }
            print "{0} creating {1}".format(tenant, zone)
            resp = CLIENT.post_zone(data=json.dumps(payload),
                                    headers=prepare_headers(tenant))
            if not resp.ok or not resp.json():
                error(resp.text)
            else:
                val = (tenant, get_api_key(tenant), resp.json()['id'], zone)
                result.append(val)
    return result

def get_records_of_type(domains, rtype):
    """
    domains is a list of tuples as returned by create_domains().
    For each domain, grab the existing records of type rtype ('NS' or 'SOA').
    returns a list of tuples:
        (tenant, api_key, zone_id, zone_name, record_id, record_data, record_type)
    """
    result = []
    for domain in domains:
        tenant, api_key, zone_id, zone_name = domain
        print "%s getting NS records for %s" % (tenant, zone_name)
        resp = CLIENT.list_recordsets(zone_id, params={'type': rtype},
                                      headers=prepare_headers(tenant))
        if not resp.ok or not resp.json():
            error(resp.text)
            continue

        for recordset in resp.json()['recordsets']:
            for record in recordset['records']:
                val = (tenant, api_key, zone_id, zone_name, recordset['id'],
                       record, recordset['type'])
                print "  added %s record %s" % (recordset['type'], record)
                result.append(val)
    return result

def create_A_records(domains):
    result = []
    for domain in domains:
        tenant, api_key, zone_id, zone_name = domain
        ip = random_ip()
        payload = { "name" : zone_name,
                    "type" : "A",
                    "ttl" : 3600,
                    "records" : [ ip ] }
        print "%s creating A record %s --> %s" % (tenant, zone_name, ip)
        resp = CLIENT.post_recordset(zone_id, data=json.dumps(payload),
                                     headers=prepare_headers(tenant))
        if not resp.ok:
            error(resp.text)
            continue

        recordset = resp.json()
        record = recordset['records'][0]  # !
        val = (tenant, api_key, zone_id, zone_name, recordset['id'],
               record, recordset['type'])
        result.append(val)
    return result

def save_domains(filename, domains):
    """Save the given domains to a comma-delimited CSV file. domains is a list
    of tuple as returned by create_domains()."""
    if not domains:
        print "Not saving %s. No domains created" % filename
        return
    format_row = "{0},{1},{2},{3}\n"
    with open(filename, 'w') as f:
        f.write(format_row.format('username', 'apikey', 'domainid', 'domainname'))
        for row in domains:
            f.write(format_row.format(*row))
    print 'Saved %s' % filename

def save_records(filename, records):
    """Save the given records to a comma-delimited CSV file. records is a list
    of tuples as returned by create_A_records() or get_records_of_type()"""
    if not records:
        print "Not saving %s. No records found/created" % filename
        return
    format_row = "{0},{1},{2},{3},{4},{5},{6}\n"
    with open(filename, 'w') as f:
        f.write(format_row.format('username', 'apikey', 'domainid', 'domainname',
                                  'recordid', 'recorddata', 'recordtype'))
        for row in records:
            f.write(format_row.format(*row))
    print 'Saved %s' % filename

if __name__ == '__main__':
    increase_quotas()
    domains = create_domains(ARGS.n_domains_per_tenant, prefix='testdomain')
    # del_domains = create_domains(ARGS.n_domains_per_tenant, prefix='deletedomain')
    # ns_records = get_records_of_type(domains, 'NS')
    a_records = create_A_records(domains)

    #save_domains('domains.dat', domains)
    #save_domains('domainsdelete.dat', del_domains)
    #save_records('records.dat', ns_records)
    #save_records('recordsdelete.dat', a_records)

    if ERR_FLAG:
        print "Terminating gracefully, but some requests failed."

