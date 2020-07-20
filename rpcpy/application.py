import typing
import inspect
from base64 import b64encode
from types import FunctionType

from rpcpy.types import Environ, StartResponse, Scope, Receive, Send
from rpcpy.serializers import BaseSerializer, JSONSerializer
from rpcpy.asgi import (
    Request as ASGIRequest,
    Response as ASGIResponse,
    EventResponse as ASGIEventResponse,
)
from rpcpy.wsgi import (
    Request as WSGIRequest,
    Response as WSGIResponse,
    EventResponse as WSGIEventResponse,
)

__all__ = ["RPC"]

Function = typing.TypeVar("Function", FunctionType, FunctionType)


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
        assert prefix.startswith("/") and prefix.endswith("/")
        self.callbacks: typing.Dict[str, typing.Callable] = {}
        self.prefix = prefix
        self.serializer = serializer

    def register(self, func: Function) -> Function:
        self.callbacks[func.__name__] = func
        return func


class WSGIRPC(RPC):
    def register(self, func: Function) -> Function:
        if inspect.iscoroutinefunction(func) or inspect.isasyncgenfunction(func):
            raise TypeError("WSGI mode can only register synchronization functions.")
        self.callbacks[func.__name__] = func
        return func

    def create_generator(
        self, generator: typing.Generator
    ) -> typing.Generator[str, None, None]:
        for data in generator:
            yield b64encode(self.serializer.encode(data)).decode("ascii")

    def __call__(
        self, environ: Environ, start_response: StartResponse
    ) -> typing.Iterable[bytes]:
        request = WSGIRequest(environ)
        if request.method != "POST":
            return WSGIResponse(status_code=405)(environ, start_response)

        content_type = request.headers["content-type"]
        if content_type == "application/json":
            data = request.json
        else:
            data = request.form
        assert isinstance(data, typing.Mapping)

        result = self.callbacks[request.url.path[len(self.prefix) :]](**data)

        if inspect.isgenerator(result):
            return WSGIEventResponse(
                self.create_generator(result),
                headers={"serializer": self.serializer.name},
            )(environ, start_response)

        return WSGIResponse(
            self.serializer.encode(result),
            headers={"serializer": self.serializer.name},
        )(environ, start_response)


class ASGIRPC(RPC):
    def register(self, func: Function) -> Function:
        if not (inspect.iscoroutinefunction(func) or inspect.isasyncgenfunction(func)):
            raise TypeError("ASGI mode can only register asynchronous functions.")
        self.callbacks[func.__name__] = func
        return func

    async def create_generator(
        self, generator: typing.AsyncGenerator
    ) -> typing.AsyncGenerator[str, None]:
        async for data in generator:
            yield b64encode(self.serializer.encode(data)).decode("ascii")

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        request = ASGIRequest(scope, receive, send)

        if request.method != "POST":
            return await ASGIResponse(status_code=405)(scope, receive, send)

        content_type = request.headers["content-type"]
        if content_type == "application/json":
            data = await request.json()
        else:
            data = await request.form()
        assert isinstance(data, typing.Mapping)

        result = self.callbacks[request.url.path[len(self.prefix) :]](**data)

        if inspect.isasyncgen(result):
            return await ASGIEventResponse(
                self.create_generator(result),
                headers={"serializer": self.serializer.name},
            )(scope, receive, send)

        return await ASGIResponse(
            self.serializer.encode(await result),
            headers={"serializer": self.serializer.name},
        )(scope, receive, send)
