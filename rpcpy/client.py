import typing
import inspect
import functools
from types import FunctionType

import httpx

from rpcpy.serializers import BaseSerializer, JSONSerializer

__all__ = ["Client"]

Function = typing.TypeVar("Function", FunctionType, FunctionType)


class Client:
    def __init__(
        self,
        client: typing.Union[httpx.Client, httpx.AsyncClient],
        *,
        base_url: str,
        serializer: BaseSerializer = JSONSerializer(),
    ) -> None:
        assert base_url.endswith("/"), "base_url must be end with '/'"
        self.base_url = base_url
        self.serializer = serializer
        self.client = client
        self.is_async = isinstance(client, httpx.AsyncClient)

    def remote_call(self, func: Function) -> Function:
        is_async = inspect.iscoroutinefunction(func)

        if is_async:
            return self.async_remote_call(func)
        return self.sync_remote_call(func)

    def async_remote_call(self, func: Function) -> Function:
        if not self.is_async:
            raise TypeError(
                "Synchronization Client can only register synchronization functions."
            )

        @functools.wraps(func)
        async def wrapper(*args: typing.Any, **kwargs: typing.Any) -> typing.Any:
            sig = inspect.signature(func)
            bound_values = sig.bind(*args, **kwargs)
            url = self.base_url + func.__name__
            resp: httpx.Response = await self.client.post(  # type: ignore
                url, json=dict(bound_values.arguments.items())
            )
            resp.raise_for_status()
            assert resp.headers.get("serializer") == self.serializer.name
            return self.serializer.decode(resp.content)

        return typing.cast(Function, wrapper)

    def sync_remote_call(self, func: Function) -> Function:
        if self.is_async:
            raise TypeError(
                "Asynchronous Client can only register asynchronous functions."
            )

        @functools.wraps(func)
        def wrapper(*args: typing.Any, **kwargs: typing.Any) -> typing.Any:
            sig = inspect.signature(func)
            bound_values = sig.bind(*args, **kwargs)
            url = self.base_url + func.__name__
            resp: httpx.Response = self.client.post(  # type: ignore
                url, json=dict(bound_values.arguments.items()),
            )
            resp.raise_for_status()
            assert resp.headers.get("serializer") == self.serializer.name
            return self.serializer.decode(resp.content)

        return typing.cast(Function, wrapper)
