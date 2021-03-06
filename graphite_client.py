import sys
import logging

import locust
import gevent
from gevent.socket import socket
from gevent.queue import Queue

import insight

LOG = logging.getLogger(__name__)

graphite_queue = Queue()

def _escape_metric_name(name):
    """Graphite does not allow spaces or slashes"""
    return name.replace(' ', '_').replace('/', '-')

def graphite_worker(host, port):
    """The worker pops each item off the queue and sends it to graphite."""
    sock = socket()
    try:
        sock.connect((host, port))
    except Exception as e:
        LOG.error("Failed to connect to Graphite at {0}:{1}".format(host, port))
        LOG.error("{0}".format(e))
        return

    LOG.info("Connected to graphite at {0}:{1}".format(host, port))

    while True:
        data = graphite_queue.get()
        # print "graphite_worker: got data {0!r}".format(data)
        sock.sendall(data)

def _get_requests_per_second_graphite_message(stat, client_id):
    request = stat['method'] + stat['name'].replace('/', '-')

    graphite_key = "locust.{0}.reqs_per_sec.{1}".format(request, client_id)
    graphite_data = "".join(
        "{0} {1} {2}\n".format(graphite_key, count, epoch_time)
        for epoch_time, count in stat['num_reqs_per_sec'].iteritems())
    return graphite_data

def _get_response_time_graphite_message(stat, client_id):
    request = stat['method'] + stat['name'].replace('/', '-')
    request = _escape_metric_name(request)

    graphite_key = "locust.{0}.response_time.{1}".format(request, client_id)
    epoch_time = int(stat['start_time'])

    # flatten a dictionary of {time: count} to [time, time, time, ...]
    response_times = []
    for t, count in stat['response_times'].iteritems():
        for _ in xrange(count):
            response_times.append(t)

    graphite_data = "".join(
        "{0} {1} {2}\n".format(graphite_key, response_time, epoch_time)
        for response_time in response_times)
    return graphite_data

def graphite_producer(client_id, data):
    """This takes a Locust client_id and some data, as given to
    locust.event.slave_report handlers."""
    #print "Got data: ", data, 'from client', client_id
    for stat in data['stats']:
        graphite_data = (
            _get_response_time_graphite_message(stat, client_id)
            + _get_requests_per_second_graphite_message(stat, client_id))
        graphite_queue.put(graphite_data)

def setup_graphite_communication(graphite_host, graphite_port):
    # only the master sends data to graphite
    if not insight.is_slave():
        gevent.spawn(graphite_worker, graphite_host, graphite_port)
        locust.events.slave_report += graphite_producer
