"""
This module is used to talk to digaas, an exteranl service used to poll
nameservers. Digaas is a separate service we can use to figure out (external
from Designate) the propagation time from when Designate's API returns until
the time the corresponding change shows up on the nameserver backend.

There are two things here:
    1. A client class we can use to talk to digaas
    2. A setup function that ensures we grab the plot and stats from digaas
    when we stop generating load. The plot and statistics will be integrated
    into the persistent report.
"""

import datetime
import logging
import json
import os
import time

import requests
from requests.exceptions import RequestException
import gevent

import persistence
import accurate_config as CONFIG

LOG = logging.getLogger(__name__)
EPOCH_START = datetime.datetime(1970, 1, 1)


def resp_to_string(resp):
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
    return msg


class DigaasClient(object):

    ZONE_CREATE = 'ZONE_CREATE'
    ZONE_UPDATE = 'ZONE_UPDATE'
    ZONE_DELETE = 'ZONE_DELETE'
    RECORD_CREATE = 'RECORD_CREATE'
    RECORD_UPDATE = 'RECORD_UPDATE'
    RECORD_DELETE = 'RECORD_DELETE'

    PROPAGATION_PLOT = 'propagation_by_type'
    PROPAGATION_BY_NS_PLOT = 'propagation_by_nameserver'
    QUERY_PLOT = 'query'

    JSON_HEADERS = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    def __init__(self, endpoint):
        self.endpoint = endpoint.rstrip('/')

    def ping_check(self):
        try:
            resp = requests.get(self.endpoint)
            if not resp.ok:
                LOG.error("Failed to connect to digaas")
                LOG.error(resp_to_string(resp))
                return False
        except RequestException as e:
            LOG.error("Failed to connect to digaas")
            LOG.exception(e)
            return False

        return True

    def post_observer(self, name, nameserver, start_time, type, timeout,
                      interval, serial=None, rdata=None, rdatatype=None):
        """
        :param serial: only pass this in is type is ZONE_UPDATE
        :param rdata: only pass this if the type is RECORD_*
        :param rdatatype: only pass this if the type is RECORD_*
        """
        url = self.endpoint + '/observers'
        payload = dict(
            name=name,
            nameserver=nameserver,
            type=type,
            start_time=start_time,
            timeout=timeout,
            interval=interval,
        )
        if rdatatype is not None:
            payload['rdatatype'] = rdatatype
        if rdata is not None:
            payload['rdata'] = rdata
        if serial is not None:
            payload['serial'] = serial
        return requests.post(url, data=json.dumps(payload),
                             headers=self.JSON_HEADERS)

    def get_observer(self, id):
        url = "{0}/observers/{1}".format(self.endpoint, id)
        return requests.get(url, headers=self.JSON_HEADERS)

    def post_stats_request(self, start_time, end_time):
        url = self.endpoint + '/stats'
        payload = json.dumps(dict(
            start=start_time,
            end=end_time,
        ))
        return requests.post(url, data=payload, headers=self.JSON_HEADERS)

    def get_stats_request(self, stats_id):
        url = "{0}/stats/{1}".format(self.endpoint, stats_id)
        return requests.get(url, headers=self.JSON_HEADERS)

    def get_stats_summary(self, stats_id):
        url = "{0}/stats/{1}/summary".format(self.endpoint, stats_id)
        return requests.get(url, headers=self.JSON_HEADERS)

    def get_plot(self, stats_id, plot_type):
        """
        :param stats_id: the id of the stats request
        :param plot_type: either 'propagation' or 'query'
        """
        url = "{0}/stats/{1}/plots/{2}".format(
            self.endpoint, stats_id, plot_type)
        return requests.get(url)


class DigaasBehaviors(object):
    """A place to put code to declutter our Tasks class"""

    def __init__(self, client, config):
        """
        :param client: an instance of DigaasClient
        :param config: e.g. your accurate_config.py module
        """
        self.client = client
        self.config = config

    def to_timestamp(self, dt):
        """dt is a datetime object which must be in UTC"""
        return (dt - EPOCH_START).total_seconds()

    def parse_created_at(self, created_at):
        """Parse the given time, which is in iso format with 'T' and milliseconds:
            2015-02-02T20:07:53.000000
        We're assuming this time is UTC.
        Return a datetime instance.
        """
        return datetime.datetime.strptime(created_at, '%Y-%m-%dT%H:%M:%S.%f')

    def _debug_resp(self, resp):
        if resp.ok:
            return
        msg = resp_to_string(resp)
        LOG.debug(msg)

    def observe_zone_create(self, resp, start_time, name=None):
        """
        :param resp: A successful POST /v2/zones or PATCH /v2/zones response
        :param name: Override the query name with this, instead of what's in
            the resp (useful for zone imports)
        """
        query_name = name
        if query_name is None:
            query_name = resp.json()['name']
        for nameserver in self.config.nameservers:
            r = self.client.post_observer(
                name=query_name,
                nameserver=nameserver,
                start_time=start_time,
                type=self.client.ZONE_CREATE,
                timeout=self.config.digaas_timeout,
                interval=self.config.digaas_interval,
            )
            self._debug_resp(r)

    def observe_zone_update(self, resp, start_time):
        name = resp.json()['name']
        serial = resp.json()['serial']
        for nameserver in self.config.nameservers:
            r = self.client.post_observer(
                name=name,
                nameserver=nameserver,
                start_time=start_time,
                type=self.client.ZONE_UPDATE,
                timeout=self.config.digaas_timeout,
                interval=self.config.digaas_interval,
                serial=serial,
            )
            self._debug_resp(r)

    def observe_zone_delete(self, name, start_time):
        for nameserver in self.config.nameservers:
            r = self.client.post_observer(
                name=name,
                nameserver=nameserver,
                start_time=start_time,
                type=self.client.ZONE_DELETE,
                timeout=self.config.digaas_timeout,
                interval=self.config.digaas_interval,
            )
            self._debug_resp(r)

    def observe_record_create(self, resp, start_time):
        name = resp.json()["name"]
        rdata = resp.json()["records"][0]
        rdatatype = resp.json()["type"]

        for nameserver in self.config.nameservers:
            r = self.client.post_observer(
                name=name,
                nameserver=nameserver,
                start_time=start_time,
                type=self.client.RECORD_CREATE,
                timeout=self.config.digaas_timeout,
                interval=self.config.digaas_interval,
                rdata=rdata,
                rdatatype=rdatatype,
            )
            self._debug_resp(r)

    def observe_record_update(self, resp, start_time):
        name = resp.json()["name"]
        rdata = resp.json()["records"][0]
        rdatatype = resp.json()["type"]

        for nameserver in self.config.nameservers:
            r = self.client.post_observer(
                name=name,
                nameserver=nameserver,
                start_time=start_time,
                type=self.client.RECORD_UPDATE,
                timeout=self.config.digaas_timeout,
                interval=self.config.digaas_interval,
                rdata=rdata,
                rdatatype=rdatatype,
            )
            self._debug_resp(r)

    def observe_record_delete(self, name, rdata, rdatatype, start_time):
        for nameserver in self.config.nameservers:
            r = self.client.post_observer(
                name=name,
                nameserver=nameserver,
                start_time=start_time,
                type=self.client.RECORD_DELETE,
                timeout=self.config.digaas_timeout,
                interval=self.config.digaas_interval,
                rdata=rdata,
                rdatatype=rdatatype,
            )
            self._debug_resp(r)


def setup(digaas_client):
    if digaas_client.ping_check():
        LOG.info("USING DIGaaS")
