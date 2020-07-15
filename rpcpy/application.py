import typing
import inspect

from rpcpy.types import Environ, StartResponse, Scope, Receive, Send
from rpcpy.serializers import BaseSerializer, JSONSerializer
from rpcpy.asgi import Request as ASGIRequest, Response as ASGIResponse
from rpcpy.wsgi import Request as WSGIRequest, Response as WSGIResponse


Function = typing.TypeVar("Function")


class RPCMeta(type):
    def __call__(cls, *args: typing.Any, **kwargs: typing.Any) -> typing.Any:
        mode = kwargs.get("mode", "WSGI")
        assert mode in ("WSGI", "ASGI"), "mode must be in ('WSGI', 'ASGI')"

        if cls.__name__ == "RPC":
            if mode == "WSGI":
                return WSGIRPC(*args, **kwargs)

            if mode == "ASGI":
                return ASGIRPC(*args, **kwargs)

        return super().__call__(*args, **kwargs)


class RPC(metaclass=RPCMeta):
    def __init__(
        self,
        *,
        prefix: str = "/",
        mode: str = "WSGI",
        serializer: BaseSerializer = JSONSerializer(),
    ):
        assert mode in ("WSGI", "ASGI"), "mode must be in ('WSGI', 'ASGI')"
        self.callbacks = {}
        self.prefix = prefix
        self.serializer = serializer

    def register(self, func: Function) -> Function:
        self.callbacks[func.__name__] = func
        return func


class WSGIRPC(RPC):
    def register(self, func: Function) -> Function:
        if inspect.iscoroutinefunction(func):
            raise TypeError("WSGI mode can only register synchronization functions.")
        self.callbacks[func.__name__] = func
        return func

    def __call__(
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

        result = self.callbacks[request.url.path[len(self.prefix) :]](**data)

        return WSGIResponse(
            self.serializer.encode(result),
            headers={"serializer": self.serializer.name},
        )(environ, start_response)


class ASGIRPC(RPC):
    def register(self, func: Function) -> Function:
        if not inspect.iscoroutinefunction(func):
            raise TypeError("WSGI mode can only register synchronization functions.")
        self.callbacks[func.__name__] = func
        return func

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
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

        result = await self.callbacks[request.url.path[len(self.prefix) :]](**data)

        return await ASGIResponse(
            self.serializer.encode(result),
            headers={"serializer": self.serializer.name},
        )(scope, receive, send)
