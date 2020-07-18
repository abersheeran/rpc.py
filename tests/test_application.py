import pytest

from rpcpy.application import RPC, WSGIRPC, ASGIRPC


def test_wsgirpc():
    rpc = RPC()
    assert isinstance(rpc, WSGIRPC)

    @rpc.register
    def sayhi(name: str) -> str:
        return f"hi {name}"

    with pytest.raises(
        TypeError, match="WSGI mode can only register synchronization functions."
    ):

        @rpc.register
        async def async_sayhi(name: str) -> str:
            return f"hi {name}"


def test_asgirpc():
    rpc = RPC(mode="ASGI")
    assert isinstance(rpc, ASGIRPC)

    @rpc.register
    async def sayhi(name: str) -> str:
        return f"hi {name}"

    with pytest.raises(
        TypeError, match="ASGI mode can only register asynchronous functions."
    ):

        @rpc.register
        def sync_sayhi(name: str) -> str:
            return f"hi {name}"
