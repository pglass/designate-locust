from locust import HttpLocust
from locust import TaskSet
from locust import task

import time
import gevent
from gevent.socket import socket


def start_worker():
    sock = socket()
    sock.connect(('localhost', 8001))

    while True:
        sock.sendall('jerry, HELLO!')
        gevent.sleep(0.5)

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
