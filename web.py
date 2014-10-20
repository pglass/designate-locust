import os
from locust import web
import locust.stats
import json
import flask

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
