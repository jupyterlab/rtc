import dataclasses
import asyncio
import typing
import time

import graphql
import pytest
from graphql.type.schema import GraphQLSchema

from .resources import *
from .schema import *


@pytest.fixture
def schema(serverapp):
    return create_schema(serverapp)


@dataclasses.dataclass
class QueryCaller:
    schema: GraphQLSchema

    async def __call__(self, query: str, expect_error=False, **variables):
        result = await graphql.graphql(self.schema, query, variable_values=variables)
        if expect_error:
            assert result.errors
        else:
            assert result.errors is None

        return result.data


@pytest.fixture
def query(schema):
    return QueryCaller(schema)


async def assert_eventually(
    condition: typing.Callable[[], typing.Awaitable[bool]], timeout=3.0
) -> None:
    """
    Waits until the `condition` function returns true, failing if it doesn't after `timeout` seconds.


    It repeatedly calls and awaits the `condition` function in a tight loop.
    """
    start_time = time.monotonic()
    while (time.monotonic() - start_time) <= timeout:
        if await condition():
            return
    raise RuntimeError(f"Timed out waiting for condition: {condition}")


async def test_schema_example(query):
    assert await query(EXAMPLE_QUERY_STR) == {
        "execution": {
            "code": "some code",
            "status": {"__typename": "ExecutionStatusPending"},
            "displays": {
                "pageInfo": {"hasNextPage": False},
                "edges": [{"node": {"data": "JSON! from hi"}}],
            },
        }
    }


async def test_kernelspecs(query):
    assert (
        await query(
            """query {
    kernelspecs {
        displayName
    }
    }"""
        )
        == {"kernelspecs": [{"displayName": "Python 3"}]}
    )


async def test_get_kernelspec(query):
    assert (
        await query(
            """query {
    kernelspec(name: "python3") {
        displayName
    }
    }"""
        )
        == {"kernelspec": {"displayName": "Python 3"}}
    )


async def test_get_kernelspec_not_found(query):
    assert (
        await query(
            """query {
    kernelspec(name: "not-here") {
        displayName
    }
    }""",
            expect_error=True,
        )
        == {"kernelspec": None}
    )


async def test_get_kernelspec_by_id(query):
    kernelspecs = await query(
        """query {
    kernelspecs {
        id,
        displayName
    }
    }"""
    )
    kernelspec = kernelspecs["kernelspecs"][0]
    kernelspec_id = kernelspec["id"]
    kernelspec_display_name = kernelspec["displayName"]

    assert (
        await query(
            """query($id: ID!) {
        kernelspecByID(id: $id) {
            displayName
        }
    }
    """,
            id=kernelspec_id,
        )
        == {"kernelspecByID": {"displayName": kernelspec_display_name}}
    )


async def test_create_list_get_kernels(query):
    assert (
        await query(
            """
            query {
                kernels {
                    id
                }
            }
            """
        )
        == {"kernels": []}
    )

    client_mutation_id = "some id!"
    start_kernel_payload = (
        await query(
            """
            mutation($clientMutationId: String!) {
                startKernel(input: {
                    clientMutationId: $clientMutationId
                }) {
                    clientMutationId,
                    kernel {
                        id,
                        kernelID,
                        name
                    }
                }
            }
            """,
            clientMutationId=client_mutation_id,
        )
    )["startKernel"]
    assert start_kernel_payload["clientMutationId"] == client_mutation_id

    id = start_kernel_payload["kernel"]["id"]
    kernel_id = start_kernel_payload["kernel"]["kernelID"]
    results = await query(
        """
        query($id: ID!, $kernelID: String!) {
            kernels {
                id,
                kernelID,
                name
            }
            kernel(kernelID: $kernelID) {
                id
            }
            kernelByID(id: $id) {
                id
            }

        }
        """,
        id=id,
        kernelID=kernel_id,
    )

    # Test listing kernels
    assert len(results["kernels"]) == 1
    assert results["kernels"][0]["id"] == id
    assert results["kernels"][0]["kernelID"] == kernel_id
    assert results["kernels"][0]["name"] == start_kernel_payload["kernel"]["name"]

    # test getting kernel
    assert results["kernel"]["id"] == id

    # test getting kernel by id
    assert results["kernelByID"]["id"] == id

    # Test restarting kernel
    assert (
        await query(
            """
            mutation($id: ID!, $clientMutationId: String!) {
                restartKernel(input: {
                    clientMutationId: $clientMutationId,
                    id: $id
                }) {
                    clientMutationId,
                    kernel {
                        kernelID,
                        executionState
                    }
                }
            }
            """,
            id=id,
            clientMutationId=client_mutation_id,
        )
        == {
            "restartKernel": {
                "clientMutationId": client_mutation_id,
                "kernel": {"kernelID": kernel_id, "executionState": "RESTARTING"},
            }
        }
    )

    # TODO: test interrupt

    # Test deleting
    assert (
        await query(
            """
            mutation($id: ID!, $clientMutationId: String!) {
                stopKernel(input: {
                    clientMutationId: clientMutationId,
                    id: id
                }) {
                    clientMutationId,
                    id
                }
            }
            """,
            id=id,
            clientMutationId=client_mutation_id,
        )
        == {"restartKernel": {"clientMutationId": client_mutation_id, "id": id}}
    )

    # Verify it's gone
    assert (
        await query(
            """
            query {
                kernels {
                    id
                }
            }
            """
        )
        == {"kernels": []}
    )