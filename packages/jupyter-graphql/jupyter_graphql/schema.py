import dataclasses
import typing

import ariadne
import graphql
import jupyter_client.kernelspec
import jupyter_server
import jupyter_server._tz
import jupyter_server.utils
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


# TODO: don't inherit from services
@dataclasses.dataclass
class SchemaFactory(Services):
    """
    Creates a schema using the services passed in as context.

    Uses a class so that all resolvers can access the services.
    """

    def __post_init__(self):
        query = QueryType()
        mutation = ariadne.MutationType()

        query.set_field("execution", self.resolve_execution)

        query.set_field("kernelspecs", self.resolve_kernelspecs)
        query.set_field("kernelspec", self.resolve_kernelspec)
        query.set_field("kernelspecByID", self.resolve_kernelspec_by_id)

        mutation.set_field("startKernel", self.resolve_start_kernel)
        query.set_field("kernels", self.resolve_kernels)

        execution = ObjectType("Execution")
        execution.set_field("displays", self.resolve_displays)

        # kernel_spec = ObjectType("KernelSpec")
        # kernel_spec.set_field("argv", self.resolve_kernelspec_argv)

        self.schema = make_executable_schema(
            GRAPHQL_SCHEMA_STR, [query, mutation, execution]
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
        spec: jupyter_client.kernelspec.KernelSpec = (
            await jupyter_server.utils.ensure_async(
                self.kernel_spec_manager.get_kernel_spec(name)
            )
        )
        return serialize_kernelspec(name, spec.to_dict())

    async def resolve_kernelspec_by_id(self, _, info, id):
        tp, name = deserialize_id(id)
        if tp != "kernelspec":
            return None
        return await self.resolve_kernelspec(_, info, name)

    async def resolve_start_kernel(self, _, info, input):
        kernel_id = await self.kernel_manager.start_kernel(
            kernel_name=input.get(
                "kernelspecName", self.kernel_manager.default_kernel_name
            ),
            path=input.get("path"),
        )

        return {
            "kernel": self.serialize_kernel(kernel_id),
            "clientMutationId": input["clientMutationId"],
        }

    def resolve_kernels(self, _, info):
        return [
            self.serialize_kernel(kernel_id)
            for kernel_id in self.kernel_manager.pinned_superclass.list_kernel_ids(
                self.kernel_manager
            )
        ]

    def resolve_execution(self, _, info: graphql.GraphQLResolveInfo, id, **kwargs):
        return {
            "id": id,
            "code": "some code",
            "status": {
                "__typename": "ExecutionStatusPending",
            },
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

    def serialize_kernel(self, kernel_id):
        kernel = self.kernel_manager._kernels[kernel_id]
        return {
            "id": serialize_id("kernel", kernel_id),
            "kernelID": kernel_id,
            "name": kernel.kernel_name,
            "lastActivity": jupyter_server._tz.isoformat(kernel.last_activity),
            "exeuctionState": kernel.execution_state.upper(),
            "connections": self.kernel_manager._kernel_connections[kernel_id],
        }


def serialize_kernelspec(name: str, spec: dict) -> dict:
    return {
        "id": serialize_id("kernelspec", name),
        "argv": spec["argv"],
        "displayName": spec["display_name"],
        "language": spec["language"],
        "interruptMode": spec.get("interrupt_mode", "SIGNAL"),
        "env": spec.get("env", {}),
        "metadata": spec.get("metadata", {}),
    }


def serialize_id(type, id):
    return f"{type}:{id}"


def deserialize_id(id: str) -> typing.Tuple[str, str]:
    """
    Returns type and id
    """
    split = id.find(":")
    return id[:split], id[split + 1 :]
