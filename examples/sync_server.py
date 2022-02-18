from typing import Generator

import uvicorn
from typing_extensions import TypedDict

from rpcpy import RPC

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
