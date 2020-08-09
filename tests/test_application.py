import httpx
import pytest

from rpcpy.application import RPC, WSGIRPC, ASGIRPC


def test_wsgirpc():
    rpc = RPC()
    assert isinstance(rpc, WSGIRPC)

    @rpc.register
    def sayhi(name: str) -> str:
        return f"hi {name}"

    with pytest.raises(
        TypeError, match="WSGI mode can only register synchronization functions."
    ):

        @rpc.register
        async def async_sayhi(name: str) -> str:
            return f"hi {name}"

    with httpx.Client(app=rpc, base_url="http://testServer/") as client:
        assert client.get("/openapi-docs").status_code == 404


@pytest.mark.asyncio
async def test_asgirpc():
    rpc = RPC(mode="ASGI")
    assert isinstance(rpc, ASGIRPC)

    @rpc.register
    async def sayhi(name: str) -> str:
        return f"hi {name}"

    with pytest.raises(
        TypeError, match="ASGI mode can only register asynchronous functions."
    ):

        @rpc.register
        def sync_sayhi(name: str) -> str:
            return f"hi {name}"

    async with httpx.AsyncClient(app=rpc, base_url="http://testServer/") as client:
        assert (await client.get("/openapi-docs")).status_code == 404


def test_wsgi_openapi():
    rpc = RPC(openapi={"title": "Title", "description": "Description", "version": "v1"})

    @rpc.register
    def sayhi(name: str) -> str:
        return f"hi {name}"

    assert rpc.get_openapi_docs() == {
        "openapi": "3.0.0",
        "info": {"description": "Description", "title": "Title", "version": "v1"},
        "paths": {
            "/sayhi": {
                "post": {
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "name": {"title": "Name", "type": "string"}
                                    },
                                    "required": ["name"],
                                }
                            }
                        },
                    }
                }
            }
        },
    }

    with httpx.Client(app=rpc, base_url="http://testServer/") as client:
        assert client.get("/openapi-docs").status_code == 200
        assert client.get("/get-openapi-docs").status_code == 200


@pytest.mark.asyncio
async def test_asgi_openapi():
    rpc = RPC(
        mode="ASGI",
        openapi={"title": "Title", "description": "Description", "version": "v1"},
    )

    @rpc.register
    async def sayhi(name: str) -> str:
        return f"hi {name}"

    assert rpc.get_openapi_docs() == {
        "openapi": "3.0.0",
        "info": {"description": "Description", "title": "Title", "version": "v1"},
        "paths": {
            "/sayhi": {
                "post": {
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "name": {"title": "Name", "type": "string"}
                                    },
                                    "required": ["name"],
                                }
                            }
                        },
                    }
                }
            }
        },
    }

    async with httpx.AsyncClient(app=rpc, base_url="http://testServer/") as client:
        assert (await client.get("/openapi-docs")).status_code == 200
        assert (await client.get("/get-openapi-docs")).status_code == 200
