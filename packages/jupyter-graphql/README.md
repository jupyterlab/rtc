# Jupyter GraphQL

GraphQL powered Jupyter server, that exposes a stateful representation of the executions.

## Development

```bash
pip install flit
flit install --symlink
# https://github.com/jupyter/jupyter_server/tree/master/examples/simple#extension-1
jupyter server --ServerApp.jpserver_extensions="{'jupyter_graphql': True}" --ServerApp.tornado_settings="{'debug': True}"
# Open GraphQL inspector
open http://127.0.0.1:8888/graphql/
```

## Goals

The goal here is to provide a Jupyter server which contains the the state of all executions. So clients, instead of connecting to websockets or kernels directly, will send requests like "execute this code on this kernel" and they can listen for responses to the data model, which contains all the outputs for that execution request.

By moving this state from the client to the server, we can make it easier to synchronize between different clients.

In the data model should be a view of all notebooks, all their cells, and all their executions.

It should also have all kernels and all their executions.

## Implementation

We choose to implement this in Python, to make it the most accessible to install for existing Jupyter users.

We also choose to make using GraphQL because there is a large community there working on specifying these sorts of problems. The real end result here is not the implementation, but the GraphQL spec. This will let any other backend implement the same spec. And GrahpQL is a community that is working to maintain these sorts of specs, so we should work with them.

There are a variety of existing Python GraphQL tools. The most popular is [Graphene Python](https://docs.graphene-python.org/en/latest/quickstart/). However, it has a few "issues" that I see:

1. The first is that it is Python DSL first, schema second. This obscures the underlying GraphQL schema you are generating.
2. It also doesn't work with MyPy compatible type annotations (https://github.com/graphql-python/graphene/issues/729)
3. It doesn't support subscriptions with fastapi/starlette (https://github.com/tiangolo/fastapi/issues/823)

There are two other Python frameworks that fix issues 1 and 3, [adriadne](https://ariadnegraphql.org/) and [tartiflette](https://tartiflette.io/). See https://ariadnegraphql.org/docs/starlette-integration.html and https://florimond.dev/blog/articles/2019/07/introducing-tartiflette-starlette/.

Tartiflatte wraps [`libgraphqlparser`](https://github.com/graphql/libgraphqlparser) and adriadne uses [`graphql-core`](https://github.com/graphql-python/graphql-core) version 3 (was called `graphql-core-next`).

They look relatively similar, and for this project at least initially the idea will be to use adriadne, because it seems slightly more popular.

## Schema Generation

We are also [Postgraphile](https://www.graphile.org/postgraphile/) to generate some initial schemas. It is helping me understand how to move from a relational mapping to GraphQL queries and mutations.
