"""
Various session related exceptions.
"""


class SessionError(Exception):
    """
    Base exception class for session related errors
    """


class StateError(SessionError):
    """
    Any errors related to state operations use this error.
    """


class AlreadyOpenedError(StateError):
    """
    Raised when attempting to open an already opened session.
    """


class SessionClosed(StateError):
    """
    Raised when an attempt is made to attach a transport to a closed session.
    """


class SessionUnavailable(SessionError):
    """
    Raised when an attempt to bind a session to a transport fails because the
    session is in an unusable state.

    :ivar code: Code for error, see ``protocol``.
    :ivar reason: Reason for error, see ``protocol``.
    """

    def __init__(self, code, reason):
        self.code = code
        self.reason = reason


class TransportAlreadySet(SessionError):
    pass


class UnboundSessionError(SessionError):
    """
    Raised when an operation occurred to an session that has not been bound
    with a connection.
    """
