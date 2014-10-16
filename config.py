import json
import os


class InvalidConfig(Exception):
    pass


class JsonConfig(object):

    REDIS_HOST_KEY = 'redis_host'
    REDIS_PORT_KEY = 'redis_port'
    REDIS_PASSWORD_KEY = 'redis_password'
    DESIGNATE_HOST_KEY = 'designate_host'
    NUMBER_TENANTS_KEY = 'n_tenants'
    MIN_WAIT_KEY = 'min_wait'
    MAX_WAIT_KEY = 'max_wait'
    GRAPHITE_HOST = 'graphite_host'
    GRAPHITE_PORT = 'graphite_port'

    def __init__(self, json_data):
        self.json = json_data

    @classmethod
    def from_file(cls, filename):
        with open(filename, 'r') as f:
            try:
                return JsonConfig(json_data=json.load(f))
            except ValueError as error:
                raise InvalidConfig(
                    "JSON file '{0}' is invalid:\n{1}".format(filename, error))

    def get(self, key):
        return self.json.get(key)


class EnvironmentConfig(object):

    REDIS_HOST_KEY = 'LOCUST_REDIS_HOST'
    REDIS_PORT_KEY = 'LOCUST_REDIS_PORT'
    REDIS_PASSWORD_KEY = 'LOCUST_REDIS_PASSWORD'
    DESIGNATE_HOST_KEY = 'LOCUST_DESIGNATE_HOST'
    NUMBER_TENANTS_KEY = 'LOCUST_N_TENANTS'
    MIN_WAIT_KEY = 'LOCUST_MIN_WAIT'
    MAX_WAIT_KEY = 'LOCUST_MAX_WAIT'
    GRAPHITE_HOST = 'LOCUST_GRAPHITE_HOST'
    GRAPHITE_PORT = 'LOCUST_GRAPHITE_PORT'

    def get(self, key):
        return os.environ.get(key)


class Config(object):
    """Look for configs in a json file, with environment variable overrides.
    Usage, with a json file:
        config = Config(json_file='config.json')
        print config.redis_host
        print config.redis_port
        print config.redis_password
        print config.designate_host
    """

    def __init__(self, json_file=None):
        self.env_config = EnvironmentConfig()
        if json_file:
            try:
                self.json_config = JsonConfig.from_file(json_file)
            except IOError as e:
                print ("Warning: json config '{0}' not found. "
                       "Looking for configs in environment variables.")
                self.json_config = JsonConfig(json_data={})
        else:
            self.json_config = JsonConfig(json_data={})

    def _get(self, env_key, json_key, warning_msg=None):
        result = (self.env_config.get(env_key) or self.json_config.get(json_key))
        if result == None and warning_msg:
            print "Warning: {0}".format(warning_msg)
        return result

    def _get_required(self, env_key, json_key):
        val = self._get(env_key, json_key)
        if val == None:
            raise InvalidConfig(
                "Need environment variable '{0}' or json key '{1}'"
                .format(env_key, json_key))
        return val

    @property
    def redis_host(self):
        return self._get_required(self.env_config.REDIS_HOST_KEY,
                                  self.json_config.REDIS_HOST_KEY)

    @property
    def redis_port(self):
        return self._get_required(self.env_config.REDIS_PORT_KEY,
                                  self.json_config.REDIS_PORT_KEY)

    @property
    def redis_password(self):
        result = self._get(self.env_config.REDIS_PASSWORD_KEY,
                           self.json_config.REDIS_PASSWORD_KEY,
                           warning_msg="Redis password not found")
        return result

    @property
    def designate_host(self):
        return self._get_required(self.env_config.DESIGNATE_HOST_KEY,
                                  self.json_config.DESIGNATE_HOST_KEY)

    @property
    def n_tenants(self):
        return self._get(self.env_config.NUMBER_TENANTS_KEY,
                         self.json_config.NUMBER_TENANTS_KEY,
                         warning_msg="Number of tenants not specified")

    @property
    def min_wait(self):
        result = self._get(self.env_config.MIN_WAIT_KEY,
                         self.json_config.MIN_WAIT_KEY)
        if result is not None:
            print "Found min_wait time {0}".format(result)
        return result

    @property
    def max_wait(self):
        result = self._get(self.env_config.MAX_WAIT_KEY,
                           self.json_config.MAX_WAIT_KEY)
        if result is not None:
            print "Found max_wait time {0}".format(result)
        return result

    @property
    def graphite_host(self):
        return self._get(self.env_config.GRAPHITE_HOST,
                         self.json_config.GRAPHITE_HOST)

    @property
    def graphite_port(self):
        return self._get(self.env_config.GRAPHITE_PORT,
                         self.json_config.GRAPHITE_PORT)

if __name__ == '__main__':
    x = Config(json_file='config.json')
    print x.redis_host
    print x.redis_port
    print x.redis_password
    print x.designate_host
