import asyncio
import functools
import inspect
import typing

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
            result = self.func(obj)
            if inspect.isawaitable(result):
                result = asyncio.ensure_future(result)
            value = obj.__dict__[self.func.__name__] = result
            return value
