import typing
from http import cookies as http_cookies


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


class cached_property:
    """
    A property that is only computed once per instance and then replaces
    itself with an ordinary attribute. Deleting the attribute resets the
    property.
    """

    def __init__(self, func: typing.Callable) -> None:
        self.__doc__ = getattr(func, "__doc__")
        self.func = func

    def __get__(self, obj: typing.Any, cls: typing.Any) -> typing.Any:
        if obj is None:
            return self
        value = obj.__dict__[self.func.__name__] = self.func(obj)
        return value


def merge_list(
    raw: typing.List[typing.Tuple[str, str]]
) -> typing.Dict[str, typing.Union[typing.List[str], str]]:
    """
    If there are values with the same key value, they are merged into a List.
    """
    d: typing.Dict[str, typing.Union[typing.List[str], str]] = {}
    for k, v in raw:
        if k in d:
            if isinstance(d[k], list):
                typing.cast(typing.List, d[k]).append(v)
            else:
                d[k] = [typing.cast(str, d[k]), v]
        else:
            d[k] = v
    return d
