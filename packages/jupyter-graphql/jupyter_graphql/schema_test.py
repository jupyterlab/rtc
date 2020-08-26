import ariadne
import graphql
from .schema import *
from .resources import *


def test_schema_example():

    result = graphql.graphql_sync(schema, EXAMPLE_QUERY_STR)
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
