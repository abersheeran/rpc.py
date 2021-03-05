import copy
import inspect
import json
import typing
from base64 import b64encode
from collections.abc import AsyncGenerator, Generator

from baize.asgi import Request as AsgiRequest
from baize.asgi import Response as AsgiResponse
from baize.asgi import SendEventResponse as AsgiEventResponse
from baize.typing import ASGIApp, ServerSentEvent, WSGIApp
from baize.wsgi import Request as WsgiRequest
from baize.wsgi import Response as WsgiResponse
from baize.wsgi import SendEventResponse as WsgiEventResponse

from rpcpy.exceptions import SerializerNotFound
from rpcpy.openapi import TEMPLATE as OPENAPI_TEMPLATE
from rpcpy.openapi import (
    create_model,
    is_typed_dict_type,
    parse_typed_dict,
    set_type_model,
)
from rpcpy.serializers import (
    SERIALIZER_NAMES,
    SERIALIZER_TYPES,
    BaseSerializer,
    JSONSerializer,
    get_serializer,
)
from rpcpy.typing import (
    Environ,
    Literal,
    Receive,
    Scope,
    Send,
    StartResponse,
    TypedDict,
)

__all__ = ["RPC", "WsgiRPC", "AsgiRPC"]

Callable = typing.TypeVar("Callable", bound=typing.Callable)


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
        response_serializer: BaseSerializer = JSONSerializer(),
        openapi: OpenAPI = None,
    ) -> None:
        assert prefix.startswith("/") and prefix.endswith("/")
        self.callbacks: typing.Dict[str, typing.Callable] = {}
        self.prefix = prefix
        self.response_serializer = response_serializer
        self.openapi = openapi

    def register(self, func: Callable) -> Callable:
        self.callbacks[func.__name__] = func
        set_type_model(func)
        return func

    def get_openapi_docs(self) -> dict:
        openapi: dict = {
            "openapi": "3.0.0",
            "info": copy.deepcopy(self.openapi) or {},
            "paths": {},
        }
        openapi["definitions"] = definitions = {}

        for name, callback in self.callbacks.items():
            _ = {}
            # summary and description
            doc = callback.__doc__
            if isinstance(doc, str):
                _.update(
                    zip(
                        ("summary", "description"),
                        map(lambda i: i.strip(), doc.strip().split("\n\n", 1)),
                    )
                )
            _["parameters"] = [
                {
                    "name": "content-type",
                    "in": "header",
                    "description": "At least one of serializer and content-type must be used"
                    " so that the server can know which serializer is used to parse the data.",
                    "required": True,
                    "schema": {
                        "type": "string",
                        "enum": [serializer_type for serializer_type in SERIALIZER_TYPES],
                    },
                },
                {
                    "name": "serializer",
                    "in": "header",
                    "description": "At least one of serializer and content-type must be used"
                    " so that the server can know which serializer is used to parse the data.",
                    "required": True,
                    "schema": {
                        "type": "string",
                        "enum": [serializer_name for serializer_name in SERIALIZER_NAMES],
                    },
                },
            ]
            # request body
            body_model = getattr(callback, "__body_model__", None)
            if body_model:
                _schema = copy.deepcopy(body_model.schema())
                definitions.update(_schema.pop("definitions", {}))
                del _schema["title"]
                _["requestBody"] = {
                    "required": True,
                    "content": {
                        serializer_type: {"schema": _schema}
                        for serializer_type in SERIALIZER_TYPES
                    },
                }
            # response & only 200
            sig = inspect.signature(callback)
            if sig.return_annotation != sig.empty:
                content_type = self.response_serializer.content_type
                return_annotation = sig.return_annotation
                if getattr(sig.return_annotation, "__origin__", None) in (
                    Generator,
                    AsyncGenerator,
                ):
                    content_type = "text/event-stream"
                    return_annotation = return_annotation.__args__[0]
                if is_typed_dict_type(return_annotation):
                    resp_model = parse_typed_dict(return_annotation)
                else:
                    resp_model = create_model(
                        callback.__name__ + "-return",
                        __root__=(return_annotation, ...),
                    )
                _schema = copy.deepcopy(resp_model.schema())
                definitions.update(_schema.pop("definitions", {}))
                del _schema["title"]
                _["responses"] = {
                    200: {
                        "content": {content_type: {"schema": _schema}},
                        "headers": {
                            "serializer": {
                                "schema": {
                                    "type": "string",
                                    "enum": [self.response_serializer.name],
                                },
                                "description": "Serializer Name",
                            }
                        },
                    }
                }
            if _:
                openapi["paths"][f"{self.prefix}{name}"] = {"post": _}
        return openapi

    @typing.overload
    def return_response_class(self, request: WsgiRequest) -> typing.Type[WsgiResponse]:
        pass

    @typing.overload
    def return_response_class(self, request: AsgiRequest) -> typing.Type[AsgiResponse]:
        pass

    def return_response_class(self, request):
        return AsgiResponse if isinstance(request, AsgiRequest) else WsgiResponse

    @typing.overload
    def preprocess(self, request: WsgiRequest) -> typing.Optional[WsgiResponse]:
        pass

    @typing.overload
    def preprocess(self, request: AsgiRequest) -> typing.Optional[AsgiResponse]:
        pass

    def preprocess(self, request):
        """
        Preprocess request
        """
        # try return openapi
        if self.openapi is not None and request.method == "GET":
            if request.url.path[len(self.prefix) :] == "openapi-docs":
                return self.return_response_class(request)(
                    OPENAPI_TEMPLATE, media_type="text/html"
                )
            elif request.url.path[len(self.prefix) :] == "get-openapi-docs":
                return self.return_response_class(request)(
                    json.dumps(self.get_openapi_docs(), ensure_ascii=False),
                    media_type="application/json",
                )

        # check request method
        if request.method != "POST":
            return self.return_response_class(request)(b"", status_code=405)

        # check serializer
        try:
            self.request_serializer = get_serializer(request.headers)
        except SerializerNotFound as exception:
            return self.return_response_class(request)(
                str(exception), status_code=415, media_type="text/plain"
            )


class WsgiRPC(RPC):
    def register(self, func: Callable) -> Callable:
        if inspect.iscoroutinefunction(func) or inspect.isasyncgenfunction(func):
            raise TypeError("WSGI mode can only register synchronization functions.")
        return super().register(func)

    def create_generator(
        self, generator: typing.Generator
    ) -> typing.Generator[ServerSentEvent, None, None]:
        for data in generator:
            yield {
                "data": b64encode(self.response_serializer.encode(data)).decode("ascii")
            }

    def on_call(self, request: WsgiRequest) -> WSGIApp:
        data = self.request_serializer.decode(request.body)

        callback = self.callbacks[request.url.path[len(self.prefix) :]]
        if hasattr(callback, "__body_model__"):
            result = callback(**getattr(callback, "__body_model__")(**data).dict())
        else:
            result = callback(**data)

        response: typing.Union[WsgiEventResponse, WsgiResponse]
        if inspect.isgenerator(result):
            response = WsgiEventResponse(
                self.create_generator(result), headers={"serializer-base": "base64"}
            )
        else:
            response = WsgiResponse(
                self.response_serializer.encode(result),
                headers={"content-type": self.response_serializer.content_type},
            )
        response.headers["serializer"] = self.response_serializer.name
        return response

    def __call__(
        self, environ: Environ, start_response: StartResponse
    ) -> typing.Iterable[bytes]:
        request = WsgiRequest(environ)
        response = self.preprocess(request) or self.on_call(request)
        return response(environ, start_response)


class AsgiRPC(RPC):
    def register(self, func: Callable) -> Callable:
        if not (inspect.iscoroutinefunction(func) or inspect.isasyncgenfunction(func)):
            raise TypeError("ASGI mode can only register asynchronous functions.")
        return super().register(func)

    async def create_generator(
        self, generator: typing.AsyncGenerator
    ) -> typing.AsyncGenerator[ServerSentEvent, None]:
        async for data in generator:
            yield {
                "data": b64encode(self.response_serializer.encode(data)).decode("ascii")
            }

    async def on_call(self, request: AsgiRequest) -> ASGIApp:
        data = self.request_serializer.decode(await request.body)

        callback = self.callbacks[request.url.path[len(self.prefix) :]]
        if hasattr(callback, "__body_model__"):
            result = callback(**getattr(callback, "__body_model__")(**data).dict())
        else:
            result = callback(**data)

        response: typing.Union[AsgiEventResponse, AsgiResponse]
        if inspect.isasyncgen(result):
            response = AsgiEventResponse(
                self.create_generator(result), headers={"serializer-base": "base64"}
            )
        else:
            response = AsgiResponse(
                self.response_serializer.encode(await result),
                headers={"content-type": self.response_serializer.content_type},
            )
        response.headers["serializer"] = self.response_serializer.name
        return response

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        request = AsgiRequest(scope, receive, send)
        response = self.preprocess(request) or await self.on_call(request)
        return await response(scope, receive, send)
