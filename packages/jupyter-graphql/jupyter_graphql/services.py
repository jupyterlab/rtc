import dataclasses
import typing

import jupyter_client.kernelspec
import jupyter_server.serverapp
import jupyter_server.services.config
import jupyter_server.services.contents.manager
import jupyter_server.services.kernels.kernelmanager
import jupyter_server.services.sessions.sessionmanager
import terminado

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
