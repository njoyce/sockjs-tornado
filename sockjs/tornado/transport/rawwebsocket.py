# -*- coding: utf-8 -*-
"""
    sockjs.tornado.transport.rawwebsocket
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Raw websocket transport implementation
"""

from sockjs.tornado.log import transport as LOG
from sockjs.tornado import session
from sockjs.tornado.transport import websocket


class RawWebSocket(session.Session):
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
            LOG.exception('Failed to dispatch')

            self.close()

    def send_open_frame(self):
        # deliberate no-op, raw-websocket does not send an open frame
        pass

    def send_close_frame(self, close_reason):
        # deliberate no-op, raw-websocket does not send a close frame
        pass

    def send(self, data):
        self.write_message(data)
