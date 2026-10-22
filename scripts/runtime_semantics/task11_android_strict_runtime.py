#!/usr/bin/env python3
"""Source-parameterized strict Android runtime scorer for Task11."""

from __future__ import annotations

import argparse
import copy
import fcntl
import hashlib
import json
from pathlib import Path
import importlib.util
import os
import shutil
import sys
import time
import traceback


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))

import android_robolectric
import android_runner
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


TASK = "11_room_upgrade_navigation"
CONTRACT = ROOT / "benchmark_tasks" / TASK / "transitions.json"
TASK_ROOT = ROOT / "state_tests/runtime/android" / TASK
BUILD_LOCK = ROOT / "state_tests/runtime/android/.build.lock"
NATIVE_ROOT = TASK_ROOT / "messages/.native"
from task11_android_entry import probe as probe_entry
from task11_android_resource_audit import record_slice_resources


def _run_owned(script: Path, arguments: list[str], patches: dict | None = None) -> None:
    prepare = android_robolectric.prepare
    resources = android_robolectric.compile_resources
    try:
        with record_slice_resources():
            invoke_main(script, arguments, patches=patches)
    finally:
        android_robolectric.prepare = prepare
        android_robolectric.compile_resources = resources


def _case(report: dict, key: str) -> dict:
    rows = report.get("semantic", {}).get("cases", report.get("observations", []))
    row = next((item for item in rows if item.get("key") == key), None)
    if row is None:
        raise RuntimeError(f"Task11 runtime slice omitted {key}")
    return copy.deepcopy(row)


def _canonical_runtime_row(raw: dict, spec: dict, role: str) -> dict:
    if raw.get("status") not in {"pass", "fail"}:
        raise RuntimeError(f"Task11 runtime transition has no semantic verdict: {spec['key']}")
    if len(raw.get("checkpoints", [])) < 2:
        raise RuntimeError(f"Task11 runtime transition lacks before/after evidence: {spec['key']}")
    row = canonical_row(raw, spec, role=role)
    validate_rows([row], {"cases": [spec]})
    return row


def _run_rendered_banner(script: Path, arguments: list[str], output: Path) -> None:
    """Retain the exact banner row while loaded navigation owns case006."""
    try:
        _run_owned(script, arguments)
    except RuntimeError as error:
        if str(error) != f"{script.name} returned 1" or not output.is_file():
            raise
        raw = json.loads(output.read_text(encoding="utf-8"))
        banner = _case(raw, "predecessor_banner")
        if raw.get("runtimeCompile", {}).get("status") != "passed":
            raise RuntimeError("Task11 rendered banner failed before the expected navigation-boundary NS")
        spec = next(item for item in json.loads(CONTRACT.read_text())["cases"]
                    if item["key"] == "predecessor_banner")
        _canonical_runtime_row(banner, spec, "agent")


def _prepare_native_dependencies() -> dict:
    script = TASK_ROOT / "messages/prepare_native.py"
    spec = importlib.util.spec_from_file_location("_ltb_task11_prepare_native", script)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load Task11 native dependency builder")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with Path("/tmp/long-term-benchmark-android-full-build.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        library = NATIVE_ROOT / "target/debug/libuniffi_wysiwyg_composer.dylib"
        if not library.exists() and shutil.disk_usage(ROOT).free < 8 * 1024**3:
            raise RuntimeError("Environment unavailable: less than 8 GiB free; native runtime preparation was not started")
        settings = {"CARGO_PROFILE_DEV_DEBUG": "0", "CARGO_INCREMENTAL": "0", "CARGO_BUILD_JOBS": "2"}
        previous = {key: os.environ.get(key) for key in settings}
        try:
            os.environ.update(settings)
            result = module.prepare()
            return {**result, "preparationEnvironment": settings,
                    "environmentScope": "process environment for preparation; a verified existing library may use earlier build flags"}
        finally:
            for key, value in previous.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value


def _select_runtime_dependency() -> dict:
    manifest = NATIVE_ROOT / "provenance.json"
    if manifest.is_file():
        previous = json.loads(manifest.read_text())
        items = [previous.get(key, {}) for key in ("library", "log", "cargoLock")]
        if (previous.get("commit") == "85035e2651fa9f41946455b391bb71950aeb7dc2" and all(
                item.get("path") and Path(item["path"]).is_file() and
                hashlib.sha256(Path(item["path"]).read_bytes()).hexdigest() == item.get("sha256") for item in items)):
            magic = Path(items[0]["path"]).read_bytes()[:4]
            if magic in {b"\xcf\xfa\xed\xfe", b"\xfe\xed\xfa\xcf", b"\xca\xfe\xba\xbe"}:
                return {**previous, "mode": "verified_existing_host_native_artifact", "rustBuildStarted": False}
    from task11_plaintext_sdk import SDK_SOURCE
    return {"mode": "upstream_sdk_plain_text_switch", "sdk": "io.element.android:wysiwyg:2.38.3",
            "sdkFixture": record(SDK_SOURCE), "rustBuildStarted": False,
            "nativeRustExecuted": False, "navigationReplaced": False,
            "reason": "No matching hash-verified Mach-O artifact; use SDK-owned plain-text rendering switch, reject links/mentions."}


def _cleanup_native_target(native_root: Path, manifest: Path | None = None) -> dict:
    target = native_root / "target"
    hashes = [record(path) for path in sorted(target.rglob("*")) if path.is_file()]
    if manifest:
        write_json(manifest, {"target": str(target), "binaryHashes": hashes,
                              "stage": "hash_recorded_before_delete"})
    if target.exists():
        shutil.rmtree(target)
    return {"performed": True, "target": str(target), "binaryHashes": hashes,
            "targetRemoved": not target.exists(), "binariesRetained": target.exists()}


def execute(source: Path, role: str, output: Path, artifact_root: Path, timeout: float) -> dict:
    started = time.monotonic()
    deadline = started + timeout
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    specs = {item["key"]: item for item in contract["cases"]}
    if contract.get("taskId") != TASK or len(specs) != 6:
        raise RuntimeError("Task11 canonical contract identity/count changed")
    artifact_root.mkdir(parents=True, exist_ok=True)
    raw_records = []
    native_cleanup = {"performed": False, "targetRemoved": True, "binaryHashes": []}
    native_preparation_attempted = False

    def remaining() -> float:
        budget = deadline - time.monotonic()
        if budget <= 0:
            raise TimeoutError("Task11 Android strict runner exhausted its unified deadline")
        return budget

    try:
        with bound_git_snapshot(source, artifact_root / "work") as (control, snapshot), \
                patched_candidate(control, source):
            entry_path = artifact_root / "entry-capability.json"
            entry_capability = probe_entry(TASK, control, role, entry_path, remaining())
            raw_records.append(record(entry_path))
            native_dependency = _select_runtime_dependency()
            sdk_arguments = ["--sdk-plain-text"] if native_dependency["mode"] == "upstream_sdk_plain_text_switch" else []
            if not entry_capability["fullFeatureEntry"]:
                raw_dir = artifact_root / "base-prefix"
                patches = {"SOURCE": control, "BASE_COMMIT": snapshot["snapshotCommit"],
                           "BASE_TREE": snapshot["snapshotTree"]}
                _run_owned(TASK_ROOT / "base_prefix_v2/run.py", [
                    "--output-dir", str(raw_dir), "--timeout", str(remaining()), "--role", role,
                    *sdk_arguments], patches=patches)
                raw_path = raw_dir / "android_11_room_upgrade_navigation_base_prefix_v2.json"
                raw = json.loads(raw_path.read_text())
                raw_records.append(record(raw_path))
                if raw.get("runtimeCompile", {}).get("status") != "passed":
                    raise RuntimeError("Task11 base runtime slice compilation failed")
                rows = [base_entry_failure(_case(raw, spec["key"]), spec, role=role)
                        for spec in contract["cases"]]
                components = [{"name": "six_isolated_common_state_positive_controls", "status": "passed"}]
            else:
                messages_path = artifact_root / "messages.json"
                _run_owned(TASK_ROOT / "messages/run.py", [
                    "--source", str(control), "--output", str(messages_path),
                    "--timeout", str(remaining()), *sdk_arguments])
                messages = json.loads(messages_path.read_text())
                raw_records.append(record(messages_path))

                roomlist_path = artifact_root / "roomlist.json"
                _run_owned(TASK_ROOT / "roomlist/run.py", [
                    "--role", role, "--source", str(control), "--output", str(roomlist_path),
                    "--timeout", str(remaining())])
                roomlist = json.loads(roomlist_path.read_text())
                raw_records.append(record(roomlist_path))

                primary_path = artifact_root / "mapping.json"
                with BUILD_LOCK.open("a") as lock:
                    fcntl.flock(lock, fcntl.LOCK_EX)
                    mapping = android_runner.run(TASK, role, control, primary_path, remaining())
                raw_records.append(record(primary_path))

                rendered_path = artifact_root / "beginning.json"
                _run_rendered_banner(TASK_ROOT / "rendered/run.py", [
                    "--role", role, "--source", str(control), "--output", str(rendered_path),
                    "--timeout", str(remaining())], rendered_path)
                rendered = json.loads(rendered_path.read_text())
                raw_records.append(record(rendered_path))

                navigation_path = artifact_root / "navigation.json"
                _run_owned(TASK_ROOT / "navigation/run_loaded.py", [
                    "--source", str(control), "--output", str(navigation_path),
                    "--timeout", str(remaining()), *sdk_arguments])
                navigation = json.loads(navigation_path.read_text())
                raw_records.append(record(navigation_path))

                reports = [messages, roomlist, mapping, rendered, navigation]
                for name, report in zip(("messages", "roomlist", "mapping", "beginning", "navigation"), reports):
                    if report.get("runtimeCompile", {}).get("status") != "passed":
                        raise RuntimeError(f"Task11 {name} runtime compilation failed")
                selected = {
                    "tombstone_is_read_only": _case(messages, "tombstone_is_read_only"),
                    "open_successor": _case(navigation, "open_successor"),
                    "room_list_tombstone_preview": _case(roomlist, "room_list_tombstone_preview"),
                    "map_predecessor_metadata": _case(mapping, "map_predecessor_metadata"),
                    "predecessor_banner": _case(rendered, "predecessor_banner"),
                    "open_predecessor": _case(navigation, "open_predecessor"),
                }
                rows = []
                for spec in contract["cases"]:
                    raw = selected[spec["key"]]
                    rows.append(_canonical_runtime_row(raw, spec, role))
                components = [
                    {"name": "full_messages_view_tombstone", "status": "passed"},
                    {"name": "room_summary_rendering", "status": "passed"},
                    {"name": "sdk_predecessor_mapping", "status": "passed"},
                    {"name": "room_beginning_rendering", "status": "passed"},
                    {"name": "loaded_appyx_successor_and_predecessor_navigation", "status": "passed"},
                ]
            snapshot_control = control
    finally:
        if native_preparation_attempted:
            native_cleanup = _cleanup_native_target(NATIVE_ROOT, artifact_root / "native-cleanup.json")
            write_json(artifact_root / "native-cleanup.json", native_cleanup)
    snapshot_removed = not snapshot_control.exists()

    validate_rows(rows, contract)
    cleanup = cleanup_artifacts(artifact_root)
    cleanup["task11NativeBuild"] = native_cleanup
    cleanup["temporaryArtifactRootRemoved"] = snapshot_removed
    if (cleanup["binaryArtifactsRetained"] or not cleanup["temporaryBuildRemoved"] or not snapshot_removed or
            not native_cleanup["targetRemoved"]):
        raise RuntimeError("Task11 strict runner cleanup was incomplete")
    runtime_compile = {"passed": True, "status": "passed",
                       "scope": "task11_production_runtime_slices_and_evaluator_adapters",
                       "components": components}
    report = strict_report(task_id=TASK, role=role, source=source, rows=rows,
                           runtime_compile=runtime_compile, cleanup=cleanup,
                           provenance={"contract": record(CONTRACT), "sourceSnapshot": snapshot,
                                       "entryCapability": entry_capability,
                                       "nativeDependency": native_dependency,
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
        raise ValueError("Task11 strict timeout must be in (0, 3600]")
    try:
        with wall_deadline(args.timeout):
            with Path("/tmp/ltb-task11-android-runtime.lock").open("a") as lease:
                fcntl.flock(lease, fcntl.LOCK_EX)
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
