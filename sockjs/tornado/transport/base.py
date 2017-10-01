from tornado import web

from sockjs.tornado import handler
from sockjs.tornado.log import transport as LOG
from sockjs.tornado.util import json_decode
from sockjs.tornado.util import str_to_bytes
from sockjs.tornado import proto

try:
    from urllib.parse import unquote_plus
except ImportError:
    from urllib import unquote_plus

__all__ = [
    'BaseTransport',
]


class ConnectionInfo(object):
    """Connection information object.

    Will be passed to the ``on_open`` handler of your connection class.

    Has few properties:

    `ip`
        Caller IP address
    `cookies`
        Collection of cookies
    `arguments`
        Collection of the query string arguments
    `headers`
        Collection of headers sent by the browser that established this
        connection
    `path`
        Request uri path
    """

    __slots__ = (
        'ip',
        'cookies',
        'arguments',
        'headers',
        'path',
    )

    def __init__(self, ip, cookies, arguments, headers, path):
        self.ip = ip
        self.cookies = cookies
        self.arguments = arguments
        self.headers = headers
        self.path = path

    def get_argument(self, name):
        """Return single argument by name"""
        val = self.arguments.get(name)

        if val:
            return val[0]

        return None

    def get_cookie(self, name):
        """Return single cookie by its name"""
        return self.cookies.get(name)

    def get_header(self, name):
        """Return single header by its name"""
        return self.headers.get(name)


class BaseTransport(handler.BaseHandler):
    """Implements few methods that session expects to see in each transport.
    """

    @property
    def name(self):
        raise NotImplementedError

    # set to true if the transport provides reading capabilities from the
    # connection (aka the client sends packets to the server)
    recvable = False
    # set to true if the transport provides writing capabilities from the
    # connection (aka the client receives packets from the server)
    sendable = False

    @property
    def verify_ip(self):
        return self.sockjs_settings['verify_ip']

    def prepare(self):
        super(BaseTransport, self).prepare()

        if not self.request.supports_http_1_1():
            conn = getattr(self.request, 'connection')

            conn.params.no_keep_alive = True
            conn.no_keep_alive = True

    def initialize(self, **kwargs):
        super(BaseTransport, self).initialize(**kwargs)

        self.session = None

    def check_xsrf_cookie(self):
        pass

    def get_conn_info(self):
        """Return `ConnectionInfo` object from current transport"""
        if not self.request:
            return None

        return ConnectionInfo(
            self.request.remote_ip,
            self.request.cookies,
            self.request.arguments,
            self.request.headers,
            self.request.path
        )

    def get_session(self, session_id):
        return self.endpoint.get_session(session_id)

    def create_session(self, session_id):
        return self.endpoint.create_session(session_id)

    def attach_session(self, session_id):
        session = self.get_session(session_id)

        if not session and self.sendable:
            session = self.create_session(session_id)

            session.set_conn_info(self.get_conn_info())

        if not session:
            return False

        return self.bind_session(session)

    def bind_session(self, session):
        if not self.verify_session(session):
            return False

        if session.closed:
            self.send_close_frame(session.close_reason)

            return False

        try:
            session.attach_transport(self)
        except (session.exc.TransportAlreadySet,
                session.exc.AlreadyOpenedError):
            self.send_close_frame((2010, "Another connection still open"))

            return False
        except session.exc.SessionClosed:
            self.send_close_frame((3000, "Go away!"))

            return False

        if session.closing:
            self.send_close_frame(session.close_reason)

            session.did_close()

            return False

        self.session = session

        if self.session.new:
            self.send_open_frame()

            # the act of sending the open frame may finish the request,
            # detaching the session. The lack of self. here is deliberate
            session.open()

        if not self.session:
            return False

        if self.session.closed:
            self.detach_session()

            return False

        if self.sendable:
            # flush any buffered messages to the client
            self.session.flush()

        return True

    def verify_session(self, session):
        if self.verify_ip:
            if session.conn_info.ip != self.request.remote_ip:
                self.send(
                    proto.close_frame(2010, "IP session mismatch")
                )

                return False

        return True

    def detach_session(self):
        session, self.session = self.session, None

        if session:
            session.detach_transport(self)
            self.safe_finish()

            session.set_expiry(self.sockjs_settings['disconnect_delay'])

    def session_closed(self, session):
        if self.sendable:
            self.send_close_frame(session.close_reason)

            session.did_close()

        self.detach_session()

    def send_open_frame(self):
        self.send(proto.OPEN)

    def send_close_frame(self, close_reason):
        self.send(proto.close_frame(*close_reason))

    def on_finish(self):
        self.detach_session()

    def send(self, data):
        """
        Send an encoded message to the client.
        """
        frame = self.encode_frame(data)

        self.send_raw(frame)

    def send_raw(self, data):
        self.write(str_to_bytes(data))
        self.flush()

    def encode_frame(self, data):
        return data

    def on_connection_close(self):
        super(BaseTransport, self).on_connection_close()

        if not self._finished:
            # the connection was aborted
            if self.session:
                self.session.close(1002, "Connection interrupted")

        self.detach_session()
        self.safe_finish()


class SingleRecvTransport(BaseTransport):
    """
    Transport to handle a single message received from the client.
    """

    recvable = True

    def decode_request(self, data):
        if not data:
            raise web.HTTPError(500, "Payload expected.")

        ctype = self.request.headers.get('Content-Type', '').lower()

        if ctype.startswith('application/x-www-form-urlencoded'):
            if not data.startswith('d='):
                raise web.HTTPError(500, "Payload expected.")

            data = unquote_plus(data[2:])

        if not data:
            raise web.HTTPError(500, "Payload expected.")

        # ensure that we are going to decode a list
        if data[0] != '[' and data[-1] != ']':
            raise web.HTTPError(500, "Broken JSON encoding.")

        try:
            return json_decode(data)
        except:
            raise web.HTTPError(500, "Broken JSON encoding.")

    def post(self, session_id):
        self.response_preamble()

        if not self.attach_session(session_id):
            raise web.HTTPError(404)

        data = self.request.body

        try:
            messages = self.decode_request(data)
        except:
            LOG.error('Failed to decode %r', data)

            raise

        try:
            self.session.dispatch(messages)
        except:
            LOG.exception('Failed to dispatch %r', messages)

            self.session.close()

            raise web.HTTPError(500)


class PollingTransport(BaseTransport):
    def send_raw(self, data):
        super(PollingTransport, self).send_raw(data)

        self.detach_session()
        self.safe_finish()


class StreamingTransport(BaseTransport):
    sendable = True

    def prepare(self):
        super(StreamingTransport, self).prepare()

        self.amount_limit = self.sockjs_settings['response_limit']

    def should_finish(self):
        """
        Check if transport should close long running connection after
        sending X bytes to the client.

        `data_len`
            Amount of data that was sent
        """
        if self.amount_limit <= 0:
            return True

        return False

    def send_raw(self, data):
        super(StreamingTransport, self).send_raw(data)

        self.amount_limit -= len(data)

        if not self.should_finish():
            return

        self.finish()
