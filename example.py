from locust import HttpLocust, TaskSet, task
from faker import Factory
import json
import pprint


class MyTaskSet(TaskSet):

    @task
    def index(self):
        response = self.client.get("/zones")
        print "Response status code:", response.status_code
        #  print "Response content:", response.content
        serialized_str = response.content
        response_json = json.loads(serialized_str)
        resp = response_json.get('zones')
        # pprint.pprint(resp)
        name  = resp[0]['name']
        serial = resp[0]['serial']
        id = resp[0]['id']
        created_at =resp[0]['created_at']

        print id
        print serial
        print created_at
        print name
        '''
        name = response_json.get('zones').get(name)
        id = response_json.get('zones').get(id)
        created = response_json.get('zones').get(created_at)
        '''

    @task
    def zone_post(self):
        fake = Factory.create()
        zone = fake.first_name()
        email_add = fake.email().strip('.')
        zone_name= zone + "%s" % (".com.")

        # thread-safe?
        # self.zones.add(zone_name)
        # or
        # redis.add(zone, timestamp)

        print zone_name
        print zone,email_add
        payload = {"zone": { "name": "%s" % zone_name,
                             "email": ("joe@%s" % zone_name).strip('.'),
                             "ttl": 7200} }
        headers = {"content-type": "application/json"}
        response = self.client.post("/zones", data=json.dumps(payload), headers=headers)
        print "Response status code:", response.status_code
        print "Response content:", response.content
        serialized_str = response.content

    @task
    def zone_update(self):
        self.client.patch("/zones/{0}".format(




class MyLocust(HttpLocust):
  task_set = MyTaskSet
  # in milliseconds
  min_wait = 100
  max_wait = 1000
  # defines the server running the web ui
  host="http://23.253.149.85/v2"
