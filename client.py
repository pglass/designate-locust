import logging

from locust import TaskSet

PROJECT_ID_HEADER = 'X-Auth-Project-ID'
ROLE_HEADER = 'X-Roles'

LOG = logging.getLogger(__name__)


class DesignateClient(object):
    """Extends a normal client with Designate specific http requests."""

    _HEADERS = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    def __init__(self, client, tenant=None):
        self.client = client
        self.tenant = tenant

    def as_user(self, tenant):
        return DesignateClient(self.client, tenant)

    def _prepare_headers(self, kwargs):
        """Ensures there are Content-Type and Accept headers,
        and that the headers are in the kwargs."""
        new_headers = dict(self._HEADERS)
        if self.tenant:
            new_headers['X-Auth-Project-ID'] = self.tenant.id
        if self.tenant and self.tenant.api_key:
            new_headers['X-Auth-Token'] = self.tenant.get_token()
        new_headers.update(kwargs.get('headers') or {})
        kwargs['headers'] = new_headers

    #############################################
    # Server calls
    #############################################
    def post_server(self, *args, **kwargs):
        self._prepare_headers(kwargs)
        return self.client.post("/v1/servers", *args, **kwargs)

    #############################################
    # Quotas calls
    #############################################
    def patch_quotas(self, tenant, *args, **kwargs):
        self._prepare_headers(kwargs)
        url = "/admin/quotas/{0}".format(tenant)
        return self.client.patch(url, *args, **kwargs)

    #############################################
    # Zone calls
    #############################################
    def get_zone(self, zone_id, *args, **kwargs):
        self._prepare_headers(kwargs)
        url = "/v2/zones/{0}".format(zone_id)
        return self.client.get(url, *args, **kwargs)

    def get_zone_by_name(self, zone_name, *args, **kwargs):
        self._prepare_headers(kwargs)
        url = "/v2/zones?name={0}".format(zone_name)
        return self.client.get(url, *args, **kwargs)

    def list_zones(self, *args, **kwargs):
        self._prepare_headers(kwargs)
        return self.client.get("/v2/zones", *args, **kwargs)

    def post_zone(self, *args, **kwargs):
        self._prepare_headers(kwargs)
        return self.client.post("/v2/zones", *args, **kwargs)

    def patch_zone(self, zone_id, *args, **kwargs):
        self._prepare_headers(kwargs)
        url = "/v2/zones/{0}".format(zone_id)
        return self.client.patch(url, *args, **kwargs)

    def delete_zone(self, zone_id, *args, **kwargs):
        self._prepare_headers(kwargs)
        url = "/v2/zones/{0}".format(zone_id)
        return self.client.delete(url, *args, **kwargs)

    def import_zone(self, data, *args, **kwargs):
        """data should be the text from a zone file."""
        self._prepare_headers(kwargs)
        kwargs["headers"]["Content-Type"] = "text/dns"
        return self.client.post("/v2/zones/tasks/imports", data=data, *args,
                                **kwargs)

    def get_zone_import(self, import_id, *args, **kwargs):
        self._prepare_headers(kwargs)
        url = "/v2/zones/tasks/imports/{0}".format(import_id)
        return self.client.get(url, *args, **kwargs)

    def export_zone(self, zone_id, *args, **kwargs):
        self._prepare_headers(kwargs)
        kwargs['headers']['Accept'] = 'text/dns'
        url = "/admin/zones/export/{0}".format(zone_id)
        return self.client.get(url, *args, **kwargs)

    #############################################
    # Recordset calls
    #############################################
    def list_recordsets(self, zone_id, *args, **kwargs):
        self._prepare_headers(kwargs)
        url = "/v2/zones/{0}/recordsets".format(zone_id)
        return self.client.get(url, *args, **kwargs)

    def get_recordset(self, zone_id, recordset_id, *args, **kwargs):
        self._prepare_headers(kwargs)
        url = "/v2/zones/{0}/recordsets/{1}".format(zone_id, recordset_id)
        return self.client.get(url, *args, **kwargs)

    def post_recordset(self, zone_id, *args, **kwargs):
        self._prepare_headers(kwargs)
        url = "/v2/zones/{0}/recordsets".format(zone_id)
        return self.client.post(url, *args, **kwargs)

    def put_recordset(self, zone_id, recordset_id, *args, **kwargs):
        self._prepare_headers(kwargs)
        url = "/v2/zones/{0}/recordsets/{1}".format(zone_id, recordset_id)
        return self.client.put(url, *args, **kwargs)

    def delete_recordset(self, zone_id, recordset_id, *args, **kwargs):
        self._prepare_headers(kwargs)
        url = "/v2/zones/{0}/recordsets/{1}".format(zone_id, recordset_id)
        return self.client.delete(url, *args, **kwargs)

    #############################################
    # Proxy methods for raw http requests
    #############################################
    def get(self, *args, **kwargs):
        self._prepare_headers(kwargs)
        return self.client.get(*args, **kwargs)



if __name__ == '__main__':
    class tmp(object): pass
    def _print(self, *args, **kwargs):
        print "Args:", args
        print "Kwargs:", kwargs

    import types
    client = tmp()
    client.get = types.MethodType(_print, client)
    client.put = types.MethodType(_print, client)
    client.post = types.MethodType(_print, client)
    client.patch = types.MethodType(_print, client)
    client.delete = types.MethodType(_print, client)

    x = DesignateClient(client)
    x.get_zone('test_get_zone')
    x.patch_zone('test_patch', data={'put': 'data'},
            headers={'Content-Type': 'text/dns',
                'X-Auth-Project': 'aasdfsadfsdfs'})
    x.post_zone('test_post')
    x.delete_zone('test_delete')
