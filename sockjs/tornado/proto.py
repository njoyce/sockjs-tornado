"""
SockJS protocol related functions
"""

from sockjs.tornado.util import json_encode, json_decode

# Protocol handlers
OPEN = 'o'
DISCONNECT = 'c'
MESSAGE = 'm'
HEARTBEAT = 'h'


def close_frame(code, reason):
    """Return SockJS packet with code and close reason

    `code`
        Closing code
    `reason`
        Closing reason
    """
    return 'c[%d,"%s"]' % (code, reason)


encode = json_encode
decode = json_decode
