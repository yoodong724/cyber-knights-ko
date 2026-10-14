"""Cyber Knights locale snapshots. Conflicting source keys are quarantined, never last-wins."""
from __future__ import annotations

import copy
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from .adapters import check_source, context_fingerprint, escape_key
from .util import (GlocError, digest, index_records, read_json, read_jsonl,
                   require_new_output, text_hash, write_json, write_jsonl)
from .validate import validate_text

ADAPTER = "ckf-locale-v1"
POLICY = {"identical_duplicates": "collapse", "conflicting_duplicates": "quarantine",
          "target_only": "preserve", "source_only": "add_only_when_translated",
          "shape_conflicts": "quarantine", "plural_categories": "preserve_by_key"}
MARKER = "(이 대사가 출력되었다고 보고할 것)"
HASH = re.compile(r"[0-9a-f]{64}\Z")


class Pairs(list):
    """Distinguish JSON objects from arrays, retaining every occurrence."""


def _locale_pairs(raw: bytes) -> Pairs:
    try:
        pairs = json.loads(raw.decode("utf-8-sig"), object_pairs_hook=Pairs,
                           parse_constant=lambda v: (_ for _ in ()).throw(GlocError("Non-finite number")))
    except (ValueError, UnicodeError) as exc:
        raise GlocError(f"Invalid locale JSON: {exc}") from exc
    if not isinstance(pairs, Pairs):
        raise GlocError("Locale root must be an object")
    return pairs


def _value(key: str, value: Any) -> str | dict:
    if isinstance(value, Pairs):
        plural = {}
        for category, text in value:
            if category in plural or category not in {"zero", "one", "other"} or not isinstance(text, str):
                raise GlocError(f"Unsupported/duplicate plural category: {key}/{category}")
            plural[category] = text
        if not plural:
            raise GlocError(f"Empty plural object: {key}")
        return plural
    if not isinstance(value, str):
        raise GlocError(f"Unsupported locale value: {key}")
    return value


def parse_locale(raw: bytes, allowed_target_duplicates: dict[str, list[str]] | None = None) -> tuple[dict, list[dict], set[str]]:
    pairs = _locale_pairs(raw)
    grouped: dict[str, list] = {}
    for key, value in pairs:
        if not isinstance(key, str):
            raise GlocError("Locale key must be a string")
        grouped.setdefault(key, []).append(_value(key, value))
    conflicts, duplicates, document = set(), [], {}
    for key, values in grouped.items():
        identical = all(v == values[0] for v in values)
        if len(values) > 1:
            duplicates.append({"key": key, "occurrences": values, "identical": identical})
        if identical:
            document[key] = values[0]
        elif allowed_target_duplicates and key in allowed_target_duplicates:
            document[key] = values[0]
        else:
            conflicts.add(key)
    if allowed_target_duplicates is not None:
        actual = {d["key"] for d in duplicates}
        if actual != set(allowed_target_duplicates):
            raise GlocError("Target duplicate key set differs from explicit specification")
        for d in duplicates:
            values = d["occurrences"]
            if (len(values) != 2 or d["identical"] or not all(isinstance(v, str) for v in values)
                    or [text_hash(v) for v in values] != allowed_target_duplicates[d["key"]]):
                raise GlocError(f"Target duplicate occurrence/hash mismatch: {d['key']}")
    return document, duplicates, conflicts


def validate_duplicate_spec(spec: dict) -> dict[str, list[str]]:
    if not isinstance(spec, dict) or set(spec) != {"format", "keys"} or spec["format"] != "ckf-target-duplicates-v1":
        raise GlocError("Invalid target duplicate specification")
    entries = spec["keys"]
    if not isinstance(entries, list) or not entries:
        raise GlocError("Target duplicate specification requires keys")
    result = {}
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {"key", "occurrence_hashes"}:
            raise GlocError("Invalid target duplicate entry")
        key, hashes = entry["key"], entry["occurrence_hashes"]
        if (not isinstance(key, str) or not key or key in result or not isinstance(hashes, list)
                or len(hashes) != 2 or hashes[0] == hashes[1]
                or any(not isinstance(h, str) or not HASH.fullmatch(h) for h in hashes)):
            raise GlocError("Invalid target duplicate key/hashes")
        result[key] = hashes
    return result


def snapshot(english: bytes, chinese: bytes, metadata: dict | None = None,
             target_duplicate_spec: dict | None = None) -> tuple[list, dict, dict]:
    en, duplicates, conflicts = parse_locale(english)
    allowed = validate_duplicate_spec(target_duplicate_spec) if target_duplicate_spec is not None else None
    zh, target_duplicates, _ = parse_locale(chinese, allowed)
    if target_duplicates and allowed is None:
        raise GlocError("Duplicate Chinese target keys are unsupported; resolve before extraction")
    if allowed and (set(allowed) - set(en) or set(allowed) & conflicts
                    or any(not isinstance(en[key], str) for key in allowed if key in en)):
        raise GlocError("Target duplicate key lacks unique English source")
    metadata = {} if metadata is None else metadata
    if not isinstance(metadata, dict):
        raise GlocError("Metadata must be an object")
    shape_conflicts = {k for k in en.keys() & zh.keys() if type(en[k]) is not type(zh[k])}
    rows, recognized = [], set()
    for key, value in en.items():
        if key in shape_conflicts:
            continue
        leaves = [(None, value)] if isinstance(value, str) else list(value.items())
        for category, text in leaves:
            pointer = "/" + escape_key(key) + ("/" + escape_key(category) if category is not None else "")
            ident = "ckf:" + pointer
            recognized.add(ident)
            meta = metadata.get(ident, {})
            if not isinstance(meta, dict):
                raise GlocError(f"Invalid metadata: {ident}")
            if meta.get("translate", True) is False:
                continue
            present = key in zh and (category is None or category in zh[key])
            old = (zh[key] if category is None else zh[key][category]) if present else None
            row = {
                "id": ident, "source": text, "source_hash": text_hash(text),
                "locator": {"adapter": ADAPTER, "key": key, "category": category,
                            "target_present": present, "target_hash": text_hash(old) if present else None},
                "scene_id": meta.get("scene_id", "key-group:" + key.split(".")[0]),
                "route_id": meta.get("route_id", "unknown"), "speaker": meta.get("speaker", ""),
                "kind": meta.get("kind", "unspecified"),
                "context": meta.get("context", "Key-prefix group only; scene and speaker are not verified."),
                "order": len(rows), "constraints": meta.get("constraints", {}),
            }
            row["context_hash"] = context_fingerprint(row)
            rows.append(row)
    if set(metadata) - recognized:
        raise GlocError("Metadata references unknown or quarantined IDs")
    check_source(rows)
    audit = {"duplicates": duplicates, "quarantined_conflicts": sorted(conflicts),
             "quarantined_shapes": sorted(shape_conflicts),
             "source_only_keys": sorted(en.keys() - zh.keys()),
             "target_only_keys": sorted(zh.keys() - en.keys() - conflicts),
             "excluded_by_metadata": sorted(k for k,v in metadata.items() if v.get("translate") is False)}
    if allowed:
        audit["target_duplicates"] = target_duplicates
    manifest = {"adapter": ADAPTER, "source_language": "en-US", "target_slot": "zh-CN",
                "english_sha256": hashlib.sha256(english).hexdigest(),
                "chinese_sha256": hashlib.sha256(chinese).hexdigest(),
                "source_snapshot_hash": digest(rows), "metadata_hash": digest(metadata),
                "audit_hash": digest(audit), "records": len(rows), "policy": POLICY}
    if target_duplicate_spec is not None:
        manifest["target_duplicate_spec_hash"] = digest(target_duplicate_spec)
        manifest["target_duplicate_policy"] = "explicit_occurrence_hashes"
    return rows, manifest, audit


def extract(english: Path, chinese: Path, out: Path, metadata_path: Path | None = None,
            target_duplicates_path: Path | None = None) -> dict:
    require_new_output(out, [english, chinese])
    metadata = read_json(metadata_path) if metadata_path else {}
    spec = read_json(target_duplicates_path) if target_duplicates_path else None
    rows, manifest, audit = snapshot(english.read_bytes(), chinese.read_bytes(), metadata, spec)
    out.mkdir(parents=True, exist_ok=False)
    write_jsonl(out / "source.jsonl", rows)
    write_json(out / "metadata.json", metadata)
    if spec is not None:
        write_json(out / "target-duplicates.json", spec)
    write_json(out / "audit.json", audit)
    write_json(out / "manifest.json", manifest)
    return {"output": str(out), "records": len(rows),
            "duplicate_keys": len(audit["duplicates"]),
            "quarantined_conflicts": len(audit["quarantined_conflicts"]),
            "quarantined_shapes": len(audit["quarantined_shapes"])}


def _snapshot_spec(directory: Path) -> dict | None:
    stored = read_json(directory / "manifest.json")
    if "target_duplicate_spec_hash" not in stored:
        if (directory / "target-duplicates.json").exists():
            raise GlocError("Unexpected target duplicate specification")
        return None
    spec = read_json(directory / "target-duplicates.json")
    if digest(spec) != stored["target_duplicate_spec_hash"]:
        raise GlocError("Target duplicate specification changed")
    return spec


def load_snapshot(directory: Path, english: bytes, chinese: bytes) -> list[dict]:
    rows, manifest, audit = snapshot(english, chinese, read_json(directory / "metadata.json"),
                                     _snapshot_spec(directory))
    if (manifest != read_json(directory / "manifest.json") or
            audit != read_json(directory / "audit.json") or rows != read_jsonl(directory / "source.jsonl")):
        raise GlocError("Snapshot or input changed; re-extract (English and Chinese fingerprints are separate)")
    return rows


def _duplicate_overrides(data: dict | None, allowed: dict[str, list[str]]) -> dict[str, str]:
    if data is None:
        return {}
    if (not isinstance(data, dict) or set(data) != {"format", "entries"}
            or data["format"] != "ckf-target-duplicate-overrides-v1"
            or not isinstance(data["entries"], list)):
        raise GlocError("Invalid target duplicate overrides")
    result = {}
    for entry in data["entries"]:
        if not isinstance(entry, dict) or set(entry) != {"key", "second_source_hash", "translation"}:
            raise GlocError("Invalid target duplicate override entry")
        key = entry["key"]
        if (not isinstance(key, str) or key not in allowed or key in result
                or entry["second_source_hash"] != allowed[key][1]
                or not isinstance(entry["translation"], str)):
            raise GlocError("Unknown, duplicate or stale target duplicate override")
        result[key] = entry["translation"]
    return result


def _encode_target(chinese: bytes, target: dict, overrides: dict[str, str],
                   allowed: dict[str, list[str]]) -> bytes:
    original_pairs = [(key, _value(key, value)) for key, value in _locale_pairs(chinese)]
    seen: dict[str, int] = {}
    output_pairs = []
    for key, value in original_pairs:
        occurrence = seen.get(key, 0)
        seen[key] = occurrence + 1
        replacement = overrides[key] if key in overrides and occurrence == 1 else target[key]
        # Without a translation, both original occurrences stay intact.
        if key in allowed and key not in overrides:
            replacement = value
        output_pairs.append((key, replacement))
    output_pairs.extend((key, value) for key, value in target.items() if key not in seen)
    if output_pairs == original_pairs:
        return chinese
    # Encode an ordered object directly: dict serialization would discard duplicate keys.
    lines = [json.dumps(key, ensure_ascii=False) + ": " + json.dumps(value, ensure_ascii=False)
             for key, value in output_pairs]
    return ("{\n  " + ",\n  ".join(lines) + "\n}\n").encode("utf-8")


def render(directory: Path, english: bytes, chinese: bytes, translations: list[dict], *,
           partial: bool = False, poc: bool = False, rules_hash: str = "",
           glossary: list | None = None, duplicate_overrides: dict | None = None) -> tuple[bytes, dict]:
    rows = load_snapshot(directory, english, chinese)
    spec = _snapshot_spec(directory)
    allowed = validate_duplicate_spec(spec) if spec is not None else {}
    overrides = _duplicate_overrides(duplicate_overrides, allowed)
    if duplicate_overrides is not None and not poc:
        raise GlocError("Temporary second-occurrence overrides require --poc; no human approval is recorded")
    src, translated = index_records(rows), index_records(translations, "translations")
    if not translated or not translated.keys() <= src.keys() or (not partial and translated.keys() != src.keys()):
        raise GlocError("Translation ID coverage mismatch (use --partial for an explicit subset)")
    target, target_duplicates, _ = parse_locale(chinese, allowed if allowed else None)
    new_plural_keys = {src[i]["locator"]["key"] for i in translated
                       if src[i]["locator"]["category"] is not None and src[i]["locator"]["key"] not in target}
    for key in new_plural_keys:
        english_document, _, _ = parse_locale(english)
        selected = {src[i]["locator"]["category"] for i in translated if src[i]["locator"]["key"] == key}
        if selected != set(english_document[key]):
            raise GlocError(f"New plural object requires every English category: {key}")
    target = copy.deepcopy(target)
    issues = []
    snapshot_hash = digest(rows)
    selected_duplicates = {key for key in allowed if "ckf:/" + escape_key(key) in translated}
    if set(overrides) != selected_duplicates:
        raise GlocError("Every translated target duplicate needs exactly one second-occurrence override")
    for ident, item in translated.items():
        row = src[ident]
        for field, expected in (("source_hash", row["source_hash"]), ("context_hash", row["context_hash"]),
                                ("source_snapshot_hash", snapshot_hash)):
            if item.get(field) != expected:
                raise GlocError(f"Stale {field}: {ident}")
        if not isinstance(item.get("translation"), str) or item.get("status") != "translated":
            raise GlocError(f"Translation is missing or deferred: {ident}")
        if not poc:
            approval = item.get("approval", {})
            if (approval.get("kind") != "human" or not approval.get("signoff_sha256") or
                    approval.get("approved_record_hash") != digest({k:v for k,v in item.items() if k != "approval"}) or
                    not rules_hash or item.get("rules_hash") != rules_hash or
                    item.get("provenance", {}).get("backend") == "mock"):
                raise GlocError(f"Current human-approved record required: {ident}")
        issues.extend(validate_text(row, item["translation"], glossary))
        loc = row["locator"]
        if loc["key"] in selected_duplicates and (not item["translation"].endswith(" " + MARKER)
                                               or item["translation"].count(MARKER) != 1):
            raise GlocError(f"First duplicate occurrence requires exact marker: {ident}")
        if loc["category"] is None:
            target[loc["key"]] = item["translation"]
        else:
            target.setdefault(loc["key"], {})[loc["category"]] = item["translation"]
    for key, translation in overrides.items():
        if not translation.endswith(" " + MARKER) or translation.count(MARKER) != 1:
            raise GlocError(f"Second duplicate occurrence requires exact marker: {key}")
        original_second = next(d["occurrences"][1] for d in target_duplicates if d["key"] == key)
        first = src["ckf:/" + escape_key(key)]
        second = {**first, "id": first["id"] + "#occurrence-2", "source": original_second,
                  "source_hash": text_hash(original_second)}
        issues.extend(validate_text(second, translation, glossary))
    if any(i["level"] == "error" for i in issues):
        raise GlocError(f"Injection QA failed: {[i for i in issues if i['level'] == 'error'][:5]}")
    original, _, _ = parse_locale(chinese, allowed if allowed else None)
    if allowed:
        encoded = _encode_target(chinese, target, overrides, allowed)
    else:
        # Semantic no-op preserves exact original bytes, including whitespace and BOM.
        encoded = chinese if target == original else (json.dumps(target, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    return encoded, {"adapter": ADAPTER, "translated_records": len(translated), "total_records": len(rows),
                     "partial": partial, "poc": poc, "release_approved": False,
                     "output_sha256": hashlib.sha256(encoded).hexdigest(), "issues": issues,
                     "target_duplicate_overrides": sorted(overrides)}
