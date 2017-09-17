# -*- coding: utf-8 -*-
"""
    sockjs.tornado.static
    ~~~~~~~~~~~~~~~~~~~~~

    Various static handlers required for SockJS to function properly.
"""

import hashlib
import random

from tornado import web
from tornado import ioloop

from sockjs.tornado.handler import base
from sockjs.tornado.util import json_encode
from sockjs.tornado.util import str_to_bytes


__all__ = [
    'ChunkingTestHandler',
    'GreetingsHandler',
    'IFrameHandler',
    'InfoHandler',
]

IFRAME_TEXT = b'''<!DOCTYPE html>
<html>
<head>
  <meta http-equiv="X-UA-Compatible" content="IE=edge" />
  <meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
  <script src="%s"></script>
  <script>
    document.domain = document.domain;
    SockJS.bootstrap_iframe();
  </script>
</head>
<body>
  <h2>Don't panic!</h2>
  <p>This is a SockJS hidden iframe. It's used for cross domain magic.</p>
</body>
</html>'''.strip()


class IFrameHandler(base.BaseHandler):
    """SockJS IFrame page handler"""

    cache = True
    content_type = 'text/html'

    def get(self):
        data = str_to_bytes(IFRAME_TEXT % self.sockjs_settings['sockjs_url'])

        hsh = hashlib.md5(data).hexdigest()

        value = self.request.headers.get('If-None-Match')

        if value and value == hsh:
            self.clear()

            self.set_status(304)

            return

        self.response_preamble()

        self.set_header('ETag', hsh)
        self.write(data)


class GreetingsHandler(base.BaseHandler):
    """SockJS greetings page handler"""

    cache = True
    content_type = 'text/plain'

    def get(self):
        self.response_preamble()

        self.write('Welcome to SockJS!\n')


class ChunkingTestHandler(base.BaseHandler):
    """SockJS chunking test handler"""

    cors = True
    content_type = 'application/javascript'

    # Step timeouts according to sockjs documentation
    steps = [0.005, 0.025, 0.125, 0.625, 3.125]

    @web.asynchronous
    def post(self):
        io_loop = ioloop.IOLoop.current()

        self.response_preamble()

        # Send one 'h' immediately
        self.write('h\n')
        self.flush()

        # Send 2048 spaces followed by 'h'
        self.write(' ' * 2048 + 'h\n')
        self.flush()

        # Send 'h' with different timeouts
        def run_step(step):
            try:
                self.write('h\n')
                self.flush()

                step += 1
                if step >= len(self.steps):
                    self.finish()

                    return

                delay = self.steps[step]

                io_loop.call_later(delay, lambda: run_step(step))
            except IOError:
                pass

        io_loop.call_later(self.steps[0], lambda: run_step(0))


class InfoHandler(base.BaseHandler):
    """SockJS 0.2+ /info handler"""

    access_methods = 'OPTIONS, GET'
    cache = False
    cors = True
    content_type = 'application/json'

    MAX_ENTROPY = 2 ** 32 - 1

    def get(self):
        self.response_preamble()

        options = dict(
            websocket=self.endpoint.websockets_enabled,
            cookie_needed=self.endpoint.cookie_needed,
            origins=['*:*'],
            entropy=random.randint(0, self.MAX_ENTROPY)
        )

        self.write(json_encode(options))
