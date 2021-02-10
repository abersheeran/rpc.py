import asyncio
import sys
import time
from typing import AsyncGenerator, Generator

import httpx
import pytest

from rpcpy.application import RPC, AsgiRPC, WsgiRPC
from rpcpy.serializers import SERIALIZER_NAMES, SERIALIZER_TYPES
from rpcpy.types import TypedDict


def test_wsgirpc():
    rpc = RPC()
    assert isinstance(rpc, WsgiRPC)

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
        assert client.get("/openapi-docs").status_code == 405
        assert client.post("/sayhi", data={"name": "Aber"}).status_code == 415
        assert client.post("/sayhi", json={"name": "Aber"}).status_code == 200


@pytest.mark.asyncio
async def test_asgirpc():
    rpc = RPC(mode="ASGI")
    assert isinstance(rpc, AsgiRPC)

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
        assert (await client.get("/openapi-docs")).status_code == 405
        assert (await client.post("/sayhi", data={"name": "Aber"})).status_code == 415
        assert (await client.post("/sayhi", json={"name": "Aber"})).status_code == 200


@pytest.mark.skipif("pydantic" in sys.modules, reason="Installed pydantic")
def test_wsgi_openapi_without_pydantic():
    rpc = RPC(openapi={"title": "Title", "description": "Description", "version": "v1"})

    @rpc.register
    def sayhi(name: str) -> str:
        """
        say hi with name
        """
        return f"hi {name}"

    with pytest.raises(NotImplementedError):
        rpc.get_openapi_docs()


@pytest.mark.skipif("pydantic" in sys.modules, reason="Installed pydantic")
@pytest.mark.asyncio
async def test_asgi_openapi_without_pydantic():
    rpc = RPC(
        mode="ASGI",
        openapi={"title": "Title", "description": "Description", "version": "v1"},
    )

    @rpc.register
    async def sayhi(name: str) -> str:
        """
        say hi with name
        """
        return f"hi {name}"

    with pytest.raises(NotImplementedError):
        rpc.get_openapi_docs()


@pytest.mark.skipif("pydantic" not in sys.modules, reason="Missing pydantic")
def test_wsgi_openapi():
    rpc = RPC(openapi={"title": "Title", "description": "Description", "version": "v1"})

    @rpc.register
    def sayhi(name: str) -> str:
        """
        say hi with name
        """
        return f"hi {name}"

    class DNS(TypedDict):
        dns_type: str
        host: str
        result: str

    @rpc.register
    def query_dns(dns_type: str, host: str) -> DNS:
        return {"dns_type": dns_type, "host": host, "result": "result"}

    @rpc.register
    def timestamp() -> Generator[int, None, None]:
        while True:
            yield int(time.time())
            time.sleep(1)

    assert rpc.get_openapi_docs() == OPENAPI_DOCS

    with httpx.Client(app=rpc, base_url="http://testServer/") as client:
        assert client.get("/openapi-docs").status_code == 200
        assert client.get("/get-openapi-docs").status_code == 200


@pytest.mark.skipif("pydantic" not in sys.modules, reason="Missing pydantic")
@pytest.mark.asyncio
async def test_asgi_openapi():
    rpc = RPC(
        mode="ASGI",
        openapi={"title": "Title", "description": "Description", "version": "v1"},
    )

    @rpc.register
    async def sayhi(name: str) -> str:
        """
        say hi with name
        """
        return f"hi {name}"

    DNS = TypedDict("DNS", {"dns_type": str, "host": str, "result": str})

    @rpc.register
    async def query_dns(dns_type: str, host: str) -> DNS:
        return {"dns_type": dns_type, "host": host, "result": "result"}

    @rpc.register
    async def timestamp() -> AsyncGenerator[int, None]:
        while True:
            yield int(time.time())
            await asyncio.sleep(1)

    assert rpc.get_openapi_docs() == OPENAPI_DOCS

    async with httpx.AsyncClient(app=rpc, base_url="http://testServer/") as client:
        assert (await client.get("/openapi-docs")).status_code == 200
        assert (await client.get("/get-openapi-docs")).status_code == 200


OPENAPI_DOCS = {
    "openapi": "3.0.0",
    "info": {"title": "Title", "description": "Description", "version": "v1"},
    "paths": {
        "/sayhi": {
            "post": {
                "summary": "say hi with name",
                "parameters": [
                    {
                        "name": "content-type",
                        "in": "header",
                        "description": "At least one of serializer and content-type must be used"
                        " so that the server can know which serializer is used to parse the data.",
                        "required": True,
                        "schema": {
                            "type": "string",
                            "enum": [
                                serializer_type for serializer_type in SERIALIZER_TYPES
                            ],
                        },
                    },
                    {
                        "name": "serializer",
                        "in": "header",
                        "description": "At least one of serializer and content-type must be used"
                        " so that the server can know which serializer is used to parse the data.",
                        "required": True,
                        "schema": {
                            "type": "string",
                            "enum": [
                                serializer_name for serializer_name in SERIALIZER_NAMES
                            ],
                        },
                    },
                ],
                "requestBody": {
                    "required": True,
                    "content": {
                        serializer_type: {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "name": {"title": "Name", "type": "string"}
                                },
                                "required": ["name"],
                            }
                        }
                        for serializer_type in SERIALIZER_TYPES
                    },
                },
                "responses": {
                    200: {
                        "content": {"application/json": {"schema": {"type": "string"}}},
                        "headers": {
                            "serializer": {
                                "schema": {
                                    "type": "string",
                                    "enum": ["json"],
                                },
                                "description": "Serializer Name",
                            }
                        },
                    }
                },
            }
        },
        "/query_dns": {
            "post": {
                "parameters": [
                    {
                        "name": "content-type",
                        "in": "header",
                        "description": "At least one of serializer and content-type must be used"
                        " so that the server can know which serializer is used to parse the data.",
                        "required": True,
                        "schema": {
                            "type": "string",
                            "enum": [
                                serializer_type for serializer_type in SERIALIZER_TYPES
                            ],
                        },
                    },
                    {
                        "name": "serializer",
                        "in": "header",
                        "description": "At least one of serializer and content-type must be used"
                        " so that the server can know which serializer is used to parse the data.",
                        "required": True,
                        "schema": {
                            "type": "string",
                            "enum": [
                                serializer_name for serializer_name in SERIALIZER_NAMES
                            ],
                        },
                    },
                ],
                "requestBody": {
                    "required": True,
                    "content": {
                        serializer_type: {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "dns_type": {
                                        "title": "Dns Type",
                                        "type": "string",
                                    },
                                    "host": {
                                        "title": "Host",
                                        "type": "string",
                                    },
                                },
                                "required": ["dns_type", "host"],
                            }
                        }
                        for serializer_type in SERIALIZER_TYPES
                    },
                },
                "responses": {
                    200: {
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "dns_type": {
                                            "title": "Dns Type",
                                            "type": "string",
                                        },
                                        "host": {
                                            "title": "Host",
                                            "type": "string",
                                        },
                                        "result": {
                                            "title": "Result",
                                            "type": "string",
                                        },
                                    },
                                    "required": ["dns_type", "host", "result"],
                                }
                            }
                        },
                        "headers": {
                            "serializer": {
                                "schema": {
                                    "type": "string",
                                    "enum": ["json"],
                                },
                                "description": "Serializer Name",
                            }
                        },
                    }
                },
            }
        },
        "/timestamp": {
            "post": {
                "parameters": [
                    {
                        "name": "content-type",
                        "in": "header",
                        "description": "At least one of serializer and content-type must be used"
                        " so that the server can know which serializer is used to parse the data.",
                        "required": True,
                        "schema": {
                            "type": "string",
                            "enum": [
                                serializer_type for serializer_type in SERIALIZER_TYPES
                            ],
                        },
                    },
                    {
                        "name": "serializer",
                        "in": "header",
                        "description": "At least one of serializer and content-type must be used"
                        " so that the server can know which serializer is used to parse the data.",
                        "required": True,
                        "schema": {
                            "type": "string",
                            "enum": [
                                serializer_name for serializer_name in SERIALIZER_NAMES
                            ],
                        },
                    },
                ],
                "responses": {
                    200: {
                        "content": {"text/event-stream": {"schema": {"type": "integer"}}},
                        "headers": {
                            "serializer": {
                                "schema": {"type": "string", "enum": ["json"]},
                                "description": "Serializer Name",
                            }
                        },
                    }
                },
            }
        },
    },
}
