import json

import httpx

from rpcpy.wsgi import Request, Response


def test_request_environ_interface():
    """
    A Request can be instantiated with a environ, and presents a `Mapping`
    interface.
    """
    request = Request({"type": "http", "method": "GET", "path": "/abc/"})
    assert request["method"] == "GET"
    assert dict(request) == {"type": "http", "method": "GET", "path": "/abc/"}
    assert len(request) == 3


def test_request_body_then_stream():
    def app(environ, start_response):
        request = Request(environ)
        body = request.body
        chunks = b""
        for chunk in request.stream():
            chunks += chunk
        response = Response(
            json.dumps({"body": body.decode(), "stream": chunks.decode()}),
            media_type="application/json",
        )
        return response(environ, start_response)

    with httpx.Client(app=app, base_url="http://testServer/") as client:
        response = client.post("/", data="abc")
        assert response.json() == {"body": "abc", "stream": "abc"}


def test_request_stream_then_body():
    def app(environ, start_response):
        request = Request(environ)
        chunks = b""
        for chunk in request.stream():
            chunks += chunk
        try:
            body = request.body
        except RuntimeError:
            body = b"<stream consumed>"
        response = Response(
            json.dumps({"body": body.decode(), "stream": chunks.decode()}),
            media_type="application/json",
        )
        return response(environ, start_response)

    with httpx.Client(app=app, base_url="http://testServer/") as client:
        response = client.post("/", data="abc")
        assert response.json() == {"body": "<stream consumed>", "stream": "abc"}
