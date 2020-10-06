import asyncio
import dataclasses
import time
import typing

import ariadne
import graphql.type.schema
import pytest

from .resources import *
from .schema import *
from .stopped import *


@pytest.fixture
def schema(serverapp):
    return create_schema(serverapp)


def raise_errors_directly(error, debug: bool = False) -> dict:
    """
    error formatter that just raises errors directly, so we get full tracebacks
    """
    raise error


@dataclasses.dataclass
class QueryCaller:
    schema: graphql.type.schema.GraphQLSchema

    async def __call__(self, query: str, expect_error=False, **variables):
        """
        if expect error is true, then will verify an error has been raised and return the data.

        Otherwise, raises a real error

        TODO: Is it bad practice to return an error for not finding something?
        """
        success, result = await ariadne.graphql(
            self.schema,
            {"query": query, "variables": variables},
            debug=True,
            error_formatter=raise_errors_directly
            if not expect_error
            else ariadne.format_error,
        )
        assert success
        if expect_error:
            assert result["errors"]
        return result["data"]


async def assert_results(results: typing.AsyncIterable[graphql.ExecutionResult]):
    async for res in results:
        assert not res.errors
        yield res.data


@dataclasses.dataclass
class SubscribeCaller:
    schema: graphql.type.schema.GraphQLSchema

    async def __call__(self, query: str, expect_error=False, **variables):
        success, result = await ariadne.subscribe(
            self.schema,
            {"query": query, "variables": variables},
            debug=True,
            error_formatter=raise_errors_directly,
        )
        assert success
        assert not isinstance(result, list)
        return assert_results(result)


@pytest.fixture
def query(schema):
    return QueryCaller(schema)


@pytest.fixture
def subscribe(schema):
    return SubscribeCaller(schema)


async def assert_eventually(
    callback: typing.Callable[[], typing.Awaitable[None]], timeout=5.0, wait=0.1
) -> None:
    """
    Waits until the `callback` function doesn't raise an exception, failing if it doesn't after `timeout` seconds.

    It repeatedly calls and awaits the `condition` function in a tight loop.
    """
    start_time = time.monotonic()
    n = 0
    while True:
        try:
            await callback()
        except Exception:
            n += 1
            elapsed_time = time.monotonic() - start_time
            if elapsed_time > timeout:
                raise AssertionError(
                    f"{callback} did not succeed after {timeout} seconds, failing {n} times."
                )
            await asyncio.sleep(wait)
        else:
            return


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


async def test_kernels_mutations(query):
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

    start_kernel_payload = (
        await query(
            """
            mutation {
                startKernel(input: {}) {
                    kernel {
                        id,
                        spec {
                            name
                        }
                    }
                }
            }
            """,
        )
    )["startKernel"]

    id = start_kernel_payload["kernel"]["id"]
    results = await query(
        """
        query($id: ID!) {
            kernels {
                id,
                spec {
                    name
                }
            }
            kernel(id: $id) {
                id
                info {
                    implementation
                }
            }

        }
        """,
        id=id,
    )

    # Test listing kernels
    assert len(results["kernels"]) == 1
    assert results["kernels"][0]["id"] == id
    assert results["kernels"][0]["spec"] == start_kernel_payload["kernel"]["spec"]

    # test getting kernel
    assert results["kernel"]["id"] == id
    assert results["kernel"]["info"]["implementation"] == "ipython"

    # TODO: should probably wait till idle
    # if this is resolved https://github.com/jupyter/jupyter_server/issues/305
    # await assert_eventually(is_idle)

    # Test restarting kernel
    assert (
        await query(
            """
            mutation($id: ID!) {
                restartKernel(input: {
                    id: $id
                }) {
                    kernel {
                        id,
                        executionState
                    }
                }
            }
            """,
            id=id,
        )
        == {
            "restartKernel": {
                "kernel": {"id": id, "executionState": "STARTING"},
            }
        }
    )

    # Wait for it to be startedd
    async def is_restarting() -> None:
        assert (
            (
                await query(
                    """
                    query($id: ID!) {
                        kernel(id: $id) {
                            executionState
                        }
                    }
                    """,
                    id=id,
                )
            )["kernel"]["executionState"]
            == "RESTARTING"
        )

    async def is_idle() -> None:
        assert (
            (
                await query(
                    """
                    query($id: ID!) {
                        kernel(id: $id) {
                            executionState
                        }
                    }
                    """,
                    id=id,
                )
            )["kernel"]["executionState"]
            == "IDLE"
        )

    # Should wait for restarting once this is resolved
    # https://github.com/jupyter/jupyter_client/issues/578
    # await assert_eventually(is_restarting)
    await assert_eventually(is_idle)

    # TODO: test interrupt

    # Test deleting
    assert (
        await query(
            """
            mutation($id: ID!) {
                stopKernel(input: {
                    id: $id
                }) {
                    id
                }
            }
            """,
            id=id,
        )
        == {"stopKernel": {"id": id}}
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


T = typing.TypeVar("T")
V = typing.TypeVar("V")


async def collect_async_iterable(
    iterable: typing.AsyncIterable[T],
    mapping_fn: typing.Callable[[T], V],
    items: typing.List[typing.Union[V, Stopped]],
    started: asyncio.Event,
) -> None:
    started.set()
    async for item in iterable:
        items.append(mapping_fn(item))
    items.append(_stopped)


async def async_iterable_to_list(
    iterable: typing.AsyncIterable[T],
    mapping_fn: typing.Callable[[T], V],
) -> typing.List[typing.Union[V, Stopped]]:
    """
    Turns an async iterable into a list that is updated in another coroutine.

    Waits for that coroutine to start before returnign
    """
    items: typing.List[typing.Union[V, Stopped]] = []
    started = asyncio.Event()
    asyncio.create_task(
        collect_async_iterable(
            iterable,
            mapping_fn,
            items,
            started,
        )
    )
    await started.wait()
    return items


async def test_kernels_subscriptions(query, subscribe):
    kernel_created_ids = await async_iterable_to_list(
        await subscribe("subscription { kernelCreated { id } }"),
        lambda r: r["kernelCreated"]["id"],
    )
    kernel_deleted_ids = await async_iterable_to_list(
        await subscribe("subscription { kernelDeleted }"),
        lambda r: r["kernelDeleted"],
    )

    assert kernel_created_ids == []
    assert kernel_deleted_ids == []
    id = (
        await query(
            """
            mutation {
                startKernel(input: {}) {
                    kernel {
                        id
                    }
                }
            }
            """,
        )
    )["startKernel"]["kernel"]["id"]

    kernel_execution_states = await async_iterable_to_list(
        await subscribe(
            "subscription($id: ID!) { kernelExecutionStateUpdated(id: $id) { executionState } }",
            id=id,
        ),
        lambda r: r["kernelExecutionStateUpdated"]["executionState"],
    )

    assert kernel_execution_states == []

    async def assert_kernel_created():
        assert kernel_created_ids == [id]

    async def assert_kernel_status_starting():
        # Sometimes we capture starting, sometimes not, non deterministic
        assert kernel_execution_states == ["STARTING"]

    # Verify that kernel was started
    await assert_eventually(assert_kernel_created)

    assert kernel_deleted_ids == []
    # await assert_eventually(assert_kernel_status_starting)

    # Try restating and verify statuses update

    await query(
        """
        mutation($id: ID!) {
            restartKernel(input: {
                id: $id
            }) {
                kernel {
                    id
                }
            }
        }
        """,
        id=id,
    )

    async def assert_kernel_statuses_busy_idle():
        # Sometimes we capture starting, sometimes not, non deterministic
        assert (kernel_execution_states == ["STARTING", "BUSY", "IDLE"]) or (
            kernel_execution_states == ["BUSY", "IDLE"]
        )

    await assert_kernel_created()
    assert kernel_deleted_ids == []
    await assert_eventually(assert_kernel_statuses_busy_idle)

    # Now stop and verify it is at stopped
    await query(
        """
        mutation($id: ID!) {
            stopKernel(input: {
                id: $id
            }) {
                id
            }
        }
        """,
        id=id,
    )

    async def assert_kernel_stopped():
        assert kernel_deleted_ids == [id]

    async def assert_kernel_statuses_stopped():
        assert (
            kernel_execution_states
            == [
                "STARTING",
                "BUSY",
                "IDLE",
                _stopped,
            ]
            or kernel_execution_states == ["BUSY", "IDLE", _stopped]
        )

    await assert_eventually(assert_kernel_stopped)
    await assert_eventually(assert_kernel_statuses_stopped)
    await assert_kernel_created()
