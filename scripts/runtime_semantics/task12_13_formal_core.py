#!/usr/bin/env python3
"""Fail-closed orchestration shared only by Task12 and Task13 scorers.

The caller supplies a task-owned exact runtime evaluator. Historical calibration
is used only as an audited anchor; base, final, and the supplied candidate are
always executed again under one absolute monotonic deadline.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import shutil
import time
from typing import Callable, Mapping


ROOT = Path(__file__).resolve().parents[2]
TRANSIENT_DIRECTORIES = {"build", ".gradle", ".hvigor"}
BINARY_SUFFIXES = {".apk", ".hap", ".aab", ".apks"}
INVENTORY_EXCLUDES = TRANSIENT_DIRECTORIES | {".git", "node_modules", "oh_modules"}


@dataclass(frozen=True)
class TaskSpec:
    task_id: str
    case_count: int
    contract: Path
    calibration_evidence: Mapping[str, Mapping[str, Path]]
    calibrator_files: Mapping[str, tuple[Path, ...]]
    audited_contract: Path | None = None
    expected_contract_sha256: str | None = None


RuntimeEvaluator = Callable[..., dict]
ApplicationCompiler = Callable[..., dict]


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def file_record(path: Path) -> dict:
    path = path.resolve()
    return {"path": str(path), "bytes": path.stat().st_size, "sha256": sha256(path)}


def source_inventory(source: Path) -> dict:
    source = source.resolve()
    if not source.is_dir():
        raise ValueError(f"Source directory unavailable: {source}")
    records = []
    for path in sorted(source.rglob("*")):
        relative = path.relative_to(source)
        if any(part in INVENTORY_EXCLUDES for part in relative.parts):
            continue
        if path.is_symlink():
            raise ValueError(f"Candidate symlink unsupported: {relative}")
        if path.is_file() and path.suffix.lower() not in BINARY_SUFFIXES:
            records.append({"path": relative.as_posix(), "bytes": path.stat().st_size,
                            "sha256": sha256(path)})
    encoded = json.dumps(records, sort_keys=True, separators=(",", ":")).encode()
    return {"source": str(source), "fileCount": len(records),
            "sha256": hashlib.sha256(encoded).hexdigest(), "files": records}


def _remove_tree(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)


def cleanup_artifacts(*roots: Path) -> dict:
    """Hash evaluator/application binaries, then remove only regenerable output."""
    binary_hashes = []
    removed_directories = []
    intermediate_hashes = []
    retained_audit = []
    audit_root = roots[0].resolve() / "retained-audit" if roots else None
    seen = set()
    for raw_root in roots:
        root = raw_root.resolve()
        if root in seen or not root.exists():
            continue
        seen.add(root)
        for path in sorted(root.rglob("*")):
            if path.is_file() and path.suffix.lower() in BINARY_SUFFIXES:
                record = file_record(path)
                record["root"] = str(root)
                record["relativePath"] = path.relative_to(root).as_posix()
                binary_hashes.append(record)
                path.unlink()
        directories = sorted(
            (path for path in root.rglob("*") if path.is_dir() and
             path.name in TRANSIENT_DIRECTORIES),
            key=lambda item: len(item.parts), reverse=True)
        for path in directories:
            if path.exists():
                for artifact in sorted(path.rglob("*")):
                    if not artifact.is_file():
                        continue
                    record = file_record(artifact)
                    intermediate_hashes.append(record)
                    if artifact.suffix.lower() in {".json", ".log"}:
                        identity = hashlib.sha256(str(artifact).encode()).hexdigest()[:16]
                        destination = audit_root / (identity + "-" + record["sha256"][:16] + "-" + artifact.name)
                        destination.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(artifact, destination)
                        retained_audit.append({"original": record, "retained": file_record(destination)})
                removed_directories.append(str(path))
                _remove_tree(path)
    remaining = []
    for root in seen:
        if root.exists():
            remaining.extend(str(path) for path in root.rglob("*")
                             if path.is_file() and path.suffix.lower() in BINARY_SUFFIXES)
    return {
        "performed": True,
        "binaryHashesRecordedBeforeRemoval": True,
        "binaryHashes": binary_hashes,
        "intermediateHashes": intermediate_hashes,
        "retainedAuditFiles": retained_audit,
        "removedIntermediateDirectories": sorted(removed_directories),
        "binariesRetained": bool(remaining),
        "remainingBinaries": sorted(remaining),
        "temporaryBuildRemoved": not any(
            path.is_dir() and path.name in TRANSIENT_DIRECTORIES
            for root in seen if root.exists() for path in root.rglob("*")),
    }


def _counts(report: dict) -> tuple[int, int, int] | None:
    semantic = report.get("semantic", {})
    counts = semantic.get("counts", semantic) if semantic else report.get("counts", {})
    passed = counts.get("passed", counts.get("pass"))
    failed = counts.get("failed", counts.get("fail"))
    not_scored = counts.get("notScored", counts.get("not_scored"))
    rows = semantic.get("cases") or report.get("rows") or report.get("cases")
    if rows is not None and None in (passed, failed, not_scored):
        passed = sum(row.get("status") == "pass" for row in rows)
        failed = sum(row.get("status") == "fail" for row in rows)
        not_scored = sum(row.get("status") == "not_scored" for row in rows)
    if None in (passed, failed, not_scored):
        return None
    return int(passed), int(failed), int(not_scored)


def calibration_anchors(spec: TaskSpec, platform: str) -> dict:
    selected = spec.calibration_evidence.get(platform)
    if not selected or set(selected) != {"base", "final"}:
        raise ValueError(f"Missing {platform} exact-calibration evidence map")
    result = {}
    for role, path in selected.items():
        path = path.resolve()
        if not path.is_file():
            raise ValueError(f"Missing exact-calibration evidence: {path}")
        report = load(path)
        counts = _counts(report)
        expected = (0, spec.case_count, 0) if role == "base" else (spec.case_count, 0, 0)
        if counts != expected:
            raise ValueError(f"Historical {platform} {role} calibration is not exact: {counts}")
        result[role] = {**file_record(path), "counts": {
            "passed": counts[0], "failed": counts[1], "notScored": counts[2]}}
    return result


def calibrator_lineage(spec: TaskSpec, platform: str) -> dict:
    paths = spec.calibrator_files.get(platform, ())
    if not paths:
        raise ValueError(f"Missing {platform} exact runtime calibrator lineage")
    records = []
    for path in paths:
        if not path.is_file():
            raise ValueError(f"Missing exact runtime calibrator: {path}")
        records.append(file_record(path))
    encoded = json.dumps(records, sort_keys=True, separators=(",", ":")).encode()
    return {"sha256": hashlib.sha256(encoded).hexdigest(), "files": records}


def _contains(actual, expected) -> bool:
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(
            key in actual and _contains(actual[key], value) for key, value in expected.items())
    if isinstance(expected, list):
        return isinstance(actual, list) and len(actual) == len(expected) and all(
            _contains(left, right) for left, right in zip(actual, expected))
    return type(actual) is type(expected) and actual == expected


def _check_value(check: dict) -> bool | None:
    if isinstance(check.get("passed"), bool):
        return check["passed"]
    if check.get("status") in {"pass", "fail"}:
        return check["status"] == "pass"
    return None


def _source_binding(report: dict) -> Path | None:
    provenance = report.get("provenance", {})
    value = (provenance.get("candidateSource") or provenance.get("productionSourceRoot") or
             report.get("target") or report.get("source"))
    return Path(value).resolve() if isinstance(value, str) else None


def validate_runtime_report(report: dict, *, spec: TaskSpec, platform: str, role: str,
                            source: Path, inventory: dict, contract: dict,
                            lineage: dict) -> list[dict]:
    if report.get("taskId") != spec.task_id or report.get("platform") != platform:
        raise ValueError("runtime report task/platform identity mismatch")
    if report.get("role") != role or report.get("observationMode") != "runtime_state_transition":
        raise ValueError("runtime report role or observation mode mismatch")
    if _source_binding(report) != source.resolve():
        raise ValueError("runtime report is not bound to the supplied source")
    provenance = report.get("provenance", {})
    if provenance.get("candidateMode") != "standalone_directory":
        raise ValueError("runtime report is not a standalone source execution")
    if provenance.get("archivedPatchApplied") is not False:
        raise ValueError("fixed archived patches are forbidden")
    if provenance.get("sourceInventorySha256") != inventory["sha256"]:
        raise ValueError("runtime source inventory binding differs")
    runtime_compile = report.get("runtimeCompile", {})
    if runtime_compile.get("passed") is not True or runtime_compile.get("status") != "passed":
        raise ValueError("runtime evaluator packaging/compilation did not pass")
    diagnostics = report.get("diagnostics", {})
    if diagnostics.get("adapter") != "ready" or diagnostics.get("transport") not in {
            "ready", "transport_completed", "host_runtime_completed"}:
        raise ValueError("runtime adapter or transport is not ready")
    strict = diagnostics.get("strictRuntime", {})
    required = {
        "sourceParameterized": True,
        "actualProductionExecuted": True,
        "sourceObserverUsed": False,
        "fallbackUsed": False,
        "hostTranspilationUsed": False,
    }
    if any(strict.get(key) is not value for key, value in required.items()):
        raise ValueError("strict runtime provenance is incomplete or forbidden evidence was used")
    if strict.get("calibratorLineageSha256") != lineage["sha256"]:
        raise ValueError("runtime evaluator is not derived from the reviewed exact calibrator lineage")
    runtime_kind = str(strict.get("runtimeKind", "")).lower()
    if platform == "arkts" and "device" not in runtime_kind:
        raise ValueError("ArkTS semantic evidence must execute on an OpenHarmony device")
    if platform == "android" and not any(token in runtime_kind for token in ("android", "robolectric")):
        raise ValueError("Android semantic evidence did not execute an Android production runtime")

    rows = report.get("semantic", {}).get("cases", [])
    expected_identity = [(case["caseId"], case["key"], case["traceDigest"])
                         for case in contract["cases"]]
    actual_identity = [(row.get("caseId"), row.get("key"), row.get("traceDigest"))
                       for row in rows]
    if actual_identity != expected_identity or len(rows) != spec.case_count:
        raise ValueError("runtime report does not contain the canonical case sequence")
    for row, case in zip(rows, contract["cases"]):
        if row.get("status") not in {"pass", "fail"}:
            raise ValueError("runtime/environment failures must be NOT_SCORED, never semantic verdicts")
        executed = row.get("transitionExecuted") is True
        entry = row.get("entryFailureEvidence", {})
        reviewed_entry_failure = (
            not executed and entry.get("canonicalGivenEstablished") is True and
            entry.get("positiveControlCompleted") is True)
        if row["status"] == "pass" and not executed:
            raise ValueError("semantic pass lacks an executed production transition")
        if not executed and not reviewed_entry_failure:
            raise ValueError("semantic failure lacks transition or reviewed entry-failure evidence")
        if len(row.get("checkpoints", [])) < 2:
            raise ValueError("runtime before/after or entry/positive-control checkpoints are incomplete")
        checks = {item.get("description", item.get("invariant", item.get("text"))): item
                  for item in row.get("invariantChecks", [])}
        missing = [text for text in case.get("invariants", []) if text not in checks]
        if missing and not reviewed_entry_failure:
            raise ValueError("canonical invariant executable checks are incomplete")
        expected_match = _contains(row.get("observed"), case.get("expected", {}))
        invariant_values = [_check_value(checks[text]) for text in case.get("invariants", [])
                            if text in checks]
        invariants_pass = len(invariant_values) == len(case.get("invariants", [])) and all(invariant_values)
        if row["status"] == "pass" and not (expected_match and invariants_pass):
            raise ValueError("semantic pass does not satisfy expected state and all invariants")
        if row["status"] == "fail" and expected_match and invariants_pass and not reviewed_entry_failure:
            raise ValueError("semantic fail has no state/invariant mismatch")
    return rows


def _not_scored(contract: dict, reason: str) -> list[dict]:
    return [{"caseId": case["caseId"], "key": case["key"],
             "traceDigest": case["traceDigest"], "status": "not_scored",
             "reason": reason, "observed": {}, "checkpoints": [], "invariantChecks": []}
            for case in contract["cases"]]


def score(*, spec: TaskSpec, platform: str, source: Path, base_source: Path,
          final_source: Path, output: Path, compile_passed: bool | None,
          compile_command: str, evaluator: RuntimeEvaluator, timeout: float = 3600,
          monotonic: Callable[[], float] = time.monotonic,
          application_compiler: ApplicationCompiler | None = None) -> dict:
    """Consume the caller's remaining budget without resetting it per phase."""
    if platform not in {"android", "arkts"}:
        raise ValueError("platform must be android or arkts")
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or not 0 < timeout <= 3600:
        raise ValueError("Task12/13 formal scorer remaining timeout must satisfy 0 < timeout <= 3600")
    started = monotonic()
    deadline = started + timeout
    contract = load(spec.contract)
    if contract.get("taskId") != spec.task_id or len(contract.get("cases", [])) != spec.case_count:
        raise ValueError("canonical contract identity/count mismatch")
    if spec.audited_contract is not None:
        if sha256(spec.contract) != sha256(spec.audited_contract):
            raise ValueError("canonical contract differs from its reviewed audit-after version")
    if spec.expected_contract_sha256 is not None and sha256(spec.contract) != spec.expected_contract_sha256:
        raise ValueError("canonical contract differs from its pinned reviewed SHA-256")
    anchors = calibration_anchors(spec, platform)
    lineage = calibrator_lineage(spec, platform)
    candidate = source.resolve()
    sources = {"base": base_source.resolve(), "final": final_source.resolve(), "agent": candidate}
    compile_metric = {
        "passed": compile_passed,
        "status": "passed" if compile_passed is True else "failed" if compile_passed is False else "not_provided",
        "scope": "standalone_candidate_application_build",
        "command": compile_command,
    }
    runtime_compile = {"passed": None, "status": "not_run",
                       "scope": "strict_evaluator_packaging_and_runtime_build"}
    evidence_root = output.resolve().with_suffix(".strict-evidence")
    diagnostics = {"deadlineSeconds": timeout, "deadlineMonotonic": deadline,
                   "deadlineScope": "dynamic_base_final_candidate_runtime",
                   "contract": file_record(spec.contract),
                   "auditedContract": file_record(spec.audited_contract) if spec.audited_contract else None,
                   "calibrationAnchors": anchors,
                   "calibratorLineage": lineage,
                   "phases": [], "cleanup": []}

    def remaining(phase: str) -> float:
        value = deadline - monotonic()
        if value <= 0:
            raise TimeoutError(f"{phase} exhausted the single monotonic {timeout:g}-second deadline")
        return value

    def fail(reason: str) -> dict:
        rows = _not_scored(contract, reason)
        result = {
            "schemaVersion": 2, "taskId": spec.task_id, "platform": platform, "role": "agent",
            "target": str(candidate), "observationMode": "runtime_state_transition",
            "compile": compile_metric, "runtimeCompile": runtime_compile,
            "semantic": {"total": spec.case_count, "passed": 0, "failed": 0,
                         "notScored": spec.case_count, "cases": rows},
            "calibration": {"passed": False},
            "publication": {"eligible": False, "reason": reason},
            "diagnostics": {**diagnostics, "adapter": "failed", "transport": "failed",
                            "totalElapsedSeconds": monotonic() - started},
        }
        write(output.resolve(), result)
        return result

    try:
        if len(set(sources.values())) != 3:
            raise ValueError("base, final, and candidate sources must be distinct directories")
        for role, root in sources.items():
            if not root.is_dir():
                raise ValueError(f"{role} source directory unavailable")
            if output.resolve() == root or root in output.resolve().parents:
                raise ValueError("scorer output must be outside every source tree")

        if application_compiler is not None:
            compile_root = evidence_root / "application-compile"
            before_compile = source_inventory(candidate)
            try:
                compile_metric = application_compiler(
                    platform=platform, source=candidate, output=compile_root,
                    deadline=deadline, command=compile_command,
                )
                if not isinstance(compile_metric, dict):
                    raise ValueError("application compiler returned no report")
                compile_metric.setdefault("scope", "standalone_candidate_application_build")
                compile_metric.setdefault("command", compile_command)
            finally:
                cleanup = cleanup_artifacts(compile_root, candidate)
                write(compile_root / "cleanup.json", cleanup)
                diagnostics["cleanup"].append({"role": "application_compile", **cleanup})
            if before_compile["sha256"] != source_inventory(candidate)["sha256"]:
                raise ValueError("application compiler mutated the candidate production source")
        if compile_metric.get("passed") is not True:
            if (compile_metric.get("status") == "not_scored" and
                    compile_metric.get("classification") == "dependency_transport"):
                return fail("Dependency transport failed; application compile and semantics are not scored")
            if (compile_metric.get("status") == "not_scored" and
                    compile_metric.get("classification") == "toolchain_environment"):
                return fail("Android toolchain environment failed; application compile and semantics are not scored")
            if (compile_metric.get("status") == "not_scored" and
                    compile_metric.get("classification") == "external_termination"):
                return fail("Application build was externally terminated; compile and semantics are not scored")
            return fail("Standalone candidate application build did not pass; semantics are not scored")

        candidate_rows = None
        candidate_report = None
        for role in ("base", "final", "agent"):
            remaining(role)
            phase_root = evidence_root / role
            phase_root.mkdir(parents=True, exist_ok=False)
            report_path = phase_root / "runtime.json"
            before = source_inventory(sources[role])
            report = None
            try:
                report = evaluator(task=spec, platform=platform, source=sources[role], role=role,
                                   output=report_path, deadline=deadline)
                if not isinstance(report, dict):
                    raise ValueError("task runtime evaluator returned no report")
                runtime_compile = report.get("runtimeCompile", runtime_compile)
                rows = validate_runtime_report(report, spec=spec, platform=platform, role=role,
                                               source=sources[role], inventory=before,
                                               contract=contract, lineage=lineage)
                expected_status = "fail" if role == "base" else "pass" if role == "final" else None
                if expected_status and any(row["status"] != expected_status for row in rows):
                    raise ValueError(f"dynamic {role} calibration is not all-{expected_status}")
                if role == "agent":
                    candidate_rows, candidate_report = rows, report
            finally:
                cleanup = cleanup_artifacts(phase_root, sources[role])
                write(phase_root / "cleanup.json", cleanup)
                diagnostics["cleanup"].append({"role": role, **cleanup})
            after = source_inventory(sources[role])
            if before["sha256"] != after["sha256"]:
                raise ValueError(f"runtime evaluator mutated the {role} production source")
            diagnostics["phases"].append({"role": role, "source": str(sources[role]),
                                           "sourceInventorySha256": before["sha256"],
                                           "remainingSeconds": remaining(role + " completion")})
        if candidate_rows is None or candidate_report is None:
            raise ValueError("candidate runtime phase did not produce canonical rows")
        if any(item["binariesRetained"] or not item["temporaryBuildRemoved"]
               for item in diagnostics["cleanup"]):
            raise ValueError("binary or build intermediates remain after strict scoring")
        passed = sum(row["status"] == "pass" for row in candidate_rows)
        failed = spec.case_count - passed
        result = {
            **candidate_report,
            "compile": compile_metric,
            "runtimeCompile": runtime_compile,
            "target": str(candidate),
            "semantic": {"total": spec.case_count, "passed": passed, "failed": failed,
                         "notScored": 0, "cases": candidate_rows},
            "calibration": {"passed": True, "base": {"passed": 0, "failed": spec.case_count},
                            "final": {"passed": spec.case_count, "failed": 0}},
            "publication": {"eligible": True,
                            "reason": "Dynamic exact calibration and complete candidate runtime passed"},
            "diagnostics": {**candidate_report.get("diagnostics", {}), **diagnostics,
                            "adapter": "ready", "totalElapsedSeconds": monotonic() - started},
        }
        write(output.resolve(), result)
        return result
    except (OSError, RuntimeError, ValueError, TimeoutError) as error:
        return fail(f"{type(error).__name__}: {error}")
