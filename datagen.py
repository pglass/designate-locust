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


