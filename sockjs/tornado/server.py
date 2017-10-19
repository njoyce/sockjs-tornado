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
    # SockJS location. This is used in iframe transports.
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
    """
    A connection object maps a session to an endpoint and provides app specific
    logic.
    """

    def __init__(self, endpoint, session):
        """Connection constructor.

        :param endpoint: The :ref:`Endpoint` that this connection is attached
            to.
        :param session: The :ref:`Session` that this connection is attached
            to.
        """
        self.endpoint = endpoint
        self.session = session

    def on_open(self, request):
        """
        Default on_open() handler.

        Override when you need to do some initialization or request validation.
        If you return False, connection will be rejected.

        You can also throw Tornado HTTPError to close connection.

        :param request: :ref:`ConnectionInfo` instance that contains the
            caller IP address, query string parameters and cookies associated
            with this request (if any).
        """

    def on_message(self, message):
        """
        Default on_message handler. Must be overridden in your application.

        Called when a message has been received from the client.
        """
        raise NotImplementedError

    def on_close(self):
        """
        Default on_close handler.

        Called when the session has been closed. At this point you cannot send
        any messages to the client.
        """

    def send(self, message, raw=False):
        """
        Send message to the client.

        :param message: Message to send. If raw is False, must be JSON
            encodable. IF raw is True, must be a json encoded byte string.
        :param raw: Whether the message is already JSON encoded or not.
        """
        if self.is_closed:
            return

        self.session.send(message, raw=raw)

    def broadcast(self, message, raw=False, exclude=None):
        """
        Broadcast message to all other sessions connected to the endpoint.
        Useful for chat style applications.

        Use this method if you want to send same message to lots of clients, as
        it contains several optimizations and will work fast than just having
        loop in your code.

        :param message: The message to send to the client. If raw is False then
            message must be a JSON encodable object. If raw is True then
            message must be a JSON encoded bytestring.
        :param raw: Whether the message is a JSON encoded bytestring or not.
        :param exclude: A list of session_ids to NOT send the message to.
        """
        self.endpoint.broadcast(message, raw=raw, exclude=exclude)

    def close(self):
        """
        Close this connection.
        """
        if not self.is_closed:
            self.session.close()

    @property
    def is_closed(self):
        """
        Check if connection was closed
        """
        return self.session.closed

    def session_opened(self, conn_info):
        """
        Called when the underlying session has been opened.

        :param conn_info: :ref:`ConnectionInfo` instance of the request that
            opened the session.
        """
        self.endpoint.session_opened(self.session)

        self.on_open(conn_info)

    def session_closed(self):
        """
        Called when the underlying session has been closed.
        """
        self.endpoint.session_closed(self.session)

        self.on_close()


class Endpoint(object):
    """
    An endpoint encapsulates all the logic for handling SockJS connections.

    :cvar session_class: A reference to the class that handles
        implementation of the session.
    :cvar session_pool_class: A reference to the class that handles the session
        pool logic.
    :cvar connection_class: A refererence to the class that handles the
        connection logic.
    :ivar active_sessions: A dict of session_id -> Session instance of all
        active sessions currently connected to the endpoint.
    :ivar started: Whether the endpoint has started (actively
        handling/receiving connections).
    :ivar settings: The full set of settings that govern this endpoint.
    :ivar session_pool: Handles responsibility of creating sessions and
        ensuring that stale sessions are properly reaped.
    :ivar stats: Collects some and various interesting stats about the activity
        of the endpoint and the sessions it handles.
    """

    session_class = session.Session
    session_pool_class = session.SessionPool

    @property
    def connection_class(self):
        raise NotImplementedError('Must be overridden in sub-classes')

    @property
    def websockets_enabled(self):
        return 'websocket' not in self.settings['disabled_transports']

    @property
    def cookie_needed(self):
        return self.settings['cookie_affinity']

    def __init__(self, settings=None):
        """
        Initialise the SockJS Endpoint.

        :param settings: If supplied, must be a dict of settings to override
            :ref:`DEFAULT_SETTINGS`.
        """
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
        """
        Start the management of sessions connected to this endpoint.
        """
        if self.started:
            return

        self.started = True

        self.session_pool.start()
        self.stats.start()

        self.on_started()

    def stop(self):
        """
        Stop the management of sessions connected to this endpoint.
        """
        if not self.started:
            return

        self.started = False

        self.on_stopping()

        self.session_pool.stop()
        self.stats.stop()

        if self.session_pool:
            self.session_pool = None

        if self.stats:
            self.stats = None

        self.active_sessions = {}

        self.on_stopped()

    def on_started(self):
        """
        Called when the endpoint has started accepting sessions.
        """

    def on_stopping(self):
        """
        Called when the endpoint has been told to stop accepting sessions but
        has not torn down any state yet. This provides the ability to warn the
        connected sessions of the impending event.
        """

    def on_stopped(self):
        """
        Called when the endpoint has stopped accepting sessions and all state
        has been torn down.
        """

    def get_urls(self, prefix):
        """List of the URLs to be added to the Tornado application"""
        return urls.get_urls(
            prefix,
            self.settings['disabled_transports'],
            endpoint=self,
            stats=self.stats,
        )

    def create_connection(self, session):
        """
        Return an instance of :ref:`connection_class` that is linked to this
        endpoint and the supplied session.

        :param session: The session instance.
        :type session: An instance of :ref:`session_class`.
        """
        return self.connection_class(self, session)

    def create_session(self, session_id, register=True):
        """
        Create new session instance and return it.

        :param session_id: The unique id of the session.
        :param register: Whether the session should be registered with the
            :ref:`session_pool`. Websocket connections do not get registered
            because the TCP close event is enough to immediately close the
            session.
        """
        session_ttl = (
            self.settings['heartbeat_delay'] +
            self.settings['heartbeat_timeout']
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
        """
        Get session by session id.

        :param session_id: Session id
        """
        return self.active_sessions.get(session_id)

    def session_opened(self, session):
        """
        Called by the underlying session transports signalling that the session
        has been opened.

        :param session: The session instance that was opened.
        """
        self.active_sessions[session.session_id] = session

    def session_closed(self, session):
        """
        Called by the underlying session transports signalling that the session
        has been closed.

        :param session: The session that was closed.
        """
        self.active_sessions.pop(session.session_id, None)

    def broadcast(self, message, raw=False, exclude=None):
        """
        Send a message to every active session.

        :param message: If raw is False, can be any JSON encodable object. If
            raw is True, must be a bytestring.
        :param raw: Whether the message has already been encoded.
        :param exclude: A list of session_ids to exclude from receiving the
            broadcast.
        """
        for sess in self.active_sessions.values():
            if exclude and sess.session_id in exclude:
                continue

            sess.send(message)


class Server(object):
    """
    A SockJS server encapsulates an HTTP over which it has complete domain. It
    also manages a set of SockJS endpoints that are attached to the server.

    :cvar web_application_class: A reference to the class that handles
        implementation of the web application.
    :ivar endpoints: A dict of prefix -> Endpoint.
    :ivar started: Whether the server has started.
    :ivar web_app: The underlying :ref:`tornado.web.Application` object.
    :ivar http_server: The underlying :ref:`tornado.httpserver.HTTPServer`.
    """

    web_application_class = web.Application

    def __init__(self, handlers=None, **settings):
        """
        Construct the SockJS Server.

        :param handlers: A list of handlers to supply to the `web_app.
        :param settings: A dict of settings for the web_application.
        :see:`http://www.tornadoweb.org/en/stable/web.html#
            application-configuration`
        """
        self.endpoints = {}
        self.started = False

        settings.pop('default_host', None)
        settings.pop('transforms', None)

        self.web_app = self.web_application_class(handlers, **settings)
        self.http_server = None

    def add_endpoint(self, endpoint, prefix):
        """
        Add a SockJS endpoint to this server.

        :param endpoint: The :ref:`Endpoint` instance.
        :param prefix: The url prefix to use to add the endpoint to.
        """
        prefix = '/' + prefix.lstrip('/')

        if prefix in self.endpoints:
            raise ValueError('endpoint %r already defined' % (prefix,))

        self.endpoints[prefix] = endpoint

        if self.started:
            endpoint.start()

        self.web_app.wildcard_router.add_rules(endpoint.get_urls(prefix))

    def remove_endpoint(self, prefix):
        """
        Remove a SockJS endpoint from this server

        :param prefix: The prefix of the existing endpoint.
        """
        prefix = '/' + prefix.lstrip('/')

        if prefix not in self.endpoints:
            raise ValueError('endpoint %r not found' % (prefix,))

        endpoint = self.endpoints.pop(prefix)

        endpoint.stop()

    def start(self):
        """
        Start this server.
        """
        if self.started:
            return

        self.started = True

        for endpoint in self.endpoints.values():
            endpoint.start()

    def stop(self):
        """
        Stop this server.
        """
        if not self.started:
            return

        self.started = False

        if self.http_server:
            self.http_server.stop()
            self.http_server = None

        for endpoint in self.endpoints.values():
            endpoint.stop()

    def listen(self, port, address="", **kwargs):
        """
        Start accepting connections on a given port.

        :param port: The port to listen to.
        :param address: The optional host/ip addr to bind to. By default, binds
            to all available interfaces.
        """
        self.start()

        self.http_server = self.web_app.listen(port, address=address, **kwargs)

        return self.http_server
