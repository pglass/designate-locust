Overview
--------

This uses Locust to do distributed load generation for Designate deployments. It includes the following:

- Graphite support for realtime metrics
- Authentication on Locust's web API to guard your locust cluster
- Configurable relative weights for your Locust tasks, with separate sets of weights to simulate small-sized and large-sized users
- Persisted reports: a summary report is automatically stored to disk when the test is stopped. Locust's web server is updated to serve these reports.
- Support for "[Digaas](https://github.com/pglass/digaas)" a separate service that can poll the nameserver backend and give us statistics about the API-nameserver propagation time under load. These statistics are automatically fetched and integrated into the persisted report

Installation
------------

See `setup.sh` for an installation sequence (on Ubuntu 12.04). This currently relies on [my fork of locust](https://github.com/pglass/locust) that has a couple of minor changes.

Usage
-----

#### Config ####

Copy `accurate_config.py.sample` -> `accurate_config.py`. This file can be updated with:

- *required*: The Designate API endpoint
- *required*: The list of tenants to use
- *optional*: A username/password for the Locust's web server
- *optional*: The location of your graphite server
- *optional*: The location of [Digaas](https://github.com/pglass/digaas)

#### Test setup ####

Currently, this test requires a prepared Designate environment. When the test starts, it spends some time gathering data from your environment to use for the duration of the test. You will need to create a bunch of domains and records beforehand, and specify the tenant ids you're using in the config.

#### Web Interface ####

After defining your configs, for Locust's web interface run the following

    locust -f accurate.py

Then visit `localhost:8089` in a browser. The `--host` flag gives the location of your designate endpoint. Make sure your `--host` value has the protocal (`http://`) at the front, or Locust gives an error.

#### No-web Interface ####
For Locust's commandline interface:

    locust -f accurate.py --no-web -c 1 -r 1 -n 10

where

    `-c` specifies the number of clients
    `-r` specifies the hatch rate
    `-n` specifies the total number of requests to make

#### Distributed setup ####

On your master node:

    locust -f example.py --master

Take note of your master's address, and on each of your slave nodes:
    
    locust -f example.py --slave --master-host=<master_address>
