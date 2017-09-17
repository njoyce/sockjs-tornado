# -*- coding: utf-8 -*-
"""
    sockjs.tornado.transport.rawwebsocket
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Raw websocket transport implementation
"""
import logging

from sockjs.tornado import session
from sockjs.tornado.transport import websocket

LOG = logging.getLogger("tornado.general")


class RawWebSocket(session.BaseSession):
    def __init__(self):
        super(RawWebSocket, self).__init__('raw', 0)

    def send(self, data, **kwargs):
        self.write(data)

    def send_frame(self, data, **kwargs):
        self.write(data)

    def get_buffer(self):
        return []


class RawWebSocketTransport(websocket.WebSocketTransport):
    """Raw Websocket transport"""
    name = 'raw-websocket'

    def open(self, *args, **kwargs):
        super(RawWebSocketTransport, self).open('raw-websocket')

    def create_session(self, session_id):
        sess = RawWebSocket()

        conn = self.endpoint.create_connection(sess)

        sess.bind(conn)

        return sess

    def on_message(self, message):
        if not message:
            return

        try:
            self.session.dispatch([message])
        except Exception:
            LOG.exception('RawWebSocket')

            self.close()

    def send_open_frame(self):
        pass

    def send_close_frame(self, close_reason):
        pass

    def send(self, data):
        self.write_message(data)
