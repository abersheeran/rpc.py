import typing
import inspect
import copy
import json
from base64 import b64encode
from types import FunctionType

from rpcpy.types import Environ, StartResponse, Scope, Receive, Send, TypedDict
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
from rpcpy.utils import set_type_model
from rpcpy.utils.openapi import (
    BaseModel,
    schema_request_body,
    schema_response,
    TEMPLATE as OpenapiTemplate,
)

__all__ = ["RPC"]

Function = typing.TypeVar("Function", FunctionType, FunctionType)
MethodNotAllowedHttpCode = {
    "GET": 404,
    "HEAD": 404,
}  # https://developer.mozilla.org/zh-CN/docs/Web/HTTP/Status/405


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


OpenAPI = TypedDict("OpenAPI", {"title": str, "description": str, "version": str})


class RPC(metaclass=RPCMeta):
    def __init__(
        self,
        *,
        prefix: str = "/",
        mode: str = "WSGI",
        serializer: BaseSerializer = JSONSerializer(),
        openapi: OpenAPI = None,
    ):
        assert mode in ("WSGI", "ASGI"), "mode must be in ('WSGI', 'ASGI')"
        assert prefix.startswith("/") and prefix.endswith("/")
        self.callbacks: typing.Dict[str, typing.Callable] = {}
        self.prefix = prefix
        self.serializer = serializer
        self.openapi = openapi

    def register(self, func: Function) -> Function:
        self.callbacks[func.__name__] = func
        set_type_model(func)
        return func

    def get_openapi_docs(self) -> dict:
        openapi: dict = {
            "openapi": "3.0.0",
            "info": copy.deepcopy(self.openapi) or {},
            "paths": {},
        }

        for name, callback in self.callbacks.items():
            _ = {}
            # summary and description
            doc = callback.__doc__
            if isinstance(doc, str):
                doc = doc.strip()
                _.update(
                    {
                        "summary": doc.splitlines()[0],
                        "description": "\n".join(doc.splitlines()[1:]).strip(),
                    }
                )
            # request body
            body_doc = schema_request_body(getattr(callback, "__body_model__", None))
            if body_doc:
                _["requestBody"] = body_doc
            # response & only 200
            sig = inspect.signature(callback)
            if (
                sig.return_annotation != sig.empty
                and inspect.isclass(sig.return_annotation)
                and issubclass(sig.return_annotation, BaseModel)
            ):
                _["responses"] = {
                    200: {"content": schema_response(sig.return_annotation)}
                }
            if _:
                openapi["paths"][f"{self.prefix}{name}"] = {"post": _}

        return openapi


class WSGIRPC(RPC):
    def register(self, func: Function) -> Function:
        if inspect.iscoroutinefunction(func) or inspect.isasyncgenfunction(func):
            raise TypeError("WSGI mode can only register synchronization functions.")
        return super().register(func)

    def create_generator(
        self, generator: typing.Generator
    ) -> typing.Generator[str, None, None]:
        for data in generator:
            yield b64encode(self.serializer.encode(data)).decode("ascii")

    def __call__(
        self, environ: Environ, start_response: StartResponse
    ) -> typing.Iterable[bytes]:
        request = WSGIRequest(environ)
        if self.openapi is not None and request.method == "GET":
            if request.url.path[len(self.prefix) :] == "openapi-docs":
                return WSGIResponse(
                    OpenapiTemplate, headers={"content-type": "text/html"},
                )(environ, start_response)
            elif request.url.path[len(self.prefix) :] == "get-openapi-docs":
                return WSGIResponse(
                    json.dumps(self.get_openapi_docs(), ensure_ascii=False),
                    headers={"content-type": "application/json"},
                )(environ, start_response)

        if request.method != "POST":
            return WSGIResponse(
                status_code=MethodNotAllowedHttpCode.get(request.method, 405)
            )(environ, start_response)

        content_type = request.headers["content-type"]
        assert content_type == "application/json"
        data = request.json

        callback = self.callbacks[request.url.path[len(self.prefix) :]]
        if hasattr(callback, "__body_model__"):
            result = callback(**getattr(callback, "__body_model__")(**data).dict())
        else:
            result = callback(**data)

        if inspect.isgenerator(result):
            return WSGIEventResponse(
                self.create_generator(result),
                headers={"serializer": self.serializer.name},
            )(environ, start_response)

        return WSGIResponse(
            self.serializer.encode(result),
            headers={
                "serializer": self.serializer.name,
                "content-type": self.serializer.content_type,
            },
        )(environ, start_response)


class ASGIRPC(RPC):
    def register(self, func: Function) -> Function:
        if not (inspect.iscoroutinefunction(func) or inspect.isasyncgenfunction(func)):
            raise TypeError("ASGI mode can only register asynchronous functions.")
        return super().register(func)

    async def create_generator(
        self, generator: typing.AsyncGenerator
    ) -> typing.AsyncGenerator[str, None]:
        async for data in generator:
            yield b64encode(self.serializer.encode(data)).decode("ascii")

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        request = ASGIRequest(scope, receive, send)
        if self.openapi is not None and request.method == "GET":
            if request.url.path[len(self.prefix) :] == "openapi-docs":
                return await ASGIResponse(
                    OpenapiTemplate, headers={"content-type": "text/html"},
                )(scope, receive, send)
            elif request.url.path[len(self.prefix) :] == "get-openapi-docs":
                return await ASGIResponse(
                    json.dumps(self.get_openapi_docs(), ensure_ascii=False),
                    headers={"content-type": "application/json"},
                )(scope, receive, send)

        if request.method != "POST":
            return await ASGIResponse(
                status_code=MethodNotAllowedHttpCode.get(request.method, 405)
            )(scope, receive, send)

        content_type = request.headers["content-type"]
        assert content_type == "application/json"
        data = await request.json()

        callback = self.callbacks[request.url.path[len(self.prefix) :]]
        if hasattr(callback, "__body_model__"):
            result = callback(**getattr(callback, "__body_model__")(**data).dict())
        else:
            result = callback(**data)

        if inspect.isasyncgen(result):
            return await ASGIEventResponse(
                self.create_generator(result),
                headers={"serializer": self.serializer.name},
            )(scope, receive, send)

        return await ASGIResponse(
            self.serializer.encode(await result),
            headers={
                "serializer": self.serializer.name,
                "content-type": self.serializer.content_type,
            },
        )(scope, receive, send)
