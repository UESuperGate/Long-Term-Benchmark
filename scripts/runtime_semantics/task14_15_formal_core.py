#!/usr/bin/env python3
"""Shared fail-closed orchestration for Task14/15 formal agent scorers."""

from __future__ import annotations

from contextlib import contextmanager, ExitStack
import fcntl
import hashlib
import importlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Callable, Optional


ROOT = Path(__file__).resolve().parents[2]
BINARY_SUFFIXES = {".apk", ".hap", ".aab", ".apks", ".abc", ".dex", ".so", ".jar", ".class",
                   ".der", ".pem", ".key", ".csr", ".cer", ".crt", ".p12"}
HOST_RUNTIME_CASES = {
    "14_join_room_by_address": {"jr_state_002_update_trims_and_debounces"},
    "15_account_deactivation": {
        "ad_state_002_default_form_blocks_submit", "ad_state_003_password_enables_submit",
        "ad_state_004_erase_data_option", "ad_state_007_success_completes",
        "ad_state_010_close_dialog_resets_action",
    },
}
ARKTS_RUNTIME_POLES = {
    "14_join_room_by_address": {
        "jr_state_001_entry_opens_address_flow": "openharmony_api23_device_original_ui",
        "jr_state_002_update_trims_and_debounces": "host_transpiled_virtual_clock_production",
        "jr_state_003_invalid_after_continue": "openharmony_api23_device_original_ui",
        "jr_state_004_valid_address_resolves": "native_previewer_arkvm_production_module",
        "jr_state_005_found_then_continue_navigates": "native_previewer_arkvm_production_module",
        "jr_state_006_continue_waits_for_resolution": "native_previewer_arkvm_production_module",
        "jr_state_007_not_found_recovers": "openharmony_api23_device_original_ui",
        "jr_state_008_timeout_recovers": "native_previewer_arkvm_production_module",
        "jr_state_009_dismiss_closes_flow": "native_previewer_arkvm_production_module",
    },
    "15_account_deactivation": {
        "ad_state_001_capability_gates_entry": "openharmony_api23_device_https_arkui",
        "ad_state_002_default_form_blocks_submit": "host_transpiled_current_production_presenter",
        "ad_state_003_password_enables_submit": "host_transpiled_current_production_presenter",
        "ad_state_004_erase_data_option": "host_transpiled_current_production_presenter",
        "ad_state_005_first_submit_confirms": "openharmony_api23_device_https_arkui",
        "ad_state_006_confirm_sends_payload": "openharmony_api23_device_https_arkui",
        "ad_state_007_success_completes": "host_transpiled_current_production_presenter",
        "ad_state_008_failure_preserves_form": "openharmony_api23_device_https_arkui",
        "ad_state_009_retry_bypasses_confirmation": "openharmony_api23_device_https_arkui",
        "ad_state_010_close_dialog_resets_action": "host_transpiled_current_production_presenter",
    },
}


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tree_artifact_record(directory: Path) -> dict:
    digest = hashlib.sha256()
    count = 0
    total_bytes = 0
    if directory.exists():
        for path in sorted(item for item in directory.rglob("*") if item.is_file()):
            relative = path.relative_to(directory).as_posix().encode()
            file_digest = hashlib.sha256(path.read_bytes()).digest()
            size = path.stat().st_size
            digest.update(len(relative).to_bytes(8, "big"))
            digest.update(relative)
            digest.update(size.to_bytes(8, "big"))
            digest.update(file_digest)
            count += 1
            total_bytes += size
    return {"path": str(directory), "files": count, "bytes": total_bytes,
            "aggregateSha256": digest.hexdigest(), "retained": False}


def remaining_deadline(deadline: float, phase: str) -> float:
    value = deadline - time.monotonic()
    if value <= 0:
        raise TimeoutError(f"{phase} exceeded the formal scorer deadline")
    return value


def require_build_space() -> None:
    if shutil.disk_usage(ROOT).free < 8 * 1024**3:
        raise RuntimeError("storage_protection_environment: new runtime build requires at least 8 GiB free")


@contextmanager
def bounded_file_lock(path: Path, deadline: float, phase: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as lock:
        while True:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                time.sleep(min(0.25, remaining_deadline(deadline, phase)))
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def directory_digest(source: Path) -> str:
    digest = hashlib.sha256()
    excluded = {".git", ".gradle", ".hvigor", ".idea", "build", "node_modules", "oh_modules"}
    for path in sorted(source.rglob("*")):
        relative = path.relative_to(source)
        if not path.is_file() or any(part in excluded for part in relative.parts):
            continue
        name = relative.as_posix().encode()
        data = path.read_bytes()
        digest.update(len(name).to_bytes(8, "big"))
        digest.update(name)
        digest.update(len(data).to_bytes(8, "big"))
        digest.update(data)
    return digest.hexdigest()


def filesystem_closure(source: Path, seeds: list[str]) -> list[str]:
    records: dict[str, tuple[str, list[str], str]] = {}
    symbols: dict[str, set[str]] = {}
    packages: dict[str, dict[str, set[str]]] = {}
    for file in sorted(source.rglob("*.kt")):
        relative = file.relative_to(source).as_posix()
        if "/src/main/" not in relative:
            continue
        code = file.read_text(errors="replace")
        match = re.search(r"^package ([\w.]+)", code, re.M)
        if not match:
            continue
        package = match.group(1)
        imports = re.findall(r"^import ([\w.*]+)", code, re.M)
        clean = re.sub(r"/\*.*?\*/|//[^\n]*", "", code, flags=re.S)
        names = set(re.findall(
            r"^(?:(?:public|internal|private|open|sealed|data|enum|annotation|value|fun|abstract|inline) )*"
            r"(?:class|interface|object|typealias) (\w+)", clean, re.M))
        names.update(re.findall(
            r"^(?:(?:public|internal|private|suspend|inline|tailrec|operator|infix)\s+)*"
            r"fun (?:<[^\n]+?>\s+)?(?:[^\n(]+\.)?(\w+)\(", clean, re.M))
        names.update(re.findall(
            r"^(?:internal |private |public )?(?:const )?(?:val|var) (?:[^\n ]+\.)?(\w+)\b", clean, re.M))
        records[relative] = (package, imports, clean)
        package_symbols = packages.setdefault(package, {})
        for name in names:
            symbols.setdefault(f"{package}.{name}", set()).add(relative)
            package_symbols.setdefault(name, set()).add(relative)
    selected: set[str] = set()
    pending = list(seeds)
    while pending:
        path = pending.pop()
        if path in selected:
            continue
        if path not in records:
            raise ValueError(f"Production entrypoint absent in standalone candidate: {path}")
        selected.add(path)
        package, imports, clean = records[path]
        tokens = set(re.findall(r"\b\w+\b", clean))
        for name, paths in packages[package].items():
            if name in tokens:
                pending.extend(paths - selected)
        for imported in imports:
            if not imported.startswith("io.element.android.") or imported.startswith("io.element.android.wysiwyg."):
                continue
            lookup = imported
            while lookup and lookup not in symbols:
                lookup = lookup.rpartition(".")[0]
            if lookup:
                pending.extend(symbols[lookup] - selected)
    return sorted(selected)


def prepared_android_config(source: Path, config_path: Path, temporary: Path,
                            *, keys: Optional[list[str]] = None,
                            extra_sources: Optional[list[str]] = None) -> Path:
    config = load(config_path)
    if config.get("sourceClosure"):
        config["sources"] = filesystem_closure(source, config["entrypoints"])
        config["sourceClosure"] = False
    config["sources"] = sorted(set(config.get("sources", []) + config.pop("extraProductionSources", []) +
                                   list(extra_sources or [])))
    config["evaluatorSources"] = [
        str((config_path.parent / path).resolve()) for path in config.get("evaluatorSources", [])
    ]
    if keys is not None:
        config["keys"] = keys
    target = temporary / f"{config_path.parent.name}-{config_path.name}"
    write(target, config)
    return target


def unavailable_rows(contract: dict, reason: str) -> list[dict]:
    return [{
        "caseId": case["caseId"], "key": case["key"], "traceDigest": case["traceDigest"],
        "status": "not_scored", "reason": reason, "observed": {}, "checkpoints": [],
        "invariantChecks": [],
    } for case in contract["cases"]]


def _source_binding(report: dict) -> Optional[Path]:
    provenance = report.get("provenance", {})
    value = (provenance.get("candidateSource") or provenance.get("source") or
             report.get("target") or report.get("source"))
    return Path(value).resolve() if isinstance(value, str) else None


def _runtime_compile_passed(report: dict) -> bool:
    value = report.get("runtimeCompile", {})
    return value.get("passed") is True and value.get("status") == "passed"


def _contains(actual, expected) -> bool:
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(key in actual and _contains(actual[key], value)
                                                for key, value in expected.items())
    if isinstance(expected, list):
        return actual == expected
    return type(actual) is type(expected) and actual == expected


def validate_cleanup(report: dict) -> None:
    cleanup = report.get("diagnostics", {}).get("cleanup", {})
    if cleanup.get("temporaryBuildRemoved") is not True or cleanup.get("binariesRetained") is not False:
        raise ValueError("runtime evaluator did not prove temporary-build cleanup and binary exclusion")
    evidence = report.get("provenance", {}).get("retainedEvidence", {})
    for item in evidence.get("files", []):
        suffix = Path(item.get("path", "")).suffix.lower()
        if suffix in BINARY_SUFFIXES:
            raise ValueError(f"retained runtime evidence contains a binary: {item.get('path')}")


def validate_report(report: dict, *, task_id: str, platform: str, source: Path,
                    contract: dict, expected: Optional[str]) -> list[dict]:
    if report.get("taskId") != task_id or report.get("platform") != platform:
        raise ValueError("runtime report task/platform identity mismatch")
    if report.get("role") != "agent" or report.get("observationMode") != "runtime_state_transition":
        raise ValueError("runtime report is not a standalone agent state-transition result")
    if _source_binding(report) != source.resolve():
        raise ValueError("runtime report is not bound to the supplied standalone candidate")
    provenance = report.get("provenance", {})
    if provenance.get("candidateMode") != "standalone_directory" or provenance.get("archivedPatchApplied") is not False:
        raise ValueError("runtime report used a non-standalone or archived-patch candidate")
    if not _runtime_compile_passed(report):
        raise ValueError("evaluator packaging/runtime compile did not pass")
    diagnostics = report.get("diagnostics", {})
    if diagnostics.get("adapter") != "ready" or diagnostics.get("transport") not in {
            "host_runtime_completed", "transport_completed"}:
        raise ValueError("runtime adapter or transport is not ready")
    validate_cleanup(report)
    rows = report.get("semantic", {}).get("cases", [])
    expected_identity = [(case["caseId"], case["key"], case["traceDigest"]) for case in contract["cases"]]
    actual_identity = [(row.get("caseId"), row.get("key"), row.get("traceDigest")) for row in rows]
    if actual_identity != expected_identity:
        raise ValueError("runtime report does not contain the complete canonical case sequence")
    if any(row.get("status") not in {"pass", "fail"} for row in rows):
        raise ValueError("formal runtime report contains an unscored canonical case")
    entry_observation_ids = set()
    for row, spec in zip(rows, contract["cases"]):
        if row.get("entryFailureEvidence"):
            validate_entry_failure(row, report, entry_observation_ids, contract=contract)
            continue
        runtime = str(row.get("runtime", "")).lower()
        if "source_observer" in runtime:
            raise ValueError("source-observer evidence is not scoreable")
        if "host_transpiled" in runtime and row.get("caseId") not in HOST_RUNTIME_CASES.get(task_id, set()):
            raise ValueError("host production runtime is not an audited pole for this canonical case")
        if platform == "arkts":
            missing_entry = (runtime == "openharmony_api23_device_missing_entry" and
                             row.get("status") == "fail" and
                             row.get("failureKind") == "semantic_missing_feature_entry")
            exact_pole = ARKTS_RUNTIME_POLES.get(task_id, {}).get(row.get("caseId"))
            if not missing_entry and runtime != exact_pole:
                raise ValueError(f"wrong audited ArkTS runtime pole for {row.get('caseId')}: {runtime!r}")
        if len(row.get("checkpoints", [])) < 2:
            raise ValueError(f"runtime checkpoints are incomplete for {row.get('caseId')}")
        if not isinstance(row.get("invariantChecks"), list):
            raise ValueError(f"runtime invariant evidence is malformed for {row.get('caseId')}")
        checks = {item.get("invariant", item.get("description", item.get("text"))): item
                  for item in row.get("invariantChecks", [])}
        invariant_pass = lambda item: item.get("status") == "pass" or item.get("passed") is True
        invariant_fail = lambda item: item.get("status") == "fail" or item.get("passed") is False
        expected_match = _contains(row.get("observed"), spec.get("expected", {}))
        missing_invariants = [text for text in spec.get("invariants", []) if text not in checks]
        if missing_invariants:
            raise ValueError(f"canonical invariants are missing for {row.get('caseId')}")
        if row["status"] == "pass":
            if not expected_match or any(not invariant_pass(checks[text]) for text in spec.get("invariants", [])):
                raise ValueError(f"passing verdict lacks canonical state/invariant evidence: {row.get('caseId')}")
        elif expected_match and not any(invariant_fail(checks[text]) for text in spec.get("invariants", [])) and \
                not str(row.get("failureKind", "")).startswith("semantic_"):
            raise ValueError(f"failing verdict lacks a semantic mismatch: {row.get('caseId')}")
    if expected == "all_fail" and any(row["status"] != "fail" for row in rows):
        raise ValueError("dynamic base calibration is not all-fail")
    if expected == "all_pass" and any(row["status"] != "pass" for row in rows):
        raise ValueError("dynamic final calibration is not all-pass")
    return rows


def validate_smoke(report: dict, *, task_id: str, platform: str, source: Path) -> None:
    if report.get("taskId") != task_id or report.get("platform") != platform or report.get("role") != "agent":
        raise ValueError("candidate smoke identity mismatch")
    if _source_binding(report) != source.resolve() or not _runtime_compile_passed(report):
        raise ValueError("candidate smoke is not source-bound or did not compile")
    diagnostics = report.get("diagnostics", {})
    if diagnostics.get("adapter") != "ready" or diagnostics.get("transport") not in {
            "host_runtime_completed", "transport_completed"}:
        raise ValueError("candidate smoke adapter or transport is not ready")
    validate_cleanup(report)


def validate_public_report(report: dict, contract: dict) -> None:
    scripts = str(ROOT / "scripts")
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    from run_runtime_transition_matrix import validate_report as public_validate
    public_validate(report, contract)


def validate_entry_failure(row: dict, report: dict, used_observation_ids: set, contract=None):
    if report.get("platform") == "android":
        module = "task14_15_android_entry_evidence"
    elif report.get("platform") == "arkts":
        module = "task14_15_arkts_entry_evidence"
    else:
        raise ValueError("Task14/15 entry evidence has an unsupported platform")
    verify = importlib.import_module(f"{__package__}.{module}" if __package__ else module).validate_entry_failure
    return verify(row, report, used_observation_ids, contract=contract)


def attach_arkts_production_evidence(report: dict, source: Path, evidence: Path):
    from task14_15_android_entry_evidence import attach_production_evidence
    sources = {}

    def collect(value):
        if isinstance(value, dict):
            for key, child in value.items():
                if key in {"productionSources", "production", "sourceHashes", "sources"} and isinstance(child, list):
                    for item in child:
                        if not isinstance(item, dict) or not isinstance(item.get("path"), str) or "sha256" not in item:
                            continue
                        relative = Path(item["path"])
                        candidate = source / relative
                        if relative.is_absolute() or not candidate.is_file():
                            continue
                        if sha256(candidate) != item["sha256"]:
                            raise ValueError(f"ArkTS executed production hash differs: {relative}")
                        record = {"path": relative.as_posix(), "bytes": candidate.stat().st_size,
                                  "sha256": item["sha256"]}
                        sources[relative.as_posix()] = record
                collect(child)
        elif isinstance(value, list):
            for child in value:
                collect(child)

    for artifact in sorted(evidence.rglob("*.json")):
        try:
            collect(load(artifact))
        except json.JSONDecodeError:
            continue
    attach_production_evidence(report, {"executed": {"provenance": {
        "productionSources": [sources[key] for key in sorted(sources)]}}}, source, evidence)


def score(*, task_id: str, contract_path: Path, platform: str, source: Path,
          base_source: Path, final_source: Path, output: Path, compile_passed: bool | None,
          compile_command: str, evaluator: Callable[..., dict], timeout: float = 3600,
          monotonic: Callable[[], float] = time.monotonic, context_factory=None) -> dict:
    if platform not in {"android", "arkts"}:
        raise ValueError("platform must be android or arkts")
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or not 0 < timeout <= 3600:
        raise ValueError("formal Task14/15 scorer timeout must be finite and 0 < timeout <= 3600 seconds")
    started = monotonic()
    deadline = started + timeout
    contract = load(contract_path)
    candidate = source.resolve()
    base = base_source.resolve()
    final = final_source.resolve()
    compile_result = {
        "passed": compile_passed,
        "status": "passed" if compile_passed is True else "failed" if compile_passed is False else "not_provided",
        "scope": "standalone_candidate_application_build",
        "command": compile_command,
        "source": "parent_application_build",
    }
    runtime_compile = {"passed": None, "status": "not_run", "scope": "strict_evaluator_runtime_packaging"}
    diagnostics = {
        "timeoutSeconds": timeout, "budgetClock": "time.monotonic", "candidate": str(candidate),
        "baseCalibrationSource": str(base), "finalCalibrationSource": str(final), "phases": [],
    }

    def remaining(phase: str) -> float:
        value = deadline - monotonic()
        if value <= 0:
            raise TimeoutError(f"{task_id} formal scorer exhausted its single {timeout}-second deadline during {phase}")
        return value

    def fail(reason: str) -> dict:
        return {
            "schemaVersion": 2, "taskId": task_id, "platform": platform, "role": "agent",
            "target": str(candidate), "observationMode": "runtime_state_transition",
            "provenance": {"candidateSource": str(candidate), "candidateMode": "standalone_directory",
                           "archivedPatchApplied": False},
            "compile": compile_result, "runtimeCompile": runtime_compile,
            "semantic": {"total": len(contract["cases"]), "passed": 0, "failed": 0,
                         "notScored": len(contract["cases"]), "cases": unavailable_rows(contract, reason)},
            "publication": {"eligible": False, "reason": reason},
            "diagnostics": {**diagnostics, "adapter": "failed", "reason": reason,
                            "totalElapsedSeconds": monotonic() - started},
        }

    if compile_passed is not True:
        return fail("Standalone candidate application build did not pass")
    for label, path in (("candidate", candidate), ("base calibration", base), ("final calibration", final)):
        if not path.is_dir():
            return fail(f"{label} source directory is unavailable")

    scope = ExitStack()
    negative_source = None
    try:
        if context_factory is not None:
            lease = scope.enter_context(context_factory(deadline))
            diagnostics["deviceLease"] = {key: value for key, value in lease.items() if key != "token"}
        negative_source = Path(scope.enter_context(tempfile.TemporaryDirectory(
            prefix=f"ltb-{task_id}-base-copy-"))) / "candidate"
        _copy_project(base, negative_source)
        diagnostics["baseCopySanity"] = {
            "role": "agent", "source": str(negative_source),
            "sourceRootSha256": directory_digest(negative_source),
            "matchesBaseRootSha256": directory_digest(negative_source) == directory_digest(base),
            "temporaryTreeRemoved": False,
        }
        if not diagnostics["baseCopySanity"]["matchesBaseRootSha256"]:
            raise ValueError("Random-directory base copy differs from calibration base")
        phases = [
            ("base_calibration", base, False, "all_fail"),
            ("final_calibration", final, False, "all_pass"),
            ("base_copy_sanity", negative_source, False, "all_fail"),
            ("candidate_smoke", candidate, True, None),
            ("candidate_score", candidate, False, None),
        ]
        candidate_rows = None
        candidate_report = None
        scored_reports = []
        for phase, phase_source, smoke, expected in phases:
            phase_output = output.with_name(f"{output.stem}.{phase}.runtime.json")
            report = evaluator(platform=platform, source=phase_source, output=phase_output,
                               deadline=deadline, smoke=smoke)
            diagnostics["phases"].append({"name": phase, "source": str(phase_source),
                                           "remainingSeconds": remaining(phase)})
            runtime_compile = report.get("runtimeCompile", runtime_compile)
            if smoke:
                validate_smoke(report, task_id=task_id, platform=platform, source=phase_source)
            else:
                rows = validate_report(report, task_id=task_id, platform=platform, source=phase_source,
                                       contract=contract, expected=expected)
                scored_reports.append(report)
                diagnostics["phases"][-1]["semantic"] = {
                    "passed": sum(row["status"] == "pass" for row in rows),
                    "failed": sum(row["status"] == "fail" for row in rows), "notScored": 0}
                if phase == "candidate_score":
                    candidate_rows, candidate_report = rows, report
        if candidate_rows is None or candidate_report is None:
            raise ValueError("candidate score phase did not produce a report")
        for phase_report in scored_reports:
            validate_public_report(phase_report, contract)
        passed = sum(row["status"] == "pass" for row in candidate_rows)
        failed = len(candidate_rows) - passed
        return {
            **candidate_report,
            "compile": compile_result,
            "runtimeCompile": runtime_compile,
            "target": str(candidate),
            "semantic": {"total": len(candidate_rows), "passed": passed, "failed": failed,
                         "notScored": 0, "cases": candidate_rows},
            "publication": {"eligible": True,
                            "reason": "Dynamic calibration, candidate smoke, and complete runtime verdicts passed"},
            "diagnostics": {**candidate_report.get("diagnostics", {}), **diagnostics, "adapter": "ready",
                            "totalElapsedSeconds": monotonic() - started},
        }
    except (OSError, RuntimeError, ValueError, TimeoutError, subprocess.SubprocessError) as error:
        return fail(f"{type(error).__name__}: {error}")
    finally:
        if negative_source is not None:
            diagnostics.setdefault("baseCopySanity", {})["removedTemporaryTree"] = tree_artifact_record(negative_source.parent)
        scope.close()
        if negative_source is not None:
            diagnostics["baseCopySanity"]["temporaryTreeRemoved"] = not negative_source.parent.exists()


def retain_text_evidence(temporary: Path, destination: Path) -> dict:
    if destination.exists():
        raise FileExistsError(f"Refusing existing evidence directory: {destination}")
    destination.mkdir(parents=True)
    files = []
    for source in sorted(path for path in temporary.rglob("*") if path.is_file()):
        if source.suffix.lower() in BINARY_SUFFIXES:
            continue
        relative = source.relative_to(temporary)
        if any(part in {"build", ".gradle", ".hvigor", "node_modules", "oh_modules"} for part in relative.parts):
            continue
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        files.append({"path": relative.as_posix(), "bytes": target.stat().st_size, "sha256": sha256(target)})
    return {"path": str(destination), "files": files, "binariesRetained": False}


def remove_binary_artifacts(directory: Path) -> list[dict]:
    removed = []
    if not directory.exists():
        return removed
    for path in sorted(item for item in directory.rglob("*") if item.is_file()):
        if path.suffix.lower() not in BINARY_SUFFIXES:
            continue
        removed.append({"path": path.relative_to(directory).as_posix(), "bytes": path.stat().st_size,
                        "sha256": sha256(path)})
        path.unlink()
    for path in sorted((item for item in directory.rglob("*") if item.is_dir()), reverse=True):
        try:
            path.rmdir()
        except OSError:
            pass
    return removed


def _copy_project(source: Path, destination: Path) -> None:
    excluded = {"build", ".hvigor", "oh_modules", "node_modules", ".git"}
    shutil.copytree(source, destination, dirs_exist_ok=True,
                    ignore=lambda _directory, names: [name for name in names if name in excluded])


def build_arkts_application(*, source: Path, output: Path, deadline: float, label: str) -> dict:
    """Build one temporary application HAP and retain it only for the caller's runtime phase."""
    require_build_space()
    if output.exists():
        raise FileExistsError(f"Refusing existing ArkTS application build evidence: {output}")
    output.mkdir(parents=True)
    studio = Path("/Applications/DevEco-Studio.app/Contents")
    sdk = Path.home() / "Library/OpenHarmony/Sdk"
    production = []
    for path in sorted(item for item in (source / "entry/src/main").rglob("*") if item.is_file()):
        production.append({"path": path.relative_to(source).as_posix(), "bytes": path.stat().st_size,
                           "sha256": sha256(path)})
    report = {"schemaVersion": 1, "role": "agent", "source": str(source.resolve()),
              "label": label, "sources": production, "passed": False}
    work_path = None
    try:
        with tempfile.TemporaryDirectory(prefix=f"ltb-{label}-app-") as raw:
            work = Path(raw)
            work_path = work
            _copy_project(source, work)
            shutil.copytree(ROOT / "elementx_harmony_full/oh_modules", work / "oh_modules",
                            symlinks=True, dirs_exist_ok=True)
            (work / "node_modules/@ohos").mkdir(parents=True, exist_ok=True)
            for name in ("hvigor", "hvigor-ohos-plugin"):
                target = work / "node_modules/@ohos" / name
                if not target.exists():
                    target.symlink_to(studio / "tools/hvigor" / name)
            (work / "local.properties").write_text(f"sdk.dir={sdk}\nhwsdk.dir={studio / 'sdk'}\n")
            command = [str(studio / "tools/node/bin/node"),
                       str(studio / "tools/hvigor/hvigor/bin/hvigor.js"), "assembleHap", "--mode", "module",
                       "-p", "module=entry@default", "-p", "product=default", "-p", "buildMode=debug",
                       "--no-daemon", "--no-parallel"]
            environment = {**os.environ, "DEVECO_SDK_HOME": str(studio / "sdk"),
                           "OHOS_SDK_HOME": str(sdk), "NODE_PATH": str(work / "node_modules"),
                           "JAVA_HOME": str(studio / "jbr/Contents/Home"),
                           "PATH": f"{studio / 'jbr/Contents/Home/bin'}:{studio / 'tools/node/bin'}:"
                                   f"{studio / 'tools/ohpm/bin'}:{os.environ.get('PATH', '')}"}
            process = subprocess.run(command, cwd=work, env=environment, capture_output=True, text=True,
                                     timeout=remaining_deadline(deadline, f"{label} application build"), check=False)
            log = output / "application-build.log"
            log.write_text((process.stdout or "") + (process.stderr or ""), encoding="utf-8")
            report.update(command=command, exitCode=process.returncode,
                          log={"path": str(log), "bytes": log.stat().st_size, "sha256": sha256(log)})
            if process.returncode:
                raise RuntimeError(f"{label} application HAP build failed")
            haps = sorted((work / "entry/build").rglob("*.hap"))
            application = next((path for path in haps if "ohosTest" not in path.name and "test" not in path.name.lower()), None)
            if application is None:
                raise RuntimeError(f"{label} application HAP is missing")
            retained_hap = output / application.name
            shutil.copy2(application, retained_hap)
            report["hap"] = {"path": str(retained_hap), "bytes": retained_hap.stat().st_size,
                             "sha256": sha256(retained_hap)}
            report["removedBuildIntermediates"] = tree_artifact_record(work / "entry/build")
            report["copiedProductionUnchanged"] = all(
                (work / item["path"]).is_file() and sha256(work / item["path"]) == item["sha256"]
                for item in production)
            report["passed"] = report["copiedProductionUnchanged"]
    except Exception as error:
        report["error"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        report["temporaryProjectRemoved"] = work_path is not None and not work_path.exists()
        report["productionUnchanged"] = all(
            (source / item["path"]).is_file() and sha256(source / item["path"]) == item["sha256"]
            for item in production)
        write(output / "application-build.json", report)
    return report


def normalized_runtime_report(*, task_id: str, platform: str, source: Path, contract: dict,
                              rows: list[dict], runtime_passed: bool, transport: str,
                              retained: dict, temporary_removed: bool, reason: Optional[str] = None) -> dict:
    if not runtime_passed or transport not in {"host_runtime_completed", "transport_completed"}:
        rows = unavailable_rows(contract, reason or "strict runtime evaluator did not complete")
    return {
        "schemaVersion": 2, "taskId": task_id, "platform": platform, "role": "agent",
        "observationMode": "runtime_state_transition",
        "runtimeCompile": {"passed": runtime_passed, "status": "passed" if runtime_passed else "failed",
                           "scope": "strict evaluator packaging/runtime build; not full application compile"},
        "semantic": {"cases": rows},
        "provenance": {"candidateMode": "standalone_directory", "archivedPatchApplied": False,
                       "candidateSource": str(source.resolve()), "candidateRootSha256": directory_digest(source),
                       "retainedEvidence": retained},
        "diagnostics": {"adapter": "ready" if runtime_passed and not reason else "failed",
                        "transport": transport, "environmentFailureIsNotSemanticFailure": True,
                        "cleanup": {"temporaryBuildRemoved": temporary_removed, "binariesRetained": False,
                                    "binaryHashesRecordedBeforeRemoval": True,
                                    "removedBinaries": []},
                        "reason": reason},
    }


def arkts_runtime_evaluate(*, task_id: str, contract_path: Path, source: Path, output: Path,
                           deadline: float, smoke: bool, device_serial: Optional[str] = None,
                           selected_case_ids: Optional[set[str]] = None,
                           builder_environment: Optional[dict[str, str]] = None) -> dict:
    """Run the current native bundle evaluator against an arbitrary candidate.

    A temporary, hash-recorded derivation only injects the task id, native-UI mode,
    and reviewed contract override. It is removed with all HAP/build products after
    the shared device scorer has retained text/JSON evidence.
    """
    require_build_space()
    from task14_15_device_lease import score_device

    contract = load(contract_path)
    selected = dict(contract)
    if selected_case_ids is not None:
        selected["cases"] = [case for case in contract["cases"] if case["caseId"] in selected_case_ids]
        if len(selected["cases"]) != len(selected_case_ids):
            raise ValueError("Selected ArkTS device cases do not match the reviewed contract")
    elif smoke:
        selected["cases"] = contract["cases"][:1]
    temporary_path = None
    report = None
    with tempfile.TemporaryDirectory(prefix=f"ltb-{task_id}-formal-builder-") as raw:
        temporary = Path(raw)
        temporary_path = temporary
        selected_contract = temporary / "contract.json"
        write(selected_contract, selected)
        original = ROOT / "scripts/runtime_semantics/arkts_native_device.cjs"
        source_text = original.read_text(encoding="utf-8")
        source_text = source_text.replace(
            "'use strict';",
            "'use strict';\n" + "\n".join(
                f"process.env[{json.dumps(key)}] = {json.dumps(value)};"
                for key, value in (builder_environment or {}).items()) +
            "\nprocess.argv.splice(2, 0, '--task', " + json.dumps(task_id) +
            ", '--fixture', 'bundle', '--native-ui');",
            1,
        )
        source_text = source_text.replace(
            "const root = path.resolve(__dirname, '../..');",
            "const root = " + json.dumps(str(ROOT)) + ";",
            1,
        )
        for name in ("arkts_native_smoke.cjs", "arkts_native_bundle.cjs"):
            source_text = source_text.replace(
                f"require('./{name}')", f"require({json.dumps(str(original.parent / name))})")
        old = "{ device: true, caseId });"
        replacement = "{ device: true, caseId, contractOverride: " + json.dumps(str(selected_contract)) + " });"
        if source_text.count(old) != 1:
            raise RuntimeError("ArkTS native builder derivation point changed")
        source_text = source_text.replace(old, replacement)
        derived = temporary / "source-parameterized-native-builder.cjs"
        derived.write_text(source_text, encoding="utf-8")
        report = score_device(task_id=task_id, source=source, output=output, deadline=deadline,
                              contract_path=selected_contract, build_script=derived,
                              device_serial=device_serial)
        report.setdefault("provenance", {})["evaluatorDerivation"] = {
            "upstream": {"path": str(original), "sha256": sha256(original)},
            "derivedSha256": sha256(derived), "contract": {"path": str(contract_path),
                                                               "sha256": sha256(contract_path)},
            "changes": ["task selection", "native UI enablement", "reviewed contract override"],
        }
    assert report is not None and temporary_path is not None
    evidence = output.with_name(output.stem + "_evidence")
    retained_files = []
    removed_binaries = []
    if evidence.is_dir():
        old_manifest = evidence / "evidence-manifest.json"
        if old_manifest.is_file():
            old_manifest.unlink()
        for path in sorted(item for item in evidence.rglob("*") if item.is_file()):
            if path.suffix.lower() in BINARY_SUFFIXES:
                removed_binaries.append({"path": path.relative_to(evidence).as_posix(),
                                         "bytes": path.stat().st_size, "sha256": sha256(path)})
                path.unlink()
                continue
            retained_files.append({"path": path.relative_to(evidence).as_posix(),
                                   "bytes": path.stat().st_size, "sha256": sha256(path)})
        manifest_path = evidence / "formal-evidence-manifest.json"
        write(manifest_path, {"schemaVersion": 1, "taskId": task_id, "platform": "arkts",
                              "role": "agent", "binariesRetained": False,
                              "temporaryBuildRemoved": True, "files": retained_files})
        retained_files.append({"path": manifest_path.relative_to(evidence).as_posix(),
                               "bytes": manifest_path.stat().st_size, "sha256": sha256(manifest_path)})
    report["provenance"]["retainedEvidence"] = {
        "path": str(evidence), "files": retained_files, "binariesRetained": False,
    }
    report["provenance"]["candidateMode"] = "standalone_directory"
    report["provenance"]["archivedPatchApplied"] = False
    report["provenance"]["candidateSource"] = str(source.resolve())
    report.setdefault("diagnostics", {})["cleanup"] = {
        "temporaryBuildRemoved": not temporary_path.exists(), "binariesRetained": False,
        "binaryHashesRecordedBeforeRemoval": True, "removedBinaries": removed_binaries,
    }
    report["diagnostics"]["adapter"] = (
        "ready" if report.get("runtimeCompile", {}).get("passed") is True and
        report["diagnostics"].get("transport") == "transport_completed" else "failed")
    write(output, report)
    return report
