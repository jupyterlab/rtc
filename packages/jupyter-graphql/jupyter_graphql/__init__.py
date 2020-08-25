"""
GraphQL server for Jupyter
"""


__version__ = "0.0.0"

# https://jupyter-server.readthedocs.io/en/latest/developers/extensions.html#distributing-a-server-extension
def _jupyter_server_extension_paths():
    return [{"module": "jupyter_graphql.jupyter_server_extension",}]
