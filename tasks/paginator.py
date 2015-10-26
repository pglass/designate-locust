import urlparse

class PaginationFrontier(object):
    """This is the frontier of "next" links for exploring paginated lists
    across multiple tenants"""

    def __init__(self, tenants):
        self.tenant_list = list(tenants)
        self.next_zone_links = [('/v2/zones', t) for t in self.tenant_list]
        self.next_recordset_links = []

    @classmethod
    def parse_url(cls, link):
        """Return a tuple (path, params) where path is the url path without
        params and params is a dictionary of all the url parameters"""
        parts = urlparse.urlsplit(link)
        params = urlparse.parse_qs(parts.query)
        return parts.path, params

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
