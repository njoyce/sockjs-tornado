from __future__ import absolute_import

from tornado import web

__all__ = [
    'HTTPDelegate',
    'Application',
]


class HTTPDelegate(web._HandlerDelegate):
    def execute(self):
        # this is a stripped down version of web.Application.execute - since
        handler = self.handler_class(
            self.application,
            self.request,
            **self.handler_kwargs
        )

        handler._execute(
            [],
            *self.path_args,
            **self.path_kwargs
        )


class Application(web.Application):
    def get_handler_delegate(self, request, target_class, target_kwargs=None,
                             path_args=None, path_kwargs=None):
        return HTTPDelegate(
            self,
            request,
            target_class,
            target_kwargs,
            path_args,
            path_kwargs
        )
