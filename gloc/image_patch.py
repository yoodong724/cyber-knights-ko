"""Strict, standard-library byte contract for CKF image stream replacement.

Unity bundle parsing, PNG decoding and BC1 encoding belong to the local bridge.
This module accepts only already decoded metadata and fixed-length stream bytes.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence


class ImagePatchError(ValueError):
    """An image edit cannot be safely applied."""


_SHA = re.compile(r"[0-9a-f]{64}\Z")
_ASSET = re.compile(r"CyberKnights_Data/StreamingAssets/aa/StandaloneWindows64/[0-9a-f]{32}\.bundle\Z")
_ID = re.compile(r"ckf-image:[0-9a-f]{64}\Z")
_FORMATS = {3: 3, 4: 4, 10: 0}
_PREFIX = "CyberKnights_Data/StreamingAssets/aa/StandaloneWindows64/"
TARGETS = {
    _PREFIX + "672fb9a7811edcdde218dc5de379c935.bundle":
        ("CAB-a0006646bf97d91cc831e47e152989af", "c3cbbf6c7d409a1db46566e345288145fb2dc40bc488c9438fe3f29d86ddf3fc"),
    _PREFIX + "b50ba8b5464ec4de8ea55b111bbad63a.bundle":
        ("CAB-fbb713bd85569f8101272a4763ea6bc0", "b09d2e824819be5a672cc5211b69e2c4e339181426a2c40dcbe2a283e984209f"),
}

# Build profiles are deliberately closed sets. The current profile's IDs were
# copied from the reviewed source-contract proposal; runtime input cannot add IDs.
_TARGETS_BY_BUILD = {
    "25594089": TARGETS,
    "25697586": {
        _PREFIX + "427efad263b7a135a46a33ce3a2f2adf.bundle":
            ("CAB-a0006646bf97d91cc831e47e152989af", "cd0398e68179a30bd7deff3050a29a61cf954f6225592be821b9f68bc8a82b35"),
        _PREFIX + "b50ba8b5464ec4de8ea55b111bbad63a.bundle":
            ("CAB-fbb713bd85569f8101272a4763ea6bc0", "b09d2e824819be5a672cc5211b69e2c4e339181426a2c40dcbe2a283e984209f"),
    },
}
# The 25889011 image source bundles retain exactly these bytes and locators.
# This is an explicit build profile; English/catalog guards are pinned separately.
_TARGETS_BY_BUILD["25889011"] = dict(_TARGETS_BY_BUILD["25697586"])
# 25951469 likewise keeps both image source bundles byte-identical (hash-checked).
_TARGETS_BY_BUILD["25951469"] = dict(_TARGETS_BY_BUILD["25697586"])
_CURRENT_IDS = frozenset({
    "ckf-image:10fa5342868340bff4037730a670069c2e6e4eef7bf090150f2780354c248e71",
    "ckf-image:229f9cc082b71e3e35ac8493bc326831a23275e35f8250d1eab95d625da52204",
    "ckf-image:34a9bbe24b1b4befdd3cf4a26824fb71a17d5cfa3455d53a7ae28ece0dd5a08f",
    "ckf-image:35f5cc5cc055b936df5ba6cf9ece3da2216d315325b57081b52e24b6e72d8805",
    "ckf-image:39f90ba38f882d2e11c171055e5a61d20cc9b5ffcf525ac450793bd43c2d7b26",
    "ckf-image:43991411c1b1c9cb9f5eae019dd770f1e38fa21956c9feed2d8e2356a76dcb1a",
    "ckf-image:462779d03956d564c85cdd5ae1d56cc7705e3dfc32b28bc2f00ca328f7c87419",
    "ckf-image:4cd44412ec186759eb6f8b53f5f7e82d2b075e863440694f085a4f9b888e84e8",
    "ckf-image:5839833ff1ea3612c87a05fe4c0395d3cfcb36a8c0565efb6fef705763fcd07d",
    "ckf-image:66a6e0d543860a4e38e193737acbf195c6f9c40864a667ff0f8166443364e0d6",
    "ckf-image:6a97d5c1701bdaff024f3ebb86bcacaa4f5c7a3c61b3255fea0407b3587c88e7",
    "ckf-image:6c46f4faa8be3818380e8e899c0003a392126dfa830145347f0baf15b05760f8",
    "ckf-image:81217ca4baf4fb79b81a1a4a232b6d3a56fb7a945149d2fe6fd5ae8bf0d4416c",
    "ckf-image:8d14daa5de7063d4c59364a3e419bd7154657e0aaa042ad0b0610e87343b514a",
    "ckf-image:8f86df2a12380c113d23a6a87f32b98e08c8354ebf0c7c26a507d44390fad5cd",
    "ckf-image:959312b069b2623dfad1a642f3f130aac7b578357eefcc7d8dd151a0f9dec709",
    "ckf-image:962554279f206d7f3b54433efbbff3334408cd1ee5073cc6f183786eecf8c631",
    "ckf-image:9a9baef7b49fd2ee66f8f76fdad6bc545e1e4faac86f997ffb34259cd6027200",
    "ckf-image:9ba86746f425e1c9fd0dcfcd68f737a6991d0c45f83c76a0f933b649971d9007",
    "ckf-image:c08ef01819bdac7c2aab9987fe6ccd72c066da7d0edbb5b1ff99a4cf9104ce5d",
    "ckf-image:c1dfb8444300f56f8878a922f6f7cc1b26b823a3cb1a3ec900d595fdfcb0de4e",
    "ckf-image:c9773b7be4d773f10eff76701a65872660a3b0cff7a059638f7e27e9226401e9",
    "ckf-image:cd1971a4c5e7966a9c190a1b3401f39b927f187f0b2325875ec8bbe5ec6ee1e3",
    "ckf-image:cdd3e1ed2e58a935c83dc0d06c7e6c13de1a2a2fed97b0a9e7232fe7e42fd353",
    "ckf-image:d0b4328542a83b41f8e3af60af6fc4abd0b91eb63214bc2258e799afa6681c69",
    "ckf-image:d32acc60a653bf9c704dcd7a7ac4747f0e3c06844837f3fdff6dc2a1c4746fe2",
    "ckf-image:d4a5d3d283108352084f19c27bbf52b35738bc012f2312f342fac689ce0f7ea7",
    "ckf-image:d8dce10299f163f564e360a4ff8445b0935cee1804aad2be20dd38e4bd5510ec",
    "ckf-image:da5c48a987c641e264fb2fdf43f53223dd11a49ce3a31fc2eb72b602135920ad",
    "ckf-image:e2e6c28b3728ed018900074010c260f450b4951b7d80d73a62c42f4c725c7ab5",
    "ckf-image:f07c6b2b1446d03d4d2dc543584f7ff1bac92727dcff305f4fa490d9a8276632",
    "ckf-image:f54efe3c47127023886e8b7b0177d5a4ac064a739577e7bfc7dca692665cb6fc",
    "ckf-image:f9cb0933f1e81af8cc9b0d9ba4a308f110c7af7ca98285c60ee119b3077360b6",
})


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def image_id(asset: str, serialized_file: str, path_id: int) -> str:
    if not isinstance(asset, str) or not _ASSET.fullmatch(asset):
        raise ImagePatchError("invalid image asset path")
    if not isinstance(serialized_file, str) or not re.fullmatch(r"CAB-[0-9a-f]{32}", serialized_file):
        raise ImagePatchError("invalid serialized file")
    if type(path_id) is not int or not -(1 << 63) <= path_id < 1 << 63:
        raise ImagePatchError("invalid Texture2D path ID")
    key = json.dumps([asset, serialized_file, path_id], separators=(",", ":"))
    return "ckf-image:" + sha256(key.encode("utf-8"))


def _integer(value: object, label: str, *, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise ImagePatchError(f"invalid {label}")
    return value


def _hash(value: object, label: str) -> str:
    if not isinstance(value, str) or not _SHA.fullmatch(value):
        raise ImagePatchError(f"invalid {label}")
    return value


def _stream_size(width: int, height: int, format_id: int) -> int:
    if format_id == 10:
        if width % 4 or height % 4:
            raise ImagePatchError("DXT1 dimensions must align to 4x4 blocks")
        return (width // 4) * (height // 4) * 8
    return width * height * _FORMATS[format_id]


def _profile(source_build: str) -> Mapping:
    if not isinstance(source_build, str) or source_build not in _TARGETS_BY_BUILD:
        raise ImagePatchError("unsupported source build")
    return _TARGETS_BY_BUILD[source_build]


def get_source_profile(source_build: str = "25594089") -> Mapping:
    """Return a copy of pinned bundle locator/hash pairs for a supported build."""
    return dict(_profile(source_build))


def validate_record(record: Mapping, *, source_build: str = "25594089") -> None:
    if not isinstance(record, Mapping):
        raise ImagePatchError("image record must be an object")
    targets = _profile(source_build)
    declared_build = record.get("source_build")
    if source_build == "25594089":
        if declared_build not in (None, "25594089"):
            raise ImagePatchError("record/source build mismatch")
    elif declared_build != source_build:
        raise ImagePatchError("current image record must declare source_build")
    if record.get("id") != image_id(record.get("asset"), record.get("serialized_file"), record.get("path_id")):
        raise ImagePatchError("image ID does not match its stable locator")
    if (record["asset"] not in targets or
            (record["serialized_file"], record.get("asset_sha256")) != targets[record["asset"]]):
        raise ImagePatchError("image record is outside pinned source bundles")
    if source_build in ("25697586", "25889011", "25951469") and record["id"] not in _CURRENT_IDS:
        raise ImagePatchError("image ID is outside current build scope")
    width = _integer(record.get("width"), "width", minimum=1)
    height = _integer(record.get("height"), "height", minimum=1)
    format_id = record.get("format")
    if type(format_id) is not int or format_id not in _FORMATS:
        raise ImagePatchError("unsupported Texture2D format")
    for field, expected in (("mipmap_count", 1), ("filter_mode", 1), ("color_space", 1)):
        if record.get(field) != expected or type(record.get(field)) is not int:
            raise ImagePatchError(f"unexpected {field}")
    for field in ("source_png_sha256", "object_sha256", "member_sha256"):
        _hash(record.get(field), field)
    if record.get("status") not in ("edit", "retain", "defer"):
        raise ImagePatchError("invalid image status")
    if record["status"] != "edit" and not record.get("reason"):
        raise ImagePatchError("retain/defer image requires a reason")
    stream = record.get("stream")
    if not isinstance(stream, Mapping):
        raise ImagePatchError("missing stream locator")
    member = stream.get("member")
    if not isinstance(member, str) or not re.fullmatch(r"CAB-[0-9a-f]{32}\.resS", member):
        raise ImagePatchError("invalid stream member")
    # Never resolve m_StreamData.path against the filesystem. It is archive metadata.
    if stream.get("path") != f"archive:/{record['serialized_file']}/{member}":
        raise ImagePatchError("stream path does not name the fixed archive member")
    _integer(stream.get("offset"), "stream offset")
    size = _integer(stream.get("size"), "stream size", minimum=1)
    if size != _stream_size(width, height, format_id):
        raise ImagePatchError("stream size does not match format and dimensions")
    _hash(stream.get("sha256"), "stream hash")


def _rect(value: object, width: int, height: int, label: str) -> tuple[int, int, int, int]:
    if not isinstance(value, (list, tuple)) or len(value) != 4 or any(type(n) is not int for n in value):
        raise ImagePatchError(f"invalid {label}")
    x0, y0, x1, y1 = value
    if not (0 <= x0 < x1 <= width and 0 <= y0 < y1 <= height):
        raise ImagePatchError(f"out-of-bounds {label}")
    return x0, y0, x1, y1


def _intersects(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> bool:
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def validate_edit(edit: Mapping, record: Mapping, *, source_build: str = "25594089") -> None:
    validate_record(record, source_build=source_build)
    if record["status"] != "edit":
        raise ImagePatchError("record is not selected for editing")
    if not isinstance(edit, Mapping) or edit.get("image_id") != record["id"]:
        raise ImagePatchError("unregistered image edit")
    if edit.get("source_png_sha256") != record["source_png_sha256"]:
        raise ImagePatchError("source PNG hash mismatch")
    if edit.get("source_stream_sha256") != record["stream"]["sha256"]:
        raise ImagePatchError("source stream hash mismatch")
    _hash(edit.get("final_png_sha256"), "final PNG hash")
    if not isinstance(edit.get("style_version"), str) or not edit["style_version"]:
        raise ImagePatchError("missing style version")
    if not isinstance(edit.get("region_ids"), list) or not edit["region_ids"] or not all(isinstance(region, str) for region in edit["region_ids"]):
        raise ImagePatchError("missing or invalid region IDs")
    if len(set(edit["region_ids"])) != len(edit["region_ids"]):
        raise ImagePatchError("missing or duplicate region IDs")
    if not all(isinstance(region, str) and re.fullmatch(re.escape(record["id"]) + r":region:[1-9][0-9]*", region) for region in edit["region_ids"]):
        raise ImagePatchError("invalid region ID")
    width, height = record["width"], record["height"]
    rects = edit.get("edit_rects")
    if not isinstance(rects, list) or not rects:
        raise ImagePatchError("missing edit rectangles")
    allowed = [_rect(r, width, height, "edit rectangle") for r in rects]
    protected = edit.get("protected_rects")
    if not isinstance(protected, list):
        raise ImagePatchError("missing protected rectangles")
    protected = [_rect(r, width, height, "protected rectangle") for r in protected]
    if any(_intersects(a, p) for a in allowed for p in protected):
        raise ImagePatchError("edit intersects protected area")
    blocks = edit.get("dxt1_blocks", [])
    if record["format"] == 10:
        if not isinstance(blocks, list) or not blocks:
            raise ImagePatchError("missing DXT1 block selection")
        actual = set()
        for block in blocks:
            if not isinstance(block, (list, tuple)) or len(block) != 2:
                raise ImagePatchError("invalid DXT1 block")
            bx, by = block
            if type(bx) is not int or type(by) is not int or not (0 <= bx < width // 4 and 0 <= by < height // 4):
                raise ImagePatchError("out-of-bounds DXT1 block")
            if (bx, by) in actual:
                raise ImagePatchError("duplicate DXT1 block")
            actual.add((bx, by))
        expected = {(x // 4, y // 4) for x0, y0, x1, y1 in allowed for y in range(y0, y1) for x in range(x0, x1)}
        if actual != expected:
            raise ImagePatchError("DXT1 blocks do not exactly cover edit rectangles")
        if any(_intersects((bx * 4, by * 4, bx * 4 + 4, by * 4 + 4), p) for bx, by in actual for p in protected):
            raise ImagePatchError("DXT1 block touches protected area")
    elif blocks:
        raise ImagePatchError("DXT1 blocks on uncompressed image")


def validate_records(records: Sequence[Mapping], edits: Sequence[Mapping] = (), *,
                     source_build: str = "25594089") -> None:
    ids: set[str] = set()
    for record in records:
        validate_record(record, source_build=source_build)
        if record["id"] in ids:
            raise ImagePatchError("duplicate image ID")
        ids.add(record["id"])
    indexed = {r["id"]: r for r in records}
    used: set[str] = set()
    for edit in edits:
        if not isinstance(edit, Mapping) or edit.get("image_id") not in indexed:
            raise ImagePatchError("edit references unregistered image")
        if edit["image_id"] in used:
            raise ImagePatchError("duplicate image edit")
        validate_edit(edit, indexed[edit["image_id"]], source_build=source_build)
        used.add(edit["image_id"])


def validate_scope(records: Sequence[Mapping], edits: Sequence[Mapping], expected_ids: set[str], *,
                   pilot: bool = False, source_build: str = "25594089") -> None:
    """Require every registered ID and exactly one edit per selected record.

    The caller supplies expected IDs from the pinned findings evidence. A pilot
    may contain a strict subset, but can never be marked a final complete scope.
    """
    _profile(source_build)
    validate_records(records, edits, source_build=source_build)
    actual = {record["id"] for record in records}
    if not isinstance(expected_ids, set) or not expected_ids or not all(isinstance(i, str) and _ID.fullmatch(i) for i in expected_ids):
        raise ImagePatchError("invalid expected image scope")
    if source_build in ("25697586", "25889011", "25951469") and expected_ids != _CURRENT_IDS:
        raise ImagePatchError("expected image scope does not match current build profile")
    if pilot:
        if not actual or not actual <= expected_ids:
            raise ImagePatchError("pilot contains an unregistered image")
    elif actual != expected_ids:
        raise ImagePatchError("incomplete or expanded image scope")
    edit_ids = {edit["image_id"] for edit in edits}
    if edit_ids != {record["id"] for record in records if record["status"] == "edit"}:
        raise ImagePatchError("selected image has no edit")
    if not pilot and any(record["status"] == "defer" for record in records):
        raise ImagePatchError("deferred image in final scope")


def compose_raw_stream(original: bytes, encoded: bytes, record: Mapping, edit: Mapping, *,
                       source_build: str = "25594089") -> bytes:
    """Compose already encoded Unity row order bytes; reject out-of-scope pixel edits."""
    validate_edit(edit, record, source_build=source_build)
    if not isinstance(original, bytes) or not isinstance(encoded, bytes):
        raise ImagePatchError("stream data must be bytes")
    if sha256(original) != record["stream"]["sha256"]:
        raise ImagePatchError("original stream hash mismatch")
    if len(original) != record["stream"]["size"] or len(encoded) != len(original):
        raise ImagePatchError("encoded stream length mismatch")
    width, height, format_id = record["width"], record["height"], record["format"]
    if format_id == 10:
        result = bytearray(original)
        for bx, by in edit["dxt1_blocks"]:
            index = ((height // 4 - 1 - by) * (width // 4) + bx) * 8
            result[index:index + 8] = encoded[index:index + 8]
        return bytes(result)
    channels = _FORMATS[format_id]
    editable = [False] * (width * height)
    for x0, y0, x1, y1 in edit["edit_rects"]:
        for y in range(y0, y1):
            editable[y * width + x0:y * width + x1] = [True] * (x1 - x0)
    for y in range(height):
        for x in range(width):
            index = ((height - 1 - y) * width + x) * channels
            if format_id == 4 and original[index + 3] != encoded[index + 3]:
                raise ImagePatchError("RGBA alpha changed")
            if not editable[y * width + x] and original[index:index + 3] != encoded[index:index + 3]:
                raise ImagePatchError("pixel outside edit area changed")
    return encoded


def splice_member(original_member: bytes, replacements: Sequence[tuple[Mapping, bytes]], *,
                  source_build: str = "25594089") -> bytes:
    """Apply verified nonoverlapping stream replacements to one .resS member."""
    if not isinstance(original_member, bytes):
        raise ImagePatchError("member data must be bytes")
    ranges = []
    member_hash = sha256(original_member)
    owner = None
    for record, replacement in replacements:
        validate_record(record, source_build=source_build)
        stream = record["stream"]
        identity = (record["asset"], record["serialized_file"], stream["member"])
        if owner is None:
            owner = identity
        elif owner != identity:
            raise ImagePatchError("stream replacements mix different archive members")
        offset, size = stream["offset"], stream["size"]
        if offset + size > len(original_member):
            raise ImagePatchError("stream exceeds member bounds")
        if not isinstance(replacement, bytes) or len(replacement) != size:
            raise ImagePatchError("replacement length mismatch")
        if sha256(original_member[offset:offset + size]) != stream["sha256"]:
            raise ImagePatchError("member stream hash mismatch")
        if member_hash != record["member_sha256"]:
            raise ImagePatchError("member hash mismatch")
        ranges.append((offset, offset + size, replacement))
    ranges.sort(key=lambda item: item[0])
    if any(b[0] < a[1] for a, b in zip(ranges, ranges[1:])):
        raise ImagePatchError("overlapping stream ranges")
    result = bytearray(original_member)
    for start, end, replacement in ranges:
        result[start:end] = replacement
    return bytes(result)


def verify_members(original: Mapping[str, bytes], updated: Mapping[str, bytes], selected_member: str,
                   ranges: Sequence[tuple[int, int]]) -> None:
    """Check name/order, untouched members, and bytes outside selected stream ranges."""
    if list(original) != list(updated) or selected_member not in original:
        raise ImagePatchError("bundle member names/order changed")
    if any(original[name] != updated[name] for name in original if name != selected_member):
        raise ImagePatchError("non-target member changed")
    before, after = original[selected_member], updated[selected_member]
    if len(before) != len(after):
        raise ImagePatchError("stream member length changed")
    for start, end in ranges:
        if type(start) is not int or type(end) is not int or not (0 <= start < end <= len(before)):
            raise ImagePatchError("invalid stream range")
    ordered = sorted(ranges)
    previous = 0
    before_view, after_view = memoryview(before), memoryview(after)
    for start, end in ordered:
        if start < previous:
            raise ImagePatchError("overlapping stream ranges")
        if before_view[previous:start] != after_view[previous:start]:
            raise ImagePatchError("bytes outside target streams changed")
        previous = end
    if before_view[previous:] != after_view[previous:]:
        raise ImagePatchError("bytes outside target streams changed")
