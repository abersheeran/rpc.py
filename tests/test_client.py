import pytest
import httpx

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
    def yield_data(max_num: int):
        for i in range(max_num):
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
    async def yield_data(max_num: int):
        for i in range(max_num):
            yield i

    return app


@pytest.fixture
def sync_client(wsgi_app) -> Client:
    return Client(httpx.Client(app=wsgi_app), base_url="http://testserver/")


@pytest.fixture
def async_client(asgi_app) -> Client:
    return Client(httpx.AsyncClient(app=asgi_app), base_url="http://testserver/")


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
    for i in yield_data(10):
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
    async for i in yield_data(10):
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
