from datetime import datetime
import redis
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plot
# import pygal
from collections import OrderedDict
from config import RedisConfig
from collections import namedtuple

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
        results[datapoint.serial] = datapoint
    return results

def get_bind_data(r):
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
        results[datapoint.serial] = datapoint
    return results

def compute_times(api_data, bind_data):
    def compute_time(api_datapoint, bind_datapoint):
        return (bind_datapoint.timestamp - api_datapoint.timestamp).total_seconds()
    # use an OrderedDict to ensure things are sorted by serial
    serials = sorted(api_data.keys())
    times = OrderedDict()

    for serial in serials:
        api_datapoint = api_data[serial]
        bind_datapoint = bind_data.get(serial)
        times[serial] = [
            # add whatever times you want here
            compute_time(api_datapoint, bind_datapoint)
                if bind_datapoint else float('+inf'),
        ]
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
    api_data = get_api_data(r)
    bind_data = get_bind_data(r)
    times = compute_times(api_data, bind_data)
    make_scatter_plot(times.keys(), times.values(), 'scatter.png')

#def pygal_analyze(r):
#    """Grab data from redis and compute some statistics.
#    :param r: A Redis client
#    """
#    api = r.keys(pattern='api*')
#    api = sorted(api, key= lambda k: k.split('-')[2])
#    #times = {}
#    times = OrderedDict()
#    for key in api:
#        apitime = datetime.strptime(r.get(key), "%Y-%m-%dT%H:%M:%S.%f")
#        key = key.replace('.com.','.com')
#        key = key.replace('api','bind')
#        if r.get(key) is not None:
#            bindtime = datetime.strptime(r.get(key), "%d-%b-%Y %H:%M:%S.%f")
#            times[key.split('bind-')[1]] = abs((bindtime-apitime).total_seconds())
#
#    avg_time = sum(times.values()) / len(times)
#    # print "Average Time: %s seconds" % str(avg_time)
#
#    chart = pygal.Box()
#    chart.title = "Time from API to Bind9. Average = " + str(avg_time)
#    chart.title += " ({0})".format(datetime.now())
#    chart.add('Time', times.values())
#    chart.render_to_file('box.svg')
#
#    #chart = pygal.Line()
#    #chart.title = "Time from API to Bind9. Average = " + str(avg_time)
#    #chart.title += " ({0})".format(datetime.now())
#    #chart.x_labels = map(str, range(len(times)))
#    #chart.add('Time', times.values())
#    #chart.render_to_file('line.svg')
#
#    chart = pygal.XY(stroke=False)
#    chart.title = "Time from API to Bind9. Average = " + str(avg_time)
#    chart.title += " ({0})".format(datetime.now())
#    chart.add('Time', zip(xrange(len(times)), times.values()))
#    chart.render_to_file('scatter.svg')

def gen_test_data(r, amount=50):
    """Generate some data for testing the analyze function."""
    import random
    import time
    from datetime import timedelta
    print "generating {0} entries".format(amount)
    api_format_str = "api-{0}-{1}"
    bind_format_str = "bind-{0}-{1}"

    for i in xrange(amount):
        serial = int(time.time() * 1000000)
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
    config = RedisConfig()
    r = redis.StrictRedis(
        host=config.host,
        port=config.port,
        password=config.password)
    r.ping()
    analyze(r)
