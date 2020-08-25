"""
GraphQL server for Jupyter
"""


from ariadne import load_schema_from_path, make_executable_schema, QueryType, UnionType
from ariadne.asgi import GraphQL
import importlib.resources
from starlette.applications import Starlette

__version__ = "0.0.0"

with importlib.resources.path("jupyter_graphql", "schema.graphql") as path:
    schema_str = load_schema_from_path(path)

query = QueryType()

# execution_status = UnionType("ExecutionStatus")


# @execution_status.type_resolver
# def resolve_execution_status(obj, *_):
#     return "ExecutionStatusOK"


@query.field("execution")
def resolve_node(_, info, id):
    return {
        "id": id,
        "code": "some code",
        "status": {"__typename": "ExecutionStatusPending",},
        "displays": [
            {"__typename": "DisplayData", "data": "JSON!", "metadata": "JSON!"}
        ],
    }


schema = make_executable_schema(schema_str, [query])

app = Starlette(debug=True)
app.mount("/graphql", GraphQL(schema, debug=True))
