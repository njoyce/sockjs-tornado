from sockjs.tornado import handler
from sockjs.tornado import transport


__all__ = [
    'get_urls',
]


SESSION_PREFIX_URL = r'/[^/.]+/(?P<session_id>[^/.]+)'

# no prefix required
STATIC_HANDLERS = (
    ('?', handler.GreetingsHandler),
    ('chunking_test', handler.ChunkingTestHandler),
    ('info', handler.InfoHandler),
    ('iframe[0-9-.a-z_]*.html', handler.IFrameHandler),
    ('websocket', transport.RawWebSocketTransport),
)

# requires the SESSION_PREFIX_URL prefix
SEND_HANDLERS = (
    ('xhr_send', transport.XhrSendTransport),
    ('jsonp_send', transport.JSONPSendTransport),
)

# if enabled, requires the SESSION_PREFIX_URL prefix
TRANSPORTS = {
    'websocket': transport.WebSocketTransport,
    'xhr': transport.XhrPollingTransport,
    'xhr_streaming': transport.XhrStreamingTransport,
    'jsonp': transport.JSONPTransport,
    'eventsource': transport.EventSourceTransport,
    'htmlfile': transport.HtmlFileTransport,
}


def make_url(*args):
    return '/' + r'/'.join(args) + '$'


def get_urls(prefix, disabled_transports, **kwargs):
    prefix = prefix.lstrip('/')
    base = prefix + SESSION_PREFIX_URL

    urls = []

    for uri, handler_class in STATIC_HANDLERS:
        urls.append((
            make_url(prefix, uri),
            handler_class,
            kwargs
        ))

    for fragment, handler_class in SEND_HANDLERS:
        urls.append((
            make_url(base, fragment),
            handler_class,
            kwargs
        ))

    for transport_name, handler_class in TRANSPORTS.items():
        if transport_name in disabled_transports:
            continue

        urls.append((
            make_url(base, transport_name),
            handler_class,
            kwargs
        ))

    return urls
