import dataclasses
from dataclasses import dataclass
import typing
import asyncio

import jupyter_client.manager

import jupyter_client.kernelspec
import jupyter_server.serverapp
import jupyter_server.services.config
import jupyter_server.services.contents.manager
import jupyter_server.services.kernels.kernelmanager
import jupyter_server.services.sessions.sessionmanager
import ipython_genutils.importstring
import terminado

from .pubsub import PubSub

__all__ = ["Services"]


SERVICES = typing.TypeVar("SERVICES", bound="Services")


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


@dataclasses.dataclass
class Services:
    """
    Services provided by Jupyter Server that we need access to.
    """

    kernel_manager: jupyter_server.services.kernels.kernelmanager.MappingKernelManager
    contents_manager: jupyter_server.services.contents.manager.ContentsManager
    session_manager: jupyter_server.services.sessions.sessionmanager.SessionManager
    terminal_manager: terminado.NamedTermManager
    kernel_spec_manager: jupyter_client.kernelspec.KernelSpecManager
    config_manager: jupyter_server.services.config.ConfigManager

    # updated whenever a new kernel has been added
    kernel_added: PubSub[str] = dataclasses.field(default_factory=PubSub)
    # Updated whenever a kernel has been deleted
    kernel_deleted: PubSub[str] = dataclasses.field(default_factory=PubSub)
    # updated whenever a kernel status changes, maps from kernel ID to pubsub channel with a new event
    # All live kernels should have a pubsub in here.
    kernel_execution_state_updated: typing.Dict[str, PubSub[str]] = dataclasses.field(
        default_factory=dict
    )

    def __post_init__(self) -> None:
        # Monkeypatch del and set on kernels, to change to update kernel added, delete events.

        self.kernel_manager._kernels = ObservableDict(
            self._on_kernel_added, self._on_kernel_deleted, self.kernel_manager._kernels
        )

        # Also monkeypatch kernel class so that we can  be notificed when execution state changes
        cls = ipython_genutils.importstring.import_item(
            self.kernel_manager.kernel_manager_class
        )
        cls.execution_state = property(
            self._get_execution_state, self._set_execution_state
        )

    def _on_kernel_added(
        self, id: str, kernel: jupyter_client.manager.KernelManager
    ) -> None:
        self.kernel_added.publish(id)
        self.kernel_execution_state_updated[id] = PubSub()
        kernel.__id__ = id

    def _on_kernel_deleted(self, id: str) -> None:
        self.kernel_deleted.publish(id)
        self.kernel_execution_state_updated[id].stop()
        del self.kernel_execution_state_updated[id]

    def _set_execution_state(
        self, kernel: jupyter_client.manager.KernelManager, execution_state: str
    ):
        kernel._execution_state_value = execution_state
        self.kernel_execution_state_updated[kernel.__id__].publish(execution_state)

    def _get_execution_state(self, kernel: jupyter_client.manager.KernelManager):
        return kernel._execution_state_value

    @classmethod
    def from_server_app(
        cls: typing.Type[SERVICES], serverapp: jupyter_server.serverapp.ServerApp
    ) -> SERVICES:
        return cls(
            kernel_manager=serverapp.kernel_manager,
            contents_manager=serverapp.contents_manager,
            session_manager=serverapp.session_manager,
            terminal_manager=serverapp.web_app.settings["terminal_manager"],
            kernel_spec_manager=serverapp.kernel_spec_manager,
            config_manager=serverapp.config_manager,
        )
