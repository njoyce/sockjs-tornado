# -*- coding: utf-8 -*-
from tornado import ioloop
from tornado_console import ConsoleServer

from sockjs import tornado as sockjs

try:
    import coloredlogs
except ImportError:
    pass
else:
    coloredlogs.install(level='DEBUG')


class EchoConnection(sockjs.Connection):
    def on_message(self, msg):
        self.send(msg)


class CloseConnection(sockjs.Connection):
    def on_open(self, info):
        self.close()

    def on_message(self, msg):
        pass


class EchoEndpoint(sockjs.Endpoint):
    connection_class = EchoConnection


class CloseEndpoint(sockjs.Endpoint):
    connection_class = CloseConnection


if __name__ == '__main__':
    import logging
    logging.getLogger().setLevel(logging.DEBUG)

    sockjs_server = sockjs.Server(debug=True)

    echo_endpoint = EchoEndpoint({'response_limit': 4096})
    no_websocket_echo_endpoint = EchoEndpoint(
        {'disabled_transports': ['websocket']}
    )
    close_endpoint = CloseEndpoint()
    cookie_needed_endpoint = EchoEndpoint({'jessionid': True})

    sockjs_server.add_endpoint(
        echo_endpoint,
        '/echo',
    )

    sockjs_server.add_endpoint(
        no_websocket_echo_endpoint,
        '/disabled_websocket_echo',
    )

    sockjs_server.add_endpoint(
        close_endpoint,
        '/close',
    )

    sockjs_server.add_endpoint(
        cookie_needed_endpoint,
        '/cookie_needed_echo',
    )

    http_server = sockjs_server.listen(8081)
    console_server = ConsoleServer(locals())

    console_server.listen(1234)

    logging.info(" [*] Listening on 0.0.0.0:8081")
    logging.info(" [*] Console is at 0.0.0.0:1234")

    try:
        ioloop.IOLoop.instance().start()
    except KeyboardInterrupt:
        pass
