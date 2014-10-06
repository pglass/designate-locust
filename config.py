import os


class RedisConfig(object):
    """Gets Redis server information from environment variables.
    Usage:
        redis_config = RedisConfig()  # possible exception
        print redis_config.host
        print redis_config.port
        print redis_config.password   # None if not found
    """

    REDIS_HOST_KEY = 'LOCUST_REDIS_HOST'
    REDIS_PORT_KEY = 'LOCUST_REDIS_PORT'
    REDIS_PASSWORD_KEY = 'LOCUST_REDIS_PASSWORD'

    def __init__(self):
        """Raises an exception on missing host or missing port"""
        self.host, self.port, self.password = self.get_redis_config()
        self.port = int(self.port)

    @classmethod
    def get_redis_config(cls):
        """Returns (host, port, password). Raises an exception if missing
        either host or port. Returns None for the password if absent."""
        if (cls.REDIS_HOST_KEY not in os.environ
            or cls.REDIS_PORT_KEY not in os.environ):
            raise Exception(
                "I will not proceed without environment vars '{0}' and '{1}'"
                .format(cls.REDIS_HOST_KEY, cls.REDIS_PORT_KEY))

        if cls.REDIS_PASSWORD_KEY not in os.environ:
            print("Warning: environment var '{0}' not found. Not using redis "
                  "password.".format(cls.REDIS_PASSWORD_KEY))
        else:
            print "Found Redis password"

        return (os.environ[cls.REDIS_HOST_KEY],
                os.environ[cls.REDIS_PORT_KEY],
                os.environ.get(cls.REDIS_PASSWORD_KEY))
