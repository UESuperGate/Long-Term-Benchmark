#!/usr/bin/env python3
"""Source-parameterized strict Android runtime scorer for Task10."""

from __future__ import annotations

import argparse
import copy
import fcntl
import json
from pathlib import Path
import sys
import time
import traceback


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))

import android_robolectric
import android_runner
from tasks10_11_android_entry import probe as probe_entry
from task10_11_android_strict_common import (
    base_entry_failure,
    bound_git_snapshot,
    canonical_row,
    cleanup_artifacts,
    invoke_main,
    patched_candidate,
    record,
    strict_report,
    validate_rows,
    wall_deadline,
    write_json,
)


TASK = "10_media_upload_quality"
CONTRACT = ROOT / "benchmark_tasks" / TASK / "transitions.json"
TASK_ROOT = ROOT / "state_tests/runtime/android" / TASK
BUILD_LOCK = ROOT / "state_tests/runtime/android/.build.lock"


def _value(args: list[str], flag: str) -> str:
    index = args.index(flag) if flag in args else -1
    if index < 0 or index + 1 == len(args) or args[index + 1].startswith("--"):
        raise ValueError(f"{flag} is required")
    return args[index + 1]


def _run_owned(script: Path, arguments: list[str]) -> None:
    prepare = android_robolectric.prepare
    resources = android_robolectric.compile_resources
    try:
        invoke_main(script, arguments)
    finally:
        android_robolectric.prepare = prepare
        android_robolectric.compile_resources = resources


def _run_lifetime(script: Path, arguments: list[str], output: Path) -> None:
    """Accept only the probe's obsolete post-run contract-key lookup failure."""
    try:
        _run_owned(script, arguments)
    except StopIteration:
        if not output.is_file():
            raise
        raw = json.loads(output.read_text(encoding="utf-8"))
        observation = next(iter(raw.get("observations", [])), None)
        checkpoints = {item.get("name") for item in (observation or {}).get("checkpoints", [])}
        required = {"before_real_send", "actual_sdk_request", "dismissed_before_sdk_failure",
                    "actual_production_cleanup", "after_sdk_failure"}
        if (raw.get("runtimeCompile", {}).get("status") != "passed" or
                (observation or {}).get("status") != "pass" or not required <= checkpoints):
            raise RuntimeError("Task10 lifetime probe failed before its obsolete contract-key lookup")


def _run_preview(script: Path, arguments: list[str], output: Path) -> None:
    """Run the exact preview presenter slice despite its stale diagnostic key."""
    try:
        _run_owned(script, arguments)
    except StopIteration:
        if not output.is_file():
            raise
        raw = json.loads(output.read_text(encoding="utf-8"))
        image = next((item for item in raw.get("observations", [])
                      if item.get("key") == "image_optimization"), None)
        if (raw.get("runtimeCompile", {}).get("status") != "passed" or
                (image or {}).get("status") != "pass" or len(image.get("checkpoints", [])) < 2):
            raise RuntimeError("Task10 preview slice failed before its obsolete diagnostic-key lookup")


def _case(report: dict, key: str) -> dict:
    rows = report.get("semantic", {}).get("cases", report.get("observations", []))
    row = next((item for item in rows if item.get("key") == key), None)
    if row is None:
        raise RuntimeError(f"Task10 runtime slice omitted {key}")
    return copy.deepcopy(row)


def _case009(report: dict, spec: dict) -> dict:
    raw = next(iter(report.get("observations", [])), None)
    if raw is None or raw.get("status") != "pass":
        raise RuntimeError("Task10 case009 production lifetime transition did not pass")
    states = {item.get("name"): item.get("state", {}) for item in raw.get("checkpoints", [])}
    required = {"before_real_send", "actual_sdk_request", "dismissed_before_sdk_failure",
                "actual_production_cleanup", "after_sdk_failure"}
    if not required <= states.keys():
        raise RuntimeError("Task10 case009 lacks exact production lifetime checkpoints")
    before, request = states["before_real_send"], states["actual_sdk_request"]
    dismissed, cleanup, after = (states["dismissed_before_sdk_failure"],
                                 states["actual_production_cleanup"], states["after_sdk_failure"])
    observed = {
        "previewVisible": after.get("activeTarget") == "preview",
        "sendControlsVisible": after.get("sendControls", 0) > 0,
        "preparedMediaExists": after.get("preparedFileExists"),
        "caption": request.get("caption"),
        "presetUsed": str(before.get("preset", "")).lower(),
        "attempts": after.get("attempts"),
    }
    invariant = (request.get("attempts") == 1 and request.get("exists") is True and
                 dismissed.get("activeTarget") == "outside" and dismissed.get("sendControls") == 0 and
                 str(cleanup.get("owner", "")).endswith("AndroidMediaPreProcessor") and
                 cleanup.get("beforeExists") is True and cleanup.get("afterExists") is False and
                 cleanup.get("calls") == 1 and after.get("retryInjected") is False)
    return canonical_row({
        "status": "pass" if invariant else "fail", "observed": observed,
        "checkpoints": raw["checkpoints"],
        "invariantChecks": [{"description": spec["invariants"][0], "passed": invariant,
                             "evidence": {"request": request, "dismissed": dismissed,
                                          "cleanup": cleanup, "after": after}}],
        "observationLevel": "robolectric_original_node_ui_production_presenter_and_filesystem_lifetime",
    }, spec, role="runtime")


def execute(source: Path, role: str, output: Path, artifact_root: Path, timeout: float) -> dict:
    started = time.monotonic()
    deadline = started + timeout
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    specs = {item["key"]: item for item in contract["cases"]}
    if contract.get("taskId") != TASK or len(specs) != 9:
        raise RuntimeError("Task10 canonical contract identity/count changed")
    artifact_root.mkdir(parents=True, exist_ok=True)
    raw_records = []

    def remaining() -> float:
        budget = deadline - time.monotonic()
        if budget <= 0:
            raise TimeoutError("Task10 Android strict runner exhausted its unified deadline")
        return budget

    with bound_git_snapshot(source, artifact_root / "work") as (control, snapshot):
        with patched_candidate(control, source):
            entry_path = artifact_root / "entry-capability.json"
            entry_capability = probe_entry(TASK, control, role, entry_path, remaining())
            raw_records.append(record(entry_path))
            if not entry_capability["fullFeatureEntry"]:
                raw_path = artifact_root / "base-runtime.json"
                _run_owned(TASK_ROOT / "revision4/run_base.py", [
                    "--source", str(control), "--timeout", str(remaining()), "--output", str(raw_path)])
                raw = json.loads(raw_path.read_text())
                raw_records.append(record(raw_path))
                if raw.get("runtimeCompile", {}).get("status") != "passed":
                    raise RuntimeError("Task10 base runtime slice compilation failed")
                rows = [base_entry_failure(_case(raw, spec["key"]), spec, role=role)
                        for spec in contract["cases"]]
                runtime_components = [{"name": "base_common_preview_and_send_positive_control", "status": "passed"}]
            else:
                primary_path = artifact_root / "primary.json"
                with BUILD_LOCK.open("a") as lock:
                    fcntl.flock(lock, fcntl.LOCK_EX)
                    primary = android_runner.run(TASK, role, control, primary_path, remaining())
                raw_records.append(record(primary_path))
                if primary.get("runtimeCompile", {}).get("status") != "passed":
                    raise RuntimeError("Task10 primary production runtime compilation failed")

                rendered_path = artifact_root / "rendered.json"
                _run_owned(TASK_ROOT / "rendered/run.py", [
                    "--role", role, "--source", str(control), "--timeout", str(remaining()),
                    "--output", str(rendered_path)])
                rendered = json.loads(rendered_path.read_text())
                raw_records.append(record(rendered_path))
                if rendered.get("runtimeCompile", {}).get("status") != "passed":
                    raise RuntimeError("Task10 rendered runtime compilation failed")

                preview_path = artifact_root / "preview.json"
                _run_preview(TASK_ROOT / "preview/run.py", [
                    "--role", role, "--source", str(control), "--timeout", str(remaining()),
                    "--output", str(preview_path)], preview_path)
                preview = json.loads(preview_path.read_text())
                raw_records.append(record(preview_path))
                if preview.get("runtimeCompile", {}).get("status") != "passed":
                    raise RuntimeError("Task10 preview runtime compilation failed")

                modal_path = artifact_root / "modal.json"
                _run_owned(TASK_ROOT / "modal/run.py", [
                    "--source", str(control), "--timeout", str(remaining()), "--output", str(modal_path)])
                modal = json.loads(modal_path.read_text())
                raw_records.append(record(modal_path))
                if modal.get("runtimeCompile", {}).get("status") != "passed":
                    raise RuntimeError("Task10 modal runtime compilation failed")

                lifetime_path = artifact_root / "lifetime.json"
                _run_lifetime(TASK_ROOT / "lifetime/run.py", [
                    "--source", str(control), "--timeout", str(remaining()), "--output", str(lifetime_path)],
                    lifetime_path)
                lifetime = json.loads(lifetime_path.read_text())
                raw_records.append(record(lifetime_path))
                if lifetime.get("runtimeCompile", {}).get("status") != "passed":
                    raise RuntimeError("Task10 lifetime runtime compilation failed")

                selected = {
                    "async_loading": _case(rendered, "async_loading"),
                    "image_optimization": _case(preview, "image_optimization"),
                    **{key: _case(primary, key) for key in (
                        "limit_fallback", "estimate_video_presets",
                        "choose_best_preset", "dismiss_preserves_selection", "reject_oversized_preset")},
                    "block_when_all_oversized": copy.deepcopy(modal.get("legacyCanonical", {})),
                }
                rows = []
                for spec in contract["cases"]:
                    if spec["key"] == "background_failure_cleanup":
                        row = _case009(lifetime, spec)
                        row["role"] = role
                    else:
                        raw = selected[spec["key"]]
                        if raw.get("status") != "pass":
                            raise RuntimeError(f"Task10 exact runtime transition did not pass: {spec['key']}")
                        row = canonical_row(raw, spec, role=role)
                    rows.append(row)
                runtime_components = [
                    {"name": "presenter_state_machine_cases_002_007", "status": "passed"},
                    {"name": "rendered_compose_case_001", "status": "passed"},
                    {"name": "production_preview_presenter_case_003", "status": "passed"},
                    {"name": "global_modal_input_case_008", "status": "passed"},
                    {"name": "node_and_filesystem_lifetime_case_009", "status": "passed"},
                ]
        snapshot_control = control
    snapshot_removed = not snapshot_control.exists()
    validate_rows(rows, contract)
    cleanup = cleanup_artifacts(artifact_root)
    cleanup["temporaryArtifactRootRemoved"] = snapshot_removed
    if cleanup["binaryArtifactsRetained"] or not cleanup["temporaryBuildRemoved"] or not snapshot_removed:
        raise RuntimeError("Task10 strict runner cleanup was incomplete")
    runtime_compile = {"passed": True, "status": "passed",
                       "scope": "task10_production_runtime_slices_and_evaluator_adapters",
                       "components": runtime_components}
    report = strict_report(task_id=TASK, role=role, source=source, rows=rows,
                           runtime_compile=runtime_compile, cleanup=cleanup,
                           provenance={"contract": record(CONTRACT), "sourceSnapshot": snapshot,
                                       "entryCapability": entry_capability,
                                       "runtimeReports": raw_records, "runner": record(Path(__file__)),
                                       "unifiedDeadlineSeconds": timeout,
                                       "elapsedSeconds": round(time.monotonic() - started, 3)})
    write_json(output, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--role", choices=["base", "final", "agent"], required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--timeout", type=float, default=3600)
    parser.add_argument("--platform", choices=["android"], required=True)
    args = parser.parse_args()
    if args.timeout <= 0 or args.timeout > 3600:
        raise ValueError("Task10 strict timeout must be in (0, 3600]")
    try:
        with wall_deadline(args.timeout):
            report = execute(args.source.resolve(), args.role, args.output.resolve(),
                             args.artifact_root.resolve(), args.timeout)
        print(json.dumps({"output": str(args.output.resolve()), "semantic": {
            key: report["semantic"][key] for key in ("total", "passed", "failed", "notScored")}}))
        return 0
    except Exception as error:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        failure = {"taskId": TASK, "platform": "android", "role": args.role,
                   "target": str(args.source.resolve()), "status": "failed_closed",
                   "error": f"{type(error).__name__}: {error}", "traceback": traceback.format_exc()}
        write_json(args.output.resolve(), failure)
        print(failure["error"], file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
