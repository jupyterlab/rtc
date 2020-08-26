import importlib.resources

__all__ = ["GRAPHQL_SCHEMA_PATH", "EXAMPLE_QUERY_STR"]
with importlib.resources.path("jupyter_graphql", "schema.graphql") as path:
    GRAPHQL_SCHEMA_PATH = path


EXAMPLE_QUERY_STR = importlib.resources.read_text(
    "jupyter_graphql", "example_query.graphql"
)
