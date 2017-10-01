import datetime
import re

from tornado import web

__all__ = [
    'BaseHandler',
]


class CachingMixin(object):
    """
    Supports enabling/disabling caching for a response to a request.

    :cvar cache: Whether the response should be cached.
    :cvar CACHE_TIME: The length of time in seconds that the response should be
        cached.
    """
    cache = False

    CACHE_TIME = 31536000

    # Various helpers
    def enable_cache(self):
        """
        Enable client-side caching for the current request
        """
        self.set_header(
            'Cache-Control',
            'max-age=%d, public' % (self.CACHE_TIME,)
        )

        d = datetime.datetime.utcnow() + datetime.timedelta(
            seconds=self.CACHE_TIME
        )
        self.set_header('Expires', d.strftime('%a, %d %b %Y %H:%M:%S'))

        self.set_header('Access-Control-Max-Age', self.CACHE_TIME)

    def disable_cache(self):
        """
        Disable client-side cache for the current request
        """
        self.set_header(
            'Cache-Control',
            'no-store, no-cache, no-transform, must-revalidate, max-age=0'
        )


class CorsMixin(object):
    """
    Support for enabling CORS for a request.

    :cvar cors: Whether to add CORS related headers for a response and respond
        to an OPTIONS request.
    """
    cors = False

    def verify_origin(self):
        """
        Verify if request can be served
        """
        return True

    def preflight(self):
        """
        Handles request authentication
        """
        origin = self.request.headers.get('Origin', '*')
        self.set_header('Access-Control-Allow-Origin', origin)

        headers = self.request.headers.get('Access-Control-Request-Headers')

        if headers:
            self.set_header('Access-Control-Allow-Headers', headers)

        self.set_header('Access-Control-Allow-Credentials', 'true')


class CookieMixin(object):
    # whether or not the request affinity should be powered by cookie
    cookie = False

    COOKIE_NAME = 'JSESSIONID'

    def handle_cookie(self):
        """Handle JSESSIONID cookie logic"""
        # If JSESSIONID support is disabled in the settings, ignore cookie
        # logic
        if not self.sockjs_settings['cookie_affinity']:
            return

        cookie = self.cookies.get(self.COOKIE_NAME)

        if not cookie:
            cv = 'dummy'
        else:
            cv = cookie.value

        self.set_cookie(self.COOKIE_NAME, cv)


class ContentTypeMixin(object):
    content_type = None
    charset = 'UTF-8'

    def set_content_type(self):
        if not self.content_type:
            return

        self.set_header(
            'Content-Type',
            '%s; charset=%s' % (self.content_type, self.charset)
        )


class JSONCallbackMixin(object):
    """
    Mixin for jsonp style callback
    """

    ajax_callback = False
    ajax_query_param = 'c'

    callback_regex = re.compile(r'^[a-zA-Z0-9-_\.]+$')

    def verify_ajax_callback(self):
        callback = self.get_argument(self.ajax_query_param, None)

        if callback is None:
            raise web.HTTPError(500, '"callback" parameter required')

        if not self.callback_regex.match(callback):
            raise web.HTTPError(500, 'invalid "callback" parameter')

        self.js_callback = callback


class BaseHandler(web.RequestHandler, CachingMixin, CookieMixin, CorsMixin,
                  ContentTypeMixin, JSONCallbackMixin):
    """Base request handler with set of helpers."""

    def initialize(self, endpoint, stats, **kwargs):
        self.endpoint = endpoint
        self.stats = stats
        self.sockjs_settings = endpoint.settings

    # Statistics
    def prepare(self):
        """Increment connection count"""
        super(BaseHandler, self).prepare()

        if self.stats:
            self.stats.on_conn_opened()

    def set_default_headers(self):
        self.clear_header('Date')
        self.clear_header('Server')

    def on_connection_close(self):
        super(BaseHandler, self).on_connection_close()

        self.endpoint = None

        if self.stats:
            self.stats.on_conn_closed()

            self.stats = None

    def options(self, *args, **kwargs):
        """XHR cross-domain OPTIONS handler"""
        if not self.cors:
            raise web.HTTPError(405)

        self.response_preamble()

        if not self.verify_origin():
            raise web.HTTPError(403)

        self.set_status(204)

        allowed_methods = getattr(self, 'access_methods', 'OPTIONS, POST')
        self.enable_cache()
        self.set_header('Access-Control-Allow-Methods', allowed_methods)
        self.set_header('Allow', allowed_methods)

    def response_preamble(self):
        self.set_content_type()

        if self.cors:
            self.preflight()

        if self.cookie:
            self.handle_cookie()

        if self.cache:
            self.enable_cache()
        else:
            self.disable_cache()

        if self.ajax_callback:
            self.verify_ajax_callback()

    def safe_finish(self):
        if self._finished:
            return

        self.finish()
