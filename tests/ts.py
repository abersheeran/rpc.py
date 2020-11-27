import time

import uvicorn

from rpcpy import RPC

app = RPC()


@app.register
def ht():
    for i in range(5):
        time.sleep(5)
        yield 54


if __name__ == '__main__':
    uvicorn.run(app, interface='wsgi')
