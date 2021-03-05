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
