import typing
import inspect
import copy
import json
from base64 import b64encode
from types import FunctionType

from rpcpy.types import Environ, StartResponse, Scope, Receive, Send, TypedDict, Literal
from rpcpy.exceptions import SerializerNotAllowed
from rpcpy.serializers import BaseSerializer, JSONSerializer
from rpcpy.asgi import (
    Request as AsgiRequest,
    Response as AsgiResponse,
    EventResponse as AsgiEventResponse,
)
from rpcpy.wsgi import (
    Request as WsgiRequest,
    Response as WsgiResponse,
    EventResponse as WsgiEventResponse,
)
from rpcpy.utils import check
from rpcpy.utils.openapi import (
    BaseModel,
    create_model,
    set_type_model,
    TEMPLATE as OPENAPI_TEMPLATE,
)

__all__ = ["RPC", "WsgiRPC", "AsgiRPC"]

Function = typing.TypeVar("Function", bound=FunctionType)
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
                return WsgiRPC(*args, **kwargs)

            if mode == "ASGI":
                return AsgiRPC(*args, **kwargs)

        return super().__call__(*args, **kwargs)


OpenAPI = TypedDict("OpenAPI", {"title": str, "description": str, "version": str})


class RPC(metaclass=RPCMeta):
    def __init__(
        self,
        *,
        mode: Literal["WSGI", "ASGI"] = "WSGI",
        prefix: str = "/",
        request_serializer: BaseSerializer = JSONSerializer(),
        response_serializer: BaseSerializer = JSONSerializer(),
        openapi: OpenAPI = None,
    ) -> None:
        assert mode in ("WSGI", "ASGI"), "mode must be in ('WSGI', 'ASGI')"
        assert prefix.startswith("/") and prefix.endswith("/")
        self.callbacks: typing.Dict[str, typing.Callable] = {}
        self.prefix = prefix
        self.request_serializer = request_serializer
        self.response_serializer = response_serializer
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
            body_model = getattr(callback, "__body_model__", None)
            if body_model:
                _schema = copy.deepcopy(body_model.schema())
                del _schema["title"]
                _["requestBody"] = {
                    "required": True,
                    "content": {
                        self.request_serializer.content_type: {"schema": _schema}
                    },
                }
            # response & only 200
            sig = inspect.signature(callback)
            if sig.return_annotation != sig.empty:
                if inspect.isclass(sig.return_annotation) and issubclass(
                    sig.return_annotation, BaseModel
                ):
                    resp_model = sig.return_annotation
                else:
                    resp_model = create_model(
                        callback.__name__ + "-return",
                        __root__=(sig.return_annotation, ...),
                    )
                _schema = copy.deepcopy(resp_model.schema())
                del _schema["title"]
                _["responses"] = {
                    200: {
                        "content": {
                            self.response_serializer.content_type: {"schema": _schema}
                        }
                    }
                }
            if _:
                openapi["paths"][f"{self.prefix}{name}"] = {"post": _}
        return openapi


class WsgiRPC(RPC):
    def register(self, func: Function) -> Function:
        if inspect.iscoroutinefunction(func) or inspect.isasyncgenfunction(func):
            raise TypeError("WSGI mode can only register synchronization functions.")
        return super().register(func)

    def create_generator(
        self, generator: typing.Generator
    ) -> typing.Generator[str, None, None]:
        for data in generator:
            yield b64encode(self.response_serializer.encode(data)).decode("ascii")

    def on_call(self, request: WsgiRequest) -> WsgiResponse:
        if self.openapi is not None and request.method == "GET":
            if request.url.path[len(self.prefix) :] == "openapi-docs":
                return WsgiResponse(
                    OPENAPI_TEMPLATE, headers={"content-type": "text/html"}
                )
            elif request.url.path[len(self.prefix) :] == "get-openapi-docs":
                return WsgiResponse(
                    json.dumps(self.get_openapi_docs(), ensure_ascii=False),
                    headers={"content-type": "application/json"},
                )

        if request.method != "POST":
            return WsgiResponse(
                status_code=MethodNotAllowedHttpCode.get(request.method, 405)
            )

        check(
            request.headers["content-type"] == self.request_serializer.content_type
            or int(request.headers.get("content-type", 0)) == 0,
            SerializerNotAllowed(
                f"You should use content-type `{self.request_serializer.content_type}`"
            ),
        )
        data = self.request_serializer.decode(request.body)

        callback = self.callbacks[request.url.path[len(self.prefix) :]]
        if hasattr(callback, "__body_model__"):
            result = callback(**getattr(callback, "__body_model__")(**data).dict())
        else:
            result = callback(**data)

        if inspect.isgenerator(result):
            return WsgiEventResponse(
                self.create_generator(result),
                headers={"serializer": self.response_serializer.name},
            )

        return WsgiResponse(
            self.response_serializer.encode(result),
            headers={
                "serializer": self.response_serializer.name,
                "content-type": self.response_serializer.content_type,
            },
        )

    def __call__(
        self, environ: Environ, start_response: StartResponse
    ) -> typing.Iterable[bytes]:
        request = WsgiRequest(environ)
        response = self.on_call(request)
        return response(environ, start_response)


class AsgiRPC(RPC):
    def register(self, func: Function) -> Function:
        if not (inspect.iscoroutinefunction(func) or inspect.isasyncgenfunction(func)):
            raise TypeError("ASGI mode can only register asynchronous functions.")
        return super().register(func)

    async def create_generator(
        self, generator: typing.AsyncGenerator
    ) -> typing.AsyncGenerator[str, None]:
        async for data in generator:
            yield b64encode(self.response_serializer.encode(data)).decode("ascii")

    async def on_call(self, request: AsgiRequest) -> AsgiResponse:
        # openapi docs
        if self.openapi is not None and request.method == "GET":
            if request.url.path[len(self.prefix) :] == "openapi-docs":
                return AsgiResponse(
                    OPENAPI_TEMPLATE, headers={"content-type": "text/html"}
                )
            elif request.url.path[len(self.prefix) :] == "get-openapi-docs":
                return AsgiResponse(
                    json.dumps(self.get_openapi_docs(), ensure_ascii=False),
                    headers={"content-type": "application/json"},
                )

        if request.method != "POST":
            return AsgiResponse(
                status_code=MethodNotAllowedHttpCode.get(request.method, 405)
            )

        check(
            request.headers["content-type"] == self.request_serializer.content_type
            or int(request.headers.get("content-type", 0)) == 0,
            SerializerNotAllowed(
                f"You should use content-type `{self.request_serializer.content_type}`"
            ),
        )
        data = self.request_serializer.decode(await request.body)

        callback = self.callbacks[request.url.path[len(self.prefix) :]]
        if hasattr(callback, "__body_model__"):
            result = callback(**getattr(callback, "__body_model__")(**data).dict())
        else:
            result = callback(**data)

        if inspect.isasyncgen(result):
            return AsgiEventResponse(
                self.create_generator(result),
                headers={"serializer": self.response_serializer.name},
            )

        return AsgiResponse(
            self.response_serializer.encode(await result),
            headers={
                "serializer": self.response_serializer.name,
                "content-type": self.response_serializer.content_type,
            },
        )

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        request = AsgiRequest(scope, receive, send)
        response = await self.on_call(request)
        return await response(scope, receive, send)
