import typing
import inspect

try:
    from pydantic import create_model
    from pydantic import BaseModel
except ImportError:

    def create_model(*args, **kwargs):  # type: ignore
        raise NotImplementedError()

    BaseModel = None  # type: ignore

Callable = typing.TypeVar("Callable", bound=typing.Callable)


def set_type_model(func: Callable) -> Callable:
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
        body_model = create_model(func.__name__, **field_definitions)
        setattr(func, "__body_model__", body_model)

    return func


TEMPLATE = """<!DOCTYPE html>
<html>

<head>
    <title>OpenAPI power by rpc.py</title>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1">

    <style>
        * {
            font-family: Menlo, Consolas, "Source Code Pro", Inconsolata, Monaco, "Courier New",
                'Segoe UI', Helvetica, Arial, sans-serif !important;
        }

        h1,
        h2 {
            font-family: 'Segoe UI', Helvetica, Arial, sans-serif !important;
        }

        body {
            margin: 0;
            padding: 0;
        }
    </style>
</head>

<body>
    <redoc spec-url='get-openapi-docs'></redoc>
    <script src="https://cdn.jsdelivr.net/npm/redoc@next/bundles/redoc.standalone.js"> </script>
</body>

</html>
"""
