"""
Convenience wrapper around the Python world of json encoding and decoding,
looking for the fastest library implementation first and then falling back
to stdlib if necessary.
"""

from tornado.log import gen_log as LOG

try:
    import ujson as json

    LOG.debug('sockjs.tornado will use ujson module')
except ImportError:
    try:
        import simplejson as json

        LOG.debug('sockjs.tornado will use simplejson module')
    except ImportError:
        import json

        LOG.debug('sockjs.tornado will use json module')


__all__ = [
    'json_encode',
    'json_decode',
]


# ujson will not accept separators as part of the dumps call
try:
    json.dumps({}, separators=(',', ':'))
except TypeError:
    json_encode = json.dumps
else:
    dumps = json.dumps

    def json_encode(data):
        return dumps(data, separators=(',', ':'))


json_decode = json.loads
