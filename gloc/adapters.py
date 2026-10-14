"""A safe reference adapter for nested JSON object string leaves only.

Arrays are deliberately excluded: positional array IDs are not update-stable.
Implement an engine-specific adapter before using this kit with binary assets.
"""
from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Protocol

from .util import GlocError, digest, index_records, read_json, text_hash


class Adapter(Protocol):
    def extract(self, path: Path, metadata: dict[str, Any]) -> list[dict[str, Any]]: ...
    def inject(self, path: Path, source: list[dict[str, Any]],
               translations: list[dict[str, Any]]) -> dict[str, Any]: ...


def escape_key(key: str) -> str:
    return key.replace("~", "~0").replace("/", "~1")


def unescape_key(key: str) -> str:
    return key.replace("~1", "/").replace("~0", "~")


def get_pointer(document: dict[str, Any], pointer: str) -> Any:
    if not pointer.startswith("/"):
        raise GlocError(f"Invalid JSON pointer: {pointer}")
    node: Any = document
    for part in pointer[1:].split("/"):
        key = unescape_key(part)
        if not isinstance(node, dict) or key not in node:
            raise GlocError(f"JSON location missing: {pointer}")
        node = node[key]
    return node


def set_pointer(document: dict[str, Any], pointer: str, value: str) -> None:
    # Check existence; never introduce keys or treat lists as dictionaries.
    get_pointer(document, pointer)
    parts = pointer[1:].split("/")
    node: Any = document
    for part in parts[:-1]:
        node = node[unescape_key(part)]
    node[unescape_key(parts[-1])] = value


def context_fingerprint(record: dict[str, Any]) -> str:
    return digest({key: record.get(key) for key in (
        "scene_id", "route_id", "speaker", "kind", "context", "constraints", "order")})


def check_source(records: list[dict[str, Any]]) -> None:
    if not records:
        raise GlocError("Source snapshot is empty")
    index_records(records, "source")
    for row in records:
        if not isinstance(row.get("source"), str):
            raise GlocError(f"source must be a string: {row['id']}")
        if row.get("source_hash") != text_hash(row["source"]):
            raise GlocError(f"Source hash mismatch: {row['id']}")
        if row.get("context_hash") != context_fingerprint(row):
            raise GlocError(f"Context hash mismatch: {row['id']}")
        if not isinstance(row.get("constraints", {}), dict):
            raise GlocError(f"constraints must be an object: {row['id']}")


class JsonObjectAdapter:
    name = "json-object-v1"

    def extract(self, path: Path, metadata: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        document = read_json(path)
        metadata = metadata or {}
        if not isinstance(document, dict) or not isinstance(metadata, dict):
            raise GlocError("JSON object and metadata object required")
        rows = []
        def walk(node: Any, pointer: str) -> None:
            if isinstance(node, dict):
                # Preserve authored object order for context; ID is still key-based.
                for key, value in node.items():
                    walk(value, pointer + "/" + escape_key(key))
            elif isinstance(node, str):
                ident = "json:" + pointer
                meta = metadata.get(ident, {})
                if not isinstance(meta, dict):
                    raise GlocError(f"Bad metadata: {ident}")
                if meta.get("translate", True) is False:
                    return
                row = {
                    "id": ident, "source": node, "source_hash": text_hash(node),
                    "locator": {"adapter": self.name, "pointer": pointer},
                    "scene_id": meta.get("scene_id", pointer.rsplit("/", 1)[0] or "root"),
                    "route_id": meta.get("route_id", "main"), "speaker": meta.get("speaker", ""),
                    "kind": meta.get("kind", "unspecified"), "context": meta.get("context", ""),
                    "order": len(rows), "constraints": meta.get("constraints", {}),
                }
                row["context_hash"] = context_fingerprint(row)
                rows.append(row)
            # Numeric/bool/null/list content is intentionally unchanged and not extracted.
        walk(document, "")
        unknown = set(metadata) - {"json:" + p for p in self._all_string_pointers(document)}
        if unknown:
            raise GlocError(f"Metadata has unknown IDs: {sorted(unknown)[:5]}")
        check_source(rows)
        return rows

    @staticmethod
    def _all_string_pointers(document: dict[str, Any]) -> list[str]:
        output = []
        def walk(node: Any, pointer: str) -> None:
            if isinstance(node, dict):
                for k, v in node.items():
                    walk(v, pointer + "/" + escape_key(k))
            elif isinstance(node, str):
                output.append(pointer)
        walk(document, "")
        return output

    def inject(self, path: Path, source: list[dict[str, Any]],
               translations: list[dict[str, Any]]) -> dict[str, Any]:
        check_source(source)
        target = copy.deepcopy(read_json(path))
        src = index_records(source)
        out = index_records(translations, "translations")
        if src.keys() != out.keys():
            raise GlocError("Injection requires exactly the source ID set")
        for ident, row in src.items():
            translated = out[ident]
            if row["locator"].get("adapter") != self.name:
                raise GlocError(f"Wrong adapter: {ident}")
            if translated.get("source_hash") != row["source_hash"]:
                raise GlocError(f"Translation based on another source version: {ident}")
            if translated.get("context_hash") != row["context_hash"]:
                raise GlocError(f"Translation based on another context version: {ident}")
            text = translated.get("translation")
            if not isinstance(text, str):
                raise GlocError(f"Missing translation: {ident}")
            pointer = row["locator"]["pointer"]
            current = get_pointer(target, pointer)
            if not isinstance(current, str) or text_hash(current) != row["source_hash"]:
                raise GlocError(f"Game file changed at {ident}; re-extract first")
            set_pointer(target, pointer, text)
        return target
