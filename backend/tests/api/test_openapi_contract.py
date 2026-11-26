"""The generated API matches contracts/openapi.yaml (T039; AC-15).

Descriptions and titles are ignored; paths, operations, parameters, status codes and the shape
of every response must be equal.
"""

from pathlib import Path
from typing import Any

import yaml

from fdh.api.app import create_app

CONTRACT = Path(__file__).resolve().parents[3] / "specs/001-source-discovery/contracts/openapi.yaml"
METHODS = {"get", "put", "post", "delete", "options", "head", "patch", "trace"}
KEPT = (
    "type",
    "format",
    "enum",
    "const",
    "minimum",
    "maximum",
    "maxLength",
    "maxItems",
    "default",
)


async def ok() -> None:
    return None


def generated() -> dict[str, Any]:
    app = create_app(check_database=ok, queries=None, allowed_hosts=["127.0.0.1"])  # type: ignore[arg-type]
    return app.openapi()


def contract() -> dict[str, Any]:
    loaded: dict[str, Any] = yaml.safe_load(CONTRACT.read_text(encoding="utf-8"))
    return loaded


def resolve(document: dict[str, Any], node: dict[str, Any]) -> dict[str, Any]:
    while "$ref" in node:
        target: Any = document
        for part in node["$ref"].removeprefix("#/").split("/"):
            target = target[part]
        node = target
    return node


def shape(document: dict[str, Any], node: dict[str, Any]) -> dict[str, Any]:
    """A schema reduced to its constraints, with references and unions expanded."""
    node = resolve(document, node)
    if "allOf" in node:
        merged: dict[str, Any] = {"type": ["object"], "properties": {}, "required": []}
        for part in node["allOf"]:
            piece = shape(document, part)
            merged["properties"].update(piece.get("properties", {}))
            merged["required"] = sorted({*merged["required"], *piece.get("required", [])})
        return merged
    if "anyOf" in node:
        options = [resolve(document, option) for option in node["anyOf"]]
        (value,) = [o for o in options if o.get("type") != "null"]
        reduced = shape(document, value)
        if len(options) > 1:
            reduced["type"] = sorted({*reduced["type"], "null"})
        return reduced
    result = {key: node[key] for key in KEPT if key in node}
    if "type" in result:
        kinds = result["type"]
        result["type"] = sorted(kinds if isinstance(kinds, list) else [kinds])
    if "const" in result:
        result["enum"] = [result.pop("const")]
    if "properties" in node:
        result["properties"] = {
            name: shape(document, value) for name, value in node["properties"].items()
        }
        result["required"] = sorted(node.get("required", []))
    if "items" in node:
        result["items"] = shape(document, node["items"])
    if isinstance(node.get("additionalProperties"), dict):
        result["additionalProperties"] = shape(document, node["additionalProperties"])
    return result


def operations(document: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    found = {}
    for path, item in document["paths"].items():
        for method, operation in item.items():
            if method in METHODS:
                found[path, method] = operation
    return found


def parameters(document: dict[str, Any], operation: dict[str, Any]) -> dict[str, Any]:
    result = {}
    for raw in operation.get("parameters", []):
        parameter = resolve(document, raw)
        schema = shape(document, parameter["schema"])
        # A query parameter that may be absent is optional, not nullable.
        schema["type"] = [kind for kind in schema["type"] if kind != "null"]
        if schema.get("default") is None:
            schema.pop("default", None)
        result[parameter["name"]] = (parameter["in"], parameter.get("required", False), schema)
    return result


def responses(document: dict[str, Any], operation: dict[str, Any]) -> dict[str, Any]:
    result = {}
    for status, raw in operation["responses"].items():
        response = resolve(document, raw)
        schema = response["content"]["application/json"]["schema"]
        result[str(status)] = shape(document, schema)
    return result


def test_the_same_operations_and_only_reads() -> None:
    expected, actual = operations(contract()), operations(generated())
    assert sorted(actual) == sorted(expected)
    assert {method for _, method in actual} == {"get"}
    assert {k: v["operationId"] for k, v in actual.items()} == {
        k: v["operationId"] for k, v in expected.items()
    }


def test_parameters_match() -> None:
    expected, actual = contract(), generated()
    for key, operation in operations(expected).items():
        assert parameters(actual, operations(actual)[key]) == parameters(expected, operation), key


def test_responses_match() -> None:
    expected, actual = contract(), generated()
    for key, operation in operations(expected).items():
        got = responses(actual, operations(actual)[key])
        want = responses(expected, operation)
        assert sorted(got) == sorted(want), key
        for status in want:
            assert got[status] == want[status], (key, status)
