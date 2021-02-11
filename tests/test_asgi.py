import asyncio
import json

import httpx
import pytest

from rpcpy.asgi import ClientDisconnect, Request, Response


def test_request_scope_interface():
    """
    A Request can be instantiated with a scope, and presents a `Mapping`
    interface.
    """
    request = Request({"type": "http", "method": "GET", "path": "/abc/"})
    assert request["method"] == "GET"
    assert dict(request) == {"type": "http", "method": "GET", "path": "/abc/"}
    assert len(request) == 3


@pytest.mark.asyncio
async def test_request_body_then_stream():
    async def app(scope, receive, send):
        request = Request(scope, receive)
        body = await request.body
        chunks = b""
        async for chunk in request.stream():
            chunks += chunk
        response = Response(
            json.dumps({"body": body.decode(), "stream": chunks.decode()}),
            media_type="application/json",
        )
        await response(scope, receive, send)

    async with httpx.AsyncClient(app=app, base_url="http://testServer/") as client:
        response = await client.post("/", data="abc")
        assert response.json() == {"body": "abc", "stream": "abc"}


@pytest.mark.asyncio
async def test_request_stream_then_body():
    async def app(scope, receive, send):
        request = Request(scope, receive)
        chunks = b""
        async for chunk in request.stream():
            chunks += chunk
        try:
            body = await request.body
        except RuntimeError:
            body = b"<stream consumed>"
        response = Response(
            json.dumps({"body": body.decode(), "stream": chunks.decode()}),
            media_type="application/json",
        )
        await response(scope, receive, send)

    async with httpx.AsyncClient(app=app, base_url="http://testServer/") as client:
        response = await client.post("/", data="abc")
        assert response.json() == {"body": "<stream consumed>", "stream": "abc"}


def test_request_disconnect():
    """
    If a client disconnect occurs while reading request body
    then ClientDisconnect should be raised.
    """

    async def app(scope, receive, send):
        request = Request(scope, receive)
        await request.body

    async def receiver():
        return {"type": "http.disconnect"}

    scope = {"type": "http", "method": "POST", "path": "/"}
    loop = asyncio.get_event_loop()
    with pytest.raises(ClientDisconnect):
        loop.run_until_complete(app(scope, receiver, None))
