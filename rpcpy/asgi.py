import json
import typing
import asyncio
from collections.abc import Mapping

from rpcpy.types import Message, Receive, Scope, Send
from rpcpy.utils import cookie_parser, cached_property
from rpcpy.datastructures import (
    URL,
    Headers,
    QueryParams,
    State,
    MutableHeaders,
)


__all__ = ["Request", "Response"]


class ClientDisconnect(Exception):
    pass


async def empty_receive() -> Message:
    raise RuntimeError("Receive channel has not been made available")


async def empty_send(message: Message) -> None:
    raise RuntimeError("Send channel has not been made available")


class Request(Mapping):
    """
    A base class for incoming HTTP connections, that is used to provide
    any functionality that is common to both `Request` and `WebSocket`.
    """

    def __init__(
        self, scope: Scope, receive: Receive = empty_receive, send: Send = empty_send
    ) -> None:
        assert scope["type"] == "http"
        self.scope = scope
        self.send = send
        self.receive = receive
        self._stream_consumed = False
        self._is_disconnected = False

    def __getitem__(self, key: str) -> str:
        return self.scope[key]

    def __iter__(self) -> typing.Iterator[str]:
        return iter(self.scope)

    def __len__(self) -> int:
        return len(self.scope)

    @cached_property
    def url(self) -> URL:
        return URL(scope=self.scope)

    @cached_property
    def headers(self) -> Headers:
        return Headers(scope=self.scope)

    @cached_property
    def query_params(self) -> QueryParams:
        return QueryParams(self.scope["query_string"])

    @cached_property
    def cookies(self) -> typing.Dict[str, str]:
        cookies: typing.Dict[str, str] = {}
        cookie_header = self.headers.get("cookie")

        if cookie_header:
            cookies = cookie_parser(cookie_header)
        return cookies

    @cached_property
    def state(self) -> State:
        # Ensure 'state' has an empty dict if it's not already populated.
        self.scope.setdefault("state", {})
        # Create a state instance with a reference to the dict in which it should store info
        return State(self.scope["state"])

    @cached_property
    def method(self) -> str:
        return self.scope["method"]

    async def stream(self) -> typing.AsyncGenerator[bytes, None]:
        if hasattr(self, "_body"):
            yield self._body
            yield b""
            return

        if self._stream_consumed:
            raise RuntimeError("Stream consumed")

        self._stream_consumed = True
        while True:
            message = await self.receive()
            if message["type"] == "http.request":
                body = message.get("body", b"")
                if body:
                    yield body
                if not message.get("more_body", False):
                    break
            elif message["type"] == "http.disconnect":
                self._is_disconnected = True
                raise ClientDisconnect()
        yield b""

    async def body(self) -> bytes:
        if not hasattr(self, "_body"):
            chunks = []
            async for chunk in self.stream():
                chunks.append(chunk)
            self._body = b"".join(chunks)
        return self._body

    async def json(self) -> typing.Any:
        if not hasattr(self, "_json"):
            body = await self.body()
            self._json = json.loads(body)
        return self._json


class Response:
    media_type = None
    charset = "utf-8"

    def __init__(
        self,
        content: typing.Any = None,
        status_code: int = 200,
        headers: dict = None,
        media_type: str = None,
    ) -> None:
        self.status_code = status_code
        if media_type is not None:
            self.media_type = media_type
        self.body = self.render(content)
        self.init_headers(headers)

    def render(self, content: typing.Any) -> bytes:
        if content is None:
            return b""
        if isinstance(content, bytes):
            return content
        return content.encode(self.charset)

    def init_headers(self, headers: typing.Mapping[str, str] = None) -> None:
        if headers is None:
            raw_headers: typing.List[typing.Tuple[bytes, bytes]] = []
            populate_content_length = True
            populate_content_type = True
        else:
            raw_headers = [
                (k.lower().encode("latin-1"), v.encode("latin-1"))
                for k, v in headers.items()
            ]
            keys = [h[0] for h in raw_headers]
            populate_content_length = b"content-length" not in keys
            populate_content_type = b"content-type" not in keys

        body = getattr(self, "body", b"")
        if body and populate_content_length:
            content_length = str(len(body))
            raw_headers.append((b"content-length", content_length.encode("latin-1")))

        content_type = self.media_type
        if content_type is not None and populate_content_type:
            if content_type.startswith("text/"):
                content_type += "; charset=" + self.charset
            raw_headers.append((b"content-type", content_type.encode("latin-1")))

        self.raw_headers = raw_headers

    @cached_property
    def headers(self) -> MutableHeaders:
        return MutableHeaders(raw=self.raw_headers)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        await send(
            {
                "type": "http.response.start",
                "status": self.status_code,
                "headers": self.raw_headers,
            }
        )
        await send({"type": "http.response.body", "body": self.body})


class EventResponse(Response):
    """
    Server send event

    https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events/Using_server-sent_events
    """

    media_type = "text/event-stream"

    def __init__(
        self,
        generator: typing.AsyncGenerator[str, None],
        status_code: int = 200,
        headers: dict = None,
        *,
        ping_interval: int = 3,
    ) -> None:

        _headers = {"Cache-Control": "no-cache", "Connection": "keep-alive"}
        if headers:
            _headers.update(headers)
        super().__init__(None, status_code, _headers)
        self.generator = generator
        self.ping_interval = ping_interval

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        await send(
            {
                "type": "http.response.start",
                "status": self.status_code,
                "headers": self.raw_headers,
            }
        )

        done, pending = await asyncio.wait(
            (self.keep_alive(send), self.send_event(send)),
            return_when=asyncio.FIRST_COMPLETED,
        )
        [task.cancel() for task in pending]
        [task.result() for task in done]
        await send({"type": "http.response.body", "body": b""})

    async def send_event(self, send: Send) -> None:
        async for chunk in self.generator:
            await send(
                {
                    "type": "http.response.body",
                    "body": f"data: {chunk.strip()}\r\n\r\n".encode("utf8"),
                    "more_body": True,
                }
            )

    async def keep_alive(self, send: Send) -> None:
        while True:
            await asyncio.sleep(self.ping_interval)
            await send(
                {
                    "type": "http.response.body",
                    "body": ": ping\r\n\r\n".encode("utf8"),
                    "more_body": True,
                }
            )
