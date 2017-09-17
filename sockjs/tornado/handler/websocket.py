from tornado import websocket

try:
    from urllib.parse import urlparse  # py3
except ImportError:
    from urlparse import urlparse  # py2

__all__ = [
    'WebSocketHandler',
    'WebSocketClosedError',
]


WebSocketClosedError = websocket.WebSocketClosedError


class WebSocketHandler(websocket.WebSocketHandler):
    SUPPORTED_METHODS = ('GET',)

    def get_compression_options(self):
        # let tornado use compression when
        # Sec-WebSocket-Extensions:permessage-deflate is provided
        return {}

    def check_origin(self, origin):
        # let tornado first check if connection from the same domain
        same_domain = super(WebSocketHandler, self).check_origin(origin)

        if same_domain:
            return True

        # this is cross-origin connection - check using SockJS server settings
        allow_origin = self.sockjs_settings.get("websocket_allow_origin", "*")
        if allow_origin == "*":
            return True

        parsed_origin = urlparse(origin)
        origin = parsed_origin.netloc.lower()

        return origin in allow_origin

    def abort_connection(self):
        if self.ws_connection:
            self.ws_connection._abort()
