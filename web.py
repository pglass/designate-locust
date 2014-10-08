import os
from locust import web
import flask

module_dir = os.path.dirname(__file__)

@web.app.route('/plots/line')
def line_plot():
    return flask.send_from_directory(module_dir, 'line.svg')

@web.app.route('/plots/box')
def box_plot():
    return flask.send_from_directory(module_dir, 'box.svg')

@web.app.route('/plots/scatter')
def scatter_plot():
    return flask.send_from_directory(module_dir, 'scatter.svg')
