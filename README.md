Overview
--------

This uses Locust to do distributed load generation for Designate deployments. API operations are executed to induce zone transfers to the DNS backend. Each time a zone's serial changes, the timestamp is put in a Redis store. Afterwards, these timestamps are compared to corresponding timestamps taken externally on the DNS backend server. In particular, this is looking to load test the miniDNS component.

Installation
------------

Optionally, create a virtual environment to work in first.

    pip install fake-factory locustio pyzmq redis

Or see `setup.sh` for an installation sequence (on Ubuntu 12.04).

Usage
-----

#### Redis config ####

This requires a Redis server location, which is specified through environment variables:

    export LOCUST_REDIS_HOST=localhost
    export LOCUST_REDIS_PORT=6379

If your Redis server requires a password, then additionally:

    export LOCUST_REDIS_PASSWORD=my_password

#### Web Interface ####

For Locust's web interface run the following

    locust -f example.py --host=http://192.168.33.20:9001

Then visit `localhost:8089` in a browser. The `--host` flag gives the location of your designate endpoint. Make sure your `--host` value has the protocal (`http://`) at the front, or Locust gives an error.

#### No-web Interface ####
For Locust's commandline interface:

    locust -f example.py --host=http://192.168.33.20:9001 --no-web -c 1 -r 1 -n 10

where

    `-c` specifies the number of clients
    `-r` specifies the hatch rate
    `-n` specifies the total number of requests to make

#### Distributed setup ####

On your master node:

    locust -f example.py --host=http://192.168.33.20:9001 --master

Take note of your master's address, and on each of your slave nodes:
    
    locust -f example.py --host=http://192.168.33.20:9001 --slave --master-host=<master_address>
