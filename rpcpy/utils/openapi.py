from copy import deepcopy
from typing import Any, Dict, Optional, Union, Sequence

try:
    from pydantic import create_model
    from pydantic import BaseModel
except ImportError:

    def create_model(*args, **kwargs):  # type: ignore
        raise NotImplementedError()

    BaseModel = None  # type: ignore


def replace_definitions(schema: Dict[str, Any]) -> Dict[str, Any]:
    """
    replace $ref
    """
    schema = deepcopy(schema)

    if schema.get("definitions") is not None:

        def replace(value: Union[str, Sequence[Any], Dict[str, Any]]) -> None:
            if isinstance(value, str):
                return
            elif isinstance(value, Sequence):
                for _value in value:
                    replace(_value)
            elif isinstance(value, Dict):
                for _name in tuple(value.keys()):
                    if _name == "$ref":
                        define_schema = schema
                        for key in value["$ref"][2:].split("/"):
                            define_schema = define_schema[key]
                        # replace ref and del it
                        value.update(define_schema)
                        del value["$ref"]
                    else:
                        replace(value[_name])

        replace(schema["definitions"])
        replace(schema["properties"])
        del schema["definitions"]

    return schema


def schema_request_body(body: BaseModel = None) -> Optional[Dict[str, Any]]:
    if body is None:
        return None

    _schema = replace_definitions(body.schema())
    del _schema["title"]

    return {
        "required": True,
        "content": {"application/json": {"schema": _schema}},
    }


def schema_response(model: BaseModel) -> Dict[str, Any]:
    return {"application/json": {"schema": replace_definitions(model.schema())}}


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
