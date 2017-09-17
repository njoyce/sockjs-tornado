from datetime import datetime

import time

from sockjs.tornado import proto
from sockjs.tornado.log import session as LOG
from sockjs.tornado.session import exc


__all__ = [
    'BaseSession',
]

# Session states
# session has been newly created and has not completed opening handshakes
NEW = 0
# session is open and is ready to send/recv messages
OPEN = 1
# session is in the process of closing
CLOSING = 2
# session was closed cleanly
CLOSED = 3


class StateMixin(object):
    """
    :ivar _state: What state this session is currently in. Valid values:
        - NEW: session is new and has not been ``opened`` yet.
        - OPEN: session has been opened and is in a usable state.
        - CLOSING: the session is closing and all that is left to do is flush
          the remaining messages.
        - CLOSED: a session has been closed successfully and is now ready for
          garbage collection.
    """

    def __init__(self):
        self._state = NEW
        self.close_reason = None

    def __del__(self):
        try:
            if self.opened:
                self.close()
        except:
            # close() may fail if __init__ didn't complete
            pass

    @property
    def new(self):
        return self._state == NEW

    @property
    def opened(self):
        return self._state == OPEN

    @property
    def closing(self):
        return self._state == CLOSING

    @property
    def closed(self):
        return self._state in [CLOSING, CLOSED]

    @property
    def state(self):
        """
        Stringified version of the state
        """
        if self._state == NEW:
            return "new"

        if self._state == OPEN:
            return "open"

        if self._state == CLOSED:
            return "closed"

        if self._state == CLOSING:
            return "closing"

        return "<unknown>"

    @state.setter
    def state(self, value):
        self._state = value

    def open(self):
        """
        Ready this session for accepting/dispatching messages.
        """
        if not self.new:
            raise exc.AlreadyOpenedError

        self._state = OPEN

        self.on_open()

    def close(self, code=3000, message='Go away!'):
        """
        Close this session.
        """
        if self.closed:
            return

        self._state = CLOSING
        self.close_reason = (code, message)

        self.on_close()

    def did_close(self):
        self._state = CLOSED

    def on_open(self):
        raise NotImplementedError

    def on_close(self):
        raise NotImplementedError


class TransportMixin(object):
    """
    Each SockJS session has a read and write transport. For bi-directional
    transports like websocket, this will the the same instance but for polling
    and long polling like xhr or jsonp, these are two separate handlers.

    This mixin holds weak references to the transports so that if the
    underlying connection disappears, they will be gc'd and disappear.

    :ivar send_transport: The transport that will send SockJS frames to the
        client.
    :ivar recv_transport: The transport that will receive SockJS frames from
        the client.
    """

    def __init__(self):
        self.send_transport = None
        self.recv_transport = None

    def attach_transport(self, transport):
        if not (transport.recvable or transport.sendable):
            raise AssertionError('Cannot attach to %r' % (transport,))

        orig_send = self.send_transport
        orig_recv = self.recv_transport

        try:
            if transport.sendable:
                if self.send_transport:
                    raise exc.TransportAlreadySet

                self.send_transport = transport

            if transport.recvable:
                if self.recv_transport:
                    raise exc.TransportAlreadySet

                self.recv_transport = transport
        except:
            self.send_transport = orig_send
            self.recv_transport = orig_recv

            raise

    def detach_transport(self, transport):
        if not (transport.recvable or transport.sendable):
            raise AssertionError('Cannot deattach from %r' % (transport,))

        orig_send = self.send_transport
        orig_recv = self.recv_transport

        try:
            if transport.sendable:
                if self.send_transport:
                    if transport is not self.send_transport:
                        raise exc.TransportAlreadySet

                self.send_transport = None

            if transport.recvable:
                if self.recv_transport:
                    if transport is not self.recv_transport:
                        raise exc.TransportAlreadySet

                self.recv_transport = None
        except:
            self.send_transport = orig_send
            self.recv_transport = orig_recv

            raise


class ExpiryMixin(object):
    """
    :ivar expires_at: The timestamp at which this session will expire.
    :ivar ttl_interval: The value to set `expires_at` to as a delta to the
        current time.
    """

    def __init__(self, ttl, time_func=time.time):
        self.ttl = ttl

        self.set_expiry(ttl, time_func=time_func)

    def touch(self, time_func=time.time):
        """
        Bump the TTL of the session.
        """
        self.expires_at = time_func() + self.ttl

    def set_expiry(self, expires, time_func=time.time):
        """
        Possible values for expires and its effects:
         - None/0: session will never expire
         - int/long: seconds until the session expires
         - datetime: absolute date/time that the session will expire.
        """
        if not expires:
            self.expires_at = 0

            return

        if isinstance(expires, datetime):
            expires = time.mktime(expires.timetuple())

        if expires < 1e9:
            # delta
            expires += time_func()

        self.expires_at = expires

    def has_expired(self, now=None, time_func=time.time):
        """
        Whether this session has expired.
        """
        if not self.expires_at:
            return False

        return self.expires_at <= (now or time_func())


class BaseSession(StateMixin, TransportMixin, ExpiryMixin):
    """
    Base class for SockJS sessions. Provides a transport independent way to
    queue data frames from/to the client.

    :ivar session_id: The unique id of the session.
    :ivar conn: Connection object to which this session is bound. See ``bind``.
        All events will be dispatched to this object.
    """

    exc = exc

    def __init__(self, session_id, ttl_interval):
        StateMixin.__init__(self)
        TransportMixin.__init__(self)
        ExpiryMixin.__init__(self, ttl_interval)

        self.session_id = session_id
        self.conn = None
        self.conn_info = None

    def __repr__(self):
        handlers = ''

        if self.send_transport:
            handlers += 's'

        if self.recv_transport:
            handlers += 'r'

        return '<%s %s(%s) %s at 0x%x>' % (
            self.__class__.__name__,
            self.state,
            handlers,
            self.session_id,
            id(self)
        )

    def bind(self, conn):
        """
        Bind this session to the connection object.
        """
        self.conn = conn

        self.touch()

    def set_conn_info(self, conn_info):
        self.conn_info = conn_info

    def on_open(self):
        if not self.conn:
            raise exc.UnboundSessionError

        if not self.conn_info:
            raise RuntimeError('on_open: Missing conn_info')

        self.touch()

        self.conn.session_opened(self.conn_info)

    def on_close(self):
        if self.conn:
            # only dispatch the close event if we were previously opened
            try:
                self.conn.session_closed()
            except:
                LOG.exception('Failed to call on_close on %r', self.conn)
            finally:
                self.conn = None

        if self.send_transport:
            self.send_transport.session_closed(self)
            self.send_transport = None

        if self.recv_transport:
            self.recv_transport.session_closed(self)
            self.recv_transport = None

    def has_expired(self, *args, **kwargs):
        if self.closed:
            return True

        return super(BaseSession, self).has_expired(*args, **kwargs)

    def attach_transport(self, transport):
        if self._state == CLOSED:
            raise exc.SessionClosed(self._state)

        try:
            super(BaseSession, self).attach_transport(transport)
        except exc.TransportAlreadySet:
            raise exc.AlreadyOpenedError

    def dispatch(self, messages):
        """
        Called when the handler has received one or messages from the
        underlying transport and has decoded them successfully.

        :param messages: One or more messages. This can be of any type/value.
            It is up to the conn object to validate its content.
        """
        self.touch()

        for msg in messages:
            self.conn.on_message(msg)

    def send(self, message, raw=False):
        if not raw:
            message = proto.encode(message)

        self.send_frame(message)

    def send_multi(self, messages, raw=False):
        if raw:
            messages = ','.join(messages)
        else:
            messages = proto.encode(messages)

        self.send_frame(messages, multi=True)

    def send_frame(self, data, multi=True):
        if multi:
            frame = 'a[' + data + ']'
        else:
            frame = 'm' + data

        if not self.write(frame):
            self.append_to_buffer(data)

    def write(self, frame):
        if not self.send_transport:
            return False

        try:
            self.send_transport.send(frame)
        except IOError:
            return False

        self.touch()

        return True

    def flush(self):
        if not self.send_transport:
            return

        send_buffer = self.get_buffer()

        if not send_buffer:
            return

        self.send_multi(send_buffer, raw=True)
        self.clear_buffer()

    def send_heartbeat(self):
        self.write('h')

    def append_to_buffer(self, frame):
        raise NotImplementedError

    def get_buffer(self):
        raise NotImplementedError

    def clear_buffer(self):
        raise NotImplementedError
