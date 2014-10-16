from socket import socket

class Graphite(object):
    """Dumb interface for talking to a Graphite server. Graphite accepts data
    over text or pickle protocols or using AMQP. Be careful because a different
    port is required for each protocol."""

    def __init__(self, host, port):
        try:
            self.sock = socket()
            self.sock.connect((host, port))
        except Exception as e:
            raise Exception(
                "Couldn't connect to Graphite server {0} on port {1}: {2}"
                .format(host, port, e))

    def send_text(self, key, value, timestamp):
        data = "{0} {1} {2}\n".format(key, value, timestamp)
        print "sending %r".format(data)
        # returns None on success. Exception on error.
        sock.sendall(data)
