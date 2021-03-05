import pytest

from rpcpy.serializers import (
    CBORSerializer,
    JSONSerializer,
    MsgpackSerializer,
    PickleSerializer,
)


@pytest.mark.parametrize(
    "serializer",
    [JSONSerializer(), PickleSerializer(), MsgpackSerializer(), CBORSerializer()],
)
@pytest.mark.parametrize(
    "data",
    ["123", "中文", 1, 0, 1239.123, ["123", 1, 123.98], {"a": 1}],
)
def test_serializer(serializer, data):
    _ = serializer.encode(data)
    assert isinstance(_, bytes)
    assert serializer.decode(_) == data
