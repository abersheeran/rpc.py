# rpc.py

An easy-to-use and powerful RPC framework. Base WSGI & ASGI.

Based on WSGI/ASGI, you can deploy the rpc.py server to any server and use http2 to get better performance.

## Install

Install from PyPi:

```bash
pip install rpc.py
```

Install from github:

```bash
pip install git+https://github.com/abersheeran/rpc.py@setup.py
```

## Usage

### Server side:

```python
import uvicorn
from rpcpy import RPC

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


if __name__ == "__main__":
    uvicorn.run(app, interface="asgi3", port=65432)
```

OR

```python
import uvicorn
from rpcpy import RPC

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


if __name__ == "__main__":
    uvicorn.run(app, interface="wsgi", port=65432)
```

### Client side:

```python
import httpx
from rpcpy.client import Client

app = Client(httpx.Client(), base_url="http://127.0.0.1:65432/")


@app.remote_call
def none() -> None:
    ...


@app.remote_call
def sayhi(name: str) -> str:
    ...


@app.remote_call
def yield_data(max_num: int):
    yield
```

OR

```python
import httpx
from rpcpy.client import Client

app = Client(httpx.AsyncClient(), base_url="http://127.0.0.1:65432/")


@app.remote_call
async def none() -> None:
    ...


@app.remote_call
async def sayhi(name: str) -> str:
    ...


@app.remote_call
async def yield_data(max_num: int):
    yield
```
