import sys
import argparse
import getpass
import requests
from requests.auth import HTTPDigestAuth

def parse_args():
    p = argparse.ArgumentParser(description="Controls a Locust cluster")
    p.add_argument("-e", "--locust-endpoint", required=True,
        help="The address of the Locust master process")
    p.add_argument("-u", "--username",
        help="A username for the Locust server")
    p.add_argument("-p", "--password",
        help="A password for the Locust server. Prompts you if not provided.")

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

    return p.parse_args()

def start_locust(args):
    return requests.post(args.locust_endpoint.strip('/') + '/swarm',
                         data={'locust_count': args.locust_count,
                               'hatch_rate': args.hatch_rate },
                         auth=HTTPDigestAuth(args.username, args.password))

def stop_locust(args):
    return requests.get(args.locust_endpoint.strip('/') + '/stop',
                        auth=HTTPDigestAuth(args.username, args.password))

def handle_args(args):
    if not args.locust_endpoint.startswith('http'):
        old_endpoint = args.locust_endpoint
        args.locust_endpoint = "http://" + args.locust_endpoint
        print("WARNING: Fixing locust endpoint '{0}' to be '{1}'"
              .format(old_endpoint, args.locust_endpoint))
    if args.username and not args.password:
        args.password = getpass.getpass()
        if not args.password:
            print "ERROR: Password required for user '{0}'".format(args.username)
            sys.exit(1)


    if args.command == 'start':
        resp = start_locust(args)
    if args.command == 'stop':
        resp = stop_locust(args)

    print resp
    print resp.text

    if not resp.ok:
        sys.exit(1)

if __name__ == "__main__":
    args = parse_args()
    handle_args(args)
