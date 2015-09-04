import sys
import os
from sys import stderr
import argparse
import requests
from requests.auth import HTTPBasicAuth

def parse_args():
    p = argparse.ArgumentParser(description="Controls a Locust cluster")
    p.add_argument("-e", "--locust-endpoint", required=True,
        help="The address of the Locust master process")
    p.add_argument("-u", "--username", required=False,
        help="A username for the Locust server [LOCUST_USERNAME]")
    p.add_argument("-p", "--password", required=False,
        help="A password for the Locust server. [LOCUST_PASSWORD]")

    # check args.command for which command was used
    subparsers = p.add_subparsers(help="The command to execute", dest="command")

    # add the start command
    start_parser = subparsers.add_parser("start", help="Start load generation")
    start_parser.add_argument("-r", "--hatch-rate", type=float,
        help="Specify the user spawn rate", required=True)
    start_parser.add_argument("-c", "--locust-count", type=int,
        help="Specify the number of users", required=True)

    # add the stop command
    stop_parser = subparsers.add_parser("stop", help="Stop load generation")

    # add a get status command
    get_status_parser = subparsers.add_parser("status",
        help="Fetch the Locust's status")

    return p.parse_args()

def credentials(args):
    username = args.username or os.environ.get('LOCUST_USERNAME')
    password = args.password or os.environ.get('LOCUST_PASSWORD')
    return HTTPBasicAuth(username, password)

def start_locust(args):
    return requests.post(args.locust_endpoint.strip('/') + '/swarm',
                         data={'locust_count': args.locust_count,
                               'hatch_rate': args.hatch_rate },
                         auth=credentials(args))

def stop_locust(args):
    return requests.get(args.locust_endpoint.strip('/') + '/stop',
                        auth=credentials(args))

def get_status(args):
    return requests.get(args.locust_endpoint.strip('/') + '/status',
                        auth=credentials(args))

def handle_args(args):
    if not args.locust_endpoint.startswith('http'):
        old_endpoint = args.locust_endpoint
        args.locust_endpoint = "http://" + args.locust_endpoint

    if args.command == 'start':
        resp = start_locust(args)
    elif args.command == 'stop':
        resp = stop_locust(args)
    elif args.command == 'status':
        resp = get_status(args)

    print resp.text

    if not resp.ok:
        sys.exit(1)

if __name__ == "__main__":
    handle_args(parse_args())
