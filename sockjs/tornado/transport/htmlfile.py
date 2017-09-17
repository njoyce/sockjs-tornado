# -*- coding: utf-8 -*-
"""
    sockjs.tornado.transport.htmlfile
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    HtmlFile transport implementation.
"""

from tornado import web

from sockjs.tornado.transport import base
from sockjs.tornado.util import json_encode

__all__ = [
    'HtmlFileTransport',
]


# HTMLFILE template
HTMLFILE_HEAD = b'''
<!doctype html>
<html><head>
  <meta http-equiv="X-UA-Compatible" content="IE=edge" />
  <meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
</head><body><h2>Don't panic!</h2>
  <script>
    document.domain = document.domain;
    var c = parent.%s;
    c.start();
    function p(d) {c.message(d);};
    window.onload = function() {c.stop();};
  </script>
'''.strip()
HTMLFILE_HEAD += b' ' * (1024 - len(HTMLFILE_HEAD) + 14)
HTMLFILE_HEAD += b'\r\n\r\n'


class HtmlFileTransport(base.StreamingTransport):
    name = 'htmlfile'

    sendable = True

    cors = True
    cookie = True
    cache = False
    content_type = 'text/html'
    ajax_callback = True

    @web.asynchronous
    def get(self, session_id):
        self.response_preamble()

        self.write(HTMLFILE_HEAD % (self.js_callback,))
        self.flush()

        if not self.attach_session(session_id):
            self.finish()

    def encode_frame(self, frame):
        return b'<script>\np(%s);\n</script>\r\n' % (
            # only used to escape strings
            json_encode(frame)
        )
