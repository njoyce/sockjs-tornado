# -*- coding: utf-8 -*-
"""
    sockjs.tornado.transport.xhr
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Xhr-Polling transport implementation
"""
from tornado import web

from sockjs.tornado.transport import base

__all__ = [
    'XhrPollingTransport',
    'XhrSendTransport',
]


class XhrPollingTransport(base.PollingTransport):
    """xhr-polling transport implementation"""
    name = 'xhr'

    sendable = True

    cors = True
    cookie = True
    cache = False
    content_type = 'application/javascript'

    @web.asynchronous
    def post(self, session_id):
        self.response_preamble()

        if not self.attach_session(session_id):
            self.safe_finish()

    def encode_frame(self, data):
        return data + '\n'


class XhrSendTransport(base.SingleRecvTransport):
    name = 'xhr_send'

    cors = True
    cookie = True
    cache = False
    content_type = 'text/plain'

    def post(self, session_id):
        super(XhrSendTransport, self).post(session_id)

        self.set_status(204)
        # have to force the flush otherwise tornado will clear the
        # Content-Type header
        self.flush()
