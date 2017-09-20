# -*- coding: utf-8 -*-
"""
    sockjs.tornado.transport.websocket
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Websocket transport implementation
"""
import logging

from sockjs.tornado.handler import websocket
from sockjs.tornado.transport import base
from sockjs.tornado.util import bytes_to_str
from sockjs.tornado.util import json_decode

LOG = logging.getLogger("tornado.general")


class WebSocketTransport(websocket.WebSocketHandler,
                         base.BaseTransport):
    """Websocket transport"""
    name = 'websocket'

    sendable = True
    recvable = True

    @property
    def ping_interval(self):
        return self.sockjs_settings['heartbeat_delay']

    def send_raw(self, data):
        self.write_message(data)

    def on_finish(self):
        # override existing on_finish routines
        # this is on purpose a no-op
        pass

    def open(self, session_id):
        self.stats.on_conn_opened()

        # Disable nagle
        if self.sockjs_settings['disable_nagle']:
            self.stream.set_nodelay(True)

        # Handle session
        session = self.create_session(session_id)

        session.conn_info = self.get_conn_info()

        if not self.bind_session(session):
            self.close(*session.close_reason)

    def on_message(self, message):
        if not message:
            return

        try:
            msg = json_decode(bytes_to_str(message))
        except Exception:
            LOG.exception('Failed to decode %r', message)

            self.close()

            return

        if not isinstance(msg, list):
            msg = [msg]

        try:
            self.session.dispatch(msg)
        except Exception:
            LOG.exception('Failed to dispatch message %r', msg)

            self.close()

            return

    def on_close(self):
        self.stats.on_conn_closed()

        if self.session:
            self.session.close()

    def session_closed(self, session):
        super(WebSocketTransport, self).session_closed(session)

        self.close()

    def on_pong(self, data):
        self.session.touch()

    def send_close_frame(self, close_reason):
        try:
            super(WebSocketTransport, self).send_close_frame(close_reason)
        except websocket.WebSocketClosedError:
            pass
