"""
We should refactor this at some point to:

1. At least modularize into different subfolders for different parts of server
2. Try to create well typed interfaces based on graphql using codegen, so it can be verified with mypy
3. Split out core logic interacting with jupyter server from graphql endpoints part. Extract that out into `models.py` maybe.
"""

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
        super().__post_init__()
        query = QueryType()
        mutation = ariadne.MutationType()
        subscription = ariadne.SubscriptionType()

        query.set_field("execution", self.resolve_execution)

        # kernelspecs
        query.set_field("kernelspecs", self.resolve_kernelspecs)
        query.set_field("kernelspec", self.resolve_kernelspec)
        query.set_field("kernelspecByID", self.resolve_kernelspec_by_id)

        # Kernels
        mutation.set_field("startKernel", self.resolve_start_kernel)
        query.set_field("kernels", self.resolve_kernels)
        query.set_field("kernel", self.resolve_kernel)
        query.set_field("kernelByID", self.resolve_kernel_by_id)
        mutation.set_field("stopKernel", self.resolve_stop_kernel)
        mutation.set_field("interruptKernel", self.resolve_interrupt_kernel)
        mutation.set_field("restartKernel", self.resolve_restart_kernel)
        subscription.set_field(
            "kernelExecutionStateUpdated", self.resolve_kernel_execution_state_updated
        )
        subscription.set_source(
            "kernelExecutionStateUpdated",
            self.kernel_execution_state_generator,
        )
        subscription.set_field("kernelCreated", self.resolve_kernel_created)
        subscription.set_source(
            "kernelCreated",
            self.kernel_created_generator,
        )
        subscription.set_field("kernelDeleted", self.resolve_kernel_deleted)
        subscription.set_source(
            "kernelDeleted",
            self.kernel_deleted_generator,
        )

        execution = ObjectType("Execution")
        execution.set_field("displays", self.resolve_displays)

        # kernel_spec = ObjectType("KernelSpec")
        # kernel_spec.set_field("argv", self.resolve_kernelspec_argv)

        self.schema = make_executable_schema(
            GRAPHQL_SCHEMA_STR, [query, mutation, subscription, execution]
        )

        # Save factory on self, so we can access it for debugging when we just have access to schema
        self.schema.__factory__ = self  # type: ignore

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
            "kernel": await self.serialize_kernel(kernel_id),
            "clientMutationId": input.get("clientMutationId"),
        }

    async def resolve_kernels(self, _, info):
        return [
            await self.serialize_kernel(kernel_id)
            for kernel_id in self.kernel_manager.pinned_superclass.list_kernel_ids(
                self.kernel_manager
            )
        ]

    async def resolve_kernel(self, _, info, kernelID: str):
        return await self.serialize_kernel(kernelID)

    async def resolve_kernel_by_id(self, _, info, id: str):
        return await self.serialize_kernel(deserialize_id(id).name)

    async def resolve_stop_kernel(self, _, info, input):
        kernel_id = deserialize_id(input["id"]).name
        await jupyter_server.utils.ensure_async(
            self.kernel_manager.shutdown_kernel(kernel_id)
        )
        return {"clientMutationId": input.get("clientMutationId"), "id": input["id"]}

    async def resolve_interrupt_kernel(self, _, info, input):
        kernel_id = deserialize_id(input["id"]).name
        await jupyter_server.utils.ensure_async(
            self.kernel_manager.interrupt_kernel(kernel_id)
        )
        return {
            "clientMutationId": input.get("clientMutationId"),
            "kernel": self.serialize_kernel(kernel_id),
        }

    async def resolve_restart_kernel(self, _, info, input):
        kernel_id = deserialize_id(input["id"]).name
        await jupyter_server.utils.ensure_async(
            self.kernel_manager.restart_kernel(kernel_id)
        )
        return {
            "clientMutationId": input.get("clientMutationId"),
            "kernel": self.serialize_kernel(kernel_id),
        }

    def resolve_kernel_execution_state_updated(self, execution_state, info, id: str):
        kernel_id = deserialize_id(id).name
        return self.serialize_kernel(kernel_id, execution_state=execution_state)

    async def kernel_execution_state_generator(self, obj, info, id: str):
        kernel_id = deserialize_id(id).name
        # kernel is already deleted
        if kernel_id not in self.kernel_execution_state_updated:
            return
        with self.kernel_execution_state_updated[
            kernel_id
        ].subscribe() as execution_states:
            async for execution_state in execution_states:
                yield execution_state

    def resolve_kernel_created(self, kernel_id, info):
        return self.serialize_kernel(kernel_id)

    async def kernel_created_generator(self, obj, info):
        with self.kernel_added.subscribe() as kernel_ids:
            async for kernel_id in kernel_ids:
                yield kernel_id

    def resolve_kernel_deleted(self, kernel_id, info):
        return serialize_id("kernel", kernel_id)

    async def kernel_deleted_generator(self, obj, info):
        with self.kernel_deleted.subscribe() as kernel_ids:
            async for kernel_id in kernel_ids:
                yield kernel_id

    def resolve_execution(self, _, info: graphql.GraphQLResolveInfo, id, **kwargs):
        return {
            "id": id,
            "code": "some code",
            "status": {
                "__typename": "ExecutionStatePending",
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

    async def serialize_kernel(self, kernel_id, execution_state=None):
        kernel = self.kernel_manager._kernels[kernel_id]
        return {
            "id": serialize_id("kernel", kernel_id),
            "kernelID": kernel_id,
            "spec": await self.resolve_kernelspec(None, None, kernel.kernel_name),
            "lastActivity": jupyter_server._tz.isoformat(kernel.last_activity),
            "executionState": (execution_state or kernel.execution_state).upper(),
            "connections": self.kernel_manager._kernel_connections[kernel_id],
        }


def serialize_kernelspec(name: str, spec: dict) -> dict:
    return {
        "id": serialize_id("kernelspec", name),
        "name": name,
        "argv": spec["argv"],
        "displayName": spec["display_name"],
        "language": spec["language"],
        "interruptMode": spec.get("interrupt_mode", "SIGNAL"),
        "env": spec.get("env", {}),
        "metadata": spec.get("metadata", {}),
    }


def serialize_id(type, id):
    return f"{type}:{id}"


class TypeAndName(typing.NamedTuple):
    type: str
    name: str


def deserialize_id(id: str) -> TypeAndName:
    split = id.find(":")
    return TypeAndName(id[:split], id[split + 1 :])
