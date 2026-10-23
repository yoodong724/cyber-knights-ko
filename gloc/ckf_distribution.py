"""Offline COPY/ADD delta packages for the Windows CKF installer (stdlib only)."""
from __future__ import annotations

import gzip
import hashlib
import io
import re
import struct
import zipfile
from pathlib import Path, PurePosixPath

from .ckf_install import (CHINESE, FONT, FONT_26097464, FONT_26097464_PROFILE,
                          GUARDS, GUARDS_26097464, GUARDS_26138768, GUARDS_26151125, no_links, disjoint, valid_hash)
from .image_patch import get_source_profile
from .util import GlocError, file_hash, read_json, read_jsonl, require_new_output, write_json

MAGIC = b'CKFDLT1\0'
TARGETS = (CHINESE, FONT,
    'CyberKnights_Data/StreamingAssets/aa/StandaloneWindows64/137c9c9d0e2661b191cb5b5abcb264d0.bundle',
    'CyberKnights_Data/StreamingAssets/aa/StandaloneWindows64/56da66cbd81e37886e44ed6c467fca8e.bundle')
UPDATE_TARGETS = (CHINESE, FONT,
    'CyberKnights_Data/StreamingAssets/aa/StandaloneWindows64/f3165aa803db5d6316c3952a1d313627.bundle',
    TARGETS[3])
UPDATE_GUARDS = {
    'CyberKnights_Data/StreamingAssets/Locales/en-US.json': '3888d0e89a488073871af9b40d74eb79e1d07330e552acb5a11bc5208bb74a3a',
    'CyberKnights_Data/StreamingAssets/aa/catalog.bin': 'e38e0251c570115feea465d356c3db1011a09e80e7d162480f1a4ab29a79b59b',
}
UPDATE_25951469_TARGETS = (CHINESE, FONT,
    'CyberKnights_Data/StreamingAssets/aa/StandaloneWindows64/12a93a93a631419a4acec10bebefc84a.bundle',
    TARGETS[3])
UPDATE_25951469_GUARDS = {
    'CyberKnights_Data/StreamingAssets/Locales/en-US.json': '02752bed120a3cd3bb1757b02c11bee6a8754b2a812f4ef890c0fa389bd3befb',
    'CyberKnights_Data/StreamingAssets/aa/catalog.bin': '382d80b33027e0bc863302c92c79fa84c39c717e3bb17daf991fa2409a545efe',
}
# 25964281 keeps the 25951469 target bytes; only English/catalog guards changed.
UPDATE_25964281_GUARDS = {
    'CyberKnights_Data/StreamingAssets/Locales/en-US.json': '96b480317ed77cbd43ca6dcb87a8099a1eba29840512c02f69f33f89f8a30912',
    'CyberKnights_Data/StreamingAssets/aa/catalog.bin': '4730c1ddb4fe809e5835dda6b5251a114736ae05180fd98aef883fea1cab62bd',
}
UPDATE_26097464_TARGETS = (CHINESE, FONT_26097464,
    'CyberKnights_Data/StreamingAssets/aa/StandaloneWindows64/81abd4ea29932d9b79d378d018b7d98a.bundle',
    'CyberKnights_Data/StreamingAssets/aa/StandaloneWindows64/b19430f3a52557e1df858dc46e1b0233.bundle')
UPDATE_26097464_GUARDS = dict(GUARDS_26097464)
# All original target hashes come from the frozen 26097464 original-files.json.
UPDATE_26097464_ORIGINALS = dict(zip(UPDATE_26097464_TARGETS, (
    '46b39cf4d342bb6901ee7d07e03e6425dcebc92c98e8bd8c76d3473f98218c45',
    '876d7d2963fa00e6752e961d845fe59fb41f3a9c204226c35a74a122e85bc770',
    '9b4db040dcf96a3d123ca23f0716423c7f25aed2596f5952cf8102d53b6464f7',
    '7398233a5ef51249b296057a634b3bc3d5726f102d7435c2199efb566998bbe6')))
# 26138768 keeps the font/caption/fallback bytes of 26097464; zh-CN and guards changed.
UPDATE_26138768_GUARDS = dict(GUARDS_26138768)
UPDATE_26138768_ORIGINALS = dict(zip(UPDATE_26097464_TARGETS, (
    '25d244ba3aa65f5ba4401dbe86095c4dd5b5f8f2469e3e03cc5f0e8d97699921',
    *tuple(UPDATE_26097464_ORIGINALS.values())[1:])))
# Frozen 26151125 inventory: all six originals retain the previous build's bytes.
UPDATE_26151125_GUARDS = dict(GUARDS_26151125)
UPDATE_26151125_ORIGINALS = dict(UPDATE_26138768_ORIGINALS)
# Builds whose tutorial image streams are relocated from the released 25964281-rc1
# evidence instead of reusing old bundle bytes; only that evidence lane permits this.
RELOCATION_BUILDS = ('26097464', '26138768', '26151125')
# Explicit update profiles.
UPDATE_BUILDS = ('25889011', '25951469', '25964281', *RELOCATION_BUILDS)


def relocation_profile(build: str) -> dict | None:
    """Pinned relocation build profile; module constants are looked up at call time."""
    return {'26097464': {'game_version': '2.7.99', 'targets': UPDATE_26097464_TARGETS,
                         'guards': UPDATE_26097464_GUARDS, 'originals': UPDATE_26097464_ORIGINALS},
            '26138768': {'game_version': '2.7.101', 'targets': UPDATE_26097464_TARGETS,
                         'guards': UPDATE_26138768_GUARDS, 'originals': UPDATE_26138768_ORIGINALS},
            '26151125': {'game_version': '2.7.103', 'targets': UPDATE_26097464_TARGETS,
                         'guards': UPDATE_26151125_GUARDS, 'originals': UPDATE_26151125_ORIGINALS}}.get(build)


def update_profile(build: str) -> tuple[tuple[str, ...], dict[str, str]] | None:
    """Pinned (four targets, guards) for caption-moved builds; looked up at call time."""
    return {'25889011': (UPDATE_TARGETS, UPDATE_GUARDS),
            '25951469': (UPDATE_25951469_TARGETS, UPDATE_25951469_GUARDS),
            '25964281': (UPDATE_25951469_TARGETS, UPDATE_25964281_GUARDS),
            '26097464': (UPDATE_26097464_TARGETS, UPDATE_26097464_GUARDS),
            '26138768': (UPDATE_26097464_TARGETS, UPDATE_26138768_GUARDS),
            '26151125': (UPDATE_26097464_TARGETS, UPDATE_26151125_GUARDS)}.get(build)
IMAGE_TARGETS = (
    'CyberKnights_Data/StreamingAssets/aa/StandaloneWindows64/672fb9a7811edcdde218dc5de379c935.bundle',
    'CyberKnights_Data/StreamingAssets/aa/StandaloneWindows64/b50ba8b5464ec4de8ea55b111bbad63a.bundle')
CURRENT_IMAGE_TARGETS = (
    'CyberKnights_Data/StreamingAssets/aa/StandaloneWindows64/427efad263b7a135a46a33ce3a2f2adf.bundle',
    'CyberKnights_Data/StreamingAssets/aa/StandaloneWindows64/b50ba8b5464ec4de8ea55b111bbad63a.bundle')
V2_TARGETS = TARGETS + IMAGE_TARGETS
IMAGE_SCOPE_SHA256 = '1ee4a806c35824db7dde05922fba50cea84a79baa129b6d64c6ea60975a423b0'
CURRENT_IMAGE_SCOPE_SHA256 = '25241429f0f87236674c207a4cab3e05e65bb2c917c4893110fc8588e371e0f0'
CURRENT_GUARDS = {
    'CyberKnights_Data/StreamingAssets/Locales/en-US.json': 'dc181972ed1c734fdd703e7077af492972d9bdd9af212d8dbc8a2800c448e2d8',
    'CyberKnights_Data/StreamingAssets/aa/catalog.bin': '48bb9cca0500656eede32b28a366e82f10a5cee54e3a02686a1e15234910954a',
}
LEGACY_IMAGE_GUARDS = {
    'CyberKnights_Data/StreamingAssets/Locales/en-US.json': '6a0de0621ab04c4865cabcab5b3058ae854261f7952a0b3f0a44c1ec9c704c6a',
    'CyberKnights_Data/StreamingAssets/aa/catalog.bin': '08778902ee99fc8714d0c4752349075d002720a00162c9dad186c12d9f327133',
}
WEAPON_ICONS_ID = 'ckf-image:0a73058397dc62ee49c119882bfb71e4de6daee5aec515cb235edad9d7c707cf'
CURRENT_WEAPON_ICONS_ID = 'ckf-image:6a97d5c1701bdaff024f3ebb86bcacaa4f5c7a3c61b3255fea0407b3587c88e7'
BANNER_ID = 'ckf-image:d32acc60a653bf9c704dcd7a7ac4747f0e3c06844837f3fdff6dc2a1c4746fe2'
ANCHOR = re.compile(b'[\x00-\x03][\x00-\x3f]')
LIMIT = 512 * 1024 * 1024


def archive_name(build: str, revision: int = 0) -> str:
    if not isinstance(build, str) or not re.fullmatch(r'[1-9][0-9]{0,19}', build):
        raise GlocError('Invalid Steam build')
    if type(revision) is not int or not 0 <= revision <= 9999:
        raise GlocError('Invalid patch revision')
    return f'cyberknights-ko-{build}' + (f'-rc{revision}' if revision else '') + '.zip'


def chunks(data: bytes):
    """Content-defined boundaries survive shifted offsets; no external diff tool."""
    start = 0
    for match in ANCHOR.finditer(data):
        end = match.end()
        if end - start < 64:
            continue
        while end - start > 65536:
            yield start, start + 65536
            start += 65536
        yield start, end
        start = end
    while len(data) - start > 65536:
        yield start, start + 65536
        start += 65536
    if start < len(data):
        yield start, len(data)


def make_delta(before: bytes, after: bytes) -> bytes:
    if max(len(before), len(after)) > LIMIT:
        raise GlocError('File too large')
    index = {}
    for a, b in chunks(before):
        index.setdefault(hashlib.blake2b(before[a:b], digest_size=16).digest(), (a, b))
    operations = []
    for a, b in chunks(after):
        block = after[a:b]
        hit = index.get(hashlib.blake2b(block, digest_size=16).digest())
        if hit and before[hit[0]:hit[1]] == block:
            offset, end = hit
            if operations and operations[-1][0] == 1 and operations[-1][1] + operations[-1][2] == offset:
                operations[-1][2] += end - offset
            else:
                operations.append([1, offset, end-offset])
        elif operations and operations[-1][0] == 2:
            operations[-1][1].extend(block)
        else:
            operations.append([2, bytearray(block)])
    out = io.BytesIO()
    with gzip.GzipFile(fileobj=out, mode='wb', mtime=0) as stream:
        stream.write(MAGIC + struct.pack('<Q', len(after)))
        for op in operations:
            stream.write(bytes([op[0]]))
            if op[0] == 1:
                stream.write(struct.pack('<QI', op[1], op[2]))
            else:
                stream.write(struct.pack('<I', len(op[1])))
                stream.write(op[1])
        stream.write(b'\0')
    return out.getvalue()


def apply_delta(before: bytes, patch: bytes, expected_size: int) -> bytes:
    if type(expected_size) is not int or not 0 <= expected_size <= LIMIT:
        raise GlocError('Invalid output size')
    result = bytearray()
    def exact(stream, n):
        data = stream.read(n)
        if len(data) != n:
            raise GlocError('Truncated delta')
        return data
    try:
        with gzip.GzipFile(fileobj=io.BytesIO(patch)) as stream:
            if exact(stream, 8) != MAGIC or struct.unpack('<Q', exact(stream, 8))[0] != expected_size:
                raise GlocError('Wrong delta header')
            while True:
                op = exact(stream, 1)[0]
                if op == 0:
                    if len(result) != expected_size or stream.read(1):
                        raise GlocError('Wrong delta end')
                    break
                if op == 1:
                    offset, size = struct.unpack('<QI', exact(stream, 12))
                    if offset > len(before) or size > len(before) - offset:
                        raise GlocError('Copy outside source')
                elif op == 2:
                    size = struct.unpack('<I', exact(stream, 4))[0]
                else:
                    raise GlocError('Unknown delta opcode')
                if not size or size > expected_size - len(result):
                    raise GlocError('Delta output overflow')
                result.extend(before[offset:offset+size] if op == 1 else exact(stream, size))
    except (OSError, EOFError, struct.error) as exc:
        raise GlocError('Invalid compressed delta') from exc
    return bytes(result)


def _image_validation(stage: Path, rows: dict, *, build: str = '25594089') -> None:
    """A v2 package requires final, hash-bound image and game QA evidence."""
    manifest_path = no_links(stage/'manifest.json')
    validation = read_json(no_links(stage/'image-validation.json'))
    if build not in ('25594089', '25697586'):
        raise GlocError('Unsupported image source build')
    targets = IMAGE_TARGETS if build == '25594089' else CURRENT_IMAGE_TARGETS
    if tuple(get_source_profile(build)) != targets:
        raise GlocError('Distribution targets differ from the image source profile')
    scope_hash = IMAGE_SCOPE_SHA256 if build == '25594089' else CURRENT_IMAGE_SCOPE_SHA256
    weapon_icons_id = WEAPON_ICONS_ID if build == '25594089' else CURRENT_WEAPON_ICONS_ID
    if not isinstance(validation, dict) or validation.get('format') != 'ckf-image-validation-v1':
        raise GlocError('Missing image validation contract')
    declared_build = validation.get('source_build')
    if (build == '25697586' and declared_build != build) or (
            build == '25594089' and declared_build not in (None, build)):
        raise GlocError('Image validation source build mismatch')
    if validation.get('probe') is True:
        raise GlocError('Probe image validation cannot authorize a package')
    if validation.get('complete') is not True or validation.get('pilot') is not False:
        raise GlocError('Pilot or incomplete image validation')
    if any(validation.get(k) != [] for k in ('held_ids', 'unresolved_ids', 'ingame_not_run_ids')):
        raise GlocError('Image scope has unresolved or untested IDs')
    inputs = validation.get('inputs')
    if not isinstance(inputs, dict):
        raise GlocError('Missing image input hashes')
    sources = {'stage_manifest_sha256': manifest_path,
               'edits_sha256': no_links(stage.parent/'image-edits.jsonl'),
               'build_report_sha256': no_links(stage.parent/'build-report.json'),
               'qa_sha256': no_links(stage.parent/'image-qa.jsonl')}
    if set(inputs) != set(sources) or any(inputs[k] != file_hash(path) for k, path in sources.items()):
        raise GlocError('Image evidence hash mismatch')
    scope = validation.get('scope')
    if not isinstance(scope, dict) or set(scope) != {'expected_ids', 'edited_ids', 'retained'}:
        raise GlocError('Invalid image scope')
    expected, edited, retained = scope['expected_ids'], scope['edited_ids'], scope['retained']
    if (not isinstance(expected, list) or len(expected) != 33 or
            any(not isinstance(x, str) or not re.fullmatch(r'ckf-image:[0-9a-f]{64}', x) for x in expected) or
            len(set(expected)) != 33 or
            hashlib.sha256('\n'.join(sorted(expected)).encode()).hexdigest() != scope_hash):
        raise GlocError('Image scope differs from the fixed 33 IDs')
    if (not isinstance(edited, list) or not isinstance(retained, list) or
            any(not isinstance(x, str) for x in edited) or
            any(not isinstance(x, dict) for x in retained)):
        raise GlocError('Invalid image disposition')
    retained_ids = []
    for item in retained:
        image_id = item.get('id')
        disposition = item.get('disposition')
        if (not isinstance(image_id, str) or image_id not in expected or
                disposition not in ('confirmed_unused', 'weapon_icons_only') or
                not isinstance(item.get('reason'), str) or not item['reason'].strip() or
                not isinstance(item.get('evidence'), str) or not item['evidence'].strip() or
                (image_id == weapon_icons_id) != (disposition == 'weapon_icons_only')):
            raise GlocError('Unsubstantiated retained image')
        retained_ids.append(image_id)
    if (len(set(edited)) != len(edited) or len(set(retained_ids)) != len(retained_ids) or
            set(edited).intersection(retained_ids) or set(edited).union(retained_ids) != set(expected) or
            weapon_icons_id not in retained_ids or BANNER_ID not in edited):
        raise GlocError('Incomplete image scope partition')
    edits = read_jsonl(sources['edits_sha256'])
    if (len(edits) != len(edited) or
            any(not isinstance(item, dict) or not isinstance(item.get('image_id'), str) or
                not isinstance(item.get('final_png_sha256'), str) or
                not re.fullmatch(r'[0-9a-f]{64}', item['final_png_sha256']) for item in edits) or
            {item['image_id'] for item in edits} != set(edited)):
        raise GlocError('Image edits do not match the complete edited scope')
    edit_by_id = {item['image_id']: item for item in edits}
    files = validation.get('files')
    if (not isinstance(files, list) or len(files) != 2 or
            [item.get('path') for item in files if isinstance(item, dict)] != list(targets)):
        raise GlocError('Image validation does not cover both fixed bundles')
    for item in files:
        row = rows[item['path']][0]
        if item.get('before') != row['before'] or item.get('after') != row['after']:
            raise GlocError('Image stage and validation file hashes disagree')
    report = read_json(sources['build_report_sha256'])
    selected = report.get('selected_ids') if isinstance(report, dict) else None
    report_build = report.get('source_build') if isinstance(report, dict) else None
    if ((build == '25697586' and report_build != build) or
            (build == '25594089' and report_build not in (None, build))):
        raise GlocError('Image build report source build mismatch')
    if report.get('probe') is True:
        raise GlocError('Probe image build report cannot authorize a package')
    if ((build == '25697586' and report.get('physical_save_reload_verified') is not True) or
            (build == '25594089' and 'physical_save_reload_verified' in report and
             report.get('physical_save_reload_verified') is not True)):
        raise GlocError('Physical save/reload verification is incomplete')
    if (not isinstance(report, dict) or report.get('complete') is not True or
            report.get('pilot') is not False or not isinstance(selected, list) or
            any(not isinstance(x, str) for x in selected) or
            len(selected) != len(set(selected)) or set(selected) != set(edited) or
            any(report.get(k) is not True for k in ('non_target_objects_unchanged',
                'member_metadata_unchanged', 'stream_ranges_valid', 'final_decode_verified',
                'scope_preserved'))):
        raise GlocError('Image build report is incomplete')
    report_inputs = report.get('inputs')
    if (not isinstance(report_inputs, dict) or any(report_inputs.get(k) != inputs[k]
            for k in ('stage_manifest_sha256', 'edits_sha256', 'qa_sha256'))):
        raise GlocError('Image build report input hashes are stale')
    results = report.get('results')
    if (not isinstance(results, list) or len(results) != len(edited) or
            any(not isinstance(item, dict) or not isinstance(item.get('id'), str) for item in results) or
            {item['id'] for item in results} != set(edited)):
        raise GlocError('Image build results do not cover every edited ID')
    for item in results:
        bundle = targets[1] if item['id'] == BANNER_ID else targets[0]
        if (item.get('bundle_path') != bundle or
                item.get('bundle_sha256') != rows[bundle][0]['after'] or
                not isinstance(item.get('final_decoded_pixels_sha256'), str) or
                not re.fullmatch(r'[0-9a-f]{64}', item['final_decoded_pixels_sha256']) or
                item.get('format') not in ((4,) if bundle == targets[1] else (3, 10)) or
                item.get('protected_blocks_unchanged') is not True or
                item.get('visual') != 'PASS' or item.get('ingame') != 'PASS'):
            raise GlocError('Image build result is incomplete or bound to the wrong bundle')
    qa = read_jsonl(sources['qa_sha256'])
    if (len(qa) != len(edited) or any(not isinstance(q, dict) or not isinstance(q.get('id'), str) for q in qa) or
            {q.get('id') for q in qa} != set(edited)):
        raise GlocError('Image QA does not cover every edited ID')
    for item in qa:
        qa_build = item.get('source_build')
        if ((build == '25697586' and qa_build != build) or
                (build == '25594089' and qa_build not in (None, build)) or item.get('probe') is True):
            raise GlocError('Image QA source build/probe mismatch')
        bundle = targets[1] if item['id'] == BANNER_ID else targets[0]
        if (item.get('human_language_approval') is not False or
                item.get('bundle_path') != bundle or
                item.get('bundle_sha256') != rows[bundle][0]['after'] or
                item.get('final_png_sha256') != edit_by_id[item['id']]['final_png_sha256']):
            raise GlocError('Image QA is not bound to final bundle')
        for check in ('machine', 'visual', 'ingame'):
            result = item.get(check)
            if (not isinstance(result, dict) or result.get('status') != 'PASS' or
                    not isinstance(result.get('evidence'), str) or
                    not isinstance(result.get('evidence_sha256'), str) or
                    not re.fullmatch(r'[0-9a-f]{64}', result['evidence_sha256'])):
                raise GlocError('Image QA has an unverified check')
            relative = result['evidence']
            path = PurePosixPath(relative)
            if (path.is_absolute() or not path.parts or path.parts[0] != 'qa-evidence' or
                    len(path.parts) < 2 or any(part in ('.', '..') for part in relative.split('/')) or
                    '\\' in relative or str(path) != relative):
                raise GlocError('Image QA evidence path is unsafe')
            evidence = no_links(stage.parent/relative)
            if not evidence.is_file() or file_hash(evidence) != result['evidence_sha256']:
                raise GlocError('Image QA evidence hash mismatch')


def build_package(*, stages: list[Path], original: Path, templates: Path,
                  font_license: Path, font_notice: str, build: str, game_version: str,
                  revision: int, out: Path, work: Path,
                  allow_partial_images: bool = False) -> dict:
    """Explicit locally authorized package assembly; not the language approval gate."""
    name = archive_name(build, revision)
    if type(allow_partial_images) is not bool:
        raise GlocError('Partial image authorization must be boolean')
    if not isinstance(game_version, str) or not re.fullmatch(r'[0-9]+(?:\.[0-9]+){1,3}', game_version):
        raise GlocError('Invalid game version')
    original, out, work = map(no_links, (original, out, work))
    templates, font_license = map(no_links, (templates, font_license))
    stages = [no_links(s) for s in stages]
    disjoint(out, work)
    for output in (out, work):
        for source in (original, templates, font_license, *stages):
            disjoint(output, source)
    require_new_output(work)
    require_new_output(out/name)
    rows = {}; guards = {}; image_stage = None
    profile = update_profile(build)
    base_targets = profile[0] if profile else TARGETS
    if build == '25594089':
        accepted_stage_targets = set(TARGETS) | set(get_source_profile('25594089'))
    elif build == '25697586':
        accepted_stage_targets = set(TARGETS) | set(get_source_profile('25697586'))
    elif profile:
        accepted_stage_targets = set(base_targets) | set(get_source_profile(build))
    else:
        # Historical four-file packages keep accepting their caller-supplied build.
        # Image stages always require one of the explicit profiles below.
        accepted_stage_targets = set(base_targets)
    for stage in stages:
        m = read_json(no_links(stage/'manifest.json'))
        if m.get('format') not in ('ckf-local-stage-v1','ckf-local-asset-overlay-v1'):
            raise GlocError('Unsupported source stage')
        stage_paths = [row.get('path') for row in m.get('files', []) if isinstance(row, dict)]
        if len(stage_paths) != len(m.get('files', [])):
            raise GlocError('Invalid source stage entries')
        all_image_targets = set(IMAGE_TARGETS) | set(CURRENT_IMAGE_TARGETS)
        for relocated in RELOCATION_BUILDS:
            all_image_targets |= set(get_source_profile(relocated))
        if any(path in all_image_targets for path in stage_paths):
            if image_stage is not None or m['format'] != 'ckf-local-asset-overlay-v1' or len(stage_paths) != 2:
                raise GlocError('Image stage must contain exactly two image bundles')
            if build not in ('25594089', '25697586', *UPDATE_BUILDS):
                raise GlocError('Unsupported image source build')
            profile_targets = set(get_source_profile(build))
            if set(stage_paths) != profile_targets:
                raise GlocError('Image stage mixes source-build profiles')
            image_stage = stage
        for row in m['files']:
            if row['path'] not in accepted_stage_targets or row['path'] in rows or not re.fullmatch(r'[0-9]+\.bin', row['payload']):
                raise GlocError('Unexpected/duplicate source stage entry')
            rows[row['path']] = (row, no_links(stage/row['payload']))
        for guard in m['guards']:
            if guard['path'] not in GUARDS or guards.get(guard['path'],guard['sha256']) != guard['sha256']:
                raise GlocError('Inconsistent guards')
            guards[guard['path']] = guard['sha256']
    current_v2_targets = base_targets + (tuple(get_source_profile(build)) if profile else CURRENT_IMAGE_TARGETS)
    paths = base_targets if set(rows) == set(base_targets) else (
        V2_TARGETS if set(rows) == set(V2_TARGETS) else
        current_v2_targets if set(rows) == set(current_v2_targets) else None)
    if paths is None or set(guards) != set(GUARDS):
        raise GlocError('Patch requires exactly four or six fixed files and two guards')
    if profile and guards != profile[1]:
        raise GlocError(f'{build} stage requires its pinned build and guards')
    relocation = relocation_profile(build)
    if relocation:
        if paths != current_v2_targets or not allow_partial_images:
            raise GlocError(f'{build} requires the authorized six-file partial-image package')
        if game_version != relocation['game_version']:
            raise GlocError(f"{build} requires game version {relocation['game_version']}")
        originals = {**relocation['originals'],
                     **{p: h for p, (_, h) in get_source_profile(build).items()}}
        if any(rows[p][0].get('before') != h for p, h in originals.items()):
            raise GlocError(f'{build} original target profile mismatch')
        if (not valid_hash(FONT_26097464_PROFILE['patched']) or
                rows[FONT_26097464][0].get('after') != FONT_26097464_PROFILE['patched']):
            raise GlocError(f'{build} Korean font result is not verified/pinned')
    image_summary = None
    if allow_partial_images and (build not in ('25697586', *UPDATE_BUILDS) or paths != current_v2_targets):
        raise GlocError('Partial images require the current six-file build profile')
    if paths == V2_TARGETS:
        if image_stage is None:
            raise GlocError('Missing image stage')
        if build != '25594089' or guards != LEGACY_IMAGE_GUARDS:
            raise GlocError('Legacy image stage requires its pinned build and guards')
        _image_validation(image_stage, rows, build=build)
    elif paths == current_v2_targets:
        if image_stage is None:
            raise GlocError('Missing image stage')
        expected_guards = profile[1] if profile else CURRENT_GUARDS
        if build not in ('25697586', *UPDATE_BUILDS) or guards != expected_guards:
            raise GlocError('Current image stage requires its pinned build and guards')
        if allow_partial_images:
            from .ckf_partial_images import validate_partial_images
            image_summary = validate_partial_images(image_stage, rows, build=build)
        else:
            if profile:
                raise GlocError(f'{build} images require explicit partial-image authorization')
            _image_validation(image_stage, rows, build=build)
    for rel, digest in guards.items():
        if file_hash(no_links(original/rel)) != digest: raise GlocError('Guard mismatch')
    package = work/'cyberknights-ko'
    (package/'payload').mkdir(parents=True)
    entries = []
    for i,rel in enumerate(paths):
        row, source = rows[rel]
        if no_links(original/rel).stat().st_size > LIMIT or source.stat().st_size > LIMIT:
            raise GlocError('File too large')
        before = no_links(original/rel).read_bytes()
        after = source.read_bytes()
        if hashlib.sha256(before).hexdigest() != row['before'] or hashlib.sha256(after).hexdigest() != row['after']:
            raise GlocError('Source hash mismatch')
        delta = make_delta(before, after)
        if apply_delta(before, delta, len(after)) != after: raise GlocError('Delta reconstruction mismatch')
        payload = f'payload/{i}.delta.gz'
        (package/payload).write_bytes(delta)
        entries.append({'path':rel,'before':row['before'],'after':row['after'],
            'before_size':len(before),'after_size':len(after),'payload':payload,
            'payload_sha256':hashlib.sha256(delta).hexdigest(),'payload_size':len(delta)})
    manifest = {'format':'ckf-distribution-v1' if paths == base_targets else 'ckf-distribution-v2','steam_build':build,'revision':revision,
        'patch_id':build+(f'-rc{revision}' if revision else ''),'game_version':game_version,
        'files':entries,'guards':[{'path':r,'sha256':h} for r,h in sorted(guards.items())],
        'human_language_approval':False,'full_game_qa':False,
        'scope':('Korean locale, fonts, three scene captions; existing saved names are not migrated' if paths == base_targets else
                 'Korean locale, fonts, scene captions, tutorial and menu images; shared images appear in other languages; existing saved names are not migrated')}
    if image_summary is not None:
        manifest['image_status'] = image_summary
        manifest['scope'] = ('Korean locale, fonts, scene captions and PARTIAL tutorial/menu images; '
                             'untranslated image text remains; shared images appear in other languages; '
                             'existing saved names are not migrated')
    write_json(package/'manifest.json',manifest)
    allow = ('install.cmd','uninstall.cmd','verify.cmd','Patch.cs','README.txt')
    for relative in allow:
        content = no_links(templates/relative).read_text(encoding='utf-8')
        if relative == 'README.txt' and image_summary is not None:
            s = image_summary
            content = ('부분 이미지 포함 한국어 패치 — Steam '+build+' / '+game_version+
                       (f' / rc{revision}' if revision else '')+'\n'
                       '이미지 전체 번역은 미완료입니다. 영문 문구가 남아 있습니다.\n'
                       f"이미지 {len(s['edited_ids'])}점·{s['rendered_regions']}개 영역 반영, "
                       f"그중 {len(s['partial_ids'])}점 부분 수정. "
                       f"미반영 {len(s['unrendered_ids'])}점, 배경 복원 보류 {len(s['held_ids'])}점, "
                       f"숫자/아이콘 원본 유지 {len(s['retained_ids'])}점.\n"
                       '보류: Tutorial_ActionPointsMove, Tutorial_MovementLinesGray.\n'+
                       (f"현재 빌드 이미지 게임 확인 {len(s['ingame_observed_ids'])}점; " if s.get('evidence_source_build') else
                        f"기존 동일 번들 게임 확인 {len(s['ingame_observed_ids'])}점; ")+
                       f"반영 이미지 중 {len(s['ingame_not_run_ids'])}점은 게임 화면 미확인.\n"
                       '사람 언어 승인·전체 게임 QA·전체 이미지 완료 승인은 없습니다.\n\n'+content)
        content = content.replace('\n','\r\n')
        (package/relative).write_bytes(content.encode('utf-8'))
    (package/'FONT-LICENSE.txt').write_text(font_notice+'\n\n'+font_license.read_text(),encoding='utf-8')
    out.mkdir(parents=True,exist_ok=True)
    members = sorted(p for p in package.rglob('*') if p.is_file())
    expected = {'manifest.json','FONT-LICENSE.txt',*allow,*(r['payload'] for r in entries)}
    if {p.relative_to(package).as_posix() for p in members} != expected:
        raise GlocError('Package allowlist mismatch')
    with zipfile.ZipFile(out/name,'x',compression=zipfile.ZIP_DEFLATED) as archive:
        for path in members: archive.write(path,'cyberknights-ko/'+path.relative_to(package).as_posix())
    with zipfile.ZipFile(out/name) as archive:
        if archive.testzip() is not None or len(archive.namelist()) != len(expected):
            raise GlocError('Archive verification failed')
        for path in members:
            if archive.read('cyberknights-ko/'+path.relative_to(package).as_posix()) != path.read_bytes():
                raise GlocError('Archive readback failed')
    return {'archive':str(out/name),'sha256':file_hash(out/name),'bytes':(out/name).stat().st_size,
            'manifest':manifest,'members':len(members)}
