# Jupyter GraphQL

GraphQL powered Jupyter server, that exposes a stateful representation of the executions.

## Development

```bash
pip install flit
flit install --symlink

# To start the server:
# https://github.com/jupyter/jupyter_server/tree/master/examples/simple#extension-1
jupyter server --ServerApp.jpserver_extensions="{'jupyter_graphql': True}" --ServerApp.tornado_settings="{'debug': True}"
# Open GraphQL inspector
open http://127.0.0.1:8888/graphql/

# To run tests:
pytest jupyter_graphql

# To check types:
mypy jupyter_graphql

# To format code:
isort jupyter_graphql
black jupyter_graphql
```

## Goals

The goal here is to provide a Jupyter server which contains the state of all executions. So clients, instead of connecting to websockets or kernels directly, will send requests like “execute this code on this kernel” and they can listen for responses to the data model, which contains all the outputs for that execution request.

By moving this state from the client to the server, we can make it easier to synchronize between different clients.

In the data model should be a view of all notebooks, all their cells, and all their executions.

It should also have all kernels and all their executions.

## Implementation

We choose to implement this in Python, to make it the most accessible to install for existing Jupyter users.

We also choose to make using GraphQL because there is a large community there working on specifying these sorts of problems. The real end result here is not the implementation, but the GraphQL spec. This will let any other backend implement the same spec. And GraphQL is a community that is working to maintain these sorts of specs, so we should work with them.

We chose to use [Adriadne](https://ariadnegraphql.org/), because it is a schema first Python GraphQL implementation is popular and supports subscriptions.

[Tartiflette](https://tartiflette.io/) was also attractive but seemed less used.
