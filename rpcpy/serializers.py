import json
import pickle
import typing
from abc import ABCMeta, abstractmethod


class BaseSerializer(metaclass=ABCMeta):
    """
    Base Serializer
    """

    name: str

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

    def __init__(self, default: typing.Callable = json_default) -> None:
        self.default = default

    def encode(self, data: typing.Any) -> bytes:
        return json.dumps(data, ensure_ascii=False).encode("utf8")

    def decode(self, data: bytes) -> typing.Any:
        return json.loads(data.decode("utf8"))


class PickleSerializer(BaseSerializer):
    name = "pickle"

    def encode(self, data: typing.Any) -> bytes:
        return pickle.dumps(data)

    def decode(self, data: bytes) -> typing.Any:
        return pickle.loads(data)
