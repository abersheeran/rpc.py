import asyncio
import time
from typing import AsyncGenerator, Generator

import httpx
import pytest

from rpcpy import RPC
from rpcpy.client import Client


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

    return app


@pytest.fixture
def sync_client(wsgi_app) -> Client:
    httpx_client = httpx.Client(app=wsgi_app)
    try:
        yield Client(httpx_client, base_url="http://testserver/")
    finally:
        httpx_client.close()


@pytest.fixture
def async_client(asgi_app) -> Client:
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
