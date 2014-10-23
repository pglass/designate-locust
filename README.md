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

#### Config ####

Configuration values are specified either through environment variable or a json file, which must be named `config.json`. Any values not found in environment variables are then looked for in the json file.

`config.json`:

    {
        "redis_host": "localhost",
        "redis_port": 6379,
        "redis_password": null,
        "designate_host": "http://192.168.33.20:9001",
        "n_tenants": 10,
        "min_wait": 250,
        "max_wait": 750,
        "graphite_host": "192.168.33.21",
        "graphite_port": 2023,
        "locust_username": "imauser",
        "locust_password": "imapassword"
    }

Or, using environment variables:

    LOCUST_REDIS_HOST=localhost   
    LOCUST_REDIS_PORT=6379    
    LOCUST_REDIS_PASSWORD=password
    LOCUST_DESIGNATE_HOST=http://192.168.33.20:9001
    ...


See `config.py` for definitions of all the key names used.

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
