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
import locust
import json
import os
import requests
import shutil
import time
import uuid

import gevent

import insight
import persistence


class DigaasClient(object):

    JSON_HEADERS = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    def __init__(self, endpoint):
        self.endpoint = endpoint.rstrip('/')

    def post_poll_request(self, nameserver, query_name, serial, start_time,
                          condition, timeout, frequency, rdatatype=None):
        url = self.endpoint + '/poll_requests'
        payload = dict(
            nameserver = nameserver,
            query_name = query_name,
            serial = serial,
            start_time = start_time,
            condition = condition,
            timeout = timeout,
            frequency = frequency,
        )
        if rdatatype is not None:
            payload['rdatatype'] = rdatatype
        return requests.post(url, data=json.dumps(payload), headers=self.JSON_HEADERS)

    def get_poll_request(self, id):
        url = "{0}/poll_requests/{1}".format(self.endpoint, id)
        return requests.get(url, headers=self.JSON_HEADERS)

    def post_stats_request(self, start_time, end_time):
        url = self.endpoint + '/stats'
        payload = json.dumps(dict(
            start_time = start_time,
            end_time = end_time,
        ))
        return requests.post(url, data=payload, headers=self.JSON_HEADERS)

    def get_stats_request(self, id):
        url = "{0}/stats/{1}".format(self.endpoint, id)
        return requests.get(url, headers=self.JSON_HEADERS)

    def get_image(self, id):
        """Use resp.raw to access the image data"""
        url = "{0}/images/{1}".format(self.endpoint, id)
        resp = requests.get(url, stream=True)
        resp.raw.decode_content = True
        return resp


EPOCH_START = datetime.datetime(1970, 1, 1)
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
        if not resp.ok:
            print "Digaas request failed:"
            print resp.request.body
            print resp.text

    def check_zone_create_or_update(self, resp):
        """Tell digaas to poll the nameservers to for a zone serial change

        :param resp: A successful POST /v2/zones or PATCH /v2/zones response
        """
        # digaas uses the start_time when computing the propagation
        # time to the nameserver. We're assuming this time is UTC.
        start_time = self.parse_created_at(resp.json()['created_at'])

        for nameserver in self.config.nameservers:
            # print "  POST digaas (create/update zone) - %s" % nameserver
            r = self.client.post_poll_request(
                nameserver = nameserver,
                query_name = resp.json()['name'],
                serial = resp.json()['serial'],
                start_time = self.to_timestamp(start_time),
                condition = "serial_not_lower",
                timeout = self.config.digaas_timeout,
                frequency = self.config.digaas_interval)
            self._debug_resp(r)

    def check_name_removed(self, query_name, start_time):
        """Tell digaas to poll the nameservers until the name is removed"""
        for nameserver in self.config.nameservers:
            # print "  POST digaas (delete zone/record) - %s" % nameserver
            r = self.client.post_poll_request(
                nameserver = nameserver,
                query_name = query_name,
                serial = 0,
                start_time = self.to_timestamp(start_time),
                condition = "zone_removed",
                timeout = self.config.digaas_timeout,
                frequency = self.config.digaas_interval)
            self._debug_resp(r)

    def check_record_create_or_update(self, resp):
        record_name = resp.json()["name"]
        expected_data = resp.json()["records"][0]
        record_type = resp.json()["type"]
        start_time = self.parse_created_at(resp.json()['created_at'])

        for nameserver in self.config.nameservers:
            # print "  POST digaas (create/update recordset) - %s" % nameserver
            # digaas will poll until the zone's serial is higher
            r = self.client.post_poll_request(
                nameserver = nameserver,
                query_name = record_name,
                rdatatype = record_type,
                serial = 0,
                start_time = self.to_timestamp(start_time),
                condition = "data=" + expected_data,
                timeout = self.config.digaas_timeout,
                frequency = self.config.digaas_interval)
            self._debug_resp(r)


def fetch_plot(client, start_time, end_time, output_filename):
    print "fetching plot"
    post_resp = client.post_stats_request(start_time, end_time)
    if not post_resp.ok:
        print "ERROR fetching plot: {0}".format(post_resp)
        return

    id = post_resp.json()['id']

    timeout = 300
    end_time = time.time() + timeout
    while time.time() < end_time:
        # we must yield to other greenlets or this loop will block the world
        gevent.sleep(1)

        resp = client.get_stats_request(id)
        print resp
        if resp.ok:
            print "stats request suceeded"
            print resp.text
            image_id = resp.json()['image_id']
            print "image_id = %s" % image_id
            image_resp = client.get_image(image_id)
            print "writing to file %s" % output_filename
            # save all images to the images directory
            output_path = os.path.join(persistence.images_dir, output_filename)
            with open(output_path, 'wb') as f:
                shutil.copyfileobj(image_resp.raw, f)
            break


def persist_digaas_data(stats, digaas_client):
    """An event handler called before stats are persisted to disk.

    :param stats: the dictionary persisted to disk at the end of each test run
        (don't stomp all over this data)

    The stats dictionary is updated with some filenames containing data fetched
    from digaas. These files don't yet exist; a greenlet is spawned to
    asynchronously fetch things from digaas and store that to files.
    """
    start_time = int(stats['start_time'])
    end_time = int(stats['last_request_timestamp'] + 1)
    print start_time, end_time
    plot_filename = "propagation_plot{0}.png".format(start_time)
    print plot_filename

    gevent.spawn(fetch_plot, digaas_client, start_time, end_time, plot_filename)

    stats['digaas'] = {
        'plot_file': plot_filename,
    }


def setup_digaas_integration(digaas_client):
    print "USING DIGaaS"
    # register our event handlers
    persistence.persisting_info += \
        lambda stats: persist_digaas_data(stats, digaas_client)
