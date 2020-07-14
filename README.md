# rpc.py

An easy-to-use and powerful RPC framework. Base WSGI & ASGI.

## Usage

Server side:

```python
import uvicorn
from rpcpy import RPC

app = RPC()


@app.register
def sayhi(name: str) -> str:
    return f"hi {name}"


if __name__ == "__main__":
    uvicorn.run(app.wsgi, port=65432)
```

Client side:

```python
from rpcpy import Client

app = Client(host="localhost", port=65432)


@app.remote_call
def sayhi(name: str) -> str:
    ...


if __name__ == "__main__":
    print(sayhi("rpc.py"))
```
