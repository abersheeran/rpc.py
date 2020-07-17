import json
import http
import typing
from http import HTTPStatus
from collections.abc import Mapping

from rpcpy.types import Environ, StartResponse
from rpcpy.utils import cookie_parser, cached_property

from .datastructures import URL, FormData, Headers, QueryParams, State, MutableHeaders
from .formparsers import FormParser, MultiPartParser

from multipart.multipart import parse_options_header

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

    @cached_property
    def form(self) -> FormData:
        content_type_header = self.headers.get("Content-Type")
        content_type, options = parse_options_header(content_type_header)
        if content_type == b"multipart/form-data":
            multipart_parser = MultiPartParser(self.headers, self.stream())
            return multipart_parser.parse()
        elif content_type == b"application/x-www-form-urlencoded":
            form_parser = FormParser(self.headers, self.stream())
            return form_parser.parse()
        else:
            return FormData()

    def close(self) -> None:
        if hasattr(self, "_form"):
            self.form.close()


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

    def set_cookie(
        self,
        key: str,
        value: str = "",
        max_age: int = None,
        expires: int = None,
        path: str = "/",
        domain: str = None,
        secure: bool = False,
        httponly: bool = False,
        samesite: str = "lax",
    ) -> None:
        cookie: http.cookies.SimpleCookie = http.cookies.SimpleCookie()
        cookie[key] = value
        if max_age is not None:
            cookie[key]["max-age"] = max_age
        if expires is not None:
            cookie[key]["expires"] = expires
        if path is not None:
            cookie[key]["path"] = path
        if domain is not None:
            cookie[key]["domain"] = domain
        if secure:
            cookie[key]["secure"] = True
        if httponly:
            cookie[key]["httponly"] = True
        if samesite is not None:
            assert samesite.lower() in [
                "strict",
                "lax",
                "none",
            ], "samesite must be either 'strict', 'lax' or 'none'"
            cookie[key]["samesite"] = samesite
        cookie_val = cookie.output(header="").strip()
        self.raw_headers.append(("set-cookie", cookie_val))

    def delete_cookie(self, key: str, path: str = "/", domain: str = None) -> None:
        self.set_cookie(key, expires=0, max_age=0, path=path, domain=domain)

    def __call__(
        self, environ: Environ, start_response: StartResponse
    ) -> typing.Iterable[bytes]:
        start_response(
            f"{self.status_code} {HTTPStatus(self.status_code).phrase}",
            self.raw_headers,
            None,
        )
        yield self.body
