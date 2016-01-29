import random

def randomize(string):
    return "{0}{1}".format(string, random.randint(1000000000, 9999999999))

def random_ip():
    return ".".join(str(random.randint(0, 255)) for _ in range(4))

def random_zone_email(name='random_zone', user='rando'):
    name = randomize(randomize(name))
    zone = "{0}.com.".format(name)
    email = "{0}@{1}".format(user, zone).strip('.')
    return zone, email

def select_random_item(vals):
    """Return a random item in this list, or None if empty."""
    if vals:
        return random.choice(vals)

def pop_random_item(vals):
    """Remove and return a random item from the list, or None"""
    if vals:
        i = random.randrange(0, len(vals))
        return vals.pop(i)

def random_zone_file(name='random_import', user='rando'):
    """Returns a RandomZoneFile"""
    return RandomZoneFile(name=name, user=user)

class RandomZoneFile(object):

    def __init__(self, name='random_import', user='rando'):
        name = randomize(randomize(name))
        self.zone_name = "{0}.com.".format(name)
        self.email = "{0}.{1}".format(user, self.zone_name)

    def __str__(self):
        result = ""
        result += "$ORIGIN %s\n" % self.zone_name
        result += "$TTL 300\n"
        result += "\n"
        result += "@ IN SOA ns.{0} {1} 100 101 102 103 104\n".format(self.zone_name, self.email)
        result += "@ IN NS ns.%s\n" % self.zone_name
        result += "ns.%s IN A %s\n" % (self.zone_name, random_ip())
        result += "mail.%s IN A %s\n" % (self.zone_name, random_ip())
        return result

    def get_zone_file_text(self):
        return str(self)
