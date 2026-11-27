"""Strict serialization, durable local writes, hashes, and a single-writer lock."""
from __future__ import annotations

import contextlib
import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator


class GlocError(RuntimeError):
    """An actionable error; the CLI prints it without a traceback."""


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise GlocError(f"Duplicate JSON key: {key!r}")
        result[key] = value
    return result


def loads(text: str) -> Any:
    try:
        return json.loads(text, object_pairs_hook=_pairs,
                          parse_constant=lambda value: (_ for _ in ()).throw(
                              GlocError(f"Non-finite JSON number: {value}")))
    except (json.JSONDecodeError, UnicodeError) as exc:
        raise GlocError(f"Invalid JSON: {exc}") from exc


def read_json(path: Path) -> Any:
    return loads(path.read_text(encoding="utf-8-sig"))


def canonical_bytes(obj: Any) -> bytes:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(obj: Any) -> str:
    return hashlib.sha256(canonical_bytes(obj)).hexdigest()


def text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def atomic_bytes(path: Path, data: bytes) -> None:
    """Replace one local file. This is NOT a multi-file/SQLite transaction."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix="." + path.name + ".", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, path)
        # Best-effort directory durability on POSIX; Windows does not support it.
        if os.name == "posix":
            dfd = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(dfd)
            finally:
                os.close(dfd)
    finally:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(tmp)


def write_json(path: Path, obj: Any) -> None:
    atomic_bytes(path, (json.dumps(obj, ensure_ascii=False, indent=2,
                                  sort_keys=True, allow_nan=False) + "\n").encode("utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    result = []
    with path.open(encoding="utf-8-sig") as stream:
        for number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            try:
                item = loads(line)
                if not isinstance(item, dict):
                    raise GlocError("Expected a JSON object")
                result.append(item)
            except GlocError as exc:
                raise GlocError(f"{path}:{number}: {exc}") from exc
    return result


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    atomic_bytes(path, b"".join(canonical_bytes(row) + b"\n" for row in records))


def index_records(records: list[dict[str, Any]], label: str = "records") -> dict[str, dict[str, Any]]:
    result = {}
    for row in records:
        ident = row.get("id")
        if not isinstance(ident, str) or not ident:
            raise GlocError(f"{label}: nonempty string id required")
        if ident in result:
            raise GlocError(f"{label}: duplicate id {ident}")
        result[ident] = row
    return result


def within(root: Path, path: str | Path) -> Path:
    """Reject escaping/absolute paths unless they actually resolve under root."""
    root = root.resolve()
    target = (root / path).resolve()
    if not target.is_relative_to(root):
        raise GlocError(f"Path escapes project: {path}")
    return target


def require_new_output(path: Path, inputs: list[Path] = ()) -> None:
    if path.resolve() in {p.resolve() for p in inputs}:
        raise GlocError("Refusing to overwrite an input/original file")
    if path.exists() or path.is_symlink():
        raise GlocError(f"Output already exists; choose a new snapshot path: {path}")


class ProjectLock:
    """OS-released local advisory lock. Never use SQLite/WAL on network shares."""
    def __init__(self, path: Path):
        self.path = path
        self.stream = None

    def __enter__(self) -> "ProjectLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.stream = self.path.open("a+b")
        self.stream.seek(0, os.SEEK_END)
        if self.stream.tell() == 0:
            self.stream.write(b"0")
            self.stream.flush()
        self.stream.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self.stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            self.stream.close()
            raise GlocError("Another project writer is running; do not run two orchestrators") from exc
        return self

    def __exit__(self, *args: Any) -> None:
        if self.stream is not None:
            if os.name == "nt":
                import msvcrt
                self.stream.seek(0)
                msvcrt.locking(self.stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.stream.fileno(), fcntl.LOCK_UN)
            self.stream.close()
