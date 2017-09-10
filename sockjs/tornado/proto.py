# -*- coding: utf-8 -*-
"""
    sockjs.tornado.proto
    ~~~~~~~~~~~~~~~~~~~~

    SockJS protocol related functions
"""

# Protocol handlers
CONNECT = 'o'
DISCONNECT = 'c'
MESSAGE = 'm'
HEARTBEAT = 'h'


# Various protocol helpers
def disconnect(code, reason):
    """Return SockJS packet with code and close reason

    `code`
        Closing code
    `reason`
        Closing reason
    """
    return 'c[%d,"%s"]' % (code, reason)
