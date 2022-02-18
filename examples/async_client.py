from typing import AsyncGenerator

import httpx
from typing_extensions import TypedDict

from rpcpy.client import Client

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
