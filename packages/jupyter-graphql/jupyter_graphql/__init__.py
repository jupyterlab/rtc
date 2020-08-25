"""
GraphQL server for Jupyter
"""


from ariadne import load_schema_from_path, make_executable_schema, QueryType
from ariadne.asgi import GraphQL
import importlib.resources
from starlette.applications import Starlette

__version__ = "0.0.0"

with importlib.resources.path("jupyter_graphql", "schema.graphql") as path:
    schema_str = load_schema_from_path(path)

query = QueryType()


@query.field("hello")
def resolve_hello(_, info):
    request = info.context["request"]
    user_agent = request.headers.get("user-agent", "guest")
    return "Hello, %s!" % user_agent


schema = make_executable_schema(schema_str, query)

app = Starlette(debug=True)
app.mount("/graphql", GraphQL(schema, debug=True))
