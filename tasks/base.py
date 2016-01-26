import time
from collections import namedtuple

from locust import TaskSet
import locust.events
import gevent

import digaas_integration
import client
import accurate_config as CONFIG
from datagen import select_random_item


class AsyncError(Exception):
    def __init__(self, msg):
        super(AsyncError, self).__init__(msg)


class BaseTaskSet(TaskSet):

    def __init__(self, tenant_list, *args, **kwargs):
        super(BaseTaskSet, self).__init__(*args, **kwargs)

        self.designate_client = client.DesignateClient(self.client,
            use_project_id=CONFIG.use_project_id,
            tenant_id_in_url=CONFIG.tenant_id_in_url)

        self.tenant_list = tenant_list

        if CONFIG.use_digaas:
            self.digaas_client = digaas_integration.DigaasClient(CONFIG.digaas_endpoint)
            self.digaas_behaviors = digaas_integration.DigaasBehaviors(self.digaas_client, CONFIG)

    def select_random_tenant(self):
        return select_random_item(self.tenant_list)

    def _poll_until_active_or_error(self, api_call, status_function,
                                    success_function, failure_function,
                                    expected='ACTIVE',
                                    interval=CONFIG.async_interval,
                                    timeout=CONFIG.async_timeout):
        end_time = time.time() + timeout
        while time.time() < end_time:
            resp = api_call()
            if resp.ok and status_function(resp) == expected:
                success_function()
                return
            elif resp.ok and status_function(resp) == 'ERROR':
                failure_function("Failed - saw ERROR status")
                return
            gevent.sleep(interval)
        failure_function("Failed - timed out after %s seconds" % timeout)

    def _poll_until_404(self, api_call, success_function, failure_function,
                        interval=CONFIG.async_interval,
                        timeout=CONFIG.async_timeout):
        end_time = time.time() + timeout
        while time.time() < end_time:
            with api_call() as resp:
                if resp.status_code == 404:
                    # ensure the 404 isn't marked as a failure in the report
                    resp.success()
                    # mark the original (delete) request as a success
                    success_function()
                    return
            gevent.sleep(interval)
        failure_function("Failed - timed out afer %s seconds" % timeout)

    def async_success(self, resp, start_time, name):
        """When polling for an ACTIVE status, we want the response time to be
        the time until we saw the ACTIVE status. This is used to do that
        in combination with catch_response"""
        locust.events.request_success.fire(
            request_type=resp.request.method,
            name=name,
            response_time=int((time.time() - start_time) * 1000),
            response_length=len(resp.content),

        )

    def async_failure(self, resp, start_time, name, message):
        locust.events.request_failure.fire(
            request_type=resp.request.method,
            name=name,
            response_time=int((time.time() - start_time) * 1000),
            exception=AsyncError(message),
        )
