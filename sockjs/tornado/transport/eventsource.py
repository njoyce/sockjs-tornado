# -*- coding: utf-8 -*-
"""
    sockjs.tornado.transport.eventsource
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    EventSource transport implementation.
"""

from tornado import web

from sockjs.tornado.transport import base


class EventSourceTransport(base.StreamingTransport):
    name = 'eventsource'

    cors = True
    cookie = True
    cache = False
    content_type = 'text/event-stream'

    @web.asynchronous
    def get(self, session_id):
        self.response_preamble()

        self.write('\r\n')
        self.flush()

        if not self.attach_session(session_id):
            self.safe_finish()

    def encode_frame(self, frame):
        return b'data: %s\r\n\r\n' % (frame,)
