Overview
--------

This uses Locust to do distributed load generation for Designate deployments. API operations are executed to induce zone transfers to the DNS backend. Each time a zone's serial changes, the timestamp is put in a Redis store. Afterwards, these timestamps are compared to corresponding timestamps taken externally on the DNS backend server. In particular, this is looking to load test the miniDNS component.

Installation
------------

Optionally, create a virtual environment to work in first.

Install some dependencies:

    pip install fake-factory pyzmq redis

Install Locust. This relies on a fork with a couple of changes:

    git clone https://github.com/pglass/locust
    cd locust
    pip install .

Or see `setup.sh` for an installation sequence (on Ubuntu 12.04).

Usage
-----

#### Config ####

For example.py, config values are specified in a json file, or through environment variables (see config.py).

For accurate.py, config values are specifed in a Python file (see accurate_config.py).

#### Web Interface ####

After defining your configs, for Locust's web interface run the following

    locust -f example.py

Then visit `localhost:8089` in a browser. The `--host` flag gives the location of your designate endpoint. Make sure your `--host` value has the protocal (`http://`) at the front, or Locust gives an error.

#### No-web Interface ####
For Locust's commandline interface:

    locust -f example.py --no-web -c 1 -r 1 -n 10

where

    `-c` specifies the number of clients
    `-r` specifies the hatch rate
    `-n` specifies the total number of requests to make

#### Distributed setup ####

On your master node:

    locust -f example.py --master

Take note of your master's address, and on each of your slave nodes:
    
    locust -f example.py --slave --master-host=<master_address>
