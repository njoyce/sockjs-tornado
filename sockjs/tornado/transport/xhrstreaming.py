# -*- coding: utf-8 -*-
"""
    sockjs.tornado.transport.xhrstreaming
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Xhr-Streaming transport implementation
"""

from tornado import web

from sockjs.tornado.transport import base


class XhrStreamingTransport(base.StreamingTransport):
    name = 'xhr_streaming'

    sendable = True

    cors = True
    cache = False
    cookie = True
    content_type = 'application/javascript'

    @web.asynchronous
    def post(self, session_id):
        # Handle cookie
        self.response_preamble()

        # Send prelude and flush any pending messages
        self.write('h' * 2048 + '\n')
        self.flush()

        if not self.attach_session(session_id):
            self.safe_finish()

    def encode_frame(self, frame):
        return frame + '\n'
