username = None
password = None

# set to true to reset stats after rampup
reset_stats = False

designate_host = 'http://192.168.33.20:9001'

use_redis = True
redis_host = "localhost"
redis_port = 6379
redis_password = None

graphite_host = None
graphite_port = None

min_wait = 100
max_wait = 1000

large_tenants = ['T1', 'T2']
small_tenants = ['T3', 'T4']
assert not set(large_tenants).intersection(set(small_tenants))

class Weights(object):

    def __init__(self, get_domain_by_id, get_domain_by_name, list_domain,
                 export_domain, create_domain, modify_domain, remove_domain,
                 list_records, get_record, create_record, remove_record,
                 modify_record):
        self.get_domain_by_id = get_domain_by_id
        self.get_domain_by_name = get_domain_by_name
        self.list_domain = list_domain
        self.export_domain = export_domain
        self.create_domain = create_domain
        self.modify_domain = modify_domain
        self.remove_domain = remove_domain
        self.list_records = list_records
        self.get_record = get_record
        self.create_record = create_record
        self.remove_record = remove_record
        self.modify_record = modify_record

    def total(self):
        return sum(self.__dict__.itervalues())

large_weights = Weights(
    get_domain_by_id = 576,
    get_domain_by_name = 192,
    list_domain = 768,
    export_domain = 0,
    create_domain = 120,
    modify_domain = 0,
    remove_domain = 0,
    list_records = 324,
    get_record = 216,
    create_record = 1560,
    modify_record = 600,
    remove_record = 300,

)
total_large_weight = large_weights.total()

small_weights = Weights(
    get_domain_by_id = 342,
    get_domain_by_name = 114,
    list_domain = 456,
    export_domain = 60,
    create_domain = 1980,
    modify_domain = 600,
    remove_domain = 720,
    list_records = 6984,
    get_record = 4656,
    create_record = 180,
    modify_record = 60,
    remove_record = 480,

)
total_small_weight = small_weights.total()

print total_large_weight
print total_small_weight

# n_large_domains_per_tenant is the number of domains to fetch for use with
# gets/deletes for large tenants during the test. Due to the implementation,
# these domains are divided equally, three ways:
#   1/3 used for getting domains
#   1/3 used for deleting domains
#   1/3 used for fetching records
# n_large_records_per_domain is the number of records to fetch for each of the
# 1/3 domains retrieved above, of which:
#   1/2 used for getting records (all NS records)
#   1/4 used for updating records (all A records)
#   1/4 used for deleting records (all A records)
# So the total number of records available for deletion during the test, among
# all large tenants is:
#   n_large_domains_per_tenant * 1/3 * n_large_domains_per_tenant * 1/4
#
# These numbers should have no effect on the rates seen during the test.
n_large_domains_per_tenant = 120
n_large_records_per_domain = 1
n_small_domains_per_tenant = 60
n_small_records_per_domain = 1
