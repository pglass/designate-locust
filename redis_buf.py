

class RedisBuffer(list):
    """A buffer for data written to Redis. The buffer is flushed whenever
    the length of this list reaches the max_size (note that will only work if
    you use the append() method)"""

    CREATE = 1
    UPDATE = 2

    def __init__(self, client, max_size=1000):
        self.client = client
        self.max_size = max_size

    def append(self, item):
        super(RedisBuffer, self).append(item)
        if len(self) >= self.max_size:
            self.flush()

    def flush(self):
        """Write everything stored in this buffer to redis."""
        print "Flushing buffer -- {0} items to redis".format(len(self))
        while self:
            item = self.pop()
            if not self._store_item(item):
                print "Failed to store: ", item[0], item[1].json()

    def _store_item(self, item):
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
        return self.client.set(key, value)



