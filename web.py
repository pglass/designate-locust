import os
import json
import string
import random
from datetime import datetime

from locust import web
import locust.stats
import flask
from flask import request
from flask.ext.httpauth import HTTPDigestAuth

import persistence


"""
I need a way to retrofit Flask view/routing functions in locust.web to require
authentication with HTTP digest auth. There are easy ways to do this with HTTP
basic auth, but seemingly not with HTTP digest auth (which at least does not
expose your password in plaintext like basic auth).

This works in the same way the flask-basicauth extension works.
"""
def setup_authentication(authorized_username, authorized_password):
    if not all((authorized_username, authorized_password)):
        # inform the user which parts we're missing
        print ('WARNING: no authentication setup -- (username, password) = {0}'
               .format(map(bool, (authorized_username, authorized_password))))
        return
    print "Setting up authentication..."

    # Flask docs:
    #  If you have the Flask.secret_key set you can use sessions in Flask
    #  applications. A session basically makes it possible to remember
    #  information from one request to another. The way Flask does this is by
    #  using a signed cookie. So the user can look at the session contents, but
    #  not modify it unless they know the secret key, so make sure to set that
    #  to something complex and unguessable.
    #
    # Here we generate a random string of length 256. Since we regenerate the
    # secret key each time locust is started, the user will need to
    # re-authenticate whenever locust is restarted.
    web.app.config['SECRET_KEY'] = ''.join(
        random.choice(string.ascii_letters + string.digits) for _ in xrange(256))
    digest_auth = HTTPDigestAuth()

    # specify the available usernames and passwords
    @digest_auth.get_password
    def _get_pw(username):
        if username == authorized_username:
            return authorized_password

    # require username/password auth before accessing any page.
    # browsers are smart enough to only prompt the user once.
    # use incognito mode to check that this is working.
    @web.app.before_request
    @digest_auth.login_required
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

@web.app.route('/plots/line.svg')
def line_plot():
    return flask.send_from_directory(module_dir, 'line.svg')

@web.app.route('/plots/box.svg')
def box_plot():
    return flask.send_from_directory(module_dir, 'box.svg')

@web.app.route('/plots/scatter.svg')
def scatter_plot():
    return flask.send_from_directory(module_dir, 'scatter.svg')

@web.app.route('/plots/scatter.png')
def scatter_png():
    return flask.send_from_directory(module_dir, 'scatter.png')

@web.app.route('/reports')
def reports():
    """Return a page with a listing of reports."""
    stats_files = persistence.list_stats_files()
    if not stats_files:
        return "No reports found"

    def extract_timestamp(filename):
        head, tail = os.path.split(filename.strip('/'))
        return int(tail.strip('stats').strip('.json')), tail

    time_pairs = [(datetime.fromtimestamp(x), x, filename)
                  for x, filename in map(extract_timestamp, stats_files)]
    time_pairs.sort(key=lambda t: -t[1])
    return flask.render_template('reports_index.html', time_pairs=time_pairs)

@web.app.route('/images/<name>')
def image(name):
    print module_dir
    print name
    return flask.send_from_directory(module_dir, name)

@web.app.route('/reports/<name>')
def report(name):
    """Return a summary page for a particular run."""
    stats_file = os.path.abspath("{0}/{1}".format(
        persistence.stats_dir, name if name.endswith('.json') else name + '.json'))
    if not os.path.exists(stats_file):
        return flask.abort(404)

    stats = json.loads(open(stats_file, 'r').read())
    if name.endswith('.json'):
        return flask.send_file(stats_file, mimetype='application/json')

    # compute some things that are easier to do here than in a jinja template
    start_datetime = datetime.fromtimestamp(stats['start_time'])
    duration = (datetime.fromtimestamp(round(stats['last_request_timestamp']))
                - datetime.fromtimestamp(round(stats['start_time'])))
    info = {
        "start_datetime": start_datetime,
        "duration": duration
    }
    return flask.render_template('report.html', stats=stats, info=info,
            propagation_plot='/../images/timmayy.jpg')
