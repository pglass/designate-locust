from collections import namedtuple

from locust import TaskSet

import digaas_integration
import client
import accurate_config as CONFIG
from datagen import select_random_item


class BaseTaskSet(TaskSet):

    def __init__(self, tenant_list, *args, **kwargs):
        super(BaseTaskSet, self).__init__(*args, **kwargs)

        self.designate_client = client.DesignateClient(self.client)

        self.tenant_list = tenant_list

        if CONFIG.use_digaas:
            self.digaas_client = digaas_integration.DigaasClient(CONFIG.digaas_endpoint)
            self.digaas_behaviors = digaas_integration.DigaasBehaviors(self.digaas_client, CONFIG)

    def select_random_tenant(self):
        return select_random_item(self.tenant_list)
