"""
Extracted from https://gist.github.com/bollwyvl/c2139c60de01d5bef88d1d30a01e0143

Changes:

1. switched to use jupyter server import
2. added support for playground html
3. Changed to use ariadne.graphql over graphql.graphql function to mirror ariedne.asgi code
"""

import dataclasses
import json
import typing

import ariadne
import ariadne.asgi
import ariadne.constants
import ariadne.exceptions
import jupyter_server.base.handlers
import starlette.websockets
import tornado.escape
import tornado.httputil
import tornado.web
import tornado.websocket


@dataclasses.dataclass
class MockStarletteWebsocket:
    """
    Mock a starlette websocket so we can pass it to the ariadne asgi handler for websockets
    """

    handler: tornado.websocket.WebSocketHandler

    async def send_json(self, json: dict) -> None:
        self.handler.write_message(json)

    async def close(self) -> None:
        self.handler.close()

    @property
    def application_state(self) -> starlette.websockets.WebSocketState:
        if (
            self.handler.ws_connection is None
            or self.handler.ws_connection.is_closing()
        ):
            return starlette.websockets.WebSocketState.DISCONNECTED
        return starlette.websockets.WebSocketState.CONNECTED

    @property
    def client_state(self) -> starlette.websockets.WebSocketState:
        """
        Not sure if this is right but :shrug: not sure how to get this from tornado
        """
        return self.application_state


class GraphQLHandler(
    jupyter_server.base.handlers.JupyterHandler, tornado.websocket.WebSocketHandler
):
    def initialize(
        self, graphql_app: ariadne.asgi.GraphQL, playground_html: str, *args, **kwargs
    ):
        super().initialize(*args, **kwargs)
        self.graphql_app = graphql_app
        self.playground_html = playground_html
        self.subscriptions: typing.Dict[str, typing.AsyncGenerator] = {}

    @tornado.web.authenticated
    async def get(self):
        # if upgrading use websockethandler behavior
        if self.request.headers.get("Upgrade", "").lower() == "websocket":
            return await super().get()
        self.finish(self.playground_html)

    @tornado.web.authenticated
    async def post(self):
        try:
            data = await self.extract_data_from_request(self.request)
        except ariadne.exceptions.HttpError as error:
            self.set_header("Content-Type", "text/plain")
            self.set_status(400)
            self.write(error.message or error.status)
            return

        success, response = await ariadne.graphql(
            self.graphql_app.schema,
            data,
            root_value=self.graphql_app.root_value,
            logger=self.graphql_app.logger,
            error_formatter=self.graphql_app.error_formatter,
            introspection=self.graphql_app.introspection,
        )
        self.set_status(200 if success else 400)
        self.write(response)

    async def extract_data_from_request(
        self, request: tornado.httputil.HTTPServerRequest
    ):
        if request.headers.get("Content-Type") != ariadne.constants.DATA_TYPE_JSON:
            raise ariadne.exceptions.HttpBadRequestError(
                "Posted content must be of type {}".format(
                    ariadne.constants.DATA_TYPE_JSON
                )
            )

        try:
            data = tornado.escape.json_decode(request.body)
        except ValueError:
            raise ariadne.exceptions.HttpBadRequestError(
                "Request body is not a valid JSON"
            )
        return data

    def open(self):
        pass

    async def on_message(self, message):
        await self.graphql_app.handle_websocket_message(
            json.loads(message),
            typing.cast(starlette.websockets.WebSocket, MockStarletteWebsocket(self)),
            self.subscriptions,
        )

    def on_close(self):
        pass
