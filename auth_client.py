import json
import logging

import requests

import accurate_config as CONFIG

class AuthClient(object):

    _HEADERS = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    def __init__(self, endpoint=None):
        if endpoint is not None:
            self.endpoint = endpoint
        else:
            self.endpoint = CONFIG.auth_endpoint.strip('/')

    def get_token(self, username, api_key):
        url = "{0}/tokens".format(self.endpoint)
        data = {
            "auth": {
                "apiKeyCredentials": {
                    "username": username,
                    "apiKey": api_key,
                }
            }
        }
        return requests.post(url, data=json.dumps(data), headers=self._HEADERS)

    def revoke_token(self, token):
        url = "{0}/tokens".format(self.endpoint)
        headers = dict(self._HEADERS)
        headers['X-Auth-Token'] = token
        return requests.delete(url, headers=headers)
