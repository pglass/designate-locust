import os
import json
import string
import random
import datetime

from locust import web
import locust.runners
import locust.stats
import flask
from flask import request
from flask.ext.httpauth import HTTPBasicAuth

import persistence

def setup_authentication(authorized_username, authorized_password):
    if not all((authorized_username, authorized_password)):
        # inform the user which parts we're missing
        print ('WARNING: no authentication setup -- (username, password) = {0}'
               .format(map(bool, (authorized_username, authorized_password))))
        return
    print "Setting up authentication..."

    auth = HTTPBasicAuth()

    # specify the available usernames and passwords
    @auth.get_password
    def _get_pw(username):
        if username == authorized_username:
            return authorized_password

    # require username/password auth before accessing any page.
    # browsers are smart enough to only prompt the user once.
    # use incognito mode to check that this is working.
    @web.app.before_request
    @auth.login_required
    def require_digest_auth():
        pass

module_dir = os.path.dirname(__file__)
images_dir = os.path.join(module_dir, 'images')


# By default, jinja uses a directory somewhere in the Locust codebase
# when it looks for templates. This adds our local templates directory.
# Be careful about name overlaps with Locust's default template filenames.
import jinja2
web.app.jinja_loader = jinja2.ChoiceLoader([
    web.app.jinja_loader,
    jinja2.FileSystemLoader([module_dir.rstrip('/') + '/templates'])
])

def extract_timestamp(filename):
    head, tail = os.path.split(filename.strip('/'))
    return int(tail.strip('stats').strip('.json')), tail

@web.app.route('/reports')
def reports():
    """Return a page with a listing of reports."""
    stats_files = persistence.list_stats_files()
    if not stats_files:
        return "No reports found"
    time_pairs = [(datetime.datetime.fromtimestamp(x), x, filename)
                  for x, filename in map(extract_timestamp, stats_files)]
    time_pairs.sort(key=lambda t: -t[1])
    return flask.render_template('reports_index.html', time_pairs=time_pairs)

@web.app.route('/reports/json')
def reports_json():
    stats_files = persistence.list_stats_files()
    result = [{ "timestamp": stamp,
                "path": "/reports/{0}".format(filename) }
              for stamp, filename in (extract_timestamp(f) for f in stats_files)]
    result.sort(key=lambda item: -item['timestamp'])
    return flask.Response(json.dumps(result), mimetype='application/json')

@web.app.route('/images/<name>')
def image(name):
    d = os.path.join(module_dir, images_dir)
    return flask.send_from_directory(d, name)

@web.app.route('/reports/<name>')
def report(name):
    """Return a summary page for a particular run."""

    # the name is something like stats132486733[.json] which contains a dump of
    # data about a test run that we use to render a jinja template.
    stats_file = os.path.abspath("{0}/{1}".format(
        persistence.stats_dir, name if name.endswith('.json') else name + '.json'))
    if not os.path.exists(stats_file):
        return flask.abort(404)

    stats = json.loads(open(stats_file, 'r').read())
    if name.endswith('.json'):
        return flask.send_file(stats_file, mimetype='application/json')

    # compute some things here that I didn't know how to do in a jinja template
    start_datetime = datetime.datetime.fromtimestamp(stats['start_time'])
    end_datetime = datetime.datetime.fromtimestamp(round(stats['last_request_timestamp']))
    duration = (end_datetime - datetime.datetime.fromtimestamp(round(stats['start_time'])))
    timeinfo = {
        "start_datetime": start_datetime,
        "end_datetime": end_datetime,
        "duration": duration
    }
    propagation_plot = stats['digaas'].get('plot_file') if 'digaas' in stats else None
    return flask.render_template('report.html', stats=stats, timeinfo=timeinfo,
            propagation_plot=propagation_plot)

@web.app.route('/status')
def status():
    result = {"status": locust.runners.locust_runner.state}
    return flask.Response(json.dumps(result), mimetype='application/json')
