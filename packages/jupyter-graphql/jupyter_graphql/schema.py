import dataclasses

import graphql
import jupyter_server
import jupyter_server.utils
from ariadne import QueryType, load_schema_from_path, make_executable_schema
from ariadne.objects import ObjectType
from graphql.type.schema import GraphQLSchema
import jupyter_client.kernelspec

from .resources import GRAPHQL_SCHEMA_PATH
from .services import Services

__all__ = ["create_schema"]

GRAPHQL_SCHEMA_STR = load_schema_from_path(str(GRAPHQL_SCHEMA_PATH))


def create_schema(serverapp: jupyter_server.serverapp.ServerApp) -> GraphQLSchema:
    """
    Create a GraphQL schema with resolvers hooked up to the services
    """
    return SchemaFactory.from_server_app(serverapp).schema


# TODO: don't inherit from services
@dataclasses.dataclass
class SchemaFactory(Services):
    """
    Creates a schema using the services passed in as context.

    Uses a class so that all resolvers can access the services.
    """

    def __post_init__(self):
        query = QueryType()
        query.set_field("execution", self.resolve_execution)
        query.set_field("kernelspecs", self.resolve_kernelspecs)
        query.set_field("kernelspec", self.resolve_kernelspec)

        execution = ObjectType("Execution")
        execution.set_field("displays", self.resolve_displays)

        kernel_spec = ObjectType("KernelSpec")
        # kernel_spec.set_field("argv", self.resolve_kernelspec_argv)

        self.schema = make_executable_schema(
            GRAPHQL_SCHEMA_STR, [query, execution, kernel_spec]
        )

    # If we need a bunch of fields from a kernelspec, how to group them as one resolve?
    # So that we only hit filesystem once?
    async def resolve_kernelspecs(self, _, info):
        specs = await jupyter_server.utils.ensure_async(
            self.kernel_spec_manager.get_all_specs()
        )
        return [
            serialize_kernelspec(name, spec["spec"]) for name, spec in specs.items()
        ]

    async def resolve_kernelspec(self, _, info, name):
        spec: jupyter_client.kernelspec.KernelSpec = await jupyter_server.utils.ensure_async(
            self.kernel_spec_manager.get_kernel_spec(name)
        )
        return serialize_kernelspec(name, spec.to_dict())

    def resolve_execution(self, _, info: graphql.GraphQLResolveInfo, id, **kwargs):
        return {
            "id": id,
            "code": "some code",
            "status": {"__typename": "ExecutionStatusPending",},
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


def serialize_kernelspec(name: str, spec: dict) -> dict:
    return {
        "id": f"kernelspec:{name}",
        "argv": spec["argv"],
        "displayName": spec["display_name"],
        "language": spec["language"],
        "interruptMode": spec.get("interrupt_mode", "SIGNAL"),
        "env": spec.get("env", {}),
        "metadata": spec.get("metadata", {}),
    }

