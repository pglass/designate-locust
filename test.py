from locust import HttpLocust
from locust import TaskSet
from locust import task

import time
import gevent
from gevent.socket import socket

import sys

is_master = '--master' in sys.argv
is_slave = '--slave' in sys.argv
is_neither = not is_master and not is_slave

sock = None
def start_worker():
    global sock
    if sock is not None:
        sock.close()
    sock = socket()
    sock.connect(('localhost', 8001))
    while True:
        sock.sendall('jerry, HELLO!')
        gevent.sleep(1.0)

if is_master:
    g = gevent.spawn(start_worker)

class MyTaskSet(TaskSet):

    def __init__(self, *args, **kwargs):
        super(MyTaskSet, self).__init__(*args, **kwargs)

    @task
    def do_get(self):
        self.client.get('/')


class MyLocust(HttpLocust):
    task_set = MyTaskSet

    min_wait = 300
    max_wait = 500

    host = 'http://localhost:8000'
