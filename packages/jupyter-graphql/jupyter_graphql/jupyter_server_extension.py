import tornado
import tornado.wsgi
import ariadne.wsgi
import ariadne.constants
import typing
from .schema import schema


# https://github.com/prisma-labs/graphql-playground#properties
NEW_PLAYGROUND_HTML = ariadne.constants.PLAYGROUND_HTML.replace(
    "// options as 'endpoint' belong here",
    "settings: {'request.credentials': 'include'}",
)


class GraphQL(ariadne.wsgi.GraphQL):
    """
    Change graphql playground to support passing xref to POST requsts
    """

    def handle_get(self, start_response) -> typing.List[bytes]:
        super().handle_get(start_response)
        return [NEW_PLAYGROUND_HTML.encode("utf-8")]


# https://www.tornadoweb.org/en/stable/web.html#tornado.web.FallbackHandler
# https://ariadnegraphql.org/docs/wsgi
wsgi_app = tornado.wsgi.WSGIContainer(GraphQL(schema))
handlers = [
    (r".*", tornado.web.FallbackHandler, {"fallback": wsgi_app}),
]

# https://jupyter-server.readthedocs.io/en/latest/developers/extensions.html#distributing-a-server-extension
def _load_jupyter_server_extension(serverapp):
    """
    This function is called when the extension is loaded.
    """
    # https://github.com/bdarnell/django-tornado-demo/blob/master/testsite/tornado_main.py

    serverapp.web_app.add_handlers(".*$", handlers)

