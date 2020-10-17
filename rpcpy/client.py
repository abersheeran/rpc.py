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


class Client:
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
        self.is_async = isinstance(client, httpx.AsyncClient)

    def remote_call(self, func: Function) -> Function:
        is_async = inspect.iscoroutinefunction(func) or inspect.isasyncgenfunction(func)
        set_type_model(func)  # try set `__body_model__`
        if is_async:
            return self.__async_remote_call(func)
        return self.__sync_remote_call(func)

    def _get_url(self, func: Function) -> str:
        return self.base_url + func.__name__

    def __async_remote_call(self, func: Function) -> Function:
        if not self.is_async:
            raise TypeError(
                "Synchronization Client can only register synchronization functions."
            )

        sig = inspect.signature(func)
        url = self._get_url(func)

        def get_post_content(*args: typing.Any, **kwargs: typing.Any) -> bytes:
            bound_values = sig.bind(*args, **kwargs)
            if hasattr(func, "__body_model__"):
                _params = getattr(func, "__body_model__")(
                    **bound_values.arguments
                ).dict()
            else:
                _params = dict(**bound_values.arguments)
            return self.request_serializer.encode(_params)

        if not inspect.isasyncgenfunction(func):

            @functools.wraps(func)
            async def wrapper(*args: typing.Any, **kwargs: typing.Any) -> typing.Any:
                post_data = get_post_content(*args, **kwargs)
                resp: httpx.Response = await self.client.post(  # type: ignore
                    url,
                    content=post_data,
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
                post_data = get_post_content(*args, **kwargs)
                async with self.client.stream(
                    "POST",
                    url,
                    content=post_data,
                    headers={
                        "content-type": self.request_serializer.content_type,
                        "serializer": self.request_serializer.name,
                    },
                ) as resp:
                    resp.raise_for_status()
                    async for line in resp.aiter_lines():  # type: ignore
                        if line.startswith("data:"):
                            data = line.split(":", maxsplit=1)[1]
                            yield self.response_serializer.decode(
                                b64decode(data.encode("ascii"))
                            )

        return typing.cast(Function, wrapper)

    def __sync_remote_call(self, func: Function) -> Function:
        if self.is_async:
            raise TypeError(
                "Asynchronous Client can only register asynchronous functions."
            )

        sig = inspect.signature(func)
        url = self._get_url(func)

        def get_post_content(*args: typing.Any, **kwargs: typing.Any) -> bytes:
            bound_values = sig.bind(*args, **kwargs)
            if hasattr(func, "__body_model__"):
                _params = getattr(func, "__body_model__")(
                    **bound_values.arguments
                ).dict()
            else:
                _params = dict(**bound_values.arguments)
            return self.request_serializer.encode(_params)

        if not inspect.isgeneratorfunction(func):

            @functools.wraps(func)
            def wrapper(*args: typing.Any, **kwargs: typing.Any) -> typing.Any:
                post_content = get_post_content(*args, **kwargs)
                resp: httpx.Response = self.client.post(  # type: ignore
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
                post_content = get_post_content(*args, **kwargs)
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
