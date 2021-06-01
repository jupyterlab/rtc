import typing

__all__ = ["ObservableDict"]

K = typing.TypeVar("K")
V = typing.TypeVar("V")


class ObservableDict(dict, typing.Generic[K, V]):
    """
    Dict where you can observe setting and deleting keys, after the action has completed.
    """

    def __init__(
        self,
        on_set: typing.Callable[[K, V], None],
        on_del: typing.Callable[[K], None],
        original: typing.Mapping[K, V],
    ):
        self.on_set = on_set
        self.on_del = on_del
        super().__init__(original)

    def __setitem__(self, k: K, v: V) -> None:
        super().__setitem__(k, v)
        self.on_set(k, v)

    def __delitem__(self, k: K) -> None:
        super().__delitem__(k)
        self.on_del(k)

    def pop(self, k, *args, **kwargs):
        self.on_del(k)
        super().pop(k, *args, **kwargs)
