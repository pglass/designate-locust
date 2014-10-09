from collections import OrderedDict, namedtuple
from datetime import datetime, timedelta
import random
import time

import pygal
import redis
import matplotlib
# avoid matplotlib defaulting to an X backend when do $DISPLAY is defined.
# this backend change must occur prior to importing matplotlib.pyplot
matplotlib.use('Agg')
import matplotlib.pyplot as plot
import numpy as np

from config import Config


DataPoint = namedtuple('DataPoint', ['type', 'zone', 'serial', 'timestamp'])

API = 1
BIND = 2

def get_api_data(r):
    """Return a list of DataPoints"""
    api_keys = r.keys(pattern='api*')
    results = {}
    for key in api_keys:
        val = r.get(key)
        apitime = datetime.strptime(val, "%Y-%m-%dT%H:%M:%S.%f")
        parts = key.split('-')
        datapoint = DataPoint(type=API,
                              zone=parts[1],
                              serial=int(parts[2]),
                              timestamp=apitime)
        if datapoint.serial in results:
            results[datapoint.serial].append(datapoint)
        else:
            results[datapoint.serial] = [datapoint]
    return results

def get_bind_data(r):
    """Return a list of DataPoints"""
    bind_keys = r.keys(pattern='bind*')
    results = {}
    for key in bind_keys:
        val = r.get(key)
        bindtime = datetime.strptime(val, "%d-%b-%Y %H:%M:%S.%f")
        parts = key.split('-')
        # normalize the trailing '.'
        parts[1] = parts[1].strip('.') + '.'
        datapoint = DataPoint(type=BIND,
                              zone=parts[1],
                              serial=int(parts[2]),
                              timestamp=bindtime)
        if datapoint.serial in results:
            results[datapoint.serial].append(datapoint)
        else:
            results[datapoint.serial] = [datapoint]
    return results

def compute_times(api_data, bind_data):
    """Return a list of tuples (serial, time)"""
    def compute_time(api_datapoint, bind_datapoint):
        return (bind_datapoint.timestamp - api_datapoint.timestamp).total_seconds()
    # use an OrderedDict to ensure things are sorted by serial
    serials = sorted(api_data.keys())
    times = []

    for serial in serials:
        api_datapoints = api_data[serial]
        bind_datapoints = bind_data.get(serial) or []
        # we have list of changes with the same serial, so differentiate
        # between them using the zone name
        for api_datapoint in api_data[serial]:
            for bind_datapoint in bind_datapoints:
                if bind_datapoint.zone == api_datapoint.zone:
                    timediff = compute_time(api_datapoint, bind_datapoint) \
                               if bind_datapoint else float('+inf'),
                    times.append((api_datapoint, bind_datapoint, timediff))
    return times

def make_scatter_plot(xs, ys, filename):
    x = np.array(xs)
    y = np.array(ys)

    # plot the data
    plot.scatter(x, y)

    # adjust tick labels
    tickvals, _ = plot.xticks()
    ticklabels = map(lambda x: str(int(x)), tickvals)
    plot.xticks(tickvals, ticklabels, rotation='vertical')

    # make room for new tick labels
    plot.subplots_adjust(bottom=0.5)

    plot.savefig(filename)

def analyze(r):
    """Generate plots using matplotlib."""
    api_data = get_api_data(r)
    bind_data = get_bind_data(r)
    times = compute_times(api_data, bind_data)

    make_scatter_plot([a.serial for a, b, v in times],
                      [v for _, _, v in times],
                      'scatter.png')

def pygal_analyze(r):
    """Grab data from redis and compute some statistics.
    :param r: A Redis client
    """
    api = r.keys(pattern='api*')
    api = sorted(api, key= lambda k: k.split('-')[2])
    #times = {}
    times = OrderedDict()
    for key in api:
        apitime = datetime.strptime(r.get(key), "%Y-%m-%dT%H:%M:%S.%f")
        key = key.replace('.com.','.com')
        key = key.replace('api','bind')
        if r.get(key) is not None:
            bindtime = datetime.strptime(r.get(key), "%d-%b-%Y %H:%M:%S.%f")
            times[key.split('bind-')[1]] = abs((bindtime-apitime).total_seconds())

    avg_time = sum(times.values()) / len(times)
    # print "Average Time: %s seconds" % str(avg_time)

    chart = pygal.Box()
    chart.title = "Time from API to Bind9. Average = " + str(avg_time)
    chart.title += " ({0})".format(datetime.now())
    chart.add('Time', times.values())
    chart.render_to_file('box.svg')

    chart = pygal.Line()
    chart.title = "Time from API to Bind9. Average = " + str(avg_time)
    chart.title += " ({0})".format(datetime.now())
    chart.x_labels = map(str, range(len(times)))
    chart.add('Time', times.values())
    chart.render_to_file('line.svg')

    chart = pygal.XY(stroke=False)
    chart.title = "Time from API to Bind9. Average = " + str(avg_time)
    chart.title += " ({0})".format(datetime.now())
    chart.add('Time', zip(xrange(len(times)), times.values()))
    chart.render_to_file('scatter.svg')

SERIALS = [1412869563399719, 1412869563399720, 1412869563399721,
           1412869563399722, 1412869563399723, 1412869563399724,
           1412869563399725, 1412869563399726, 1412869563399727,
           1412869563399728, 1412869563399729, 1412869563399730,
           1412869563399731, 1412869563399732, 1412869563399733,
           1412869563399734, 1412869563399735, 1412869563399736,
           1412869563399737, 1412869563399738, 1412869563399739,
           1412869563399740, 1412869563399741, 1412869563399742,
           1412869563399743, 1412869563399744, 1412869563399745,
           1412869563399746, 1412869563399747, 1412869563399748,
           1412869563399749, 1412869563399750, 1412869563399751,
           1412869563399752, 1412869563399753, 1412869563399754,
           1412869563399755, 1412869563399756, 1412869563399757,
           1412869563399758, 1412869563399759, 1412869563399760,
           1412869563399761, 1412869563399762, 1412869563399763,
           1412869563399764, 1412869563399765, 1412869563399766,
           1412869563399767, 1412869563399768]

def gen_test_data(r, amount=50):
    # we want to have some duplicate serial numbers for different zones
    """Generate some data for testing the analyze function."""
    print "generating {0} entries".format(amount)
    api_format_str = "api-{0}-{1}"
    bind_format_str = "bind-{0}-{1}"

    for i in xrange(amount):
        serial = random.choice(SERIALS)
        zone_name = "zone{0}".format(i)
        api_key = api_format_str.format(zone_name + '.com.', serial)
        bind_key = bind_format_str.format(zone_name + '.com', serial)

        api_val = datetime.now()
        bind_val = api_val + timedelta(0, random.randrange(10, 200))

        #print api_key, api_val
        #print bind_key, bind_val
        #print
        r.set(api_key, api_val.strftime('%Y-%m-%dT%H:%M:%S.%f'))
        r.set(bind_key, bind_val.strftime('%d-%b-%Y %H:%M:%S.%f'))

if __name__ == '__main__':
    config = Config(json_file='config.json')
    r = redis.StrictRedis(
        host=config.redis_host,
        port=config.redis_port,
        password=config.redis_password)
    #r.flushall()
    #gen_test_data(r, 100)
    #api_data = get_api_data(r)
    #bind_data = get_bind_data(r)
    #times = compute_times(api_data, bind_data)
    #for a, b, v in times:
    #    print "----", v
    #    print "  ", a
    #    print "  ", b

    r.ping()
    print 'matplotlib analyze...'
    analyze(r)

    print 'pygal analyze...'
    pygal_analyze(r)
