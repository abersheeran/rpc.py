# rpc.py

[![Codecov](https://img.shields.io/codecov/c/github/abersheeran/rpc.py?style=flat-square)](https://codecov.io/gh/abersheeran/rpc.py)

An fast and powerful RPC framework based on ASGI/WSGI.

Based on WSGI/ASGI, you can deploy the rpc.py server to any server and use http2 to get better performance.

## Install

Install from PyPi:

```bash
pip install rpc.py

# need use client
pip install rpc.py[client]

# need use pydantic type hint or OpenAPI docs
pip install rpc.py[type]

# need use msgpack to serializer
pip install rpc.py[msgpack]

# need use CBOR to serializer
pip install rpc.py[cbor]

# or install all dependencies
pip install rpc.py[full]
```

Install from github:

```bash
pip install git+https://github.com/abersheeran/rpc.py@setup.py
```

## Usage

### Server side:

<details markdown="1">
<summary>Use <code>ASGI</code> mode to register <code>async def</code>...</summary>

```python
from typing import AsyncGenerator

import uvicorn
from rpcpy import RPC
from rpcpy.typing import TypedDict

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
        yield i


D = TypedDict("D", {"key": str, "other-key": str})


@app.register
async def query_dict(value: str) -> D:
    return {"key": value, "other-key": value}


if __name__ == "__main__":
    uvicorn.run(app, interface="asgi3", port=65432)
```
</details>

OR

<details markdown="1">
<summary>Use <code>WSGI</code> mode to register <code>def</code>...</summary>

```python
from typing import Generator

import uvicorn
from rpcpy import RPC
from rpcpy.typing import TypedDict

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
        yield i


D = TypedDict("D", {"key": str, "other-key": str})


@app.register
def query_dict(value: str) -> D:
    return {"key": value, "other-key": value}


if __name__ == "__main__":
    uvicorn.run(app, interface="wsgi", port=65432)
```
</details>

### Client side:

Notice: Regardless of whether the server uses the WSGI mode or the ASGI mode, the client can freely use the asynchronous or synchronous mode.

<details markdown="1">
<summary>Use <code>httpx.Client()</code> mode to register <code>def</code>...</summary>

```python
from typing import Generator

import httpx
from rpcpy.client import Client
from rpcpy.typing import TypedDict

app = Client(httpx.Client(), base_url="http://127.0.0.1:65432/")


@app.remote_call
def none() -> None:
    ...


@app.remote_call
def sayhi(name: str) -> str:
    ...


@app.remote_call
def yield_data(max_num: int) -> Generator[int, None, None]:
    yield


D = TypedDict("D", {"key": str, "other-key": str})


@app.remote_call
def query_dict(value: str) -> D:
    ...
```
</details>

OR

<details markdown="1">
<summary>Use <code>httpx.AsyncClient()</code> mode to register <code>async def</code>...</summary>

```python
from typing import AsyncGenerator

import httpx
from rpcpy.client import Client
from rpcpy.typing import TypedDict

app = Client(httpx.AsyncClient(), base_url="http://127.0.0.1:65432/")


@app.remote_call
async def none() -> None:
    ...


@app.remote_call
async def sayhi(name: str) -> str:
    ...


@app.remote_call
async def yield_data(max_num: int) -> AsyncGenerator[int, None]:
    yield


D = TypedDict("D", {"key": str, "other-key": str})


@app.remote_call
async def query_dict(value: str) -> D:
    ...
```
</details>

### Sub-route

If you need to deploy the rpc.py server under `example.com/sub-route/*`, you need to set `RPC(prefix="/sub-route/")` and modify the `Client(base_path=https://example.com/sub-route/)`.

### Serialization

Currently supports three serializers, JSON, Pickle and Msgpack. JSON is used by default. You can override the default `JSONSerializer` with parameters.

```python
import httpx
from rpcpy import RPC
from rpcpy.client import Client
from rpcpy.serializers import PickleSerializer, MsgpackSerializer

RPC(response_serializer=MsgpackSerializer())
# Or
Client(
    ...,
    request_serializer=PickleSerializer(),
)
```

## Type hint and OpenAPI Doc

Thanks to the great work of [pydantic](https://pydantic-docs.helpmanual.io/), which makes rpc.py allow you to use type annotation to annotate the types of function parameters and response values, and perform type verification and JSON serialization . At the same time, it is allowed to generate openapi documents for human reading.

### OpenAPI Documents

If you want to open the OpenAPI document, you need to initialize `RPC` like this `RPC(openapi={"title": "TITLE", "description": "DESCRIPTION", "version": "v1"})`.

Then, visit the `"{prefix}openapi-docs"` of RPC and you will be able to see the automatically generated OpenAPI documentation. (If you do not set the `prefix`, the `prefix` is `"/"`)

## Limitations

Currently, file upload is not supported, but you can do this by passing a `bytes` object.
