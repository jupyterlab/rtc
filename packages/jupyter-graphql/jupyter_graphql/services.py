from __future__ import annotations
import dataclasses
import typing
import asyncio
import functools

import ipython_genutils.importstring
import jupyter_client.kernelspec
import jupyter_client.manager
import jupyter_server.serverapp
import jupyter_server.services.config
import jupyter_server.services.contents.manager
import jupyter_server.services.kernels.kernelmanager
import jupyter_server.services.sessions.sessionmanager
import jupyter_client.session
import terminado
import zmq.eventloop.zmqstream

from .observable_dict import ObservableDict
from .pubsub import PubSub

__all__ = ["Services"]


SERVICES = typing.TypeVar("SERVICES", bound="Services")


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
    # session: jupyter_client.session.Session

    # updated whenever a new kernel has been added
    kernel_added: PubSub[str] = dataclasses.field(default_factory=PubSub)
    # Updated whenever a kernel has been deleted
    kernel_deleted: PubSub[str] = dataclasses.field(default_factory=PubSub)
    # updated whenever a kernel status changes, maps from kernel ID to pubsub channel with a new event
    # All live kernels should have a pubsub in here.
    kernel_execution_state_updated: typing.Dict[str, PubSub[str]] = dataclasses.field(
        default_factory=dict
    )

    # kernel_shell_channels: typing.Dict[
    #     str, zmq.eventloop.zmqstream.ZMQStream
    # ] = dataclasses.field(default_factory=dict)

    # mapping of kernel info ids to futures for their initial kernel info replies
    _kernel_info_replies: typing.Dict[str, asyncio.Future] = dataclasses.field(
        default_factory=dict
    )

    async def kernel_info_reply(self, id: str) -> KernelInfoReplyContent:
        return await self._kernel_info_replies[id]

    @classmethod
    def from_server_app(
        cls: typing.Type[SERVICES], serverapp: jupyter_server.serverapp.ServerApp
    ) -> SERVICES:
        # session = jupyter_client.session.Session(
        #     config=serverapp.web_app.settings["config"]
        # )
        # session.session = "some uuid"
        return cls(
            kernel_manager=serverapp.kernel_manager,
            contents_manager=serverapp.contents_manager,
            session_manager=serverapp.session_manager,
            terminal_manager=serverapp.web_app.settings["terminal_manager"],
            kernel_spec_manager=serverapp.kernel_spec_manager,
            config_manager=serverapp.config_manager,
            # session=session,
        )

    def __post_init__(self) -> None:
        # Monkeypatch del and set on kernels, to change to update kernel added, delete events.

        self.kernel_manager._kernels = ObservableDict(
            self._on_kernel_added, self._on_kernel_deleted, self.kernel_manager._kernels
        )

        # Also monkeypatch kernel class so that we can  be notified when execution state changes
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

        self._kernel_info_replies[id] = asyncio.get_running_loop().create_future()
        # Set up shell channel and send kernel info request, like
        # `request_kernel_info` on ZMQChannellsHandler
        # Except we keep shell channel open
        shell_channel = typing.cast(
            zmq.eventloop.zmqstream.ZMQStream, self.kernel_manager.connect_shell(id)
        )
        # TODO: DO we have to close this at some point? Will it be closed automatically?
        shell_channel.on_recv(functools.partial(self._on_shell_message, id))
        self._session(id).send(shell_channel, "kernel_info_request")

    def _on_kernel_deleted(self, id: str) -> None:
        self.kernel_deleted.publish(id)
        self.kernel_execution_state_updated[id].stop()
        del self.kernel_execution_state_updated[id]
        del self._kernel_info_replies[id]

    def _set_execution_state(
        self, kernel: jupyter_client.manager.KernelManager, execution_state: str
    ):
        kernel._execution_state_value = execution_state
        self.kernel_execution_state_updated[kernel.__id__].publish(execution_state)

    def _get_execution_state(self, kernel: jupyter_client.manager.KernelManager):
        return kernel._execution_state_value

    def _on_shell_message(self, kernel_id: str, original_msg) -> None:
        print("received result", kernel_id, original_msg)
        # Like `_handle_kernel_info_reply` on ZMQCHannnelsHandler
        idents, msg_wout_identities = self._session(kernel_id).feed_identities(
            original_msg
        )
        msg: Message = self._session(kernel_id).deserialize(msg_wout_identities)

        msg_type = msg["msg_type"]
        if msg_type == "kernel_info_reply":
            try:
                self._kernel_info_replies[kernel_id].set_result(msg["content"])
            except asyncio.InvalidStateError:
                # If we already set the kernel info reply, just ignore this message
                pass
        else:
            print("got other message", msg_type)
            pass

    def _session(self, kernel_id: str) -> jupyter_client.session.Session:
        return self.kernel_manager.get_kernel(kernel_id).session


class Message(typing.TypedDict):
    """
    The message returned by session.deserialize
    """

    header: dict
    msg_id: str
    msg_type: str
    parent_header: dict
    metadata: dict
    content: dict
    buffers: typing.List[memoryview]


class KernelInfoReplyContent(typing.TypedDict):
    """
    https://jupyter-client.readthedocs.io/en/stable/messaging.html#kernel-info
    """

    status: typing.Literal["ok"]
    protocol_version: str
    implementation: str
    implementation_version: str
    language_info: KernelInfoLanguageInfo
    banner: str
    help_links: typing.List[KernelInfoHelpLink]


class KernelInfoLanguageInfo(typing.TypedDict):
    name: str
    version: str
    mimetype: str
    file_extension: str
    pygments_lexer: str
    codemirror_mode: typing.Union[str, dict]
    nbconvert_exporter: str


class KernelInfoHelpLink(typing.TypedDict):
    text: str
    url: str