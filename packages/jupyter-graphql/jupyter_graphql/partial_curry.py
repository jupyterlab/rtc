from __future__ import annotations

import functools
import inspect
import typing

__all__ = ["partial_curry"]

# TODO: improve typing in python 3.9 https://www.python.org/dev/peps/pep-0593/
def partial_curry(
    *first_args: str,
) -> typing.Callable[[typing.Callable], typing.Callable]:
    """
    Partially curry a function, to move the args around so one set must be called first and then the other second.

    Updates the signature properly.

    >>> @partial_curry("hi", "there")
    ... def hello_world(hi, there, other):
    ...     return hi + there + other
    >>> hello_world(hi="h", there="t")(other="r")
    'htr'
    >>> hello_world("h", "t")("r")
    'htr'
    >>> hello_world(hi="h", there="t")("r")
    'htr'
    >>> import inspect
    >>> inspect.signature(hello_world)
    <Signature (hi, there)>
    >>> inspect.signature(hello_world(1, 2))
    <Signature (other)>
    """

    def wrapper(f):
        s = inspect.signature(f)
        outer_s = s.replace(
            parameters=[p for p in s.parameters.values() if p.name in first_args]
        )
        inner_s = s.replace(
            parameters=[p for p in s.parameters.values() if p.name not in first_args]
        )

        @functools.wraps(f)
        def outer(*outer_args, **outer_kwargs):
            # Bind each so args/kwargs are all resolved properly and normalized
            outer_bound = outer_s.bind(*outer_args, **outer_kwargs)

            @functools.wraps(f)
            def inner(*inner_args, **inner_kwargs):
                inner_bound = inner_s.bind(*inner_args, **inner_kwargs)
                return f(
                    *outer_bound.args,
                    *inner_bound.args,
                    **outer_bound.kwargs,
                    **inner_bound.kwargs,
                )

            inner.__signature__ = inner_s  # type: ignore
            return inner

        outer.__signature__ = outer_s  # type: ignore
        return outer

    return wrapper
