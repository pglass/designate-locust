import json
from collections import namedtuple
import accurate_config as CONFIG
import locust
import client
import digaas_integration
import random
from datagen import *

ZoneTuple = namedtuple('ZoneTuple', ['tenant', 'api_key', 'id', 'name'])
RecordTuple = namedtuple('RecordTuple', ['tenant', 'api_key', 'zone_id',
                                         'zone_name', 'record_id',
                                         'record_data', 'record_type'])

_client = locust.clients.HttpSession(CONFIG.designate_host)
_designate_client = client.DesignateClient(_client)
_digaas_client = digaas_integration.DigaasClient(CONFIG.digaas_endpoint)


def prepare_headers_with_tenant(tenant):
    return { client.ROLE_HEADER: 'admin',
             client.PROJECT_ID_HEADER: tenant }

def get_domains_data(tenants, n):
    # print "Tenants: %s" % tenants
    result = []
    for tenant in tenants:
        # print "Using tenant: %s" % tenant
        resp = _designate_client.list_zones(
            headers=prepare_headers_with_tenant(tenant),
            params={"limit": n},
            name='-- prep data')
        if not resp.ok:
            raise Exception("Failed to list zones for tenant %s" % tenant)
        else:
            for zone in resp.json()['zones']:
                val = ZoneTuple(tenant=tenant, api_key=None, id=zone['id'], name=zone['name'])
                # print val
                result.append(val)
    random.shuffle(result)
    print "Got %s domains for tenants %s" % (len(result), tenants)
    return result

def get_records_data(zone_infos, n, rtype):
    result = []
    for zone_info in zone_infos:
        resp = _designate_client.list_recordsets(
            zone_info.id,
            headers=prepare_headers_with_tenant(zone_info.tenant),
            params={"limit": n, "type": rtype},
            name='-- prep data')
        if not resp.ok:
            raise Exception("Failed to list recordsets for tenant %s" % zone_info.tenant)

        if rtype == 'A' and not len(resp.json()['recordsets']):
            ip = random_ip()
            payload = { "name" : zone_info.name,
                        "type" : "A",
                        "ttl" : 3600,
                        "records" : [ ip ] }
            #print "%s creating A record %s --> %s" % (zone_info.tenant, zone_info.name, ip)
            resp = _designate_client.post_recordset(
                zone_info.id, data=json.dumps(payload),
                headers=prepare_headers_with_tenant(zone_info.tenant),
                name='-- prep data')
            recordset = resp.json()
            record = recordset['records'][0]  # !
            val = RecordTuple(zone_info.tenant, zone_info.api_key, zone_info.id,
                              zone_info.name, recordset['id'], record,
                              recordset['type'])
            result.append(val)
        else:
            #print "%s found %s A records for domain %s" \
                    #% (zone_info.tenant, len(resp.json()['recordsets']), zone_info.id)
            for recordset in resp.json()['recordsets']:
                val = RecordTuple(tenant=zone_info.tenant,
                                  api_key=None,
                                  zone_id=zone_info.id,
                                  zone_name=zone_info.name,
                                  record_id=recordset['id'],
                                  record_data=recordset['records'],
                                  record_type=recordset['type'])
                # print val
                result.append(val)
    print "Got %s records for tenants %s" % (len(result), set([z.tenant for z in zone_infos]))
    return result

