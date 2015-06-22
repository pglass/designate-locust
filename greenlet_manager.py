import time
import gevent

class GreenletManager(list):

    @classmethod
    def get(cls, _instance=[]):
        if not _instance:
            _instance.append(GreenletManager())
        return _instance[0]

    def tracked_greenlet(self, f, timeout=10):
        """A wrapper function that stores the current greenlet in list in order
        to keep track of our asynchronous request 'threads'. The greenlet
        remains in the list until it terminates, or until an explicit cleanup.

        Usage:
            for _ in xrange(...):
                # spawn
                gevent.spawn(
                    greenlet_manager.tracked_greenlet,
                    lambda: do_thing(arg, arg),
                    timeout=10
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
            with gevent.Timeout(seconds=timeout) as timeout:
                f()
        except gevent.Timeout:
            # if the greenlet is killed externally don't print the exception
            pass
        finally:
            self.remove(current_greenlet)

    def cleanup_greenlets(self, timeout=None):
        """Allow the greenlets stored in this list timeout seconds to finish.
        After the timeout, kill the remaining greenlets."""
        print "Cleaning up greenlets"
        if timeout:
            gevent.joinall(self, timeout=timeout)
        gevent.killall(self, exception=gevent.Timeout)
