import pytest

from rpcpy.serializers import JSONSerializer, PickleSerializer


@pytest.mark.parametrize(
    "serializer",
    [JSONSerializer(), PickleSerializer()],
)
@pytest.mark.parametrize(
    "data",
    ["123", "中文", 1, 0, 1239.123, ["123", 1, 123.98], {"a": 1}],
)
def test_serializer(serializer, data):
    assert serializer.decode(serializer.encode(data)) == data
