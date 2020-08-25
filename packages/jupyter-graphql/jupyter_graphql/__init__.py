"""
GraphQL server for Jupyter
"""


from ariadne import load_schema_from_path, make_executable_schema
from ariadne.asgi import GraphQL
import importlib.resources
from starlette.applications import Starlette

__version__ = "0.0.0"

with importlib.resources.path("jupyter_graphql", "schema.graphql") as path:
    schema = load_schema_from_path(path)

app = Starlette(debug=True)
app.mount("/graphql", GraphQL(schema, debug=True))
