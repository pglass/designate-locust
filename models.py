from datagen import select_random_item, pop_random_item
from collections import namedtuple

Zone = namedtuple('Zone', ['id', 'name'])
Recordset = namedtuple('Recordset', ['zone', 'id', 'data', 'type'])

class Tenant(object):

    SMALL = 'small'
    LARGE = 'large'

    def __init__(self, id, api_key, type):
        self.id = id
        self.api_key = api_key
        self.type = type
        self.data = TenantData()

    def __str__(self):
        if not self.api_key:
            api_key_msg = "<no-api-key>"
        else:
            api_key_msg = "<api-key-not-shown>"
        return "(%s, %s, %s)" % (self.id, api_key_msg, self.type)

    def __repr__(self):
        return "Tenant%s" % str(self)

class TenantData(object):

    def __init__(self):
        self.zones_for_get = []
        self.zones_for_delete = []
        self.recordsets_for_get = []
        self.recordsets_for_delete = []

    def zone_count(self):
        return len(self.zones_for_get) + len(self.zones_for_delete)

    def recordset_count(self):
        return len(self.recordsets_for_get) + len(self.recordsets_for_delete)

    def select_zone_for_get(self):
        return select_random_item(self.zones_for_get)

    def select_recordset_for_get(self):
        return select_random_item(self.recordsets_for_get)

    def pop_zone_for_delete(self):
        return pop_random_item(self.zones_for_delete)

    def pop_recordset_for_delete(self):
        return pop_random_item(self.recordsets_for_delete)

    def exceeds_quotas(self, n_get_zones, n_delete_zones, n_get_recordsets,
                       n_delete_recordsets):
        return (
            len(self.zones_for_get) >= n_get_zones and
            len(self.zones_for_delete) >= n_delete_zones and
            len(self.recordsets_for_get) >= n_get_recordsets and
            len(self.recordsets_for_delete) >= n_delete_recordsets)
