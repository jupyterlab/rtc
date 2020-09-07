import dataclasses

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
