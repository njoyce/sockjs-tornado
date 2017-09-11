import re

from sockjs.tornado import session


__all__ = [
    'BaseTransportMixin',
    'JSONCallbackMixin',
]


class BaseTransportMixin(object):
    """Base transport.

    Implements few methods that session expects to see in each transport.
    """

    name = 'override_me_please'

    def get_conn_info(self):
        """Return `ConnectionInfo` object from current transport"""
        return session.ConnectionInfo(self.request.remote_ip,
                                      self.request.cookies,
                                      self.request.arguments,
                                      self.request.headers,
                                      self.request.path)

    def session_closed(self):
        """Called by the session, when it gets closed"""
        pass


class JSONCallbackMixin(object):
    """
    Mixin for jsonp style callback
    """

    callback_regex = re.compile(r'^[a-zA-Z0-9-_]+$')

    def verify_callback(self, arg_name='c'):
        callback = self.get_argument(arg_name, None)

        if callback is None:
            self.write('"callback" parameter required')
            self.set_status(500)
            self.finish()

            return

        if not self.callback_regex.match(callback):
            self.write('invalid "callback" parameter')
            self.set_status(500)
            self.finish()

            return

        self.json_callback = callback
