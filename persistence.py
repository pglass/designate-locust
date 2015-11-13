"""
A module for saving statistics to disk when a test is stopped.
Does nothing unless setup_persistence() is called.
Set stats_dir to a directory to use, before calling setup_persistence
"""
import json
import logging
import os
import sys
import time

import locust.events
import locust.runners
import locust.stats

import insight

LOG = logging.getLogger(__name__)

def ensure_dir_exists(d):
    if not os.path.exists(d):
        os.mkdir(d)

module_dir = os.path.dirname(os.path.realpath(__file__))
stats_dir = os.path.join(module_dir, 'saved_stats')
persistence_dir = os.path.join(module_dir, 'persisted_files')
ensure_dir_exists(persistence_dir)
ensure_dir_exists(stats_dir)

# Tracks the maximum number of users during load generation
max_users = 0

# an event that alerts others who want to persist something when a test stops
persisting_info = locust.events.EventHook()

def get_stats():
    """Returns a dictionary with the statistics we want to persist."""
    global_stats = locust.stats.global_stats

    def to_stats_dict(stats):
        return { "method": stats.method,
                 "name": stats.name,
                 "num_requests": stats.num_requests,
                 "num_failures": stats.num_failures,
                 "avg_response_time": stats.avg_response_time,
                 "min_response_time": stats.min_response_time or 0,
                 "max_response_time": stats.max_response_time,
                 "total_rps": stats.total_rps,
                 "median_response_time": stats.median_response_time,
                 "avg_content_length": stats.avg_content_length, }

    # add the per-requests stats
    entries = [to_stats_dict(stats) for stats in global_stats.entries.itervalues()]

    # add aggregated stats across requests
    entries.append(to_stats_dict(
        global_stats.aggregated_stats(full_request_history=True)))

    stats = {
        'entries': entries,
        'errors': [error.to_dict() for error in global_stats.errors.itervalues()],
        'num_requests': global_stats.num_requests,
        'num_failures': global_stats.num_failures,
        'max_requests': global_stats.max_requests,
        'last_request_timestamp': global_stats.last_request_timestamp,
        'start_time': global_stats.start_time,
        'max_users': max_users,
    }

    # grab extra information from anyone hook in via this event
    persisting_info.fire(stats=stats)

    return stats

def save_stats_to_file(stats, timestamp):
    """Saves stats to a json file, so stats must be json-serializable. The
    filename is 'stats<timestamp>' and is placed in persistence.stats_dir."""
    stats_filepath = "{0}/stats{1}.json".format(stats_dir, timestamp)
    LOG.info("Writing stats to file: {0}".format(os.path.abspath(stats_filepath)))
    with open(stats_filepath, 'w') as f:
        f.write(json.dumps(stats))

def list_stats_files():
    if not os.path.exists(stats_dir):
        return []
    return [os.path.join(stats_dir, x)
            for x in os.listdir(stats_dir)
            if x.startswith('stats') and x.endswith('.json')]

def store_max_users(previous, current):
    """Event handler that updates max_users after whenever users are hatched"""
    global max_users
    if previous == locust.runners.STATE_HATCHING:
        max_users = max(max_users, locust.runners.locust_runner.user_count)
        LOG.debug("Updated max_users: {0}".format(max_users))

def persists_stats(previous, current):
    """Event handler that saves stats to disk when the test is stopped."""
    if (previous not in (None, locust.runners.STATE_INIT)
            and current == locust.runners.STATE_STOPPED):
        stats = get_stats()
        timestamp = str(int(time.time()))
        save_stats_to_file(stats, timestamp)

def setup_persistence():
    if not insight.is_slave():
        LOG.info("Setting up persistence with directory {0}".format(stats_dir))
        locust.events.state_changed += persists_stats
        locust.events.state_changed += store_max_users
