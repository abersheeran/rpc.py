import typing
import inspect
import traceback
import logging

from rpcpy.types import Environ, StartResponse, Scope, Receive, Send
from rpcpy.serializers import BaseSerializer, JSONSerializer
from rpcpy.asgi import Request as ASGIRequest, Response as ASGIResponse
from rpcpy.wsgi import Request as WSGIRequest, Response as WSGIResponse


Function = typing.TypeVar("Function")


class RPC:
    def __init__(
        self,
        *,
        prefix: str = "/",
        serializer: BaseSerializer = JSONSerializer(),
        logger: logging.Logger = logging.getLogger("rpcpy")
    ):
        self.async_callbacks = {}
        self.sync_callbacks = {}
        self.prefix = prefix
        self.serializer = serializer
        self.logger = logger

    def register(self, func: Function) -> Function:
        if inspect.iscoroutinefunction(func):
            self.async_callbacks[func.__name__] = func
        else:
            self.sync_callbacks[func.__name__] = func
        return func

    def wsgi(
        self, environ: Environ, start_response: StartResponse
    ) -> typing.Iterable[bytes]:
        request = WSGIRequest(environ)
        if request.method != "POST":
            if request.method in ("GET", "HEAD"):
                status_code = 404
            else:
                status_code = 405
            return WSGIResponse(status_code=status_code)(environ, start_response)

        content_type = request.headers["content-type"]
        if content_type == "application/json":
            data = request.json
        else:
            data = request.form
        assert isinstance(data, typing.Mapping)

        result = self.sync_callbacks[request.url.path[len(self.prefix) :]](**data)

        return WSGIResponse(
            self.serializer.encode(result),
            headers={"serializer": self.serializer.name},
        )(environ, start_response)

    async def asgi(self, scope: Scope, receive: Receive, send: Send) -> None:
        request = ASGIRequest(scope, receive, send)

        if request.method != "POST":
            if request.method in ("GET", "HEAD"):
                status_code = 404
            else:
                status_code = 405
            return ASGIResponse(status_code=status_code)(scope, receive, send)

        content_type = request.headers["content-type"]
        if content_type == "application/json":
            data = await request.json()
        else:
            data = await request.form()
        assert isinstance(data, typing.Mapping)

        result = result = await self.async_callbacks[
            request.url.path[len(self.prefix) :]
        ](**data)

        return await ASGIResponse(
            self.serializer.encode(result),
            headers={"serializer": self.serializer.name},
        )(scope, receive, send)
