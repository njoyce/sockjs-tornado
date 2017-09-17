# -*- coding: utf-8 -*-
"""
    sockjs.tornado.session
    ~~~~~~~~~~~~~~~~~~~~~~

    SockJS session implementation.
"""

from sockjs.tornado.session.pool import SessionPool
from sockjs.tornado.session.base import BaseSession


__all__ = [
    'BaseSession',
    'SessionPool',
    'InMemorySession',
]


class InMemorySession(BaseSession):
    def __init__(self, *args, **kwargs):
        super(InMemorySession, self).__init__(*args, **kwargs)

        self.send_buffer = []

    def append_to_buffer(self, data):
        self.send_buffer.append(data)

    def get_buffer(self):
        return self.send_buffer

    def clear_buffer(self):
        self.send_buffer = []
