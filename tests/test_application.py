import asyncio
import json
import sys
import time
from typing import AsyncGenerator, Generator

if sys.version_info[:2] < (3, 8):
    from typing_extensions import TypedDict
else:
    from typing import TypedDict

import httpx
import pytest

from rpcpy.application import RPC, AsgiRPC, WsgiRPC
from rpcpy.serializers import SERIALIZER_NAMES, SERIALIZER_TYPES


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

    @rpc.register
    def sayhi_without_type_hint(name):
        return f"hi {name}"

    with httpx.Client(app=rpc, base_url="http://testServer/") as client:
        assert client.get("/openapi-docs").status_code == 405
        assert client.post("/sayhi", data={"name": "Aber"}).status_code == 415
        assert client.post("/sayhi", json={"name": "Aber"}).status_code == 200
        assert (
            client.post("/sayhi_without_type_hint", json={"name": "Aber"})
        ).status_code == 200
        assert (
            client.post("/sayhi", content=json.dumps({"name": "Aber"})).status_code == 415
        )
        assert (
            client.post(
                "/sayhi",
                content=json.dumps({"name": "Aber"}).encode("utf8"),
                headers={"serializer": "application/json"},
            ).status_code
            == 415
        )
        assert (
            client.post(
                "/sayhi",
                content=json.dumps({"name": "Aber"}).encode("utf8"),
                headers={"content-type": "", "serializer": "json"},
            ).status_code
            == 200
        )
        assert client.post("/non-exists", json={"name": "Aber"}).status_code == 404


@pytest.mark.asyncio
async def test_asgirpc():
    rpc = RPC(mode="ASGI")
    assert isinstance(rpc, AsgiRPC)

    @rpc.register
    async def sayhi(name: str) -> str:
        return f"hi {name}"

    @rpc.register
    async def sayhi_without_type_hint(name):
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
        assert (
            await client.post("/sayhi_without_type_hint", json={"name": "Aber"})
        ).status_code == 200
        assert (
            await client.post(
                "/sayhi",
                content=json.dumps({"name": "Aber"}).encode("utf8"),
                headers={"serializer": "application/json"},
            )
        ).status_code == 415
        assert (
            await client.post(
                "/sayhi",
                content=json.dumps({"name": "Aber"}).encode("utf8"),
                headers={"content-type": "", "serializer": "json"},
            )
        ).status_code == 200
        assert (await client.post("/non-exists", json={"name": "Aber"})).status_code == 404


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
    def none() -> None:
        return None

    @rpc.register
    def sayhi(name: str) -> str:
        """
        say hi with name
        """
        return f"hi {name}"

    class DNSRecord(TypedDict):
        record: str
        ttl: int

    class DNS(TypedDict):
        dns_type: str
        host: str
        result: DNSRecord

    @rpc.register
    def query_dns(dns_type: str, host: str) -> DNS:
        return {"dns_type": dns_type, "host": host, "result": {"record": "", "ttl": 0}}

    @rpc.register
    def timestamp() -> Generator[int, None, None]:
        while True:
            yield int(time.time())
            time.sleep(1)

    assert rpc.get_openapi_docs() == OPENAPI_DOCS

    with httpx.Client(app=rpc, base_url="http://testServer/") as client:
        assert client.get("/openapi-docs").status_code == 200
        assert client.get("/get-openapi-docs").status_code == 200

        assert (
            client.post(
                "/sayhi",
                content=json.dumps({"name0": "Aber"}).encode("utf8"),
                headers={"content-type": "", "serializer": "json"},
            )
        ).status_code == 422


@pytest.mark.skipif("pydantic" not in sys.modules, reason="Missing pydantic")
@pytest.mark.asyncio
async def test_asgi_openapi():
    rpc = RPC(
        mode="ASGI",
        openapi={"title": "Title", "description": "Description", "version": "v1"},
    )

    @rpc.register
    async def none() -> None:
        return None

    @rpc.register
    async def sayhi(name: str) -> str:
        """
        say hi with name
        """
        return f"hi {name}"

    DNSRecord = TypedDict("DNSRecord", {"record": str, "ttl": int})
    DNS = TypedDict("DNS", {"dns_type": str, "host": str, "result": DNSRecord})

    @rpc.register
    async def query_dns(dns_type: str, host: str) -> DNS:
        return {"dns_type": dns_type, "host": host, "result": {"record": "", "ttl": 0}}

    @rpc.register
    async def timestamp() -> AsyncGenerator[int, None]:
        while True:
            yield int(time.time())
            await asyncio.sleep(1)

    assert rpc.get_openapi_docs() == OPENAPI_DOCS

    async with httpx.AsyncClient(app=rpc, base_url="http://testServer/") as client:
        assert (await client.get("/openapi-docs")).status_code == 200
        assert (await client.get("/get-openapi-docs")).status_code == 200

        assert (
            await client.post(
                "/sayhi",
                content=json.dumps({"name0": "Aber"}).encode("utf8"),
                headers={"content-type": "", "serializer": "json"},
            )
        ).status_code == 422


DEFAULT_PARAMETERS = [
    {
        "name": "content-type",
        "in": "header",
        "description": "At least one of serializer and content-type must be used"
        " so that the server can know which serializer is used to parse the data.",
        "required": True,
        "schema": {
            "type": "string",
            "enum": [serializer_type for serializer_type in SERIALIZER_TYPES],
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
            "enum": [serializer_name for serializer_name in SERIALIZER_NAMES],
        },
    },
]

OPENAPI_DOCS = {
    "openapi": "3.0.0",
    "info": {"title": "Title", "description": "Description", "version": "v1"},
    "paths": {
        "/none": {
            "post": {
                "parameters": DEFAULT_PARAMETERS,
                "responses": {
                    200: {
                        "content": {
                            "application/json": {
                                "schema": {"type": "object", "properties": {}},
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
        "/sayhi": {
            "post": {
                "summary": "say hi with name",
                "parameters": DEFAULT_PARAMETERS,
                "requestBody": {
                    "required": True,
                    "content": {
                        serializer_type: {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "name": {
                                        "title": "Name",
                                        "type": "string",
                                    }
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
                "parameters": DEFAULT_PARAMETERS,
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
                                        "result": {"$ref": "#/definitions/DNSRecord"},
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
                "parameters": DEFAULT_PARAMETERS,
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
    "definitions": {
        "DNSRecord": {
            "title": "DNSRecord",
            "type": "object",
            "properties": {
                "record": {"title": "Record", "type": "string"},
                "ttl": {"title": "Ttl", "type": "integer"},
            },
            "required": ["record", "ttl"],
        }
    },
}
