# Jupyter Real Time Collaboration ![.github/workflows/nodejs.yml](https://github.com/jupyterlab/rtc/workflows/.github/workflows/nodejs.yml/badge.svg)

This **Real Time Collaboration** monorepo contains current work on Real Time
collaboration for use in JupyterLab and other Jupyter applications.

## About the RTC project

We have today the following packages available:

- `packages/rtc-relay`: Patch relay server to synchronize patches for `packages/rtc-node`.
- `packages/rtc-node`: Real time collaboration client, builds on `@lumino/datastore`.
- `packages/rtc-jupyter`: Holds schema for Jupyter RTC tables that are used in server and client.
- `packages/rtc-jupyter-supernode`: Server to keep datastore in sync with jupyter server.

You can use those packages with examples:

- `packages/rtc-todo-example`: Example of simple todo app using relay server and node.
- `packages/rtc-jupyter-example`: Client to access Jupyter data.

It is currently in the planning stage, but eventually we see the repo containing
a number of additinal separate projects like:

- `src/jupyter_rtc_supernode_jupyter_extension`: Jupyter Server extension for running `packages/jupyter-rtc-supernode`.
- `src/rtc_relay_jupyter_extension`: Jupyter Server Extension for `src/rtc_relay`
- `packages/jupyterlab-rtc-client`: `packages/rtc-client` that connects over `src/rtc_relay_jupyter`.

### Project meeting schedule

We have a bi-weekly meeting call. Please come and join! All are welcome to come
and just listen or discuss any work related to this project. They are also
recorded and available here (TODO: create youtube channel). For the time, place,
and notes, see [this hackmd](https://hackmd.io/@_4xc7QhhSHKODRQn1uiulw/BkV24I3qL/edit).

We also use hackmd to set an agenda and to capture notes for these meetings.

### Learning pathway

We are striving to keep meetings productive and on topic. If you are joining
us for the first time or need a refresher about the project's scope, we
recommend reading the following documents:

- This `README.md`.
- The [Specification](./docs/source/developer/spec.md): We are working on creating a living specification for the protocol(s) created
here. We're doing our best but it may not always be totally in sync with explorations in the repo, until they are settled on.
- the [Design](./docs/source/developer/design.md) document.
- Current vision in grant proposal for CZI [`CZI-2020-proposal.md`](./docs/source/organisation/czi-2020-proposal.md).

## Development

Follow the instructions documented on the [Examples](./docs/source/developer/examples.rst)

## Contribute

We welcome any and all contributions and ideas here! This is a big task and we
will need as much help as we can get. The [`contributing`](./docs/source/organisation/contributing.md)
file contains more specific information.

### Current work on JupyterLab

Most of the work currently is living in [a PR to JupyterLab](https://github.com/jupyterlab/jupyterlab/pull/6871) and documented on [an issue](https://github.com/jupyterlab/jupyterlab/issues/5382) there.
