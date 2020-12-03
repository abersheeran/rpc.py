import typing
import inspect
import warnings

try:
    from pydantic import create_model
    from pydantic import BaseModel
except ImportError:

    def create_model(*args, **kwargs):  # type: ignore
        raise NotImplementedError("Need install `pydantic` from pypi.")

    BaseModel = type("BaseModel", (), {})  # type: ignore

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
        try:
            body_model = create_model(func.__name__, **field_definitions)
            setattr(func, "__body_model__", body_model)
        except NotImplementedError:
            message = (
                "If you wanna using type hint "
                "to create OpenAPI docs or convert type, "
                "please install `pydantic` from pypi."
            )
            warnings.warn(message, ImportWarning)
    return func


TEMPLATE = """<!DOCTYPE html>
<html>

<head>
    <link type="text/css" rel="stylesheet" href="https://cdn.jsdelivr.net/npm/swagger-ui-dist@3.30.0/swagger-ui.css">
    <title>OpenAPI Docs</title>
</head>

<body>
    <div id="swagger-ui"></div>
    <script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@3.30.0/swagger-ui-bundle.js"></script>
    <script>
        const ui = SwaggerUIBundle({
            url: './get-openapi-docs',
            dom_id: '#swagger-ui',
            presets: [
                SwaggerUIBundle.presets.apis,
                SwaggerUIBundle.SwaggerUIStandalonePreset
            ],
            layout: "BaseLayout",
            deepLinking: true,
            showExtensions: true,
            showCommonExtensions: true
        })

    </script>
</body>

</html>
"""
