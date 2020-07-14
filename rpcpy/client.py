import typing
import inspect
import functools

import httpx

from rpcpy.serializers import BaseSerializer, JSONSerializer

Function = typing.TypeVar("Function")


class Client:
    def __init__(
        self,
        client: httpx.Client,
        *,
        base_url: str,
        prefix: str = "/",
        serializer: BaseSerializer = JSONSerializer(),
    ) -> None:
        assert prefix.startswith("/") and prefix.endswith("/")
        self.base_url = base_url.rstrip("/")
        self.prefix = prefix
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
                "Asynchronous Client can only register asynchronous functions."
            )

        @functools.wraps(func)
        async def wrapper(*args: typing.Any, **kwargs: typing.Any) -> typing.Any:
            sig = inspect.signature(func)
            bound_values = sig.bind(*args, **kwargs)
            url = self.base_url + self.prefix + func.__name__
            resp = await self.client.post(
                url, json=dict(bound_values.arguments.items())
            )  # type: httpx.Response
            resp.raise_for_status()
            assert resp.headers.get("serializer") == self.serializer.name
            return self.serializer.decode(resp.content)

        return wrapper

    def sync_remote_call(self, func: Function) -> Function:
        if self.is_async:
            raise TypeError(
                "Synchronization Client can only register synchronization functions."
            )

        @functools.wraps(func)
        def wrapper(*args: typing.Any, **kwargs: typing.Any) -> typing.Any:
            sig = inspect.signature(func)
            bound_values = sig.bind(*args, **kwargs)
            url = self.base_url + self.prefix + func.__name__
            resp = self.client.post(
                url, json=dict(bound_values.arguments.items()),
            )  # type: httpx.Response
            resp.raise_for_status()
            assert resp.headers.get("serializer") == self.serializer.name
            return self.serializer.decode(resp.content)

        return wrapper
