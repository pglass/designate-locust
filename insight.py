import sys

def is_master():
    return '--master' in sys.argv

def is_slave():
    return '--slave' in sys.argv

def is_not_slave_or_master():
    return not is_master() or is_slave()
