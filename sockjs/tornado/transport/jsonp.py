# -*- coding: utf-8 -*-
"""
    sockjs.tornado.transport.jsonp
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    JSONP transport implementation.
"""
from tornado import web

from sockjs.tornado.transport import base
from sockjs.tornado.util import json_encode


class JSONPTransport(base.PollingTransport):
    name = 'jsonp'

    sendable = True

    ajax_callback = True
    cookie = True
    cache = False
    content_type = 'application/javascript'

    @web.asynchronous
    def get(self, session_id):
        self.response_preamble()

        if not self.attach_session(session_id):
            self.safe_finish()

    def encode_frame(self, frame):
        return '/**/%s(%s);\r\n' % (
            self.js_callback,
            json_encode(frame)
        )


class JSONPSendTransport(base.SingleRecvTransport):
    name = 'jsonp_send'

    cors = True
    cookie = True
    cache = False
    content_type = 'text/plain'

    def post(self, session_id):
        super(JSONPSendTransport, self).post(session_id)

        self.set_header('Content-Length', '2')
        self.write('ok')
