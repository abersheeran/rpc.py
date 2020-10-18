import typing
import inspect
import functools
from base64 import b64decode
from types import FunctionType

import httpx

from rpcpy.serializers import BaseSerializer, JSONSerializer
from rpcpy.utils.openapi import set_type_model

__all__ = ["Client"]

Function = typing.TypeVar("Function", bound=FunctionType)


class ClientMeta(type):
    def __call__(cls, *args: typing.Any, **kwargs: typing.Any) -> typing.Any:
        if cls.__name__ == "Client":
            if isinstance(args[0], httpx.Client):
                return SyncClient(*args, **kwargs)

            if isinstance(args[0], httpx.AsyncClient):
                return AsyncClient(*args, **kwargs)

            raise TypeError(
                "The parameter `client` must be an httpx.Client or httpx.AsyncClient object."
            )

        return super().__call__(*args, **kwargs)


class Client(metaclass=ClientMeta):
    def __init__(
        self,
        client: typing.Union[httpx.Client, httpx.AsyncClient],
        *,
        base_url: str,
        request_serializer: BaseSerializer = JSONSerializer(),
        response_serializer: BaseSerializer = JSONSerializer(),
    ) -> None:
        assert base_url.endswith("/"), "base_url must be end with '/'"
        self.base_url = base_url
        self.client = client
        self.request_serializer = request_serializer
        self.response_serializer = response_serializer

    def remote_call(self, func: Function) -> Function:
        set_type_model(func)  # try set `__body_model__`
        return func

    def _get_url(self, func: Function) -> str:
        return self.base_url + func.__name__

    def _get_content(
        self, func: typing.Callable, *args: typing.Any, **kwargs: typing.Any
    ) -> bytes:
        sig = inspect.signature(func)
        bound_values = sig.bind(*args, **kwargs)
        if hasattr(func, "__body_model__"):
            _params = getattr(func, "__body_model__")(**bound_values.arguments).dict()
        else:
            _params = dict(**bound_values.arguments)
        return self.request_serializer.encode(_params)


class AsyncClient(Client):
    if typing.TYPE_CHECKING:
        client: httpx.AsyncClient

    def remote_call(self, func: Function) -> Function:
        if not (inspect.iscoroutinefunction(func) or inspect.isasyncgenfunction(func)):
            raise TypeError(
                "Asynchronous Client can only register asynchronous functions."
            )

        func = super().remote_call(func)
        url = self._get_url(func)

        if not inspect.isasyncgenfunction(func):

            @functools.wraps(func)
            async def wrapper(*args: typing.Any, **kwargs: typing.Any) -> typing.Any:
                post_content = self._get_content(func, *args, **kwargs)
                resp = await self.client.post(
                    url,
                    content=post_content,
                    headers={
                        "content-type": self.request_serializer.content_type,
                        "serializer": self.request_serializer.name,
                    },
                )
                resp.raise_for_status()
                return self.response_serializer.decode(resp.content)

        else:

            @functools.wraps(func)
            async def wrapper(*args: typing.Any, **kwargs: typing.Any) -> typing.Any:
                post_content = self._get_content(func, *args, **kwargs)
                async with self.client.stream(
                    "POST",
                    url,
                    content=post_content,
                    headers={
                        "content-type": self.request_serializer.content_type,
                        "serializer": self.request_serializer.name,
                    },
                ) as resp:
                    resp.raise_for_status()
                    async for line in resp.aiter_lines():
                        if line.startswith("data:"):
                            data = line.split(":", maxsplit=1)[1]
                            yield self.response_serializer.decode(
                                b64decode(data.encode("ascii"))
                            )

        return typing.cast(Function, wrapper)


class SyncClient(Client):
    if typing.TYPE_CHECKING:
        client: httpx.Client

    def remote_call(self, func: Function) -> Function:
        if inspect.iscoroutinefunction(func) or inspect.isasyncgenfunction(func):
            raise TypeError(
                "Synchronization Client can only register synchronization functions."
            )

        func = super().remote_call(func)
        url = self._get_url(func)

        if not inspect.isgeneratorfunction(func):

            @functools.wraps(func)
            def wrapper(*args: typing.Any, **kwargs: typing.Any) -> typing.Any:
                post_content = self._get_content(func, *args, **kwargs)
                resp = self.client.post(
                    url,
                    content=post_content,
                    headers={
                        "content-type": self.request_serializer.content_type,
                        "serializer": self.request_serializer.name,
                    },
                )
                resp.raise_for_status()
                return self.response_serializer.decode(resp.content)

        else:

            @functools.wraps(func)
            def wrapper(*args: typing.Any, **kwargs: typing.Any) -> typing.Any:
                post_content = self._get_content(func, *args, **kwargs)
                with self.client.stream(
                    "POST",
                    url,
                    content=post_content,
                    headers={
                        "content-type": self.request_serializer.content_type,
                        "serializer": self.request_serializer.name,
                    },
                ) as resp:
                    resp.raise_for_status()
                    for line in resp.iter_lines():
                        if line.startswith("data:"):
                            data = line.split(":", maxsplit=1)[1]
                            yield self.response_serializer.decode(
                                b64decode(data.encode("ascii"))
                            )

        return typing.cast(Function, wrapper)
