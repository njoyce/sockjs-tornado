#!venv/bin/python
# -*- coding: utf-8 -*-
"""
Simple sockjs-tornado chat application. By default will listen on port 8080.
"""

import logging

from tornado import web
from tornado import ioloop

from sockjs import tornado as sockjs


class IndexHandler(web.RequestHandler):
    """
    Regular HTTP handler to serve the chatroom page
    """
    def get(self):
        self.render('index.html')


class ChatConnection(sockjs.Connection):
    """
    An instance of this is created for every connection made to the SockJS
    server.

    Implements the chat protocol.
    """

    def on_open(self, info):
        self.broadcast("Someone joined.")

    def on_message(self, message):
        self.broadcast(message)

    def on_close(self):
        self.broadcast("Someone left.")


class ChatEndpoint(sockjs.Endpoint):
    """
    This is the instance that connects the SockJS server to the
    `ChatConnection` class.
    """
    connection_class = ChatConnection


if __name__ == "__main__":
    logging.getLogger().setLevel(logging.DEBUG)

    handlers = [
        (r"/", IndexHandler),
    ]

    server = sockjs.Server(handlers, debug=True)

    chat_endpoint = ChatEndpoint()

    server.add_endpoint(chat_endpoint, '/chat')

    server.listen(8080)

    io_loop = ioloop.IOLoop.current()

    try:
        io_loop.start()
    except KeyboardInterrupt:
        pass
