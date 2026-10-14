"""JSON Schema definitions and a deliberately limited strict schema checker.

The checker supports exactly the keywords used by this kit, NOT arbitrary JSON
Schema. Generated schemas can also be used with a full Draft 2020-12 validator.
"""
from __future__ import annotations
from typing import Any
from .util import GlocError


def obj(properties: dict[str, Any]) -> dict[str, Any]:
    return {"type": "object", "properties": properties,
            "required": list(properties), "additionalProperties": False}


def array(item: dict[str, Any]) -> dict[str, Any]:
    return {"type": "array", "items": item}


def string(*values: str) -> dict[str, Any]:
    return {"type": "string", **({"enum": list(values)} if values else {})}


TRANSLATION_SCHEMA = obj({
    "translations": array(obj({
        "id": string(), "translation": {"type": ["string", "null"]},
        "status": string("translated", "deferred"), "note": string(),
    })),
    "proposals": array(obj({
        "kind": string("term", "canon", "context", "technical"),
        "term": string(), "source_ids": array(string()),
        "question": string(), "candidate": string(),
    })),
})
REVIEW_SCHEMA = obj({
    "reviews": array(obj({
        "id": string(), "verdict": string("accept", "revise", "blocked"),
        "severity": string("none", "minor", "major", "critical"),
        "category": string(), "reason": string(),
        "suggestion": {"type": ["string", "null"]},
    })),
})
# L1 and L2 deliberately share the output wire format, while their prompts and
# profiles remain independent so neither stage consumes the other's judgement.
REVIEW_L1_SCHEMA = REVIEW_SCHEMA
REVIEW_L2_SCHEMA = REVIEW_SCHEMA
SCHEMAS = {"translate": TRANSLATION_SCHEMA, "review": REVIEW_SCHEMA,
           "review_l1": REVIEW_L1_SCHEMA, "review_l2": REVIEW_L2_SCHEMA}


def check_schema(value: Any, schema: dict[str, Any], where: str = "$") -> None:
    """Fail closed for type/keys/enum; limits/ID coverage live in validate.py."""
    kind = schema["type"]
    kinds = kind if isinstance(kind, list) else [kind]
    matches = {"object": isinstance(value, dict), "array": isinstance(value, list),
               "string": isinstance(value, str), "null": value is None,
               "integer": type(value) is int, "boolean": type(value) is bool}
    if not any(matches.get(k, False) for k in kinds):
        raise GlocError(f"{where}: expected {kind}, got {type(value).__name__}")
    if "enum" in schema and value not in schema["enum"]:
        raise GlocError(f"{where}: invalid enum {value!r}")
    if isinstance(value, dict):
        expected = set(schema["properties"])
        if set(value) != expected:
            raise GlocError(f"{where}: keys mismatch; missing={sorted(expected-set(value))}, "
                            f"extra={sorted(set(value)-expected)}")
        for key, item in value.items():
            check_schema(item, schema["properties"][key], where + "." + key)
    if isinstance(value, list):
        for number, item in enumerate(value):
            check_schema(item, schema["items"], f"{where}[{number}]")
