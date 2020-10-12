import typing

import ariadne
import graphql.type.schema
import pytest

from .assert_eventually import *
from .partial_curry import *
from .schema import *


@pytest.fixture
def schema(serverapp):
    return create_schema(serverapp)


def raise_errors_directly(error, debug: bool = False) -> dict:
    """
    error formatter that just raises errors directly, so we get full tracebacks
    """
    raise error


async def assert_results(results: typing.AsyncIterable[graphql.ExecutionResult]):
    async for res in results:
        assert not res.errors
        yield res.data


@pytest.fixture
@partial_curry("schema")
async def query(
    schema: graphql.type.schema.GraphQLSchema,
    query: str,
    expect_error=False,
    **variables,
):
    """
    if expect error is true, then will verify an error has been raised and return the data.

    Otherwise, raises a real error.
    """
    success, result = await ariadne.graphql(
        schema,
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


@pytest.fixture
@partial_curry("schema")
async def subscribe(
    schema: graphql.type.schema.GraphQLSchema,
    query: str,
    **variables,
) -> typing.AsyncIterable:
    success, result = await ariadne.subscribe(
        schema,
        {"query": query, "variables": variables},
        debug=True,
        error_formatter=raise_errors_directly,
    )
    assert success
    assert not isinstance(result, list)
    # Returns future of async iterable, so can await first to get subscription ready, then
    return assert_results(result)


@pytest.fixture
@partial_curry("query")
async def assert_kernel_state(query, id: str, state: str) -> None:
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
        == state
    )


@pytest.fixture
@partial_curry("assert_kernel_state")
async def assert_kernel_state_eventually(
    assert_kernel_state, id: str, state: str
) -> None:
    await assert_eventually(assert_kernel_state, args=[id, state])
