import pytest
import httpx

from rpcpy import RPC
from rpcpy.client import Client


@pytest.fixture
def wsgi_app():
    app = RPC()

    @app.register
    def sayhi(name: str) -> str:
        return f"hi {name}"

    return app


@pytest.fixture
def asgi_app():
    app = RPC(mode="ASGI")

    @app.register
    async def sayhi(name: str) -> str:
        return f"hi {name}"

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
