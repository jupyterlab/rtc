from __future__ import annotations

import asyncio
import dataclasses
import functools
import logging
import typing

import ipython_genutils.importstring
import jupyter_client.kernelspec
import jupyter_client.manager
import jupyter_client.session
import jupyter_server.serverapp
import jupyter_server.services.config
import jupyter_server.services.contents.manager
import jupyter_server.services.kernels.kernelmanager
import jupyter_server.services.sessions.sessionmanager
import jupyter_server.utils
import terminado
import zmq.eventloop.zmqstream

from .observable_dict import ObservableDict
from .pubsub import PubSub

__all__ = ["Services"]


SERVICES = typing.TypeVar("SERVICES", bound="Services")

logger = logging.getLogger(__name__)


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

    # List of kernel streams, so we can close them when we need.
    kernel_streams: typing.Dict[
        str, typing.List[zmq.eventloop.zmqstream.ZMQStream]
    ] = dataclasses.field(default_factory=dict)

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
        # initialize to starting
        self.kernel_execution_state_updated[id] = PubSub(_last="starting")
        kernel.__id__ = id
        self._kernel_info_replies[id] = asyncio.get_running_loop().create_future()
        asyncio.create_task(self._connect_kernel(id))

    async def _connect_kernel(self, id: str):
        # TODO: Have manual wait here, otherwise it seems like we connect too fast and wont get actual updates
        # Need to understand why this is
        await asyncio.sleep(0.5)
        kernel: jupyter_client.manager.KernelManager = self.kernel_manager._kernels[id]
        # Connect iopub before sending kernel info request
        iopub_channel = typing.cast(
            zmq.eventloop.zmqstream.ZMQStream, kernel.connect_iopub()
        )
        iopub_channel.on_recv(functools.partial(self._on_iopub_message, id))

        # Set up shell channel and send kernel info request, like
        # `request_kernel_info` on ZMQChannellsHandler
        # Except we keep shell channel open
        shell_channel = typing.cast(
            zmq.eventloop.zmqstream.ZMQStream, kernel.connect_shell()
        )
        shell_channel.on_recv(functools.partial(self._on_shell_message, id))
        self._session(id).send(shell_channel, "kernel_info_request")

        self.kernel_streams[id] = [shell_channel, iopub_channel]

    def _disconnect_kernel(self, id: str):
        for s in self.kernel_streams[id]:
            s.close()

    def _on_kernel_deleted(self, id: str) -> None:
        self.kernel_deleted.publish(id)
        self.kernel_execution_state_updated[id].stop()
        del self.kernel_execution_state_updated[id]
        del self._kernel_info_replies[id]
        del self.kernel_streams[id]

    def _set_execution_state(
        self, kernel: jupyter_client.manager.KernelManager, execution_state: str
    ):
        # Save on kernel so it can be returned on getter
        kernel._execution_state_value = execution_state
        # Only publish if execution state is restarting or dead, because these are events
        # from the automatic kernel restarter we don't handle
        if execution_state in ("restarting", "dead"):
            self.kernel_execution_state_updated[kernel.__id__].publish(execution_state)

    def restart_kernel(
        self, id: str
    ) -> typing.Optional[typing.Coroutine[typing.Any, typing.Any, None]]:
        """
        Restarts a kernel, returning a coroutine if it is actually retarting,
        returning none if not restarting because already starting or restarting.
        """
        execution_state = self.kernel_execution_state_updated[id]
        if (execution_state.last) in ("restarting", "starting"):
            logger.warn(
                "Not restarting kernel %s because in state %s", id, execution_state.last
            )
            return None
        execution_state.publish("restarting")
        # Disconnect all streams from kernel, so no new status can be updated till restarted.
        self._disconnect_kernel(id)

        return self.restart_internal(id)

    async def restart_internal(self, id: str) -> None:
        await jupyter_server.utils.ensure_async(
            self.kernel_manager.pinned_superclass.restart_kernel(
                self.kernel_manager, id
            )
        )
        # Open new connections and send kernel info request, which will set status.

        await self._connect_kernel(id)

    def _get_execution_state(self, kernel: jupyter_client.manager.KernelManager):
        return kernel._execution_state_value

    def _on_shell_message(self, kernel_id: str, original_msg) -> None:
        # Like `_handle_kernel_info_reply` on ZMQCHannnelsHandler
        msg = self._parse_message(kernel_id, original_msg)
        msg_type = msg["msg_type"]
        if msg_type == "kernel_info_reply":
            try:
                self._kernel_info_replies[kernel_id].set_result(msg["content"])
            except asyncio.InvalidStateError:
                # If we already set the kernel info reply, just ignore this message
                pass
        else:
            logger.warn("Unhandled shell message: %s", msg)
            pass

    def _on_iopub_message(self, kernel_id: str, original_msg) -> None:
        # Like `_handle_kernel_info_reply` on ZMQCHannnelsHandler
        msg = self._parse_message(kernel_id, original_msg)
        msg_type = msg["msg_type"]
        if msg_type == "status":
            self.kernel_execution_state_updated[kernel_id].publish(
                msg["content"]["execution_state"]
            )
        else:
            logger.warn("Unhandled iopub message: %s", msg)
            pass

    def _parse_message(self, kernel_id: str, msg) -> Message:
        idents, msg_wout_identities = self._session(kernel_id).feed_identities(msg)
        return self._session(kernel_id).deserialize(msg_wout_identities)

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
