from types import TracebackType
from typing import (
    Any,
    Type,
    Tuple,
    Callable,
    Iterable,
    MutableMapping,
    Optional,
    Awaitable,
)

__all__ = [
    "Scope",
    "Message",
    "Receive",
    "Send",
    "ASGIApp",
    "ExcInfo",
    "Environ",
    "StartResponse",
    "WSGIApp",
]

# ASGI
Scope = MutableMapping[str, Any]

Message = MutableMapping[str, Any]

Receive = Callable[[], Awaitable[Message]]

Send = Callable[[Message], Awaitable[None]]

ASGIApp = Callable[[Scope, Receive, Send], Awaitable[None]]

# WSGI: view PEP3333
ExcInfo = Tuple[Type[BaseException], BaseException, Optional[TracebackType]]

Environ = MutableMapping[str, Any]

StartResponse = Callable[[str, Iterable[Tuple[str, str]], Optional[ExcInfo]], None]

WSGIApp = Callable[[Environ, StartResponse], Iterable[bytes]]
