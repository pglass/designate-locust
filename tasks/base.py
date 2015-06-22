from locust import TaskSet
import digaas_integration
import client
import accurate_config as CONFIG


class BaseTaskSet(TaskSet):

    def __init__(self, test_data, *args, **kwargs):
        super(BaseTaskSet, self).__init__(*args, **kwargs)

        self.designate_client = client.DesignateClient(self.client)

        self.test_data = test_data

        if CONFIG.use_digaas:
            self.digaas_client = digaas_integration.DigaasClient(CONFIG.digaas_endpoint)
            self.digaas_behaviors = digaas_integration.DigaasBehaviors(self.digaas_client, CONFIG)

    def get_headers(self, tenant=None):
        return {
            client.ROLE_HEADER: 'admin',
            client.PROJECT_ID_HEADER: tenant or self.test_data.pick_random_tenant() }
