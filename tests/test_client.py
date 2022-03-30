import asyncio
import time
from typing import AsyncGenerator, Generator

import httpx
import pytest

from rpcpy import RPC
from rpcpy.client import Client, ServerSentEventsParser
from rpcpy.exceptions import RemoteCallError


@pytest.fixture
def wsgi_app():
    app = RPC()

    @app.register
    def none() -> None:
        return

    @app.register
    def sayhi(name: str) -> str:
        return f"hi {name}"

    @app.register
    def yield_data(max_num: int) -> Generator[int, None, None]:
        for i in range(max_num):
            time.sleep(1)
            yield i

    @app.register
    def exception() -> str:
        raise ValueError("Message")

    @app.register
    def exception_in_g() -> Generator[str, None, None]:
        yield "Message"
        raise TypeError("Message")

    return app


@pytest.fixture
def asgi_app():
    app = RPC(mode="ASGI")

    @app.register
    async def none() -> None:
        return

    @app.register
    async def sayhi(name: str) -> str:
        return f"hi {name}"

    @app.register
    async def yield_data(max_num: int) -> AsyncGenerator[int, None]:
        for i in range(max_num):
            await asyncio.sleep(1)
            yield i

    @app.register
    async def exception() -> str:
        raise ValueError("Message")

    @app.register
    async def exception_in_g() -> AsyncGenerator[str, None]:
        yield "Message"
        raise TypeError("Message")

    return app


@pytest.fixture
def sync_client(wsgi_app):
    httpx_client = httpx.Client(app=wsgi_app)
    try:
        yield Client(httpx_client, base_url="http://testserver/")
    finally:
        httpx_client.close()


@pytest.fixture
def async_client(asgi_app):
    httpx_client = httpx.AsyncClient(app=asgi_app)
    try:
        yield Client(httpx_client, base_url="http://testserver/")
    finally:
        asyncio.get_event_loop().run_until_complete(httpx_client.aclose())


def test_sync_client(sync_client):
    @sync_client.remote_call
    def sayhi(name: str) -> str:
        ...

    assert sayhi("rpc.py") == "hi rpc.py"

    with pytest.raises(
        TypeError,
        match="Synchronization Client can only register synchronization functions.",
    ):

        @sync_client.remote_call
        async def sayhi(name: str) -> str:
            ...

    @sync_client.remote_call
    def yield_data(max_num: int):
        yield

    index = 0
    for i in yield_data(5):
        assert index == i
        index += 1

    @sync_client.remote_call
    def exception() -> str:
        ...

    with pytest.raises(RemoteCallError, match="ValueError: Message"):
        exception()

    @sync_client.remote_call
    def exception_in_g() -> Generator[str, None, None]:
        yield  # type: ignore

    with pytest.raises(RemoteCallError, match="TypeError: Message"):
        for msg in exception_in_g():
            assert msg == "Message"


@pytest.mark.asyncio
async def test_async_client(async_client):
    @async_client.remote_call
    async def sayhi(name: str) -> str:
        ...

    assert await sayhi("rpc.py") == "hi rpc.py"

    with pytest.raises(
        TypeError,
        match="Asynchronous Client can only register asynchronous functions.",
    ):

        @async_client.remote_call
        def sayhi(name: str) -> str:
            ...

    @async_client.remote_call
    async def yield_data(max_num: int):
        yield

    index = 0
    async for i in yield_data(5):
        assert index == i
        index += 1

    @async_client.remote_call
    async def exception() -> str:
        ...

    with pytest.raises(RemoteCallError, match="ValueError: Message"):
        await exception()

    @async_client.remote_call
    async def exception_in_g() -> AsyncGenerator[str, None]:
        yield  # type: ignore

    with pytest.raises(RemoteCallError, match="TypeError: Message"):
        async for msg in exception_in_g():
            assert msg == "Message"


def test_none(sync_client):
    @sync_client.remote_call
    def none() -> None:
        ...

    assert none() is None

    with pytest.raises(TypeError):
        none("hi")


@pytest.mark.asyncio
async def test_async_none(async_client):
    @async_client.remote_call
    async def none() -> None:
        ...

    assert await none() is None

    with pytest.raises(TypeError):
        await none("hi")


def test_invalid_client():
    with pytest.raises(
        TypeError,
        match="The parameter `client` must be an httpx.Client or httpx.AsyncClient object.",
    ):
        Client(0)


def test_sse_parser():
    parser = ServerSentEventsParser()

    parser.feed("data: hello\n")
    assert parser.feed("\n") == {"data": "hello"}

    parser.feed("data: hello\n")
    parser.feed("data: world\n")
    assert parser.feed("\n") == {"data": "hello\nworld"}

    parser.feed(": ping\n")
    assert parser.feed("\n") == {}

    parser.feed("retry: 1\n")
    assert parser.feed("\n") == {"retry": 1}

    parser.feed("retry: p1\n")
    assert parser.feed("\n") == {}

    parser.feed("undefined")
    assert parser.feed("\n") == {}

    parser.feed("event")
    assert parser.feed("\n") == {"event": ""}
