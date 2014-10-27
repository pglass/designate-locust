#!/bin/bash

sudo apt-get -y update

sudo apt-get -y install \
    git python python-dev python-pip gcc build-essential

# Use --no-use-wheel to solve a pkg_resources.DistributionNotFound error
# (on Ubuntu 12.04) when we try to run locust after it is installed.
# --force is added for good mesaure.
#
# see: https://github.com/pypa/pip/issues/1800
pip install -U pip
hash -r
pip install -U --force --no-use-wheel pip
hash -r
pip install -U --force --no-use-wheel setuptools
pip install -U distribute
pip install fake-factory pyzmq redis pygal Flask-HTTPAuth

git clone https://github.com/pglass/locust.git
cd locust
pip install .
cd ..

# install matplotlib dependencies
pip install python-dateutil six
sudo apt-get install libfreetype6-dev libxft-dev libpng12-dev
pip install matplotlib==1.4.1

git clone https://github.com/pglass/designate-locust.git
