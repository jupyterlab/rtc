import asyncio
import json

import IPython.display
import jupyter_server.serverapp
import pytest

# Must delete instance to make a new one
jupyter_server.serverapp.ServerApp._instance = None
__all__ = ["q", "s"]
q = None
_subscribe = None


def s(*args, **kwargs):
    asyncio.create_task(inner(*args, **kwargs))


async def inner(*args, **kwargs):
    results = []
    IPython.display
    handle = IPython.display.display("...waiting", display_id=True)
    async for res in await _subscribe(*args, **kwargs):  # type: ignore
        results.append(res)
        handle.update(results)


def test_stuff(query, subscribe):
    global q, _subscribe
    q = query
    _subscribe = subscribe

    # global _fixture_value
    # fixturedef = request._get_active_fixturedef(_fixture_name)
    # fixturedef._finalizer = []  # disable fixture teardown
    # _fixture_value = fixturedef.cached_result[0]


pytest.main(["-qq", __file__])
