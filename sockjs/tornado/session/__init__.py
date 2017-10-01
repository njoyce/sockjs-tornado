# -*- coding: utf-8 -*-
"""
    sockjs.tornado.session
    ~~~~~~~~~~~~~~~~~~~~~~

    SockJS session implementation.
"""

from sockjs.tornado.session import base
from sockjs.tornado.session.pool import SessionPool


__all__ = [
    'Session',
    'SessionPool',
]


class Session(base.BaseSession):
    """
    This is the standard session that holds all buffered messages in memory.
    """

    def __init__(self, *args, **kwargs):
        super(Session, self).__init__(*args, **kwargs)

        self.send_buffer = []

    def append_to_buffer(self, data):
        self.send_buffer.append(data)

    def get_buffer(self):
        return self.send_buffer

    def clear_buffer(self):
        self.send_buffer = []
