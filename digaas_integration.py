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

import locust
import requests
import json
import os
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
                          condition, timeout, frequency):
        url = self.endpoint + '/poll_requests'
        payload = json.dumps(dict(
            nameserver = nameserver,
            query_name = query_name,
            serial = serial,
            start_time = start_time,
            condition = condition,
            timeout = timeout,
            frequency = frequency,
        ))
        return requests.post(url, data=payload, headers=self.JSON_HEADERS)

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
