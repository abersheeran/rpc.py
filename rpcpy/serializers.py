import json
import pickle
import typing
from abc import ABCMeta, abstractmethod

from rpcpy.exceptions import SerializerNotFound


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
    def decode(self, raw_data: bytes) -> typing.Any:
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


SERIALIZER_NAMES = {
    JSONSerializer.name: JSONSerializer(),
    PickleSerializer.name: PickleSerializer(),
}

SERIALIZER_TYPES = {
    JSONSerializer.content_type: JSONSerializer(),
    PickleSerializer.content_type: PickleSerializer(),
}


def get_serializer(headers: typing.Mapping) -> BaseSerializer:
    """
    parse header and try find serializer
    """
    serializer_name = headers.get("serializer", None)
    if serializer_name:
        if serializer_name not in SERIALIZER_NAMES:
            raise SerializerNotFound(f"Serializer `{serializer_name}` not found")
        return SERIALIZER_NAMES[serializer_name]

    serializer_type = headers.get("content-type", None)
    if serializer_type:
        if serializer_type not in SERIALIZER_TYPES:
            raise SerializerNotFound(f"Serializer for `{serializer_type}` not found")
        return SERIALIZER_TYPES[serializer_type]

    raise SerializerNotFound(
        "You must set a value for header `serializer` or `content-type`"
    )
