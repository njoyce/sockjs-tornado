# -*- coding: utf-8 -*-
"""
Simple sockjs-tornado chat application. By default will listen on port 8080.
"""
from tornado import web
from tornado import ioloop

from sockjs import tornado as sockjs


class IndexHandler(web.RequestHandler):
    """Regular HTTP handler to serve the chatroom page"""
    def get(self):
        self.render('index.html')


class ChatConnection(sockjs.Connection):
    """Chat connection implementation"""
    def on_open(self, info):
        self.broadcast("Someone joined.")

    def on_message(self, message):
        self.broadcast(message)

    def on_close(self):
        self.broadcast("Someone left.")


class ChatEndpoint(sockjs.Endpoint):
    connection_class = ChatConnection


if __name__ == "__main__":
    import logging
    logging.getLogger().setLevel(logging.DEBUG)

    io_loop = ioloop.IOLoop.current()

    server = sockjs.Server([(r"/", IndexHandler)], debug=True)

    server.add_endpoint(ChatEndpoint(), '/chat')

    # 3. Make Tornado app listen on port 8080
    server.listen(8080)

    # 4. Start IOLoop
    try:
        io_loop.start()
    except KeyboardInterrupt:
        pass
