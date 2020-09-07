import graphql
import pytest

from .resources import *
from .schema import *


@pytest.fixture
def schema(serverapp):
    return create_schema(serverapp)


async def test_schema_example(schema):
    result = await graphql.graphql(schema, EXAMPLE_QUERY_STR)
    assert result.errors is None
    assert result.data == {
        "execution": {
            "code": "some code",
            "status": {"__typename": "ExecutionStatusPending"},
            "displays": {
                "pageInfo": {"hasNextPage": False},
                "edges": [{"node": {"data": "JSON! from hi"}}],
            },
        }
    }


async def test_kernelspecs(schema):
    result = await graphql.graphql(
        schema,
        """query {
  kernelspecs {
    displayName
  }
}""",
    )

    assert result.errors is None
    assert result.data == {"kernelspecs": [{"displayName": "Python 3"}]}


async def test_get_kernelspec(schema):
    result = await graphql.graphql(
        schema,
        """query {
  kernelspec(name: "python3") {
    displayName
  }
}""",
    )

    assert result.errors is None
    assert result.data == {"kernelspec": {"displayName": "Python 3"}}
