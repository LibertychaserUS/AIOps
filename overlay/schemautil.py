"""Tiny JSON Schema subset used against schema/*.json. Not a product CLI."""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from typing import Any

Schema = dict[str, Any]


def json_type(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return type(value).__name__


def _type_ok(value: Any, expected: str) -> bool:
    got = json_type(value)
    if expected == "number":
        return got in {"number", "integer"}
    return got == expected


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, default=str)


def iter_errors(instance: Any, schema: Schema, path: str = "$") -> Iterator[str]:
    if not isinstance(schema, dict):
        yield f"{path}: schema must be an object"
        return

    expected_type = schema.get("type")
    if isinstance(expected_type, str):
        if not _type_ok(instance, expected_type):
            yield f"{path}: expected {expected_type}, got {json_type(instance)}"
            return
    elif isinstance(expected_type, list):
        if not any(_type_ok(instance, item) for item in expected_type if isinstance(item, str)):
            yield f"{path}: expected one of {expected_type}, got {json_type(instance)}"
            return

    if "const" in schema and instance != schema["const"]:
        yield f"{path}: expected const {schema['const']!r}"

    if "enum" in schema and instance not in schema["enum"]:
        yield f"{path}: {instance!r} is not in {schema['enum']}"

    if isinstance(instance, str):
        min_len = schema.get("minLength")
        if isinstance(min_len, int) and len(instance) < min_len:
            yield f"{path}: shorter than minLength {min_len}"
        max_len = schema.get("maxLength")
        if isinstance(max_len, int) and len(instance) > max_len:
            yield f"{path}: longer than maxLength {max_len}"
        pattern = schema.get("pattern")
        if isinstance(pattern, str) and re.search(pattern, instance) is None:
            yield f"{path}: does not match /{pattern}/"

    if isinstance(instance, list):
        min_items = schema.get("minItems")
        if isinstance(min_items, int) and len(instance) < min_items:
            yield f"{path}: fewer than minItems {min_items}"
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(instance):
                yield from iter_errors(item, item_schema, f"{path}[{index}]")
        if schema.get("uniqueItems"):
            seen: set[str] = set()
            for index, item in enumerate(instance):
                key = _canonical(item)
                if key in seen:
                    yield f"{path}[{index}]: duplicate uniqueItems entry"
                seen.add(key)

    if isinstance(instance, dict):
        required = schema.get("required")
        if isinstance(required, list):
            for key in required:
                if key not in instance:
                    yield f"{path}: missing required {key!r}"
        props = schema.get("properties")
        if not isinstance(props, dict):
            props = {}
        additional = schema.get("additionalProperties", True)
        for key, value in instance.items():
            if key in props and isinstance(props[key], dict):
                yield from iter_errors(value, props[key], f"{path}.{key}")
            elif additional is False:
                yield f"{path}: unknown field {key!r}"
            elif isinstance(additional, dict):
                yield from iter_errors(value, additional, f"{path}.{key}")

    if "not" in schema and isinstance(schema["not"], dict):
        if not any(iter_errors(instance, schema["not"], path)):
            yield f"{path}: matches a forbidden subschema"


def validate(instance: Any, schema: Schema, path: str = "$") -> list[str]:
    return list(iter_errors(instance, schema, path))
