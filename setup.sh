#!/bin/bash

sudo apt-get -y update

sudo apt-get -y install \
    git python python-dev python-pip gcc build-essential

# With --no-use-wheel, we get a pkg_resources.DistributionNotFound error 
# (on Ubuntu 12.04) when we try to run locust after it is installed below. 
# --force is added for good mesaure.
#
# see: https://github.com/pypa/pip/issues/1800
pip install -U --force --no-use-wheel pip
pip install -U --force --no-use-wheel setuptools 
hash -r
pip install fake-factory locustio pyzmq

git clone https://github.com/pglass/designate-locust.git
