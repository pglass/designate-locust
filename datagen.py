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
    return None

def random_zone_file(name='random_import', user='rando'):
    name = randomize(randomize(name))
    zone = "{0}.com.".format(name)
    email = "{0}.{1}".format(user, zone)

    result = ""
    result += "$ORIGIN %s\n" % zone
    result += "\n"
    result += "@ IN SOA ns.{0} {1} 100 101 102 103 104\n".format(zone, email)
    result += "@ IN NS ns.%s\n" % zone
    result += "ns.%s IN A %s\n" % (zone, random_ip())
    result += "mail.%s IN A %s\n" % (zone, random_ip())
    return result
