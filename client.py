import logging

from locust import TaskSet

from requests.packages.urllib3 import disable_warnings
disable_warnings()

import accurate_config as CONFIG

PROJECT_ID_HEADER = 'X-Auth-Project-ID'
TOKEN_HEADER = 'X-Auth-Token'
ROLE_HEADER = 'X-Roles'

LOG = logging.getLogger(__name__)


class DesignateClient(object):
    """Extends a normal client with Designate specific http requests."""

    _HEADERS = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    def __init__(self, client, tenant=None, use_project_id=False):
        self.client = client
        self.tenant = tenant
        self.use_project_id = use_project_id

    def as_user(self, tenant):
        return DesignateClient(self.client, tenant)

    def _request(self, method, url, *args, **kwargs):
        # this is horrible. support a flag to disable request logging, but
        # don't pass that flag to the underlying requests lib
        no_log_request = kwargs.get('no_log_request', False)
        if 'no_log_request' in kwargs:
            del kwargs['no_log_request']
        self._prepare_headers(kwargs)

        if self.tenant and CONFIG.tenant_id_in_url:
            url = url.replace("v2", "v2/{0}".format(self.tenant.tenant_id))

        resp = method(url, *args, **kwargs)
        if not no_log_request:
            self._log_if_bad_request(resp)
        return resp

    def _prepare_headers(self, kwargs):
        """Ensures there are Content-Type and Accept headers,
        and that the headers are in the kwargs."""
        new_headers = dict(self._HEADERS)
        if self.tenant and self.use_project_id:
            new_headers[PROJECT_ID_HEADER] = self.tenant.id
        if self.tenant and self.tenant.api_key:
            new_headers[TOKEN_HEADER] = self.tenant.get_token()
        new_headers.update(kwargs.get('headers') or {})
        kwargs['headers'] = new_headers

    def _log_if_bad_request(self, resp):
        if resp.ok:
            return

        # format the request
        msg = "\n{0} {1}".format(resp.request.method, resp.request.url)
        for k, v in resp.request.headers.items():
            msg += "\n{0}: {1}".format(k, v)
        if resp.request.body:
            msg += "\n{0}".format(resp.request.body)
        else:
            msg += "\n<empty-body>"

        msg += "\n"

        # format the response
        msg += "\n{0} {1}".format(resp.status_code, resp.reason)
        for k, v in resp.headers.items():
            msg += "\n{0}: {1}".format(k, v)
        msg += "\n{0}".format(resp.text)
        msg = "\n  ".join(msg.split('\n'))
        LOG.info(msg)

    #############################################
    # Server calls
    #############################################
    def post_server(self, *args, **kwargs):
        return self._request(self.client.post, "/v1/servers", *args, **kwargs)

    #############################################
    # Quotas calls
    #############################################
    def patch_quotas(self, tenant, *args, **kwargs):
        url = "/admin/quotas/{0}".format(tenant)
        return self._request(self.client.patch, url, *args, **kwargs)

    #############################################
    # Zone calls
    #############################################
    def get_zone(self, zone_id, *args, **kwargs):
        url = "/v2/zones/{0}".format(zone_id)
        return self._request(self.client.get, url, *args, **kwargs)

    def get_zone_by_name(self, zone_name, *args, **kwargs):
        url = "/v2/zones?name={0}".format(zone_name)
        return self._request(self.client.get, url, *args, **kwargs)

    def list_zones(self, *args, **kwargs):
        return self._request(self.client.get, "/v2/zones", *args, **kwargs)

    def post_zone(self, *args, **kwargs):
        return self._request(self.client.post, "/v2/zones", *args, **kwargs)

    def patch_zone(self, zone_id, *args, **kwargs):
        url = "/v2/zones/{0}".format(zone_id)
        return self._request(self.client.patch, url, *args, **kwargs)

    def delete_zone(self, zone_id, *args, **kwargs):
        url = "/v2/zones/{0}".format(zone_id)
        return self._request(self.client.delete, url, *args, **kwargs)

    def import_zone(self, data, *args, **kwargs):
        """data should be the text from a zone file."""
        self._prepare_headers(kwargs)
        kwargs["headers"]["Content-Type"] = "text/dns"
        return self._request(self.client.post, "/v2/zones/tasks/imports",
                             *args, data=data, **kwargs)

    def get_zone_import(self, import_id, *args, **kwargs):
        url = "/v2/zones/tasks/imports/{0}".format(import_id)
        return self._request(self.client.get, url, *args, **kwargs)

    def export_zone(self, zone_id, *args, **kwargs):
        self._prepare_headers(kwargs)
        kwargs['headers']['Accept'] = 'text/dns'
        url = "/admin/zones/export/{0}".format(zone_id)
        return self._request(self.client.get, url, *args, **kwargs)

    #############################################
    # Recordset calls
    #############################################
    def list_recordsets(self, zone_id, *args, **kwargs):
        url = "/v2/zones/{0}/recordsets".format(zone_id)
        return self._request(self.client.get, url, *args, **kwargs)

    def get_recordset(self, zone_id, recordset_id, *args, **kwargs):
        url = "/v2/zones/{0}/recordsets/{1}".format(zone_id, recordset_id)
        return self._request(self.client.get, url, *args, **kwargs)

    def post_recordset(self, zone_id, *args, **kwargs):
        url = "/v2/zones/{0}/recordsets".format(zone_id)
        return self._request(self.client.post, url, *args, **kwargs)

    def put_recordset(self, zone_id, recordset_id, *args, **kwargs):
        url = "/v2/zones/{0}/recordsets/{1}".format(zone_id, recordset_id)
        return self._request(self.client.put, url, *args, **kwargs)

    def delete_recordset(self, zone_id, recordset_id, *args, **kwargs):
        url = "/v2/zones/{0}/recordsets/{1}".format(zone_id, recordset_id)
        return self._request(self.client.delete, url, *args, **kwargs)

    #############################################
    # Proxy methods for raw http requests
    #############################################
    def get(self, *args, **kwargs):
        return self._request(self.client.get, *args, **kwargs)

    #############################################
    # reports
    #############################################
    def counts(self, *args, **kwargs):
        return self._request(
            self.client.get, '/admin/reports/counts', *args, **kwargs)


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
    x.import_zone('sdfsdf')
