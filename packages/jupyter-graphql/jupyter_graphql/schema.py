import dataclasses

import ariadne
import graphql
import jupyter_server
from ariadne import QueryType, load_schema_from_path, make_executable_schema
from ariadne.objects import ObjectType
from graphql.type.schema import GraphQLSchema

from .resources import GRAPHQL_SCHEMA_PATH
from .services import Services

__all__ = ["create_schema"]

GRAPHQL_SCHEMA_STR = load_schema_from_path(str(GRAPHQL_SCHEMA_PATH))


def create_schema(serverapp: jupyter_server.serverapp.ServerApp) -> GraphQLSchema:
    """
    Create a GraphQL schema with resolvers hooked up to the services
    """
    return SchemaFactory.from_server_app(serverapp).schema


@dataclasses.dataclass
class SchemaFactory(Services):
    """
    Creates a schema using the services passed in as context.

    Uses a class so that all resolvers can access the services.
    """

    def __post_init__(self):
        query = QueryType()
        execution = ObjectType("Execution")

        query.set_field("execution", self.resolve_execution)
        execution.set_field("displays", self.resolve_displays)
        self.schema = make_executable_schema(GRAPHQL_SCHEMA_STR, [query, execution])

    def resolve_execution(self, _, info: graphql.GraphQLResolveInfo, id, **kwargs):
        return {
            "id": id,
            "code": "some code",
            "status": {"__typename": "ExecutionStatusPending",},
            # "displays": [
            #     {"__typename": "DisplayData", "data": "JSON!", "metadata": "JSON!"}
            # ],
        }

    def resolve_displays(
        self, context, info, first=None, last=None, before=None, after=None
    ):
        return {
            "pageInfo": {"hasNextPage": False},
            "edges": [
                {
                    "cursor": "hii",
                    "node": {
                        "__typename": "DisplayData",
                        "data": f"JSON! from {context['id']}",
                        "metadata": "JSON!",
                    },
                }
            ],
        }
