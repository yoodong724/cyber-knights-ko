"""Evidence gate for the explicitly incomplete CKF 25697586 image overlay.

This is a separate package lane.  The final image gate in ckf_distribution
continues to require every image and every in-game check to pass.
"""
from __future__ import annotations

import hashlib
import json
import re
import zipfile
from pathlib import Path, PurePosixPath

from .ckf_install import no_links
from .image_patch import RELOCATION_IDS, _CURRENT_IDS, get_source_profile
from .util import GlocError, file_hash, read_json, read_jsonl


_BUILD = "25697586"
_SCOPE_SHA256 = "25241429f0f87236674c207a4cab3e05e65bb2c917c4893110fc8588e371e0f0"
_WEAPON_ID = "ckf-image:6a97d5c1701bdaff024f3ebb86bcacaa4f5c7a3c61b3255fea0407b3587c88e7"
_BANNER_ID = "ckf-image:d32acc60a653bf9c704dcd7a7ac4747f0e3c06844837f3fdff6dc2a1c4746fe2"
_HELD_NAMES = {"Tutorial_ActionPointsMove", "Tutorial_MovementLinesGray"}
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_ID = re.compile(r"ckf-image:[0-9a-f]{64}\Z")
_REGION = re.compile(r"ckf-image:[0-9a-f]{64}:region:[1-9][0-9]*\Z")
_TARGETS = tuple(get_source_profile(_BUILD))
RELOCATION_ARCHIVE_SHA256 = "4833ae1876c9572100815df8045948eba80717182f4b894ba332fcbaad96983f"
# Exact preservation accounting of the two current image bundles per relocation build.
RELOCATION_COUNTS = {
    "26299178": {"total_objects": 5946, "unchanged_objects": 5946,
                 "total_texture_streams": 1930, "selected_texture_streams": 16,
                 "unchanged_nonselected_texture_streams": 1914},
    "26198171": {"total_objects": 5946, "unchanged_objects": 5946,
                 "total_texture_streams": 1930, "selected_texture_streams": 16,
                 "unchanged_nonselected_texture_streams": 1914},
    "26097464": {"total_objects": 5942, "unchanged_objects": 5942,
                 "total_texture_streams": 1928, "selected_texture_streams": 16,
                 "unchanged_nonselected_texture_streams": 1912},
    # The tutorial bundle gained one Texture2D/Sprite pair (MissionIcon_StreetMix2).
    "26138768": {"total_objects": 5944, "unchanged_objects": 5944,
                 "total_texture_streams": 1929, "selected_texture_streams": 16,
                 "unchanged_nonselected_texture_streams": 1913},
    "26151125": {"total_objects": 5944, "unchanged_objects": 5944,
                 "total_texture_streams": 1929, "selected_texture_streams": 16,
                 "unchanged_nonselected_texture_streams": 1913},
}


def _need(condition: bool, message: str) -> None:
    if not condition:
        raise GlocError(f"Partial image evidence: {message}")


def _ids(items: object, label: str, *, count: int | None = None,
         region: bool = False) -> set[str]:
    pattern = _REGION if region else _ID
    _need(isinstance(items, list) and all(isinstance(x, str) and pattern.fullmatch(x) for x in items),
          f"invalid {label}")
    found = set(items)
    _need(len(found) == len(items) and (count is None or len(found) == count), f"duplicate/wrong {label}")
    return found


def _index(items: object, key: str, label: str, *, count: int) -> dict[str, dict]:
    _need(isinstance(items, list) and len(items) == count and
          all(isinstance(x, dict) and isinstance(x.get(key), str) for x in items),
          f"invalid {label}")
    result = {x[key]: x for x in items}
    _need(len(result) == count, f"duplicate {label}")
    return result


def _file(root: Path, relative: str, *, prefix: str | None = None) -> Path:
    _need(isinstance(relative, str) and "\\" not in relative, "unsafe evidence path")
    path = PurePosixPath(relative)
    _need(not path.is_absolute() and path.parts and all(part not in (".", "..") for part in relative.split("/"))
          and str(path) == relative and (prefix is None or path.parts[0] == prefix), "unsafe evidence path")
    target = no_links(root.joinpath(*path.parts))
    _need(target.is_file() and target.is_relative_to(root.resolve()), "missing/escaping evidence file")
    return target


def _absolute_file(root: Path, name: object, *, directory: str) -> Path:
    _need(isinstance(name, str), "invalid readback path")
    path = Path(name)
    _need(path.is_absolute() and path.parent == root / directory and path.suffix.lower() == ".png",
          "unsafe readback PNG path")
    target = no_links(path)
    _need(target.is_file(), "missing readback PNG")
    return target


def _hashes(root: Path, names: dict[str, str]) -> tuple[dict[str, Path], dict[str, str]]:
    paths = {key: _file(root, relative) for key, relative in names.items()}
    return paths, {key: file_hash(path) for key, path in paths.items()}


def validate_partial_images(stage: Path, rows: dict, *, build: str) -> dict:
    """Validate the saved partial overlay and return a truthful public summary.

    ``rows`` is the distribution builder's map of target path to one staged file
    row.  No source bytes are written or regenerated here.
    """
    if build in RELOCATION_COUNTS:
        return _validate_relocated_partial_images(stage, rows, build)
    if build in ("25889011", "25951469", "25964281"):
        return _validate_reused_partial_images(stage, rows, build)
    _need(build == _BUILD, "partial lane is pinned to Steam build 25697586")
    stage = Path(stage).resolve()
    root = stage.parent
    paths, hashes = _hashes(root, {
        "stage_manifest": f"{stage.name}/manifest.json",
        "image_validation": f"{stage.name}/image-validation.json",
        "records": "image-records.jsonl",
        "edits": "image-edits.combined.v1.jsonl",
        "selected_qa": "image-qa.selected.v1.jsonl",
        "final_qa": "image-qa.available-final.v1.jsonl",
        "build_report": "available-build-report-v1.json",
        "machine_report": "available-readback-machine.v1.json",
        "visual_qa": "available-decoded-visual-qa.v1.json",
        "render_report": "render-report.combined.v1.json",
        "ingame_coverage": "ingame-coverage.final.v1.json",
    })
    manifest = read_json(paths["stage_manifest"])
    validation = read_json(paths["image_validation"])
    report = read_json(paths["build_report"])
    machine = read_json(paths["machine_report"])
    visual = read_json(paths["visual_qa"])
    render = read_json(paths["render_report"])
    coverage = read_json(paths["ingame_coverage"])
    records = _index(read_jsonl(paths["records"]), "id", "image records", count=33)
    edits = _index(read_jsonl(paths["edits"]), "image_id", "image edits", count=16)
    selected_qa = _index(read_jsonl(paths["selected_qa"]), "id", "selected QA", count=16)
    final_qa = _index(read_jsonl(paths["final_qa"]), "id", "final QA", count=33)

    expected = set(records)
    _need(all(_ID.fullmatch(x) for x in expected) and
          hashlib.sha256("\n".join(sorted(expected)).encode()).hexdigest() == _SCOPE_SHA256,
          "fixed 33-image scope mismatch")
    _need(all(x.get("source_build") == build for x in records.values()), "record source build mismatch")
    held = {key for key, x in records.items() if x.get("status") == "defer"}
    retained = {key for key, x in records.items() if x.get("status") == "retain"}
    editable = {key for key, x in records.items() if x.get("status") == "edit"}
    _need(len(editable) == 30 and len(held) == 2 and len(retained) == 1 and
          {records[x].get("name") for x in held} == _HELD_NAMES and retained == {_WEAPON_ID} and
          _BANNER_ID in edits and set(edits) <= editable and len(edits) == 16,
          "wrong edited/held/retained partition")
    unrendered = editable - set(edits)
    _need(len(unrendered) == 14, "wrong unrendered image count")
    for rec in records.values():
        _need(rec.get("asset") in _TARGETS and rec.get("asset_sha256") == get_source_profile(build)[rec["asset"]][1],
              "record source bundle mismatch")

    _need(isinstance(manifest, dict) and manifest.get("format") == "ckf-local-asset-overlay-v1" and
          manifest.get("local_only") is True and manifest.get("release_approved") is False and
          isinstance(manifest.get("files"), list) and len(manifest["files"]) == 2,
          "unsafe/missing overlay stage manifest")
    files = _index(manifest["files"], "path", "stage bundles", count=2)
    _need(set(files) == set(_TARGETS) and set(rows) >= set(_TARGETS), "wrong stage bundles")
    for path, item in files.items():
        expected_before = get_source_profile(build)[path][1]
        _need(item.get("before") == expected_before and
              isinstance(item.get("after"), str) and _SHA.fullmatch(item["after"]) and
              rows[path][0].get("before") == expected_before and rows[path][0].get("after") == item["after"],
              "stage bundle hash mismatch")
        payload = _file(stage, item.get("payload"))
        _need(file_hash(payload) == item["after"], "stage bundle payload hash mismatch")

    _need(isinstance(validation, dict) and validation.get("format") == "ckf-image-validation-v1" and
          validation.get("source_build") == build and validation.get("complete") is False and
          validation.get("pilot") is True and validation.get("probe") is True and
          validation.get("build_report_sha256") == hashes["build_report"] and
          validation.get("recovery_evidence", {}).get("independent_machine_report_sha256") == hashes["machine_report"],
          "stale/inaccurate image validation")
    scope = validation.get("scope", {})
    _need(_ids(scope.get("expected_ids"), "validation scope", count=33) == expected and
          _ids(scope.get("edited_ids"), "validation edited IDs", count=16) == set(edits) and
          _ids(validation.get("held_ids"), "validation held IDs", count=2) == held and
          _ids(validation.get("partial_ids"), "validation partial IDs", count=11) <= set(edits),
          "image validation scope mismatch")
    _need(isinstance(report, dict) and report.get("format") == "ckf-image-available-build-v1" and
          report.get("source_build") == build and report.get("complete") is False and
          report.get("physical_save_reload_verified") is True and
          all(report.get(k) is True for k in ("non_target_objects_unchanged", "member_metadata_unchanged",
                                                "stream_ranges_valid", "final_decode_verified")),
          "saved-bundle build proof incomplete")
    report_inputs = report.get("inputs", {})
    for key, evidence in (("stage_manifest_sha256", "stage_manifest"), ("records_sha256", "records"),
                          ("edits_sha256", "edits"), ("qa_sha256", "selected_qa"),
                          ("render_report_sha256", "render_report")):
        _need(report_inputs.get(key) == hashes[evidence], f"stale build {key}")
    _need(_ids(report.get("selected_ids"), "build selected IDs", count=16) == set(edits) and
          _ids(report.get("held_ids"), "build held IDs", count=2) == held,
          "build scope mismatch")
    built = _index(report.get("results"), "id", "build results", count=16)
    _need(set(built) == set(edits), "build results scope mismatch")

    _need(isinstance(machine, dict) and machine.get("source_build") == build and
          machine.get("status") == "PASS" and machine.get("complete") is False and
          machine.get("build_report_sha256") == hashes["build_report"] and
          machine.get("counts", {}).get("unchanged_objects") == 5918 and
          machine.get("counts", {}).get("unchanged_nonselected_texture_streams") == 1910,
          "machine preservation proof failed")
    _need({"Tutorial_ActionPointsMove", "Tutorial_MovementLinesGray", "Tutorial_WeaponIcons"} <=
          set(machine.get("non_target_images_decoded_equal", [])), "held/retained image preservation unproven")
    checked = _index(machine.get("results"), "id", "machine results", count=16)
    _need(set(checked) == set(edits), "machine scope mismatch")
    _need(isinstance(visual, dict) and visual.get("source_build") == build and
          visual.get("complete") is False and visual.get("partial_region_qa_only") is True and
          visual.get("machine_report_sha256") == hashes["machine_report"],
          "decoded visual proof mismatch")
    visually_checked = _index(visual.get("qa"), "id", "visual QA", count=16)
    _need(set(visually_checked) == set(edits), "visual QA scope mismatch")
    _need(isinstance(render, dict) and render.get("source_build") == build and
          render.get("complete") is False and
          _ids(render.get("selected_ids"), "render selected IDs", count=16) == set(edits),
          "render report scope mismatch")
    rendered = _index(render.get("results"), "id", "render results", count=16)
    _need(set(rendered) == set(edits), "render results scope mismatch")

    rendered_regions: set[str] = set()
    for key, edit in edits.items():
        rec, built_row, machine_row, visual_row, render_row = (
            records[key], built[key], checked[key], visually_checked[key], rendered[key])
        bundle = _TARGETS[1] if key == _BANNER_ID else _TARGETS[0]
        bundle_hash = files[bundle]["after"]
        region_ids = _ids(edit.get("region_ids"), "selected region IDs", region=True)
        _need(region_ids and all(x.startswith(key + ":region:") for x in region_ids) and
              not (rendered_regions & region_ids), "invalid/duplicate selected regions")
        rendered_regions |= region_ids
        _need(edit.get("human_language_approval") is False and
              edit.get("source_png_sha256") == rec.get("source_png_sha256") and
              edit.get("source_stream_sha256") == rec.get("stream", {}).get("sha256") and
              isinstance(edit.get("final_png_sha256"), str) and _SHA.fullmatch(edit["final_png_sha256"]) and
              file_hash(_file(root, edit.get("final_png"))) == edit["final_png_sha256"],
              "candidate PNG/source hash mismatch")
        readback = _absolute_file(root, built_row.get("readback_png"), directory="available-build-report-v1-readback")
        _need(file_hash(readback) == built_row.get("readback_png_sha256"), "saved-bundle readback PNG mismatch")
        _need(built_row.get("bundle_path") == bundle and built_row.get("bundle_sha256") == bundle_hash and
              built_row.get("format") == rec.get("format") and
              built_row.get("non_target_objects_unchanged") is True and
              _ids(built_row.get("region_ids"), "build regions", region=True) == region_ids and
              isinstance(built_row.get("final_decoded_pixels_sha256"), str) and
              _SHA.fullmatch(built_row["final_decoded_pixels_sha256"]),
              "build image result mismatch")
        _need(machine_row.get("source_build") == build and machine_row.get("bundle_path") == bundle and
              machine_row.get("bundle_sha256") == bundle_hash and
              machine_row.get("candidate_png_sha256") == edit["final_png_sha256"] and
              machine_row.get("source_png_sha256") == rec.get("source_png_sha256") and
              machine_row.get("decoded_pixels_sha256") == built_row["final_decoded_pixels_sha256"] and
              _ids(machine_row.get("selected_region_ids"), "machine regions", region=True) == region_ids and
              machine_row.get("outside_edit_pixels_or_nonselected_dxt_blocks_unchanged") is True and
              machine_row.get("protected_pixels_unchanged") is True,
              "machine image result mismatch")
        if rec["format"] == 4:
            _need(machine_row.get("alpha_unchanged") is True, "RGBA alpha preservation failed")
        _need(visual_row.get("source_build") == build and visual_row.get("bundle_path") == bundle and
              visual_row.get("bundle_sha256") == bundle_hash and
              visual_row.get("readback_png_sha256") == built_row["readback_png_sha256"] and
              visual_row.get("human_language_approval") is False and visual_row.get("full_game_qa") is False and
              _ids(visual_row.get("selected_regions"), "visual regions", region=True) == region_ids and
              visual_row.get("visual", {}).get("status") == "PASS",
              "visual QA result mismatch")
        _need(render_row.get("png_sha256") == edit["final_png_sha256"] and
              _ids(render_row.get("completed_regions"), "render regions", region=True) == region_ids and
              selected_qa[key].get("candidate_png_sha256") == edit["final_png_sha256"] and
              selected_qa[key].get("human_language_approval") is False and
              selected_qa[key].get("full_game_qa") is False,
              "render/selected QA mismatch")
    _need(len(rendered_regions) == 67, "selected region count changed")

    _need(isinstance(coverage, dict) and coverage.get("source_build") == build and
          coverage.get("complete") is False and coverage.get("full_game_qa") is False and
          coverage.get("qa_sha256") == hashes["final_qa"], "in-game evidence mismatch")
    _need(set(final_qa) == expected, "final QA scope mismatch")
    observed: set[str] = set()
    not_run: set[str] = set()
    partial: set[str] = set()
    for key, qa in final_qa.items():
        rec = records[key]
        _need(qa.get("source_build") == build and qa.get("name") == rec.get("name") and
              qa.get("disposition") == rec.get("status") and
              qa.get("source_png_sha256") == rec.get("source_png_sha256") and
              qa.get("complete") is False and qa.get("pilot_passed") is False and
              qa.get("human_language_approval") is False and qa.get("full_game_qa") is False,
              "final QA reassigned/misrepresented")
        if key in edits:
            edit = edits[key]
            _need(qa.get("candidate_png_sha256") == edit["final_png_sha256"] and
                  qa.get("bundle_sha256") == files[_TARGETS[1] if key == _BANNER_ID else _TARGETS[0]]["after"] and
                  _ids(qa.get("selected_region_ids"), "final QA regions", region=True) == set(edit["region_ids"]) and
                  qa.get("machine", {}).get("status") == "PASS" and
                  qa.get("static_visual", {}).get("status") == "PASS_SELECTED_REGIONS" and
                  qa.get("language", {}).get("status") == "PASS_SELECTED_REGIONS",
                  "final selected QA mismatch")
            if qa.get("production_status") == "PARTIAL_RENDERED":
                partial.add(key)
            else:
                _need(qa.get("production_status") == "SELECTED_REGIONS_RENDERED", "invalid selected status")
            game = qa.get("ingame", {})
            if game.get("selected_regions_status") == "PASS":
                observed.add(key)
                _need(game.get("status") == "PARTIAL" and isinstance(game.get("screens"), list) and
                      game["screens"], "invalid in-game observation")
                for screen in game["screens"]:
                    _need(screen.get("resolution") in ([2560, 1440], [1920, 1080]) and
                          isinstance(screen.get("sha256"), str) and _SHA.fullmatch(screen["sha256"]) and
                          file_hash(_file(root, screen.get("path"), prefix="ingame")) == screen["sha256"],
                          "in-game screenshot hash mismatch")
            else:
                _need(game.get("status") == "NOT_RUN" and game.get("screens") == [],
                      "unsupported in-game status")
                not_run.add(key)
        else:
            _need(qa.get("candidate_png_sha256") is None and qa.get("bundle_sha256") is None and
                  qa.get("selected_region_ids") == [] and
                  qa.get("machine", {}).get("status") == "ORIGINAL_STREAM_PRESERVED" and
                  qa.get("production_status") == ("HELD" if key in held else "RETAIN" if key in retained
                                                  else "TEXT_REVIEWED_NOT_RENDERED"),
                  "original-image QA mismatch")
    _need(partial == _ids(validation.get("partial_ids"), "partial IDs", count=11) and
          len(observed) == coverage.get("images_observed") == 11 and
          len(not_run) == 5 and
          _ids(validation.get("ingame_not_run_ids"), "validation pre-game not-run IDs", count=16) == set(edits) and
          coverage.get("selected_regions_observed") == sum(len(edits[x]["region_ids"]) for x in observed),
          "partial or in-game coverage counts mismatch")
    _need({records[x]["name"] for x in not_run} == set(coverage.get("rendered_images_not_reached", [])),
          "unreached in-game images mismatch")
    return {
        "format": "ckf-partial-image-summary-v1",
        "source_build": build,
        "complete": False,
        "edited_ids": sorted(edits),
        "partial_ids": sorted(partial),
        "held_ids": sorted(held),
        "unrendered_ids": sorted(unrendered),
        "retained_ids": sorted(retained),
        "rendered_regions": len(rendered_regions),
        "ingame_observed_ids": sorted(observed),
        "ingame_not_run_ids": sorted(not_run),
        "human_language_approval": False,
        "full_game_qa": False,
        "evidence_sha256": hashes,
    }


def _validate_reused_partial_images(stage: Path, rows: dict, build: str) -> dict:
    """Reuse byte-identical image evidence without reassigning old game QA.

    Prior records retain their real source build. The current package reports
    every image as not tested in game, even if that image was seen previously.
    """
    from .ckf_distribution import update_profile
    guards = update_profile(build)[1]
    stage = no_links(Path(stage).resolve())
    receipt_path = _file(stage, "migration-validation.json")
    receipt = read_json(receipt_path)
    _need(isinstance(receipt, dict) and receipt.get("format") == "ckf-image-byte-reuse-v1" and
          receipt.get("source_build") == build and receipt.get("evidence_source_build") == _BUILD and
          receipt.get("current_ingame") == "NOT_RUN", "invalid image reuse receipt")
    prior_value = receipt.get("prior_stage")
    _need(isinstance(prior_value, str) and Path(prior_value).is_absolute(), "invalid prior image stage")
    prior_stage = no_links(Path(prior_value))
    _need(prior_stage != stage and not prior_stage.is_relative_to(stage) and
          not stage.is_relative_to(prior_stage), "overlapping image reuse inputs")
    prior_manifest_path = _file(prior_stage, "manifest.json")
    prior_validation_path = _file(prior_stage, "image-validation.json")
    _need(file_hash(prior_manifest_path) == receipt.get("prior_manifest_sha256") and
          file_hash(prior_validation_path) == receipt.get("prior_validation_sha256"), "stale prior image stage")
    prior_manifest = read_json(prior_manifest_path)
    prior_rows = {x["path"]: (x, _file(prior_stage, x["payload"])) for x in prior_manifest["files"]}
    previous = validate_partial_images(prior_stage, prior_rows, build=_BUILD)
    manifest_path = _file(stage, "manifest.json")
    manifest = read_json(manifest_path)
    _need(manifest.get("format") == "ckf-local-asset-overlay-v1" and
          manifest.get("local_only") is True and manifest.get("release_approved") is False,
          "unsafe reused image stage")
    files = _index(manifest.get("files"), "path", "reused image bundles", count=2)
    _need(set(files) == set(_TARGETS) and set(rows) >= set(files), "wrong reused image targets")
    guard_rows = _index(manifest.get("guards"), "path", "reused image guards", count=2)
    _need({k: v.get("sha256") for k, v in guard_rows.items()} == guards,
          "image reuse guard/build mismatch")
    for path, row in files.items():
        prior = prior_rows[path][0]
        _need(row.get("before") == get_source_profile(build)[path][1] == prior["before"] and
              row.get("after") == prior["after"] and
              rows[path][0].get("before") == row["before"] and
              rows[path][0].get("after") == row["after"] and
              file_hash(_file(stage, row.get("payload"))) == row["after"],
              "reused source/payload bytes differ")
    machine_path = _file(stage.parent, "image-current-machine-check.json")
    _need(file_hash(machine_path) == receipt.get("current_machine_report_sha256"),
          "stale current image machine check")
    machine = read_json(machine_path)
    _need(machine.get("status") == "PASS" and machine.get("source_build") == build and
          machine.get("evidence_source_build") == _BUILD and machine.get("complete") is False and
          machine.get("current_stage_manifest_sha256") == file_hash(manifest_path) and
          machine.get("counts", {}).get("unchanged_objects") == 5918 and
          machine.get("counts", {}).get("unchanged_nonselected_texture_streams") == 1910,
          "current image decode/preservation proof failed")
    checked = _index(machine.get("results"), "id", "current image results", count=16)
    _need(set(checked) == set(previous["edited_ids"]), "current image check scope mismatch")
    for key, item in checked.items():
        bundle = _TARGETS[1] if key == _BANNER_ID else _TARGETS[0]
        _need(item.get("source_build") == build and item.get("bundle_path") == bundle and
              item.get("bundle_sha256") == files[bundle]["after"] and
              item.get("outside_edit_pixels_or_nonselected_dxt_blocks_unchanged") is True and
              item.get("protected_pixels_unchanged") is True,
              "current selected image preservation failed")
        if key == _BANNER_ID:
            _need(item.get("alpha_unchanged") is True, "current banner alpha preservation failed")
    previous.update(source_build=build, ingame_observed_ids=[],
                    ingame_not_run_ids=list(previous["edited_ids"]),
                    evidence_source_build=_BUILD)
    previous["evidence_sha256"] = {**previous["evidence_sha256"],
        "reuse_stage_manifest": file_hash(manifest_path), "reuse_receipt": file_hash(receipt_path),
        "current_machine_report": file_hash(machine_path)}
    return previous


def _released_relocation_evidence(stage: Path, receipt: dict) -> tuple[dict, dict, dict, dict]:
    """Read hash-anchored static evidence without claiming unavailable game QA."""
    from .ckf_distribution import UPDATE_25951469_TARGETS, UPDATE_25964281_GUARDS

    _need(receipt.get("historical_ingame_evidence_available") is False and
          receipt.get("prior_archive_sha256") == RELOCATION_ARCHIVE_SHA256,
          "invalid released image evidence anchor")
    archive_value, prior_value = receipt.get("prior_archive"), receipt.get("prior_image_stage")
    _need(all(isinstance(x, str) and Path(x).is_absolute() for x in (archive_value, prior_value)),
          "invalid released image evidence paths")
    archive = no_links(Path(archive_value))
    _need(archive.is_file() and not archive.is_relative_to(stage) and
          file_hash(archive) == RELOCATION_ARCHIVE_SHA256, "released image archive hash mismatch")
    try:
        with zipfile.ZipFile(archive) as packed:
            name = "cyberknights-ko/manifest.json"
            _need(packed.namelist().count(name) == 1 and packed.getinfo(name).file_size < 1048576,
                  "invalid released image manifest entry")
            released = json.loads(packed.read(name))
    except (zipfile.BadZipFile, KeyError, UnicodeError, ValueError) as exc:
        raise GlocError("Partial image evidence: invalid released archive manifest") from exc
    _need(isinstance(released, dict) and released.get("format") == "ckf-distribution-v2" and
          released.get("steam_build") == "25964281" and released.get("revision") == 1 and
          released.get("patch_id") == "25964281-rc1" and
          released.get("human_language_approval") is False and released.get("full_game_qa") is False,
          "wrong released image package identity")
    released_files = _index(released.get("files"), "path", "released package targets", count=6)
    _need(set(released_files) == set(UPDATE_25951469_TARGETS + _TARGETS), "wrong released package targets")
    guard_rows = _index(released.get("guards"), "path", "released package guards", count=2)
    _need({p: r.get("sha256") for p, r in guard_rows.items()} == UPDATE_25964281_GUARDS,
          "released package guard/build mismatch")
    previous = released.get("image_status")
    _need(isinstance(previous, dict) and previous.get("format") == "ckf-partial-image-summary-v1" and
          previous.get("source_build") == "25964281" and previous.get("evidence_source_build") == _BUILD and
          previous.get("complete") is False and previous.get("human_language_approval") is False and
          previous.get("full_game_qa") is False and previous.get("rendered_regions") == 67 and
          previous.get("ingame_observed_ids") == [] and
          _ids(previous.get("edited_ids"), "released selected IDs", count=16) == RELOCATION_IDS and
          _ids(previous.get("ingame_not_run_ids"), "released not-run IDs", count=16) == RELOCATION_IDS,
          "released image summary mismatch")
    partial = _ids(previous.get("partial_ids"), "released partial IDs", count=11)
    held = _ids(previous.get("held_ids"), "released held IDs", count=2)
    unrendered = _ids(previous.get("unrendered_ids"), "released unrendered IDs", count=14)
    retained = _ids(previous.get("retained_ids"), "released retained IDs", count=1)
    _need(partial <= RELOCATION_IDS and retained == {_WEAPON_ID} and
          len(RELOCATION_IDS | held | unrendered | retained) == 33 and
          RELOCATION_IDS | held | unrendered | retained == _CURRENT_IDS,
          "released image scope/partition mismatch")
    fingerprints = previous.get("evidence_sha256")
    _need(isinstance(fingerprints, dict) and all(isinstance(h, str) and _SHA.fullmatch(h)
          for h in fingerprints.values()), "invalid released evidence hashes")
    prior_stage = no_links(Path(prior_value)).resolve()
    _need(not prior_stage.is_relative_to(stage) and not stage.is_relative_to(prior_stage),
          "overlapping image relocation inputs")
    manifest_path = _file(prior_stage, "manifest.json")
    _need(file_hash(manifest_path) == fingerprints.get("stage_manifest") == receipt.get("prior_manifest_sha256"),
          "stale released prior image manifest")
    manifest = read_json(manifest_path)
    _need(isinstance(manifest, dict) and manifest.get("format") == "ckf-local-asset-overlay-v1" and
          manifest.get("local_only") is True and manifest.get("release_approved") is False,
          "unsafe released prior image stage")
    prior_files = _index(manifest.get("files"), "path", "released prior image bundles", count=2)
    _need(set(prior_files) == set(_TARGETS), "wrong released prior image targets")
    for path, item in prior_files.items():
        _need(item.get("before") == released_files[path].get("before") == get_source_profile(_BUILD)[path][1] and
              item.get("after") == released_files[path].get("after") and
              file_hash(_file(prior_stage, item.get("payload"))) == item["after"],
              "released prior image payload mismatch")
    paths, hashes = _hashes(prior_stage.parent, {
        "records": "image-records.jsonl", "edits": "image-edits.combined.v1.jsonl",
        "build_report": "available-build-report-v1.json", "machine_report": "available-readback-machine.v1.json",
        "selected_qa": "image-qa.selected.v1.jsonl", "visual_qa": "available-decoded-visual-qa.v1.json",
        "render_report": "render-report.combined.v1.json", "final_qa": "image-qa.available-final.v1.jsonl",
    })
    _need(all(h == fingerprints.get(k) for k, h in hashes.items()), "retained released image evidence hash mismatch")
    records = _index(read_jsonl(paths["records"]), "id", "released image records", count=33)
    edits = _index(read_jsonl(paths["edits"]), "image_id", "released image edits", count=16)
    report, machine = read_json(paths["build_report"]), read_json(paths["machine_report"])
    _need(set(records) == _CURRENT_IDS and set(edits) == RELOCATION_IDS and
          all(r.get("source_build") == _BUILD for r in records.values()) and
          isinstance(report, dict) and report.get("source_build") == _BUILD and report.get("complete") is False and
          report.get("physical_save_reload_verified") is True and
          isinstance(machine, dict) and machine.get("source_build") == _BUILD and
          machine.get("status") == "PASS" and machine.get("complete") is False and
          machine.get("build_report_sha256") == hashes["build_report"], "released static/machine evidence mismatch")
    results = _index(machine.get("results"), "id", "released machine results", count=16)
    _need(set(results) == RELOCATION_IDS, "released machine scope mismatch")
    return previous, records, results, prior_files


def _validate_relocated_partial_images(stage: Path, rows: dict, build: str) -> dict:
    """Bind reviewed historical streams to current locators, without new QA.

    The local Unity bridge supplies machine evidence; this stdlib gate checks
    its identity, preservation accounting and hashes against the original
    released archive's retained evidence and the exact current package inputs.
    """
    from .ckf_distribution import relocation_profile

    profile = relocation_profile(build)
    stage = no_links(Path(stage)).resolve()
    receipt_path = _file(stage, "migration-validation.json")
    receipt = read_json(receipt_path)
    _need(isinstance(receipt, dict) and receipt.get("format") == "ckf-image-relocation-v1" and
          receipt.get("source_build") == build and receipt.get("evidence_source_build") == _BUILD and
          receipt.get("current_ingame") == "NOT_RUN", "invalid image relocation receipt")
    previous, records, prior_results, prior_files = _released_relocation_evidence(stage, receipt)

    source_profile = get_source_profile(build)
    targets = tuple(source_profile)
    expected_originals = {**profile["originals"], **{p: h for p, (_, h) in source_profile.items()}}
    _need(set(rows) == set(profile["targets"] + targets), "wrong six-file relocation package targets")
    for path, before in expected_originals.items():
        _need(rows[path][0].get("before") == before, "relocation original target hash mismatch")
    manifest_path = _file(stage, "manifest.json")
    manifest = read_json(manifest_path)
    _need(isinstance(manifest, dict) and manifest.get("format") == "ckf-local-asset-overlay-v1" and
          manifest.get("local_only") is True and manifest.get("release_approved") is False,
          "unsafe relocated image stage")
    files = _index(manifest.get("files"), "path", "relocated image bundles", count=2)
    _need(set(files) == set(targets), "wrong relocated image targets")
    guards = _index(manifest.get("guards"), "path", "relocated image guards", count=2)
    _need({p: r.get("sha256") for p, r in guards.items()} == profile["guards"],
          "image relocation guard/build mismatch")
    for path, item in files.items():
        after = item.get("after")
        _need(item.get("before") == source_profile[path][1] and isinstance(after, str) and
              _SHA.fullmatch(after) and after != item["before"] and
              isinstance(item.get("payload"), str) and re.fullmatch(r"[0-9]+\.bin", item["payload"]) and
              rows[path][0].get("after") == after and
              file_hash(_file(stage, item["payload"])) == after,
              "relocated source/payload bytes differ")
    # Earlier relocation builds kept the entire banner bundle byte-identical.
    # 26198171 repacked that bundle too; its pinned original and the full
    # stream/pixel/non-target checks below bind the reviewed banner content.
    if build not in ("26198171", "26299178"):
        _need(files[targets[1]]["after"] == prior_files[_TARGETS[1]]["after"],
              "relocated banner must reuse reviewed payload bytes")

    machine_path = _file(stage.parent, "image-current-machine-check.json")
    _need(file_hash(machine_path) == receipt.get("current_machine_report_sha256"),
          "stale current image machine check")
    machine = read_json(machine_path)
    _need(isinstance(machine, dict) and machine.get("format") == "ckf-image-relocation-machine-v1" and
          machine.get("status") == "PASS" and machine.get("source_build") == build and
          machine.get("evidence_source_build") == _BUILD and machine.get("complete") is False and
          machine.get("current_ingame") == "NOT_RUN" and
          machine.get("historical_ingame_evidence_available") is False and
          machine.get("human_language_approval") is False and machine.get("full_game_qa") is False and
          machine.get("current_stage_manifest_sha256") == file_hash(manifest_path) and
          all(machine.get(k) == receipt[k] for k in ("prior_manifest_sha256", "prior_archive_sha256")) and
          all(machine.get(k) is True for k in ("non_target_objects_unchanged", "member_metadata_unchanged",
                  "nonselected_streams_unchanged", "stream_ranges_valid", "physical_save_reload_verified")),
          "current relocation preservation proof failed")
    counts = machine.get("counts")
    fields = ("total_objects", "unchanged_objects", "total_texture_streams",
              "selected_texture_streams", "unchanged_nonselected_texture_streams")
    _need(isinstance(counts, dict) and all(type(counts.get(k)) is int and counts[k] > 0 for k in fields) and
          counts["total_objects"] == counts["unchanged_objects"] >= 16 and
          counts["total_texture_streams"] <= counts["total_objects"] and
          counts["selected_texture_streams"] == 16 and
          counts["total_texture_streams"] == counts["unchanged_nonselected_texture_streams"] + 16 and
          counts == RELOCATION_COUNTS[build],
          "current relocation preservation counts mismatch")
    checked = _index(machine.get("results"), "id", "relocated image results", count=16)
    _need(set(checked) == set(previous["edited_ids"]), "relocated image scope mismatch")
    locators = set()
    for key, item in checked.items():
        record, old = records[key], prior_results[key]
        bundle = targets[1] if key == _BANNER_ID else targets[0]
        path_id = item.get("path_id")
        _need(item.get("source_build") == build and item.get("bundle_path") == bundle and
              item.get("bundle_sha256") == item.get("after") == files[bundle]["after"] and
              item.get("before") == files[bundle]["before"] and
              item.get("serialized_file") == source_profile[bundle][0] and
              type(path_id) is int and -(1 << 63) <= path_id < (1 << 63) and
              item.get("name") == record.get("name") and isinstance(item.get("name"), str) and
              all(type(item.get(k)) is int and item[k] == record.get(k) for k in ("width", "height", "format")),
              "relocated image locator/metadata mismatch")
        locator = (bundle, item["serialized_file"], path_id)
        _need(locator not in locators, "duplicate relocated image locator")
        locators.add(locator)
        _need(item.get("source_stream_sha256") == item.get("prior_source_stream_sha256") == record["stream"]["sha256"] and
              item.get("source_stream_exact_match") is True and
              item.get("source_pixels_exact_match") is True and item.get("edited_stream_exact_match") is True and
              all(isinstance(item.get(k), str) and _SHA.fullmatch(item[k]) for k in
                  ("source_decoded_pixels_sha256", "prior_source_decoded_pixels_sha256",
                   "edited_stream_sha256", "prior_edited_stream_sha256")) and
              item["source_decoded_pixels_sha256"] == item["prior_source_decoded_pixels_sha256"] and
              item["edited_stream_sha256"] == item["prior_edited_stream_sha256"] and
              item.get("decoded_pixels_sha256") == old["decoded_pixels_sha256"] and
              _ids(item.get("selected_region_ids"), "relocation selected regions", region=True) ==
              set(old["selected_region_ids"]) and
              item.get("outside_edit_pixels_or_nonselected_dxt_blocks_unchanged") is True and
              item.get("protected_pixels_unchanged") is True,
              "relocated image stream/pixel preservation failed")
        if key == _BANNER_ID:
            _need(item.get("alpha_unchanged") is True, "relocated banner alpha preservation failed")
    previous.update(source_build=build, evidence_source_build=_BUILD,
                    ingame_observed_ids=[], ingame_not_run_ids=list(previous["edited_ids"]),
                    historical_ingame_evidence_available=False)
    previous["evidence_sha256"] = {**previous["evidence_sha256"],
        "relocation_stage_manifest": file_hash(manifest_path), "relocation_receipt": file_hash(receipt_path),
        "prior_archive": RELOCATION_ARCHIVE_SHA256,
        "current_machine_report": file_hash(machine_path)}
    return previous
