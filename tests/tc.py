from rpcpy.client import Client
import httpx

app = Client(httpx.Client(), base_url='http://127.0.0.1:8000/')


@app.remote_call
def ht():
    yield


if __name__ == '__main__':
    for i in ht():
        print(i)
