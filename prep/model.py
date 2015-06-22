from data import get_domains_data
from data import get_records_data
from datagen import *


def split(L, n):
    result = []
    for i in xrange(n):
        f = i * len(L) / n
        t = (i+1) * len(L) / n
        result.append(L[f:t])
    return result


class TestData(object):

    def __init__(self, tenant_list):
        self.domain_get_data = []
        self.domain_delete_data = []
        self.record_get_data = []
        self.record_delete_data = []
        self.record_update_data = []
        self.tenant_list = list(tenant_list)

    def refresh(self, n_domains_per_tenant, n_records_per_domain):
        """Discard currently stored data and fetch new data from Designate."""
        domain_data = get_domains_data(self.tenant_list, n_domains_per_tenant)

        self.domain_get_data,    \
        self.domain_delete_data, \
        records_domains = split(domain_data, 3)

        # assume precreated NS records for gets (we can't always update these)
        self.record_get_data = get_records_data(records_domains, n_records_per_domain, 'NS')

        # assume precreated A records for deletes and updates
        a_records = get_records_data(records_domains, n_records_per_domain, 'A')

        self.record_update_data, self.record_delete_data = split(a_records, 2)

    def __str__(self):
        return ("TestData[domains=(get: %s, delete: %s), "
                "records=(get: %s, delete: %s, update: %s))"
                % (len(self.domain_get_data), len(self.domain_delete_data),
                   len(self.record_get_data), len(self.record_delete_data),
                   len(self.record_update_data)))

    def pick_zone_for_get(self):
        """Returns a tuple (tenant, api_key, zone_id, zone_name)"""
        return select_random_item(self.domain_get_data)

    def pick_zone_for_delete(self):
        """Returns a tuple (tenant, api_key, zone_id, zone_name)"""
        val = select_random_item(self.domain_delete_data)
        # ensure we don't pick this twice
        if val:
            self.domain_delete_data.remove(val)
        #print "deleted record - %s" % self.test_data
        return val

    def pick_record_for_get(self):
        """Returns a tuple (tenant, api_key, zone_id, zone_name, record_id,
        record_data, record_type)"""
        return select_random_item(self.record_get_data)

    def pick_record_for_update(self):
        return select_random_item(self.record_update_data)

    def pick_record_for_delete(self):
        """Returns a tuple (tenant, api_key, zone_id, zone_name, record_id,
        record_data, record_type)"""
        val = select_random_item(self.record_delete_data)
        if val:
            self.record_delete_data.remove(val)
        #print "deleted record - %s" % self.test_data
        return val

    def pick_random_tenant(self):
        return select_random_item(self.tenant_list)



