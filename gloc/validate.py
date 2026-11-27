"""Deterministic structural QA. A pass never implies a semantically correct translation."""
from __future__ import annotations
import re
from collections import Counter
from typing import Any
from .contracts import SCHEMAS, check_schema
from .util import GlocError, index_records

BRACE = re.compile(r"(?<!\{)\{[A-Za-z_][\w.]*\}|(?<!\{)\{\d+(?::[^{}]+)?\}")
PRINTF = re.compile(r"%(?:\d+\$)?[-+#0]*(?:\d+|\*)?(?:\.(?:\d+|\*))?(?:hh|ll|[hljztL])?[diuoxXfFeEgGaAcsp]|%%")
TAG = re.compile(r"</?[A-Za-z][A-Za-z0-9_-]*(?:\s[^<>]*|=[^<>]*)?/?>")
RPG = re.compile(r"\\(?:[A-Za-z]+\[[^\]\r\n]*\]|[.!|><^{}$])")
ESCAPE = re.compile(r"\\[nrt]")
NUMBER = re.compile(r"\d+(?:[.,]\d+)?")
SELF_TAGS = {"br", "sprite", "img", "space", "pos", "page", "quad"}


def issue(ident: str, code: str, detail: str, level: str = "error") -> dict[str, str]:
    return {"id": ident, "level": level, "code": code, "detail": detail}


def tag_structure(text: str) -> bool:
    stack: list[str] = []
    for token in TAG.findall(text):
        name = re.match(r"</?([A-Za-z][A-Za-z0-9_-]*)", token).group(1).lower()
        if token.startswith("</"):
            if not stack or stack.pop() != name:
                return False
        elif name not in SELF_TAGS and not token.endswith("/>"):
            stack.append(name)
    return not stack


def term_applies_to_record(term: dict[str, Any], row: dict[str, Any]) -> bool:
    """Match text and all scopes on one record; retain legacy substring mode."""
    needle, text = term.get("source", ""), row.get("source", "")
    if not needle:
        return False
    if term.get("whole_word", False):
        if not re.search(r"(?<!\w)" + re.escape(needle) + r"(?!\w)", text):
            return False
    elif needle not in text:
        return False
    return (("apply_ids" not in term or row.get("id") in term["apply_ids"])
            and (not term.get("scene_ids") or row.get("scene_id") in term["scene_ids"])
            and (not term.get("route_ids") or row.get("route_id") in term["route_ids"]))


def validate_text(source: dict[str, Any], translated: str,
                  glossary: list[dict[str, Any]] | None = None) -> list[dict[str, str]]:
    ident, original = source["id"], source["source"]
    constraints = source.get("constraints", {})
    result = []
    def add(code: str, detail: str, level: str = "error") -> None:
        result.append(issue(ident, code, detail, level))
    if not translated and original and not constraints.get("allow_empty", False):
        add("empty", "Nonempty source was replaced by an empty translation")
    formats = constraints.get("formats", ["brace", "printf", "tags", "escaped_newline"])
    for name, regex in (("brace", BRACE), ("rpg", RPG), ("escaped_newline", ESCAPE)):
        if name in formats and Counter(regex.findall(original)) != Counter(regex.findall(translated)):
            add("protected_" + name, "Protected token multiset changed")
    if "printf" in formats:
        old, new = PRINTF.findall(original), PRINTF.findall(translated)
        positional = [t for t in old if t != "%%"]
        all_positional = bool(positional) and all(re.match(r"%\d+\$", t) for t in positional)
        if (Counter(old) != Counter(new)) if all_positional else (old != new):
            add("printf", "printf placeholders changed (non-positional order is significant)")
    if "tags" in formats:
        if TAG.findall(original) != TAG.findall(translated):
            add("tags", "Tag sequence/attributes changed")
        if not constraints.get("tag_fragment", False) and not tag_structure(translated):
            add("tag_nesting", "Unbalanced tag nesting; fragments require explicit metadata")
    for pattern in constraints.get("protected_patterns", []):
        try:
            compiled = re.compile(pattern)
            if Counter(m.group(0) for m in compiled.finditer(original)) != Counter(
                    m.group(0) for m in compiled.finditer(translated)):
                add("custom_token", f"Protected pattern changed: {pattern}")
        except re.error as exc:
            raise GlocError(f"Invalid protected pattern for {ident}: {exc}") from exc
    if any(ord(c) < 32 and c not in "\n\r\t" for c in translated):
        add("control_character", "Unexpected control character")
    encoding = constraints.get("encoding", "utf-8")
    try:
        size = len(translated.encode(encoding))
    except (UnicodeEncodeError, LookupError):
        add("encoding", f"Cannot encode translation as {encoding}")
        size = 0
    limit = constraints.get("max_bytes", 0)
    if limit and size > limit:
        add("byte_limit", f"{size} bytes > {limit}")
    if constraints.get("max_chars", 0) and len(translated) > constraints["max_chars"]:
        add("character_limit", "Character limit exceeded; confirm in-game width", "warning")
    if constraints.get("preserve_newlines", False) and original.count("\n") != translated.count("\n"):
        add("newlines", "Required newline count changed")
    elif original.count("\n") != translated.count("\n"):
        add("newlines", "Newline count changed", "warning")
    if original == translated and original.strip() and not constraints.get("allow_unchanged", False):
        add("unchanged", "Unchanged text; determine whether intentional", "warning")
    def visible_numbers(text: str) -> Counter:
        for pattern in (BRACE, PRINTF, TAG, RPG):
            text = pattern.sub("", text)
        return Counter(NUMBER.findall(text))
    if visible_numbers(original) != visible_numbers(translated):
        add("numbers", "Visible numbers changed; inspect meaning", "warning")
    for term in glossary or []:
        if term.get("status") != "approved":
            continue
        if term_applies_to_record(term, source):
            variants = [term["target"]] + term.get("allowed", [])
            if not any(v in translated for v in variants):
                add("glossary", f"Check {term['source']} -> {term['target']}", "warning")
    return result


def validate_response(packet: dict[str, Any], response: dict[str, Any]) -> list[dict[str, str]]:
    stage = packet["stage"]
    check_schema(response, SCHEMAS[stage])
    field = "translations" if stage == "translate" else "reviews"
    actual = index_records(response[field], "worker output")
    source = index_records(packet["records"], "packet source")
    if actual.keys() != source.keys():
        raise GlocError(f"Output ID set mismatch; missing={sorted(source.keys()-actual.keys())[:10]}, "
                        f"extra={sorted(actual.keys()-source.keys())[:10]}")
    findings = []
    glossary = packet["context"].get("glossary", [])
    if stage == "translate":
        for ident, row in actual.items():
            if row["status"] == "deferred":
                if row["translation"] is not None or not row["note"].strip():
                    raise GlocError(f"Deferred rows require null translation and a reason: {ident}")
            elif not isinstance(row["translation"], str):
                raise GlocError(f"Translated row requires text: {ident}")
            else:
                findings.extend(validate_text(source[ident], row["translation"], glossary))
        for proposal in response["proposals"]:
            if not proposal["source_ids"] or not set(proposal["source_ids"]) <= source.keys():
                raise GlocError("Proposal evidence must reference IDs owned by this job")
            if not proposal["question"].strip():
                raise GlocError("Empty proposal question")
    else:
        drafts = index_records(packet["draft"])
        for ident, row in actual.items():
            if row["verdict"] == "accept":
                if row["severity"] != "none" or row["suggestion"] is not None:
                    raise GlocError(f"Accept must have severity none and no replacement: {ident}")
                if not isinstance(drafts[ident].get("translation"), str):
                    raise GlocError(f"Cannot accept a deferred translation: {ident}")
            else:
                if row["severity"] == "none" or not row["reason"].strip():
                    raise GlocError(f"Non-accept verdict needs severity and evidence: {ident}")
                if row["verdict"] == "revise" and not isinstance(row["suggestion"], str):
                    raise GlocError(f"Revise requires a replacement: {ident}")
            if row["suggestion"] is not None:
                findings.extend(validate_text(source[ident], row["suggestion"], glossary))
    return findings
