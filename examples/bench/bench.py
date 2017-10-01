# -*- coding: utf-8 -*-
"""
    sockjs-tornado benchmarking server. Works as a simple chat server
    without HTML frontend and listens on port 8080 by default.
"""
import sys
import weakref

from tornado import ioloop

from sockjs import tornado as sockjs


class EchoConnection(sockjs.Connection):
    """Echo connection implementation"""
    clients = set()
    weak_clients = weakref.WeakSet([])

    def on_open(self, info):
        # When new client comes in, will add it to the clients list
        self.clients.add(self)
        self.weak_clients.add(self)

    def on_message(self, msg):
        # For every incoming message, broadcast it to all clients
        self.broadcast(msg)

    def on_close(self):
        # If client disconnects, remove him from the clients list
        self.clients.remove(self)

    @classmethod
    def dump_stats(cls):
        # Print current client count
        print 'Clients: %d' % (len(cls.clients))
        print 'Weak Clients: %d' % (len(cls.weak_clients))


class EchoEndpoint(sockjs.Endpoint):
    connection_class = EchoConnection


if __name__ == '__main__':
    options = dict()

    if len(sys.argv) > 1:
        options['immediate_flush'] = False

    # 1. Create SockJSRouter
    server = sockjs.Server()

    server.add_endpoint(EchoEndpoint(options), '/broadcast')

    # 3. Make application listen on port 8080
    server.listen(8080)

    # 4. Every 1 second dump current client count
    ioloop.PeriodicCallback(EchoConnection.dump_stats, 1000).start()

    # 5. Start IOLoop
    try:
        ioloop.IOLoop.instance().start()
    except KeyboardInterrupt:
        pass
