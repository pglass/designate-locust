import time
import logging

import gevent

import accurate_config as CONFIG

GREENLET_TIMEOUT = CONFIG.async_timeout + CONFIG.async_interval + 120

LOG = logging.getLogger(__name__)
LOG.info("Async timeout = %s seconds", CONFIG.async_timeout)
LOG.info("Async interval = %s seconds", CONFIG.async_interval)
LOG.info("Greenlet timeout is %s seconds", GREENLET_TIMEOUT)


class GreenletManager(list):

    @classmethod
    def get(cls, _instance=[]):
        if not _instance:
            _instance.append(GreenletManager())
        return _instance[0]

    def tracked_greenlet(self, f):
        """A wrapper function that stores the current greenlet in list in order
        to keep track of our asynchronous request 'threads'. The greenlet
        remains in the list until it terminates, or until an explicit cleanup.

        There is an implicit timeout on the runtime of greenlets. It is
        computed automatically, and is guaranteed to be sufficiently longer
        than than the async_timeout + async_interval.

        Usage:
            for _ in xrange(...):
                # spawn
                gevent.spawn(
                    greenlet_manager.tracked_greenlet,
                    lambda: do_thing(arg, arg)
                )

            # wait for greenlets to do a thing
            # if they terminate, they'll remove themselves from this list
            # if not, they remain in the list
            gevent.sleep(5)

            # give the remaining greenlets 5 seconds to finish up. Then kill them.
            greenlet_manager.cleanup_greenlets(timeout=5)
        """
        try:
            current_greenlet = gevent.getcurrent()
            self.append(current_greenlet)
            with gevent.Timeout(seconds=GREENLET_TIMEOUT):
                f()
        except gevent.Timeout:
            # if the greenlet is killed externally don't print the exception
            pass
        finally:
            self.remove(current_greenlet)

    def cleanup_greenlets(self, timeout=None):
        """Allow the greenlets stored in this list timeout seconds to finish.
        After the timeout, kill the remaining greenlets."""
        LOG.info("Cleaning up greenlets")
        if timeout:
            gevent.joinall(self, timeout=timeout)
        gevent.killall(self, exception=gevent.Timeout)
