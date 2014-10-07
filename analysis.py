from datetime import datetime
import pygal
import redis
from collections import OrderedDict


def analyze(r):
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

#    # bin the times
#    values = list(sorted(times.values()))
#    # must be an int
#    binsize = int( (values[-1] - values[0]) / (len(times) / 5))
#    # binsize = 20  # must be an int
#    bounds = range(int(values[0]), int(values[-1] + binsize + 1), binsize)
#    assert bounds[0] <= values[0] and values[-1] <= bounds[-1]
#    bin_ranges = zip(bounds[:-1], bounds[1:])
#    bins = {pair: [] for pair in bin_ranges}
#
#    i = 0
#    for x in values:
#        lo, hi = bin_ranges[i]
#        while not (lo <= x < hi):
#            i += 1
#            lo, hi = bin_ranges[i]
#        bins[bin_ranges[i]].append(x)
#    for k, v in bins.iteritems():
#        print k, v
#
#    chart = pygal.Bar()
#    chart.title = "Times"
#    chart.x_labels = ["{0}".format(pair[0]) for pair in bin_ranges]
#    vals = [len(bins[x]) for x in bin_ranges]
#    chart.add('Times', vals)
#    chart.render_to_file('bar.svg')



def gen_test_data(r, amount=50):
    """Generate some data for testing the analyze function."""
    import random
    from datetime import timedelta
    print "generating {0} entries".format(amount)
    api_format_str = "api-{0}-{1}"
    bind_format_str = "bind-{0}-{1}"

    for i in xrange(amount):
        serial = i + 10
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
    r = redis.StrictRedis(host='localhost', port=6379)
    r.ping()
    r.flushall()
    gen_test_data(r, amount=100)
    analyze(r)
