import locust
import accurate_config as CONFIG

def refresh_test_data(previous, current, large_data, small_data):
    if current == locust.runners.STATE_HATCHING:
        print "refreshing test data for large tenants..."
        large_data.refresh(CONFIG.n_large_domains_per_tenant, CONFIG.n_large_records_per_domain)
        print "Large: %s" % large_data

        print "refreshing test data for small tenants..."
        small_data.refresh(CONFIG.n_small_domains_per_tenant, CONFIG.n_small_records_per_domain)
        print "Small: %s" % small_data
