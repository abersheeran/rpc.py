import typing
import inspect
import functools
from base64 import b64decode
from types import FunctionType

import httpx

from rpcpy.serializers import get_serializer

__all__ = ["Client"]

Function = typing.TypeVar("Function", FunctionType, FunctionType)


class Client:
    def __init__(
        self, client: typing.Union[httpx.Client, httpx.AsyncClient], *, base_url: str,
    ) -> None:
        assert base_url.endswith("/"), "base_url must be end with '/'"
        self.base_url = base_url
        self.client = client
        self.is_async = isinstance(client, httpx.AsyncClient)

    def remote_call(self, func: Function) -> Function:
        is_async = inspect.iscoroutinefunction(func) or inspect.isasyncgenfunction(func)

        if is_async:
            return self.async_remote_call(func)
        return self.sync_remote_call(func)

    def async_remote_call(self, func: Function) -> Function:
        if not self.is_async:
            raise TypeError(
                "Synchronization Client can only register synchronization functions."
            )

        if not inspect.isasyncgenfunction(func):

            @functools.wraps(func)
            async def wrapper(*args: typing.Any, **kwargs: typing.Any) -> typing.Any:
                sig = inspect.signature(func)
                bound_values = sig.bind(*args, **kwargs)
                url = self.base_url + func.__name__
                resp: httpx.Response = await self.client.post(  # type: ignore
                    url, json=dict(bound_values.arguments.items())
                )
                resp.raise_for_status()
                serializer = get_serializer(resp.headers)
                return serializer.decode(resp.content)

        else:

            @functools.wraps(func)
            async def wrapper(*args: typing.Any, **kwargs: typing.Any) -> typing.Any:
                sig = inspect.signature(func)
                bound_values = sig.bind(*args, **kwargs)
                url = self.base_url + func.__name__
                async with self.client.stream(
                    "POST", url, json=dict(bound_values.arguments.items())
                ) as resp:  # type: httpx.Response
                    serializer = get_serializer(resp.headers)
                    # I don't know how to solve this error:
                    # "AsyncIterator[str]" has no attribute "__iter__"; maybe "__aiter__"? (not iterable)
                    # So, mark `type: ignore`.
                    async for line in resp.aiter_lines():  # type: ignore
                        if line.startswith("data:"):
                            data = line.split(":", maxsplit=1)[1]
                            yield serializer.decode(b64decode(data.encode("ascii")))

        return typing.cast(Function, wrapper)

    def sync_remote_call(self, func: Function) -> Function:
        if self.is_async:
            raise TypeError(
                "Asynchronous Client can only register asynchronous functions."
            )
        if not inspect.isgeneratorfunction(func):

            @functools.wraps(func)
            def wrapper(*args: typing.Any, **kwargs: typing.Any) -> typing.Any:
                sig = inspect.signature(func)
                bound_values = sig.bind(*args, **kwargs)
                url = self.base_url + func.__name__
                resp: httpx.Response = self.client.post(  # type: ignore
                    url, json=dict(bound_values.arguments.items()),
                )
                resp.raise_for_status()
                serializer = get_serializer(resp.headers)
                return serializer.decode(resp.content)

        else:

            @functools.wraps(func)
            def wrapper(*args: typing.Any, **kwargs: typing.Any) -> typing.Any:
                sig = inspect.signature(func)
                bound_values = sig.bind(*args, **kwargs)
                url = self.base_url + func.__name__
                with self.client.stream(
                    "POST", url, json=dict(bound_values.arguments.items())
                ) as resp:  # type: httpx.Response
                    serializer = get_serializer(resp.headers)
                    for line in resp.iter_lines():
                        if line.startswith("data:"):
                            data = line.split(":", maxsplit=1)[1]
                            yield serializer.decode(b64decode(data.encode("ascii")))

        return typing.cast(Function, wrapper)
