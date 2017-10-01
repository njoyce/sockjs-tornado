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


class ITransport(object):
    """
    This is an interface object containing documentation of what attributes
    and methods a transport must provide to interact correctly with a session.

    Don't use this in runtime :)
    """

    @property
    def recvable(self):
        """
        This property must be set to `True` if the transport is capable of
        receiving SockJS frames from the client.

        Must be set to `False` in all other cases.
        """

    @property
    def sendable(self):
        """
        This property must be set to `True` if the transport is capable of
        sending SockJS frames to the client.
        """


class StateMixin(object):
    """
    Mixin class to define all states that a session can be in.
    :ivar _state: What state this session is currently in. Valid values:
        - NEW: session is new and has not been ``opened`` yet.
        - OPEN: session has been opened and is in a usable state.
        - CLOSING: the session is closing and all that is left to do is flush
          the remaining messages.
        - CLOSED: a session has been closed successfully and is now ready for
          garbage collection.
    :ivar close_reason: A tuple that contains the code (int) and reason (bytes)
        as to why this session was closed. This attribute is only populated
        when the session moves in to a CLOSING/CLOSED state.
    """

    def __init__(self):
        self._state = NEW
        self.close_reason = None

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

        :param code: The websocket closing code. See
            https://tools.ietf.org/html/rfc6455#section-7.4.1 for valid values.
        :param reason: The human readable string of why the session was closed.
        """
        if self.closed:
            return

        self._state = CLOSING
        self.close_reason = (code, message)

        self.on_close()

    def did_close(self):
        """
        A session that is CLOSING must eventually be transitioned to CLOSED.

        This method does just that :)
        """
        self._state = CLOSED

    def on_open(self):
        """
        Called when the session has been opened. Must be called only once per
        session instance.

        Implemented in subclasses.
        """
        raise NotImplementedError

    def on_close(self):
        """
        Called ONCE when the session has transitioned from NEW/OPEN to
        CLOSING/CLOSED. Perform cleanup.

        Implemented in subclasses.
        """
        raise NotImplementedError


class TransportMixin(object):
    """
    Each SockJS session has a read and write transport. For bi-directional
    transports like websocket, this will the the same instance but for polling
    and long polling like xhr or jsonp, these are two separate handlers.

    :ivar send_transport: The transport that will send SockJS frames to the
        client. Must implement the `ITransport` interface.
    :ivar recv_transport: The transport that will receive SockJS frames from
        the client. Must implement the `ITransport` interface.
    """

    def __init__(self):
        self.send_transport = None
        self.recv_transport = None

    def attach_transport(self, transport):
        """
        Attach a transport to this session. A transport must implement the
        `ITransport` interface. If a transport is already attached then
        `exc.TransportAlreadySet` will be raised.

        :param transport: Implements the `ITransport` interface.
        """
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
        """
        Detach the transport from the session. This must be called when the
        transport connection is lost or goes away for some other reason.

        :param transport: Implements the `ITransport` interface.
        """
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
    Each session only exists for a limited period of time. If both the send AND
    recv transports are removed then the session is considered CLOSED.

    Since SockJS is a WebSocket emulation layer, there are polling transports
    available as a backup. Since these connections come and go, the session
    expiry must be updated at regular intervals otherwise it will be
    transitioned into a CLOSING/CLOSED state. SockJS supports heartbeats to
    keep the 'session' alive.

    :ivar expires_at: The absolute timestamp at which this session will expire.
    :ivar ttl: The number of seconds from the current time value that the
        session will expire.
    """

    def __init__(self, ttl, time_func=time.time):
        """
        :param ttl: This one should be obvious :)
        :param time_func: When called, returns the number of seconds since the
            epoch. Used for testing. Should not be supplied in all other
            scenarios.
        """
        self.ttl = ttl

        self.set_expiry(ttl, time_func=time_func)

    def touch(self, time_func=time.time):
        """
        Mark this session as alive - Do this by updating the `expires_at` to
        it's maximum value.

        :param time_func: When called, returns the number of seconds since the
            epoch. Used for testing. Should not be supplied in all other
            scenarios.
        """
        self.expires_at = time_func() + self.ttl

    def set_expiry(self, expires, time_func=time.time):
        """
        :param expires:
            - None/0: session will never expire.
            - int/long: seconds until the session expires.
            - datetime: absolute date/time that the session will expire.
        :param time_func: When called, returns the number of seconds since the
            epoch. Used for testing. Should not be supplied in all other
            scenarios.
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

        :param now: The time in seconds since the epoch against which the
            expiry of this session will be evaluated. If not supplied, the
            sytem time will be used.
        :param time_func: When called, returns the number of seconds since the
            epoch. Used for testing. Should not be supplied in all other
            scenarios.
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
        All session events will be dispatched to this object.
    :ivar conn_info: Pertinent information about the connection (ip addr etc.)
        :see:`sockjs.transport.ConnectionInfo`.
    """

    # helpful way of getting to the session exceptions.
    exc = exc

    def __init__(self, session_id, ttl):
        """
        :param session_id: A unique, random ascii bytestring that represents
            the id of the session. This must be unique per server.
        :param ttl: The ttl (:see:`ExpiryMixin.ttl`).
        """
        StateMixin.__init__(self)
        TransportMixin.__init__(self)
        ExpiryMixin.__init__(self, ttl)

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
        if self.conn:
            raise exc.SessionError('Session is already bound to a conn object')

        self.conn = conn

        self.touch()

    def set_conn_info(self, conn_info):
        self.conn_info = conn_info

    def on_open(self):
        """
        Called when the session has been opened.
        """
        if not self.conn:
            raise exc.UnboundSessionError

        if not self.conn_info:
            raise RuntimeError('on_open: Missing conn_info')

        self.touch()

        self.conn.session_opened(self.conn_info)

    def on_close(self):
        """
        Called when the session has been closed.
        """
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
