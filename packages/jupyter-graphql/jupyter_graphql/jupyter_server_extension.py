import tornado
import tornado.wsgi
import ariadne.wsgi
import ariadne.constants
import typing
from .schema import schema


# Pass in other settings to graphql playground
# https://github.com/prisma-labs/graphql-playground#properties
# https://github.com/prisma-labs/graphql-playground/issues/1073#issuecomment-526509499
# To get xsrf cookie
# https://blog.jupyter.org/security-release-jupyter-notebook-4-3-1-808e1f3bb5e2
NEW_PLAYGROUND_HTML = ariadne.constants.PLAYGROUND_HTML.replace(
    "// options as 'endpoint' belong here",
    r"""
settings: {
    'request.credentials': 'include',
    'editor.reuseHeaders': true,
},
tabs: [{
    endpoint: '/graphl/',
    query: '',
    headers: {
        "X-XSRFToken": document.cookie.match("\\b_xsrf=([^;]*)\\b")[1]
    }
}]
""".strip(),
)


class GraphQL(ariadne.wsgi.GraphQL):
    """
    Change graphql playground to support passing xref to POST requsts
    """

    def handle_get(self, start_response) -> typing.List[bytes]:
        super().handle_get(start_response)
        return [NEW_PLAYGROUND_HTML.encode("utf-8")]


# https://jupyter-server.readthedocs.io/en/latest/developers/extensions.html#distributing-a-server-extension
def _load_jupyter_server_extension(serverapp):
    """
    This function is called when the extension is loaded.
    """
    # https://github.com/bdarnell/django-tornado-demo/blob/master/testsite/tornado_main.py

    serverapp.web_app.add_handlers(
        r".*$",
        [
            (
                r".*",
                tornado.web.FallbackHandler,
                # https://www.tornadoweb.org/en/stable/web.html#tornado.web.FallbackHandler
                # https://ariadnegraphql.org/docs/wsgi
                {"fallback": tornado.wsgi.WSGIContainer(GraphQL(schema))},
            ),
        ],
    )

