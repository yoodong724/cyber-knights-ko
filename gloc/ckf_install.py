"""Local, non-distributable CKF staging and recoverable two-file test-copy installation.

No Unity dependency: accepts only pinned, independently verified font pairs.
This is not a public release packager or a multi-file atomic transaction.
"""
from __future__ import annotations

import hashlib
import os
import stat
from pathlib import Path

from .ckf import render
from .util import (GlocError, ProjectLock, atomic_bytes, digest, file_hash, read_json,
                   read_jsonl, require_new_output, write_json)

ENGLISH = "CyberKnights_Data/StreamingAssets/Locales/en-US.json"
CHINESE = "CyberKnights_Data/StreamingAssets/Locales/zh-CN.json"
FONT = "CyberKnights_Data/StreamingAssets/aa/StandaloneWindows64/735c930b6d62a5600e84bfa8a8b9dbb6.bundle"
CATALOG = "CyberKnights_Data/StreamingAssets/aa/catalog.bin"
TARGETS = (CHINESE, FONT)
GUARDS = (ENGLISH, CATALOG)
# Legacy pair: observed build 25314928, Unity 6000.3.12f1.
FONT_PROFILE = {"original": "52fb3173cfb108940a392352fc683470952fda3730addfc89eadbdd4293cc916",
                "patched": "bc0dd8eef828fb3946503a0e8bafe18dd776d9714faf64a1e68aa8dd34366e11"}
FONT_26097464 = "CyberKnights_Data/StreamingAssets/aa/StandaloneWindows64/f1335b489121d5d0f88f37fff58849d9.bundle"
GUARDS_26097464 = {
    ENGLISH: "f9f37a09c8f7ac1057612c5c1682d6df9cf958e8bd5c757e637764bd7b9e5077",
    CATALOG: "e45b4dd2c6cb0e760f994a58c3fa98fe49eb0474b136eb0ba8a7ab8a7b0b4d55",
}
# 26138768 keeps the 26097464 font bundle bytes; only English/catalog guards changed.
GUARDS_26138768 = {
    ENGLISH: "00c771cb9534cdfca3ce51acd98e6b1cf8a4ee75dcef6ee34c49bd27ed52de3a",
    CATALOG: "56778d83a2fd108ebab4311a6639b9705750fb967705ff9a6852ef1c977f9d13",
}
# 26151125 retains every target and the catalog; its English locale changed.
GUARDS_26151125 = {
    ENGLISH: "0538c1abc7a51cae89ebfba154c2f84067f28c66393c50c7db213bbc0e900caa",
    CATALOG: "56778d83a2fd108ebab4311a6639b9705750fb967705ff9a6852ef1c977f9d13",
}
# 26198171 keeps the verified font bytes; both locale/catalog guards changed.
GUARDS_26198171 = {ENGLISH: "8d14bf5d963269952c29b380c1eeb79b3896d167c165a600cbda7549dfb048b7", CATALOG: "0e733e4dce50c564916044fd4b99c3d58647bf275a56d0c538282ad615846574"}
GUARDS_26299178 = {ENGLISH: "031ac1cd3aca09b11dda51afa025b0dda895c0054fe5b2a6b6bb2039b580961b", CATALOG: "1719556a038aad1c186155d204202832ccf0fb84786706e4bca9a55f69e2ddfe"}
# Guard sets whose font bundle is FONT_26097464 with FONT_26097464_PROFILE.
CURRENT_FONT_GUARDS = (GUARDS_26097464, GUARDS_26138768, GUARDS_26151125, GUARDS_26198171, GUARDS_26299178)
# Independently rebuilt current bundle: only Font.m_FontData was replaced;
# all other 23 objects are unchanged. No caller-supplied result hash is accepted.
FONT_26097464_PROFILE = {
    "original": "876d7d2963fa00e6752e961d845fe59fb41f3a9c204226c35a74a122e85bc770",
    "patched": "d23a95d170c98458973281a24c15b06b5e1065bdab6eda0d533880f2ee0730cc",
}
sha = lambda data: hashlib.sha256(data).hexdigest()


def no_links(path: Path) -> Path:
    """Reject symlinks and Windows junction/reparse ancestors, even dangling links."""
    path = Path(os.path.abspath(path))
    for item in (path, *path.parents):
        try:
            info = item.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise GlocError(f"Linked/reparse path is unsupported: {item}")
    return path


def disjoint(a: Path, b: Path) -> None:
    if a.is_relative_to(b) or b.is_relative_to(a):
        raise GlocError("Original, copy, stage and backup directories must be separate")


def copy_paths(original: Path, game_copy: Path, *, targets: tuple[str, ...] = TARGETS) -> tuple[Path, Path]:
    original, game_copy = no_links(original), no_links(game_copy)
    disjoint(original, game_copy)
    for relative in (*targets, *GUARDS):
        src, dst = no_links(original / relative), no_links(game_copy / relative)
        if not src.is_file() or not dst.is_file():
            raise GlocError(f"Missing game/copy file: {relative}")
        if src.samefile(dst) or dst.stat().st_nlink != 1:
            raise GlocError("Test copy must not share original files or hardlinks")
    return original, game_copy


def stage(snapshot_dir: Path, translations: Path, game: Path, font: Path, out: Path, **options) -> dict:
    game, out = no_links(game), no_links(out)
    disjoint(game, out)
    disjoint(no_links(snapshot_dir), out)
    require_new_output(out)
    base = {r: no_links(game / r).read_bytes() for r in GUARDS}
    current = {r: sha(base[r]) for r in GUARDS} in CURRENT_FONT_GUARDS
    font_path = FONT_26097464 if current else FONT
    targets = (CHINESE, font_path)
    profile = FONT_26097464_PROFILE if current else FONT_PROFILE
    if not valid_hash(profile["patched"]):
        raise GlocError("26097464 Korean font result is not yet verified/pinned")
    if not no_links(game / font_path).is_file():
        raise GlocError("Unverified font bundle/build: missing pinned font path")
    base.update({r: no_links(game / r).read_bytes() for r in targets})
    font_data = no_links(font).read_bytes()
    if sha(base[font_path]) != profile["original"] or sha(font_data) != profile["patched"]:
        raise GlocError("Unverified font bundle/build: expected the pinned original/result pair")
    locale, report = render(snapshot_dir, base[ENGLISH], base[CHINESE], read_jsonl(translations), **options)
    payloads = (locale, font_data)
    manifest = {"format": "ckf-local-stage-v1", "local_only": True, "release_approved": False,
                "snapshot_hash": read_json(snapshot_dir / "manifest.json")["source_snapshot_hash"],
                "translations_sha256": file_hash(translations),
                "files": [{"path": r, "before": sha(base[r]), "after": sha(data), "payload": f"{i}.bin"}
                          for i,(r,data) in enumerate(zip(targets, payloads))],
                "guards": [{"path": r, "sha256": sha(base[r])} for r in GUARDS]}
    if options.get("duplicate_overrides") is not None:
        manifest["duplicate_overrides_hash"] = digest(options["duplicate_overrides"])
    out.mkdir(parents=True, exist_ok=False)
    for i,data in enumerate(payloads):
        atomic_bytes(out / f"{i}.bin", data)
    write_json(out / "qa.json", report)
    write_json(out / "manifest.json", manifest)
    return {"output": str(out), "local_only": True, "release_approved": False,
            "translated_records": report["translated_records"], "warnings": len(report["issues"])}


def validate_manifest(manifest: dict) -> None:
    if (manifest.get("format") != "ckf-local-stage-v1" or manifest.get("local_only") is not True or
            manifest.get("release_approved") is not False):
        raise GlocError("Not a local CKF stage")
    guard_values = {r.get("path"): r.get("sha256") for r in manifest.get("guards", [])}
    current = guard_values in CURRENT_FONT_GUARDS
    targets = (CHINESE, FONT_26097464) if current else TARGETS
    profile = FONT_26097464_PROFILE if current else FONT_PROFILE
    if ([r.get("path") for r in manifest.get("files", [])] != list(targets) or
            [r.get("payload") for r in manifest["files"]] != ["0.bin", "1.bin"] or
            [r.get("path") for r in manifest.get("guards", [])] != list(GUARDS)):
        raise GlocError("Unexpected stage paths/order")
    for row in manifest["files"]:
        for field in ("before", "after"):
            if not valid_hash(row.get(field)):
                raise GlocError("Invalid file hash")
    if any(not valid_hash(r.get("sha256")) for r in manifest["guards"]):
        raise GlocError("Invalid guard hash")
    if "duplicate_overrides_hash" in manifest and not valid_hash(manifest["duplicate_overrides_hash"]):
        raise GlocError("Invalid duplicate overrides hash")
    font = manifest["files"][1]
    if not valid_hash(profile["patched"]) or (font["before"], font["after"]) != (profile["original"], profile["patched"]):
        raise GlocError("Unverified font profile")


def valid_hash(value) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def apply(stage_dir: Path, original: Path, game_copy: Path, backup: Path) -> dict:
    stage_dir, backup = no_links(stage_dir), no_links(backup)
    manifest = read_json(no_links(stage_dir / "manifest.json"))
    validate_manifest(manifest)
    original, game_copy = copy_paths(original, game_copy, targets=tuple(r["path"] for r in manifest["files"]))
    for a,b in ((stage_dir, original), (stage_dir, game_copy), (backup, original),
                (backup, game_copy), (backup, stage_dir)):
        disjoint(a,b)
    require_new_output(backup)
    payloads = [no_links(stage_dir / f"{i}.bin").read_bytes() for i in range(2)]
    if any(sha(data) != row["after"] for row,data in zip(manifest["files"],payloads)):
        raise GlocError("Corrupted staged payload")
    with ProjectLock(no_links(game_copy / ".gloc-ckf.lock")):
        originals = []
        for row in manifest["files"]:
            data = (game_copy / row["path"]).read_bytes()
            if sha(data) != row["before"] or file_hash(original / row["path"]) != row["before"]:
                raise GlocError("Original/copy version mismatch or already patched")
            originals.append(data)
        for row in manifest["guards"]:
            if any(file_hash(root / row["path"]) != row["sha256"] for root in (original,game_copy)):
                raise GlocError("English/catalog guard mismatch")
        backup.mkdir(parents=True, exist_ok=False)
        state = {"format": "ckf-local-backup-v1", "state": "PREPARED", "game_copy": str(game_copy),
                 "original_game": str(original), "manifest": manifest}
        for i,data in enumerate(originals):
            atomic_bytes(backup / f"{i}.original", data)
        write_json(backup / "state.json", state)
        # All backups are durable before the first game file is changed.
        for row in manifest["files"]:
            if file_hash(no_links(game_copy / row["path"])) != row["before"]:
                raise GlocError("Copy changed during backup preparation; not applied")
        try:
            for row,data in zip(manifest["files"],payloads):
                path = no_links(game_copy / row["path"])
                if file_hash(path) != row["before"] or path.stat().st_nlink != 1:
                    raise GlocError("Copy changed during installation")
                atomic_bytes(path, data)
                if file_hash(path) != row["after"]:
                    raise GlocError("Installed file verification failed")
            state["state"] = "APPLIED"
            write_json(backup / "state.json", state)
        except Exception as exc:
            raise GlocError(f"Installation interrupted; use ckf restore with backup {backup}: {exc}") from exc
    return {"state": "APPLIED", "game_copy": str(game_copy), "backup": str(backup), "local_only": True}


def restore(game_copy: Path, backup: Path) -> dict:
    game_copy, backup = no_links(game_copy), no_links(backup)
    disjoint(game_copy, backup)
    state = read_json(no_links(backup / "state.json"))
    if (state.get("format") != "ckf-local-backup-v1" or state.get("game_copy") != str(game_copy) or
            state.get("state") not in {"PREPARED", "APPLIED", "RESTORED"}):
        raise GlocError("Backup identity/state mismatch")
    manifest = state["manifest"]
    validate_manifest(manifest)
    original = no_links(Path(state["original_game"]))
    disjoint(game_copy, original)
    disjoint(backup, original)
    with ProjectLock(no_links(game_copy / ".gloc-ckf.lock")):
        originals = []
        # Validate EVERY current target and backup before restoring any target.
        for i,row in enumerate(manifest["files"]):
            data = no_links(backup / f"{i}.original").read_bytes()
            target = no_links(game_copy / row["path"])
            if sha(data) != row["before"] or file_hash(target) not in {row["before"],row["after"]}:
                raise GlocError("Backup damaged or game changed; preserving external changes")
            if target.stat().st_nlink != 1:
                raise GlocError("Hardlink restore target refused")
            originals.append(data)
        for row,data in zip(manifest["files"],originals):
            target = no_links(game_copy / row["path"])
            if file_hash(target) not in {row["before"],row["after"]}:
                raise GlocError("Copy changed during restoration")
            if file_hash(target) != row["before"]:
                atomic_bytes(target, data)
            if file_hash(target) != row["before"]:
                raise GlocError("Restored file verification failed")
        state["state"] = "RESTORED"
        write_json(backup / "state.json", state)
    return {"state": "RESTORED", "game_copy": str(game_copy), "byte_exact": True}
