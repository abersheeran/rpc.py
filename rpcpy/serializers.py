import json
import pickle
import typing
from abc import ABCMeta, abstractmethod

from rpcpy.exceptions import ServerImplementationError


class BaseSerializer(metaclass=ABCMeta):
    """
    Base Serializer
    """

    name: str
    content_type: str

    @abstractmethod
    def encode(self, data: typing.Any) -> bytes:
        pass

    @abstractmethod
    def decode(self, data: bytes) -> typing.Any:
        pass


def json_default(obj: typing.Any) -> typing.Any:
    raise TypeError(f"Unresolved type: {type(obj)}")


class JSONSerializer(BaseSerializer):
    name = "json"
    content_type = "application/json"

    def __init__(self, default: typing.Callable = json_default) -> None:
        self.default = default

    def encode(self, data: typing.Any) -> bytes:
        return json.dumps(data, ensure_ascii=False).encode("utf8")

    def decode(self, data: bytes) -> typing.Any:
        return json.loads(data.decode("utf8"))


class PickleSerializer(BaseSerializer):
    name = "pickle"
    content_type = "application/x-pickle"

    def encode(self, data: typing.Any) -> bytes:
        return pickle.dumps(data)

    def decode(self, data: bytes) -> typing.Any:
        return pickle.loads(data)


SERIALIZERS = {
    JSONSerializer.name: JSONSerializer(),
    PickleSerializer.name: PickleSerializer(),
}


def get_serializer(headers: typing.Mapping) -> BaseSerializer:
    """
    parse header and try find serializer
    """
    if "serializer" not in headers:
        raise ServerImplementationError("Name `serializer` not in resp.headers.")
    serializer_name = headers["serializer"]
    if serializer_name not in SERIALIZERS:
        raise ServerImplementationError(f"Serializer `{serializer_name}` not found.")
    return SERIALIZERS[serializer_name]
