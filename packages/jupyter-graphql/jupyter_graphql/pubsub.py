from __future__ import annotations

import asyncio
import dataclasses
import enum
import types
import typing

__all__ = ["PubSub"]

from .stopped import *

T = typing.TypeVar("T")


# Sentinel to signal no last value
# https://www.python.org/dev/peps/pep-0484/#support-for-singleton-types-in-unions
class NoValue(enum.Enum):
    token = 0


_no_value = NoValue.token


@dataclasses.dataclass
class PubSub(typing.Generic[T]):
    """
    One to many async communication, assuming we are pushing synchronously and pulling async.

    >>> p = PubSub()

    To publish an event:

    >>> p.publish("event")

    To listen for events:

    >>> with p.subscibe() as events:
    ...     async for event in events:
    ...         print(event)

    To end all iterators:

    >>> p.stop()

    After this, any attempt to publish will raise an error.

    Any generator created with a stopped pubsub will immediatly end.

    To get the last value:

    >>> p.last

    It must use a a context manager so we can properly cleanup after.
    If we had async iterator cleanup functions we wouldn't need this:
    https://www.python.org/dev/peps/pep-0533/
    """

    stopped: bool = False
    iterators: typing.List[PubSubAsyncIterator[T]] = dataclasses.field(
        default_factory=list
    )
    _last: typing.Union[T, NoValue] = _no_value

    @property
    def last(self) -> T:
        if isinstance(self._last, NoValue):
            raise ValueError("no last value")
        return self._last

    @last.setter
    def last(self, v: T) -> None:
        self._last = v

    def publish(self, event: T) -> None:
        if self.stopped:
            raise ValueError("Cannot publish to stopped pubsub")
        self.last = event
        for i in self.iterators:
            i.events.put_nowait(event)

    def stop(self) -> None:
        for i in self.iterators:
            i.events.put_nowait(_stopped)

    def subscribe(self) -> PubSubContextManager[T]:
        return PubSubContextManager(self)


@dataclasses.dataclass
class PubSubContextManager(
    typing.Generic[T],
    typing.ContextManager["PubSubAsyncIterator[T]"],
    typing.AsyncIterable[T],
):
    pub_sub: PubSub[T]
    pub_sub_iterator: typing.Optional[PubSubAsyncIterator[T]] = None

    def __enter__(self) -> PubSubAsyncIterator[T]:
        self.pub_sub_iterator = PubSubAsyncIterator(self.pub_sub)
        self.pub_sub.iterators.append(self.pub_sub_iterator)
        return self.pub_sub_iterator

    def __exit__(
        self,
        __exc_type: typing.Optional[typing.Type[BaseException]],
        __exc_value: typing.Optional[BaseException],
        __traceback: typing.Optional[types.TracebackType],
    ) -> typing.Literal[False]:
        assert self.pub_sub_iterator
        self.pub_sub.iterators.remove(self.pub_sub_iterator)
        return False

    def __aiter__(self) -> typing.AsyncIterator[T]:
        assert self.pub_sub_iterator
        return self.pub_sub_iterator


@dataclasses.dataclass
class PubSubAsyncIterator(typing.Generic[T], typing.AsyncIterator[T]):
    """
    https://www.python.org/dev/peps/pep-0492/#asynchronous-iterators-and-async-for
    """

    pub_sub: PubSub[T]
    events: asyncio.Queue[typing.Union[T, Stopped]] = dataclasses.field(
        default_factory=asyncio.Queue
    )

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.pub_sub.stopped:
            raise StopAsyncIteration
        while True:
            e = await self.events.get()
            if e == _stopped:
                raise StopAsyncIteration
            return e
