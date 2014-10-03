from locust import TaskSet

class DesignateClient(object):
    """Extends a normal TaskSet client with Designate specifc http requests."""

    _HEADERS = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    def __init__(self, client):
        self.client = client

    @classmethod
    def _add_headers(cls, kwargs, headers=_HEADERS):
        """If no headers in kwargs, insert application/json."""
        kwargs['headers'] = kwargs.get('headers') or headers

    #############################################
    # Zone calls
    #############################################
    def get_zone(self, zone_id, *args, **kwargs):
        url = "/v2/zones/{0}".format(zone_id)
        self._add_headers(kwargs)
        return self.client.get(url, *args, **kwargs)

    def list_zones(self, *args, **kwargs):
        self._add_headers(kwargs)
        return self.client.get("/v2/zones")

    def post_zone(self, *args, **kwargs):
        self._add_headers(kwargs)
        return self.client.post("/v2/zones", *args, **kwargs)

    def patch_zone(self, zone_id, *args, **kwargs):
        self._add_headers(kwargs)
        url = "/v2/zones/{0}".format(zone_id)
        return self.client.patch(url, *args, **kwargs)

    def delete_zone(self, zone_id, *args, **kwargs):
        self._add_headers(kwargs)
        url = "/v2/zones/{0}".format(zone_id)
        return self.client.delete(url, *args, **kwargs)

    #############################################
    # Recordset calls
    #############################################
    def list_recordsets(self, zone_id, *args, **kwargs):
        self._add_headers(kwargs)
        url = "/v2/zones/{0}/recordsets".format(zone_id)
        return self.client.get(url, *args, **kwargs)

    def get_recordset(self, zone_id, recordset_id, *args, **kwargs):
        self._add_headers(kwargs)
        url = "/v2/zones/{0}/recordsets/{1}".format(zone_id, recordset_id)
        return self.client.get(url, *args, **kwargs)

    def post_recordset(self, zone_id, *args, **kwargs):
        self._add_headers(kwargs)
        url = "/v2/zones/{0}/recordsets".format(zone_id)
        return self.client.post(url, *args, **kwargs)

    def put_recordset(self, zone_id, recordset_id, *args, **kwargs):
        self._add_headers(kwargs)
        url = "/v2/zones/{0}/recordsets/{1}".format(zone_id, recordset_id)
        return self.client.put(url, *args, **kwargs)

    def delete_recordset(self, zone_id, recordset_id, *args, **kwargs):
        self._add_headers(kwargs)
        url = "/v2/zones/{0}/recordsets/{1}".format(zone_id, recordset_id)
        return self.client.delete(url, *args, **kwargs)


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
            headers={'Content-Type': 'text/dns'})
    x.post_zone('test_post')
    x.delete_zone('test_delete')
