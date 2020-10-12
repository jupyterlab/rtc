import asyncio
import time
import typing

__all__ = ["assert_eventually"]


async def assert_eventually(
    callback: typing.Callable[..., typing.Awaitable[None]],
    timeout=2.0,
    wait=0.1,
    args: list = [],
    kwargs: dict = {},
) -> None:
    """
    Waits until the `callback` function doesn't raise an exception, failing if it doesn't after `timeout` seconds.

    It repeatedly calls and awaits the `condition` function in a tight loop.
    """
    start_time = time.monotonic()
    n = 0
    while True:
        try:
            await callback(*args, **kwargs)
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
