import graphql
from ariadne import QueryType, load_schema_from_path, make_executable_schema
from ariadne.objects import ObjectType
from .resources import GRAPHQL_SCHEMA_PATH

__all__ = ["schema"]

schema_str = load_schema_from_path(GRAPHQL_SCHEMA_PATH)

query = QueryType()

# execution_status = UnionType("ExecutionStatus")


# @execution_status.type_resolver
# def resolve_execution_status(obj, *_):
#     return "ExecutionStatusOK"


@query.field("execution")
def resolve_node(_, info: graphql.GraphQLResolveInfo, id, **kwargs):
    return {
        "id": id,
        "code": "some code",
        "status": {"__typename": "ExecutionStatusPending",},
        # "displays": [
        #     {"__typename": "DisplayData", "data": "JSON!", "metadata": "JSON!"}
        # ],
    }


execution = ObjectType("Execution")


@execution.field("displays")
def resolve_displays(context, info, first=None, last=None, before=None, after=None):

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


schema = make_executable_schema(schema_str, [query, execution])
