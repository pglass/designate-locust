from locust import HttpLocust, TaskSet, task
import locust.events
from faker import Factory
import json
import pprint
import datetime
import random
import redis

def get_timestamp():
    return str(datetime.datetime.now())

def randomize(string):
    return "{0}{1}".format(string, random.randint(1000000000, 9999999999))

def randomize_domain(name):
    parts = name.rsplit('.', 2)
    parts[0] = randomize(parts[0])
    return ".".join(parts)


class RedisBuffer(list):

    CREATE = 1
    UPDATE = 2
    CREATE_RECORDSETS = 3

    def flush(self, client):
        """Write everything stored in this buffer to redis."""
        while self:
            item = self.pop()
            if not self._store_item(item, client):
                print "Failed to store:", item

    def _store_item(self, item, client):
        """Need to store the zone_name, zone_id, and serial number"""
        print "Store: ", item
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
        elif type == self.CREATE_RECORDSETS:
            value = response_json_rec['created_at']
        else:
            print "ERORORORR"
            return False
        return client.set(key, value)


class MyTaskSet(TaskSet):

    def __init__(self, *args, **kwargs):
        super(MyTaskSet, self).__init__(*args, **kwargs)
        self.buffer = RedisBuffer()
        self.fake = Factory.create()
        locust.events.quitting += lambda: self.on_quit()

    #@task
    #def index(self):
    #    response = self.client.get("/zones")
    #    print "Response status code:", response.status_code
    #    #  print "Response content:", response.content
    #    serialized_str = response.content
    #    response_json = json.loads(serialized_str)
    #    resp = response_json.get('zones')
    #    # pprint.pprint(resp)
    #    name  = resp[0]['name']
    #    serial = resp[0]['serial']
    #    id = resp[0]['id']
    #    created_at =resp[0]['created_at']

    #    print id
    #    print serial
    #    print created_at
    #    print name
    #    '''
    #    name = response_json.get('zones').get(name)
    #    id = response_json.get('zones').get(id)
    #    created = response_json.get('zones').get(created_at)
    #    '''

    @task
    def zone_post(self):
        name = randomize(self.fake.first_name())
        zone = "{0}.com.".format(name)
        email = self.fake.email()

        payload = {"zone": { "name": zone,
                             "email": email,
                             "ttl": 7200} }
        headers = {"content-type": "application/json"}

        timestamp = get_timestamp()
        print payload
        response = self.client.post("/zones", data=json.dumps(payload), headers=headers)
        print response.content
        if response.status_code == 201:
            self.buffer.append((self.buffer.CREATE, response))

    @task
    def zone_patch(self):
        if not self.buffer:
            return

        i = random.randrange(0, len(self.buffer))
        _, response = self.buffer[i]

        response_json = response.json().get('zone')
        print "response_json", response_json
        zone_id = response_json['id']
        payload = {"zone": { "ttl": 3600 } }
        headers = {"content-type": "application/json"}

        url = "/zones/{0}".format(zone_id)
        update_resp = self.client.patch(url, data=json.dumps(payload), headers=headers)
        if update_resp.status_code == 200:
            self.buffer.append((self.buffer.UPDATE, update_resp))
       
    @task
    def recordset_create(self):
        if not self.buffer:
            return

        i = random.randrange(0, len(self.buffer))
        _, response = self.buffer[i]

        response_json = response.json().get('zone')
        print "response_json", response_json
        zone_id = response_json['id']
        zone_name = response_json['name']
        rec_ip = ".".join(map(str, (random.randint(0, 255) 
                        for _ in range(4))))
        payload ={"recordset" : {"name" : zone_name,
                                 "type" : "A",
                                 "ttl" : 3600,
                                 "records" : [ 
                                  rec_ip ] }
                                }

        headers = {"content-type": "application/json"}

        url = "/zones/{0}/recordsets".format(zone_id)
        recordset_resp = self.client.post(url, data=json.dumps(payload), headers=headers)
        if response.status_code == 201:
            self.buffer.append((self.buffer.CREATE_RECORDSETS, recordset_resp))
    
            
    def on_quit(self):
        print "on_quit: Flushing buffer"
        client = redis.StrictRedis(host='localhost', port=6379)
        self.buffer.flush(client)


class MyLocust(HttpLocust):
  task_set = MyTaskSet
  # in milliseconds
  min_wait = 100
  max_wait = 1000
  # defines the server running the web ui
  host="http://23.253.149.85/v2"
