from tornado import escape, gen, websocket

try:
    from urllib.parse import urlparse # py3
except ImportError:
    from urlparse import urlparse # py2


class SockJSWebSocketHandler(websocket.WebSocketHandler):

    SUPPORTED_METHODS = ('GET',)

    def check_origin(self, origin):
        # let tornado first check if connection from the same domain
        same_domain = super(SockJSWebSocketHandler, self).check_origin(origin)
        if same_domain:
            return True

        # this is cross-origin connection - check using SockJS server settings
        allow_origin = self.server.settings.get("websocket_allow_origin", "*")
        if allow_origin == "*":
            return True
        else:
            parsed_origin = urlparse(origin)
            origin = parsed_origin.netloc
            origin = origin.lower()
            return origin in allow_origin

    def abort_connection(self):
        if self.ws_connection:
            self.ws_connection._abort()
