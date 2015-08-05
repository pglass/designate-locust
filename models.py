import datetime
import logging

from datagen import select_random_item, pop_random_item
from collections import namedtuple
from auth_client import AuthClient

LOG = logging.getLogger(__name__)

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

        self._token = None
        self._expiry= None

    def get_token(self):
        if not self._token or self.is_expired():
            self.renew_token()
        return self._token

    def renew_token(self):
        """Revoke the current token and then renew it.

        This makes sure the token we have is good for (roughly) 24 hours.
        """
        auth_client = AuthClient()

        if self._token:
            revoke_resp = auth_client.revoke_token(token)

        auth_resp = auth_client.get_token(self.id, self.api_key)
        if auth_resp.ok:
            self._token = auth_resp.json()['access']['token']['id']
            self._expiry = self._parse_time(auth_resp.json()['access']['token']['expires'])
        else:
            LOG.error("Failed to auth %s" % self)
            LOG.error("%s" % auth_resp.text)

    def is_expired(self):
        """Return True if we deem the token to be expired.

        The token is expired if we're within 6 hours of the actual expiry time.
        """
        if self._expiry is not None:
            now = datetime.datetime.utcnow()
            expiry = self._expiry - datetime.timedelta(hours=6)
            return now >= expiry
        return False

    @classmethod
    def _parse_time(cls, time_str):
        return datetime.datetime.strptime(time_str, '%Y-%m-%dT%H:%M:%S.%fZ')

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
