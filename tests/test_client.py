import pytest
import httpx

from rpcpy import RPC
from rpcpy.client import Client


@pytest.fixture
def app():
    app = RPC()

    @app.register
    def sync_sayhi(name: str) -> str:
        return f"hi {name}"

    @app.register
    async def async_sayhi(name: str) -> str:
        return f"hi {name}"

    return app


@pytest.fixture
def sync_client(app):
    return Client(httpx.Client(app=app.wsgi), base_url="http://testserver/")


@pytest.fixture
def async_client(app):
    return Client(httpx.AsyncClient(app=app.asgi), base_url="http://testserver/")


@pytest.mark.asyncio
async def test_async_client(async_client):
    @async_client.remote_call
    async def async_sayhi(name: str) -> str:
        ...

    assert await async_sayhi("rpc.py") == "hi rpc.py"

    with pytest.raises(
        TypeError,
        match="Asynchronous Client can only register asynchronous functions.",
    ):

        @async_client.remote_call
        def sayhi(name: str) -> str:
            ...
