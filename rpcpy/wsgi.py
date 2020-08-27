import json
import time
import typing
from http import HTTPStatus
from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED

from rpcpy.types import Environ, StartResponse
from rpcpy.utils import cookie_parser, cached_property
from rpcpy.datastructures import (
    URL,
    Headers,
    QueryParams,
    State,
    MutableHeaders,
)

__all__ = ["Request", "Response"]


class Request(Mapping):
    """
    A base class for incoming HTTP connections, that is used to provide
    any functionality that is common to both `Request` and `WebSocket`.
    """

    def __init__(self, enviorn: Environ) -> None:
        self.enviorn = enviorn

    def __getitem__(self, key: str) -> str:
        return self.enviorn[key]

    def __iter__(self) -> typing.Iterator[str]:
        return iter(self.enviorn)

    def __len__(self) -> int:
        return len(self.enviorn)

    @cached_property
    def url(self) -> URL:
        return URL(environ=self.enviorn)

    @cached_property
    def headers(self) -> Headers:
        return Headers(environ=self.enviorn)

    @cached_property
    def query_params(self) -> QueryParams:
        return QueryParams(self.enviorn["QUERY_STRING"])

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
        self.enviorn.setdefault("state", {})
        # Create a state instance with a reference to the dict in which it should store info
        return State(self.enviorn["state"])

    @cached_property
    def method(self) -> str:
        return self.enviorn["REQUEST_METHOD"]

    def stream(self) -> typing.Generator[bytes, None, None]:
        if "body" in self.__dict__:
            yield self.body
            return

        while True:
            chunk = self.enviorn["wsgi.input"].read(1024 * 64)
            if not chunk:
                return
            yield chunk

    @cached_property
    def body(self) -> bytes:
        chunks = []
        for chunk in self.stream():
            chunks.append(chunk)
        return b"".join(chunks)

    @cached_property
    def json(self) -> typing.Any:
        return json.loads(self.body)


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
            raw_headers: typing.List[typing.Tuple[str, str]] = []
            populate_content_length = True
            populate_content_type = True
        else:
            raw_headers = [(k.lower(), v) for k, v in headers.items()]
            keys = [h[0] for h in raw_headers]
            populate_content_length = "content-length" not in keys
            populate_content_type = "content-type" not in keys

        body = getattr(self, "body", b"")
        if body and populate_content_length:
            content_length = str(len(body))
            raw_headers.append(("content-length", content_length))

        content_type = self.media_type
        if content_type is not None and populate_content_type:
            if content_type.startswith("text/"):
                content_type += "; charset=" + self.charset
            raw_headers.append(("content-type", content_type))

        self.raw_headers = raw_headers

    @cached_property
    def headers(self) -> MutableHeaders:
        return MutableHeaders(
            raw=[
                (key.encode("latin-1"), value.encode("latin-1"))
                for key, value in self.raw_headers
            ]
        )

    def __call__(
        self, environ: Environ, start_response: StartResponse
    ) -> typing.Iterable[bytes]:
        start_response(
            f"{self.status_code} {HTTPStatus(self.status_code).phrase}",
            self.raw_headers,
            None,
        )
        yield self.body


class EventResponse(Response):
    """
    Server send event

    https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events/Using_server-sent_events
    """

    media_type = "text/event-stream"

    thread_pool = ThreadPoolExecutor(max_workers=10)

    def __init__(
        self,
        generator: typing.Generator[str, None, None],
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
        self.queue: typing.List[str] = []
        self.has_more_data = True

    def __call__(
        self, environ: Environ, start_response: StartResponse
    ) -> typing.Iterable[bytes]:
        start_response(
            f"{self.status_code} {HTTPStatus(self.status_code).phrase}",
            self.raw_headers,
            None,
        )

        future = self.thread_pool.submit(
            wait,
            (
                self.thread_pool.submit(self.send_event),
                self.thread_pool.submit(self.keep_alive),
            ),
            return_when=FIRST_COMPLETED,
        )

        try:
            while self.has_more_data or self.queue:
                yield self.queue.pop(0).encode("utf8")
        finally:
            if not future.cancel():
                done, pending = future.result()
                [task.cancel() for task in pending]
                [task.result() for task in done]

    def send_event(self) -> None:
        for chunk in self.generator:
            self.queue.append(f"data: {chunk.strip()}\r\n\r\n")
        self.has_more_data = False

    def keep_alive(self) -> None:
        while self.has_more_data:
            time.sleep(self.ping_interval)
            self.queue.append(": ping\r\n\r\n")
