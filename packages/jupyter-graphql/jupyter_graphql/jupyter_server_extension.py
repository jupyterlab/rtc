import json

import ariadne.asgi
import ariadne.constants
import jupyter_server.serverapp
from jupyter_server import serverapp

from .Ariadneapp import GraphQLHandler
from .resources import EXAMPLE_QUERY_STR
from .schema import create_schema

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
    endpoint: '/graphql/',
    query: <QUERY>,
    headers: {
        "X-XSRFToken": document.cookie.match("\\b_xsrf=([^;]*)\\b")[1]
    }
}]
""".replace(
        "<QUERY>", json.dumps(EXAMPLE_QUERY_STR)
    ).strip(),
)


# https://jupyter-server.readthedocs.io/en/latest/developers/extensions.html#distributing-a-server-extension
def _load_jupyter_server_extension(serverapp: jupyter_server.serverapp.ServerApp):
    """
    This function is called when the extension is loaded.
    """
    # https://github.com/bdarnell/django-tornado-demo/blob/master/testsite/tornado_main.py
    serverapp.web_app.add_handlers(
        r".*$",
        [
            (
                f"/graphql/?",
                GraphQLHandler,
                {
                    "graphql_app": ariadne.asgi.GraphQL(create_schema(serverapp)),
                    "playground_html": NEW_PLAYGROUND_HTML,
                },
            ),
        ],
    )
