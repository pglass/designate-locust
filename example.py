from locust import HttpLocust
from locust import TaskSet
from locust import task
from locust import web
import locust.events
from faker import Factory
import json
import datetime
import random
import os
import redis

from client import DesignateClient
from config import RedisConfig
import analysis

@web.app.route('/plots/line')
def line_plot():
    filename = 'line.svg'
    if os.path.exists(filename):
        return open(filename, 'r').read()
    return "No line plot found"

@web.app.route('/plots/box')
def box_plot():
    filename = 'box.svg'
    if os.path.exists(filename):
        return open(filename, 'r').read()
    return "No plots found"

def get_timestamp():
    return str(datetime.datetime.now())

def randomize(string):
    return "{0}{1}".format(string, random.randint(1000000000, 9999999999))

def randomize_domain(name):
    parts = name.rsplit('.', 2)
    parts[0] = randomize(parts[0])
    return ".".join(parts)

def random_ip():
    return ".".join(str(random.randint(0, 255)) for _ in range(4))


class RedisBuffer(list):

    CREATE = 1
    UPDATE = 2

    def flush(self, client):
        """Write everything stored in this buffer to redis."""
        while self:
            item = self.pop()
            if not self._store_item(item, client):
                print "Failed to store: ", item[0], item[1].json()

    def _store_item(self, item, client):
        """Store a key-value pair in redis where the key contains the
        zone name and serial number, and the value is the timestamp of the
        create or update corresponding to that serial."""
        # print "Store: ", item[0], item[1].json()
        type, response = item

        response_json = response.json().get('zone')
        zone_name = response_json['name']
        serial = response_json['serial']
        response_json_rec = response.json().get('recordset')

        key = "api-{0}-{1}".format(zone_name, serial)
        if type == self.CREATE:
            value = response_json['created_at']
        elif type == self.UPDATE:
            value = response_json['updated_at']
        else:
            print "ERORORORR"
            return False
        return client.set(key, value)

    def get_random_item(self):
        """Return a random item in this list, or None if empty."""
        if not self:
            return None
        i = random.randrange(0, len(self))
        return self[i]


class MyTaskSet(TaskSet):

    def __init__(self, *args, **kwargs):
        super(MyTaskSet, self).__init__(*args, **kwargs)
        self.designate_client = DesignateClient(self.client)
        self.buffer = RedisBuffer()
        self.fake = Factory.create()
        # initialize redis client
        self.redis_config = RedisConfig()
        self.redis_client = redis.StrictRedis(
            host=self.redis_config.host,
            port=self.redis_config.port,
            password=self.redis_config.password,
            db=0)
        # ping redis to ensure the connection is good
        self.redis_client.ping()

        # ensure cleanup when the test is stopped
        locust.events.locust_stop_hatching += lambda: self.on_stop()
        # ensure cleanup on interrupts
        locust.events.quitting += lambda: self.on_stop()

    @task
    def zone_post(self):
        name = randomize(self.fake.first_name())
        zone = "{0}.com.".format(name)
        email = self.fake.email()

        payload = {"zone": { "name": zone,
                             "email": email,
                             "ttl": 7200} }
        # print payload
        response = self.designate_client.post_zone(data=json.dumps(payload),
                                                   name='/zones')
        # print response.content

        if response.status_code == 201:
            self.buffer.append((self.buffer.CREATE, response))

    @task
    def zone_patch(self):
        item = self.buffer.get_random_item()
        if item is None:
            return

        _, response = item

        response_json = response.json().get('zone')
        # print "response_json", response_json
        zone_id = response_json['id']
        payload = {"zone": { "ttl": 3600 } }

        update_resp = self.designate_client.patch_zone(
            zone_id, data=json.dumps(payload), name='/zone/zoneID')
        if update_resp.status_code == 200:
            self.buffer.append((self.buffer.UPDATE, update_resp))

    @task
    def recordset_create(self):
        item = self.buffer.get_random_item()
        if item is None:
            return

        _, response = item

        response_json = response.json().get('zone')
        # print "response_json", response_json
        zone_id = response_json['id']
        zone_name = response_json['name']

        a_record_name = "{0}.{1}".format(randomize("www"), zone_name)
        payload = {"recordset" : {"name" : a_record_name,
                                  "type" : "A",
                                  "ttl" : 3600,
                                  "records" : [ random_ip() ] }}

        recordset_resp = self.designate_client.post_recordset(
            zone_id, data=json.dumps(payload), name='/zones/zoneID/recordsets')

        # store the updated zone's response which contains the updated serial
        if recordset_resp.status_code == 201:
            zone_resp = self.designate_client.get_zone(zone_id,
                                                       name='/zone/zoneID')
            if zone_resp.status_code == 200:
                # print "adding zone_resp:", zone_resp.json()
                self.buffer.append((self.buffer.UPDATE, zone_resp))

    def on_start(self):
        # assume a server already exists

        # ensure we won't reach quota limits
        self.designate_client.patch_quotas(tenant='noauth-project',
            data=json.dumps({ "quota": { "zones": 999999999,
                                         "recordset_records": 999999999,
                                         "zone_records": 999999999,
                                         "zone_recordsets": 999999999}}))

    def on_stop(self):
        # write all data to redis
        print "on_stop: Flushing buffer"
        self.buffer.flush(self.redis_client)
        print "on_stop: done flushing buffer"

    #    print "on_stop: Generating plots"
    #    analysis.analyze(self.redis_client)
    #    print "on_stop: done generating plots"


class MyLocust(HttpLocust):
    task_set = MyTaskSet
    # in milliseconds
    min_wait = 100
    max_wait = 1000
