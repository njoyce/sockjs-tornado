from sockjs.tornado import session
from sockjs.tornado import stats
from sockjs.tornado import urls
from sockjs.tornado import web

__all__ = [
    'Connection',
    'Server',
    'Endpoint',
]

DEFAULT_SETTINGS = {
    # How many seconds between each session pool cleanup iteration. Larger
    # values will require a higher amount of RAM for busy servers.
    'session_check_interval': 1,
    # Heartbeat time in seconds. Do not change this value unless
    # you absolutely sure that new value will work.
    'heartbeat_delay': 25,
    # After a heartbeat has been sent, how long in seconds to wait until a
    # response before disconnecting the session
    'heartbeat_timeout': 5,
    # Max wait time in seconds after a session has been closed (specifically
    # put in the CLOSING state) before reaping the session. This allows polling
    # transports to reconnect and get the close frame. Websocket transports do
    # not respect this value.
    'disconnect_delay': 5,
    # Enabled protocols
    'disabled_transports': [],
    # SockJS location
    'sockjs_url': 'https://cdn.jsdelivr.net/sockjs/0.3.4/sockjs.min.js',
    # Max response body size
    'response_limit': 128 * 1024,
    # Enable or disable JSESSIONID cookie handling
    'cookie_affinity': True,
    # Should sockjs-tornado flush messages immediately or queue then and
    # flush on next ioloop tick
    'immediate_flush': True,
    # Enable or disable Nagle for persistent transports
    'disable_nagle': True,
    # Enable IP checks for polling transports. If enabled, all subsequent
    # polling calls should be from the same IP address.
    'verify_ip': True,
    # list of allowed origins for websocket connections
    # or "*" - accept all websocket connections
    'websocket_allow_origin': "*",
    # TODO max_sessions - the maximum number of sessions that this server can
    # support - the sockjs client should regenerate the session id and try
    # again. In a HA environment this has a high likelyhood.
    # TODO health_check - Expose a port that responds to / and determines
    # whether the server is able to continue to receive new connections.
}


class Connection(object):
    def __init__(self, endpoint, session):
        """Connection constructor.

        `session`
            Associated session
        """
        self.endpoint = endpoint
        self.session = session

    # Public API
    def on_open(self, request):
        """Default on_open() handler.

        Override when you need to do some initialization or request validation.
        If you return False, connection will be rejected.

        You can also throw Tornado HTTPError to close connection.

        `request`
            ``ConnectionInfo`` object which contains caller IP address, query
            string parameters and cookies associated with this request (if
            any).
        """

    def on_message(self, message):
        """
        Default on_message handler. Must be overridden in your application
        """
        raise NotImplementedError

    def on_close(self):
        """Default on_close handler."""

    def send(self, message, raw=False):
        """Send message to the client.

        `message`
            Message to send.
        """
        if not self.is_closed:
            self.session.send(message, raw=raw)

    def broadcast(self, message):
        """Broadcast message to the one or more clients.
        Use this method if you want to send same message to lots of clients, as
        it contains several optimizations and will work fast than just having
        loop in your code.

        `clients`
            Clients iterable
        `message`
            Message to send.
        """
        self.endpoint.broadcast(message)

    def close(self):
        self.session.close()

    @property
    def is_closed(self):
        """Check if connection was closed"""
        return self.session.closed

    def session_opened(self, conn_info):
        self.endpoint.session_opened(self.session)

        self.on_open(conn_info)

    def session_closed(self):
        self.endpoint.session_closed(self.session)

        self.on_close()


class Endpoint(object):
    """SockJS protocol router"""

    session_class = session.InMemorySession
    session_pool_class = session.SessionPool

    @property
    def connection_class(self):
        raise NotImplementedError('Must be overridden in sub-classes')

    def __init__(self, settings=None):
        self.active_sessions = {}
        self.started = False

        self.settings = DEFAULT_SETTINGS.copy()

        if settings:
            self.settings.update(settings)

        self.session_pool = self.session_pool_class(
            self.settings['session_check_interval'],
            self.settings['heartbeat_delay'],
        )
        self.stats = stats.StatsCollector()

        self.start()

    def start(self):
        if self.started:
            return

        self.started = True

        self.session_pool.start()
        self.stats.start()

        self.on_started()

    def stop(self):
        if not self.started:
            return

        self.started = False

        self.session_pool.stop()
        self.stats.stop()

        self.on_stopped()

        if self.session_pool:
            self.session_pool = None

        if self.stats:
            self.stats = None

    def on_started(self):
        pass

    def on_stopped(self):
        pass

    @property
    def websockets_enabled(self):
        return 'websocket' not in self.settings['disabled_transports']

    @property
    def cookie_needed(self):
        return self.settings['cookie_affinity']

    def get_urls(self, prefix):
        """List of the URLs to be added to the Tornado application"""
        return urls.get_urls(
            prefix,
            self.settings['disabled_transports'],
            endpoint=self,
            stats=self.stats,
        )

    def create_connection(self, session):
        return self.connection_class(self, session)

    def create_session(self, session_id, register=True):
        """Creates new session object and returns it.

        `request`
            Request that created the session. Will be used to get query string
            parameters and cookies
        `register`
            Should be session registered in a storage. Websockets don't
            need it.
        """
        session_ttl = (
            self.settings['heartbeat_delay']
            + self.settings['heartbeat_timeout']
        )

        sess = self.session_class(
            session_id,
            session_ttl,
        )

        conn = self.create_connection(sess)

        sess.bind(conn)

        if register:
            self.session_pool.add(sess)

        return sess

    def get_session(self, session_id):
        """Get session by session id

        `session_id`
            Session id
        """
        return self.session_pool.get(session_id)

    def broadcast(self, message):
        for sess in self.active_sessions.values():
            sess.send(message)

    def session_opened(self, session):
        self.active_sessions[session.session_id] = session

    def session_closed(self, session):
        self.active_sessions.pop(session.session_id, None)


class Server(object):
    """
    Manages a set of SockJS endpoints.
    """

    web_application_class = web.Application

    def __init__(self, handlers=None, **settings):
        self.endpoints = {}
        self.started = False

        settings.pop('default_host', None)
        settings.pop('transforms', None)

        self.web_app = self.web_application_class(handlers, **settings)
        self.http_server = None

    def add_endpoint(self, endpoint, prefix):
        prefix = '/' + prefix.lstrip('/')

        if prefix in self.endpoints:
            raise ValueError('endpoint %r already defined' % (prefix,))

        self.endpoints[prefix] = endpoint

        if self.started:
            endpoint.start()

        self.web_app.wildcard_router.add_rules(endpoint.get_urls(prefix))

    def remove_endpoint(self, prefix):
        prefix = '/' + prefix.lstrip('/')

        if prefix not in self.endpoints:
            raise ValueError('endpoint %r not found' % (prefix,))

        endpoint = self.endpoints.pop(prefix)

        endpoint.stop()

    def start(self):
        if self.started:
            return

        self.started = True

        for endpoint in self.endpoints.values():
            endpoint.start()

    def stop(self):
        if not self.started:
            return

        self.started = False

        if self.http_server:
            self.http_server = None

        for endpoint in self.endpoints.values():
            endpoint.stop()

    def listen(self, *args, **kwargs):
        self.start()

        self.http_server = self.web_app.listen(*args, **kwargs)

        return self.http_server
