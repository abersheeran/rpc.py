import typing
import functools
import inspect
from http import cookies as http_cookies

from .openapi import create_model


def cookie_parser(cookie_string: str) -> typing.Dict[str, str]:
    """
    This function parses a ``Cookie`` HTTP header into a dict of key/value pairs.

    It attempts to mimic browser cookie parsing behavior: browsers and web servers
    frequently disregard the spec (RFC 6265) when setting and reading cookies,
    so we attempt to suit the common scenarios here.

    This function has been adapted from Django 3.1.0.
    """
    cookie_dict: typing.Dict[str, str] = {}
    for chunk in cookie_string.split(";"):
        if "=" in chunk:
            key, val = chunk.split("=", 1)
        else:
            key, val = "", chunk
        key, val = key.strip(), val.strip()
        if key or val:
            # unquote using Python's algorithm.
            cookie_dict[key] = http_cookies._unquote(val)  # type: ignore
    return cookie_dict


if typing.TYPE_CHECKING:
    # https://github.com/python/mypy/issues/5107
    # for mypy check and IDE support
    cached_property = property
else:

    class cached_property:
        """
        A property that is only computed once per instance and then replaces
        itself with an ordinary attribute. Deleting the attribute resets the
        property.
        """

        def __init__(self, func: typing.Callable) -> None:
            self.func = func
            functools.update_wrapper(self, func)

        def __get__(self, obj: typing.Any, cls: typing.Any) -> typing.Any:
            if obj is None:
                return self
            value = obj.__dict__[self.func.__name__] = self.func(obj)
            return value


Function = typing.TypeVar("Function", typing.Callable, typing.Callable)


def set_type_model(func: Function) -> Function:
    """
    try generate request body model from type hint and default value
    """
    sig = inspect.signature(func)
    field_definitions = {}
    for name, parameter in sig.parameters.items():
        if (
            parameter.annotation == parameter.empty
            and parameter.default == parameter.empty
        ):
            # raise ValueError(
            #     f"You must specify the type for the parameter {func.__name__}:{name}."
            # )
            return func  # Maybe the type hint should be mandatory? I'm not sure.
        if parameter.annotation == parameter.empty:
            field_definitions[name] = parameter.default
        elif parameter.default == parameter.empty:
            field_definitions[name] = (parameter.annotation, ...)
        else:
            field_definitions[name] = (parameter.annotation, parameter.default)
    if field_definitions:
        body_model = create_model("temporary", **field_definitions)
        setattr(func, "__body_model__", body_model)

    return func
