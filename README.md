Overview
--------

This uses Locust to do distributed load generation for Designate deployments.

Installation
------------

Optionally, create a virtual environment to work in first.

    pip install fake-factory locustio pyzmq

Usage
-----

For Locust's web interface run the following

    locust -f example.py

Then visit `localhost:8089` in a browser.

For Locust's commandline interface:

    locust --no-web -c 1 -r 1 -f example.py -n 10

where

    `-c` specifies the number of clients
    `-r` specifies the hatch rate
    `-n` specifies the total number of requests to make
