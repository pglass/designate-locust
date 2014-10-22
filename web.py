import os
import json
import string
import random

from locust import web
import locust.stats
import flask
from flask.ext.httpauth import HTTPDigestAuth

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
