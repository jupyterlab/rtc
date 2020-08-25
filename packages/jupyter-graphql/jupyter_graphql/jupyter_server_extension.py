import tornado
import tornado.wsgi
import ariadne.wsgi
from .schema import schema

# https://www.tornadoweb.org/en/stable/web.html#tornado.web.FallbackHandler
# https://ariadnegraphql.org/docs/wsgi
wsgi_app = tornado.wsgi.WSGIContainer(ariadne.wsgi.GraphQL(schema))
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

