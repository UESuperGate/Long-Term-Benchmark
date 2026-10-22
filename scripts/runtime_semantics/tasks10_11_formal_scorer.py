#!/usr/bin/env python3
"""Fail-closed formal scoring shared only by Tasks 10 and 11.

Task modules provide an exact runtime runner for each platform. This module
owns candidate binding, dynamic base/final calibration, the single deadline,
and report validation. It deliberately has no source-observer or generic
runtime fallback.
"""

from __future__ import annotations

from dataclasses import dataclass
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import time
from typing import Callable


ROOT = Path(__file__).resolve().parents[2]
IGNORED_PARTS = {".git", ".gradle", ".hvigor", "build", "node_modules", "oh_modules"}
BINARY_SUFFIXES = {".apk", ".hap", ".aab", ".apks", ".abc", ".dex", ".so", ".jar", ".class"}


@dataclass(frozen=True)
class TaskSpec:
    task_id: str
    case_count: int


@dataclass(frozen=True)
class RuntimeRunner:
    """An exact evaluator entrypoint with no filename-based dispatch."""

    interpreter: Path
    entrypoint: Path


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _record(path: Path) -> dict:
    return {"path": str(path.resolve()), "bytes": path.stat().st_size, "sha256": _sha256(path)}


def cleanup_evidence_artifacts(evidence_root: Path, temporary_root: Path | None = None) -> dict:
    """Retain binary hashes, then remove binaries and evaluator intermediates."""
    binaries = []
    for path in sorted(evidence_root.rglob("*")):
        if path.is_file() and path.suffix.lower() in BINARY_SUFFIXES:
            item = _record(path)
            item["relativePath"] = str(path.relative_to(evidence_root))
            binaries.append(item)
            path.unlink()
    removed = []
    disposable = {"build", ".gradle", ".hvigor", "oh_modules", "node_modules"}
    directories = sorted((path for path in evidence_root.rglob("*")
                          if path.is_dir() and path.name in disposable),
                         key=lambda path: len(path.parts), reverse=True)
    for path in directories:
        if path.exists():
            removed.append(str(path.relative_to(evidence_root)))
            shutil.rmtree(path)
    temporary_root_removed = temporary_root is None
    if temporary_root is not None:
        if temporary_root.exists():
            shutil.rmtree(temporary_root)
        temporary_root_removed = not temporary_root.exists()
        temporary_parent = temporary_root.parent
        if temporary_parent != evidence_root and temporary_parent.exists() and not any(temporary_parent.iterdir()):
            temporary_parent.rmdir()
    remaining = [str(path.relative_to(evidence_root)) for path in evidence_root.rglob("*")
                 if path.is_file() and path.suffix.lower() in BINARY_SUFFIXES]
    return {"performed": True, "binaryHashes": binaries,
            "binaryArtifactsRetained": bool(remaining),
            "retainedEvidenceExcludesBinaries": not remaining,
            "remainingBinaries": remaining, "removedIntermediateDirectories": sorted(removed),
            "temporaryArtifactRoot": str(temporary_root) if temporary_root else None,
            "temporaryArtifactRootRemoved": temporary_root_removed,
            "temporaryBuildRemoved": not any(path.is_dir() and path.name in disposable
                                               for path in evidence_root.rglob("*"))}


def cleanup_source_artifacts(source_root: Path) -> dict:
    """Remove scorer-owned application outputs without touching production source."""
    binaries = []
    for path in sorted(source_root.rglob("*")):
        if path.is_file() and path.suffix.lower() in {".apk", ".hap"}:
            item = _record(path)
            item["relativePath"] = str(path.relative_to(source_root))
            binaries.append(item)
            path.unlink()
    disposable = {"build", ".gradle", ".hvigor"}
    removed = []
    directories = sorted((path for path in source_root.rglob("*")
                          if path.is_dir() and path.name in disposable),
                         key=lambda path: len(path.parts), reverse=True)
    for path in directories:
        if path.exists():
            removed.append(str(path.relative_to(source_root)))
            shutil.rmtree(path)
    remaining = [str(path.relative_to(source_root)) for path in source_root.rglob("*")
                 if path.is_file() and path.suffix.lower() in {".apk", ".hap"}]
    return {"performed": True, "source": str(source_root), "binaryHashes": binaries,
            "binaryArtifactsRetained": bool(remaining),
            "retainedEvidenceExcludesBinaries": not remaining,
            "remainingBinaries": remaining,
            "removedIntermediateDirectories": sorted(removed),
            "temporaryBuildRemoved": not any(path.is_dir() and path.name in disposable
                                               for path in source_root.rglob("*"))}


def _combined_cleanup(evidence: dict, source: dict, role: str) -> dict:
    return {"performed": True, "role": role,
            "binaryHashes": evidence["binaryHashes"] + source["binaryHashes"],
            "binaryArtifactsRetained": (evidence["binaryArtifactsRetained"]
                                        or source["binaryArtifactsRetained"]),
            "retainedEvidenceExcludesBinaries": (
                evidence["retainedEvidenceExcludesBinaries"]
                and source["retainedEvidenceExcludesBinaries"]),
            "temporaryBuildRemoved": (evidence["temporaryBuildRemoved"]
                                      and source["temporaryBuildRemoved"]),
            "temporaryArtifactRoot": evidence["temporaryArtifactRoot"],
            "temporaryArtifactRootRemoved": evidence["temporaryArtifactRootRemoved"],
            "evidence": evidence, "source": source}


def _candidate_files(source: Path, platform: str) -> list[Path]:
    roots = [source]
    if platform == "arkts":
        roots = [source / "AppScope", source / "entry" / "src" / "main"]
    files: list[Path] = []
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            relative = path.relative_to(source)
            if any(part in IGNORED_PARTS for part in relative.parts):
                continue
            if path.is_symlink():
                raise ValueError(f"Candidate symlink is unsupported: {relative}")
            if path.is_file():
                files.append(path)
    return sorted(set(files))


def candidate_smoke(source: Path, platform: str) -> dict:
    source = source.resolve()
    required = {
        "android": ("gradlew", "settings.gradle.kts", "app/build.gradle.kts"),
        "arkts": ("build-profile.json5", "hvigorfile.ts", "entry/src/main/module.json5"),
    }[platform]
    missing = [name for name in required if not (source / name).is_file()]
    if missing:
        raise ValueError(f"Standalone {platform} candidate is missing: {', '.join(missing)}")
    files = _candidate_files(source, platform)
    if not files:
        raise ValueError("Standalone candidate has no auditable production files")
    entries = [{"path": str(path.relative_to(source)), "bytes": path.stat().st_size,
                "sha256": _sha256(path)} for path in files]
    encoded = json.dumps(entries, sort_keys=True, separators=(",", ":")).encode()
    return {"passed": True, "source": str(source), "required": list(required),
            "fileCount": len(entries), "inventorySha256": hashlib.sha256(encoded).hexdigest(),
            "files": entries}


def _canonical_ns(contract: dict, reason: str) -> list[dict]:
    return [{"caseId": case["caseId"], "key": case["key"],
             "traceDigest": case["traceDigest"], "status": "not_scored",
             "reason": reason, "observed": {}, "checkpoints": [], "invariantChecks": []}
            for case in contract["cases"]]


def _compile_metric(passed: bool | None, command: str) -> dict:
    return {"passed": passed,
            "status": "passed" if passed is True else "failed" if passed is False else "not_run",
            "scope": "standalone_candidate_application_build", "command": command,
            "source": "formal_scorer_caller"}


def _expected_matches(expected, observed) -> bool:
    if isinstance(expected, dict):
        return isinstance(observed, dict) and all(
            key in observed and _expected_matches(value, observed[key]) for key, value in expected.items())
    if isinstance(expected, list):
        return isinstance(observed, list) and len(expected) == len(observed) and all(
            _expected_matches(left, right) for left, right in zip(expected, observed))
    return expected == observed


def validate_runtime_report(report: dict, contract: dict, *, spec: TaskSpec,
                            platform: str, role: str, source: Path) -> dict:
    if report.get("taskId") != spec.task_id or report.get("platform") != platform:
        raise ValueError("Strict runtime report task/platform identity mismatch")
    if report.get("role") != role or report.get("observationMode") != "runtime_state_transition":
        raise ValueError("Strict runtime report role or observation mode mismatch")
    target = report.get("target") or report.get("source") or report.get("provenance", {}).get("productionSourceRoot")
    if target is None or Path(target).resolve() != source.resolve():
        raise ValueError("Strict runtime report is not bound to the supplied candidate")
    runtime_compile = report.get("runtimeCompile", {})
    if runtime_compile.get("passed") is not True or runtime_compile.get("status") != "passed":
        raise ValueError("Strict evaluator packaging/runtime compilation did not pass")
    strict = report.get("diagnostics", {}).get("strictRuntime", {})
    required_flags = {
        "sourceParameterized": True,
        "entryEvaluator": True,
        "runtimeOrDeviceEvaluator": True,
        "sourceObserverUsed": False,
        "fallbackUsed": False,
    }
    if any(strict.get(key) is not value for key, value in required_flags.items()):
        raise ValueError("Strict runtime provenance is incomplete or a forbidden fallback was used")
    if strict.get("candidateSmoke", {}).get("passed") is not True:
        raise ValueError("Strict child runner did not complete its candidate smoke")
    cleanup = strict.get("cleanup", {})
    if (cleanup.get("temporaryBuildRemoved") is not True
            or cleanup.get("temporaryArtifactRootRemoved") is not True
            or cleanup.get("retainedEvidenceExcludesBinaries") is not True
            or cleanup.get("binaryArtifactsRetained") is not False):
        raise ValueError("Strict child runner did not declare binary/intermediate cleanup")

    expected_rows = [(case["caseId"], case["traceDigest"]) for case in contract["cases"]]
    rows = report.get("semantic", {}).get("cases", [])
    actual_rows = [(row.get("caseId"), row.get("traceDigest")) for row in rows]
    if actual_rows != expected_rows or len(rows) != spec.case_count:
        raise ValueError("Strict runtime report differs from canonical IDs/digests/order")
    specs = {case["caseId"]: case for case in contract["cases"]}
    for row in rows:
        if row.get("status") not in {"pass", "fail"}:
            raise ValueError("Formal runtime rows must all be pass/fail")
        checkpoints = row.get("checkpoints", [])
        labels = {checkpoint.get("name", checkpoint.get("label")) for checkpoint in checkpoints}
        entry_failure = row.get("entryFailureEvidence", {})
        executed = row.get("transitionExecuted") is True
        if not executed and entry_failure.get("positiveControlCompleted") is not True:
            raise ValueError("A semantic failure requires a real transition or reviewed positive-control entry failure")
        if row["status"] == "pass" and not executed:
            raise ValueError("A semantic pass requires the production transition to execute")
        if executed and not {"before:event", "after:event"}.issubset(labels):
            raise ValueError("Executed runtime transition lacks before/after checkpoints")
        canonical = specs[row["caseId"]]
        if entry_failure.get("policyId") == "tasks10_11.android.common-prefix.v1":
            try:
                from .tasks10_11_runtime_evidence import validate_entry_failure
            except ImportError:
                from tasks10_11_runtime_evidence import validate_entry_failure
            validate_entry_failure(row, report, set(), contract=contract)
            continue
        if (spec.task_id == "10_media_upload_quality" and platform == "arkts" and
                entry_failure.get("policyId") == "task10.arkts.actual-prepared-prefix.v2"):
            from scripts.runtime_semantics.task10_repository_prefix_policy import validate_entry_failure
            validate_entry_failure(row, report, set(), contract=contract)
            continue
        checks = row.get("invariantChecks", [])
        bound = {}
        for check in checks:
            description = check.get("description", check.get("text", check.get("invariant")))
            verdict = check.get("passed")
            if verdict is None and check.get("status") in {"pass", "fail"}:
                verdict = check["status"] == "pass"
            bound[description] = verdict
        if any(bound.get(description) not in {True, False} for description in canonical.get("invariants", [])):
            raise ValueError("Canonical invariant lacks an executable boolean check")
        matches = _expected_matches(canonical.get("expected", {}), row.get("observed", {}))
        invariants_pass = all(bound.get(description) is True for description in canonical.get("invariants", []))
        if row["status"] == "pass" and not (matches and invariants_pass):
            raise ValueError("Runtime pass does not satisfy canonical expected state and invariants")
        reviewed_entry_failure = (not executed
                                  and entry_failure.get("positiveControlCompleted") is True)
        if row["status"] == "fail" and matches and invariants_pass and not reviewed_entry_failure:
            raise ValueError("Runtime failure has no semantic mismatch")
    return {"total": len(rows), "passed": sum(row["status"] == "pass" for row in rows),
            "failed": sum(row["status"] == "fail" for row in rows), "notScored": 0,
            "cases": rows}


def _command(runner: RuntimeRunner, *, source: Path, role: str, output: Path,
             artifact_root: Path, timeout: float, platform: str) -> list[str]:
    return [str(runner.interpreter), str(runner.entrypoint),
            "--source", str(source.resolve()), "--role", role,
            "--output", str(output.resolve()), "--timeout", str(max(1, int(timeout))),
            "--platform", platform, "--artifact-root", str(artifact_root.resolve())]


def _verify_task11_retained_report(report_path: Path, contract: dict) -> dict:
    """Mandatory ArkTS raw-integrity gate; model-tree attestation stays separate."""
    try:
        from . import task11_retained_integrity as integrity
    except ImportError:
        import task11_retained_integrity as integrity
    report_binding = _record(report_path)
    verifier = _record(Path(integrity.__file__))
    assessment = integrity.verify_report(report_path, contract, reconstruction=None)
    rows = load(report_path)["semantic"]["cases"]
    if (assessment.get("validated") is not True or assessment.get("notScored") != 0
            or assessment.get("nativeExecutions") != len(contract["cases"])
            or assessment.get("passed") != sum(row["status"] == "pass" for row in rows)
            or assessment.get("failed") != sum(row["status"] == "fail" for row in rows)
            or assessment.get("candidateReconstructedFromPreAgentCapture") is not False
            or assessment.get("newModelOrDeviceRun") is not False):
        raise ValueError("Task11 retained integrity did not verify the complete original runtime")
    if _record(report_path) != report_binding or _record(Path(integrity.__file__)) != verifier:
        raise ValueError("Task11 bound report or integrity verifier changed during verification")
    return {"assessment": assessment, "report": report_binding, "verifier": verifier,
            "reconstruction": None,
            "scope": "original_native_execution_build_logs_nonce; model baseline+patch attestation requires a separate receipt"}


def score(*, spec: TaskSpec, platform: str, source: Path, base_source: Path,
          final_source: Path, output: Path, timeout: float = 3600,
          compile_passed: bool | None, compile_command: str,
          runtime_runner: RuntimeRunner, run=subprocess.run,
          monotonic: Callable[[], float] = time.monotonic) -> dict:
    if platform not in {"android", "arkts"}:
        raise ValueError("platform must be android or arkts")
    if timeout <= 0 or timeout > 3600:
        raise ValueError("Formal scorer timeout must be in (0, 3600]")
    started = monotonic()
    contract_path = ROOT / "benchmark_tasks" / spec.task_id / "transitions.json"
    contract = load(contract_path)
    if contract.get("taskId") != spec.task_id or len(contract.get("cases", [])) != spec.case_count:
        raise ValueError("Canonical task contract identity/count mismatch")
    candidate = source.resolve()
    calibration_sources = {"base": base_source.resolve(), "final": final_source.resolve()}
    compile_metric = _compile_metric(compile_passed, compile_command)
    runtime_compile = {"passed": None, "status": "not_run",
                       "scope": "strict_evaluator_packaging_and_runtime_build"}
    evidence_root = output.resolve().with_suffix(".strict-evidence")
    diagnostics = {"candidate": str(candidate), "timeoutSeconds": timeout,
                   "deadlineScope": "smoke_plus_dynamic_calibration_plus_candidate_runtime",
                   "contract": _record(contract_path), "strictEvidence": str(evidence_root)}
    task11_raw_gate = spec.task_id == "11_room_upgrade_navigation" and platform == "arkts"
    if task11_raw_gate:
        diagnostics["deadlineScope"] += "_plus_retained_raw_integrity_and_cleanup"

    def remaining() -> float:
        value = timeout - (monotonic() - started)
        if value <= 0:
            raise TimeoutError(f"{spec.task_id} formal scorer exhausted its single monotonic deadline")
        return value

    def unavailable(reason: str) -> dict:
        result = {"schemaVersion": 2, "taskId": spec.task_id, "platform": platform,
                  "role": "agent", "target": str(candidate),
                  "observationMode": "runtime_state_transition", "compile": compile_metric,
                  "runtimeCompile": runtime_compile,
                  "semantic": {"total": spec.case_count, "passed": 0, "failed": 0,
                               "notScored": spec.case_count, "cases": _canonical_ns(contract, reason)},
                  "calibration": diagnostics.get("calibration", {"passed": False}),
                  "publication": {"eligible": False, "reason": reason},
                  "diagnostics": {**diagnostics, "adapter": "failed", "reason": reason,
                                  "totalElapsedSeconds": monotonic() - started}}
        write(output.resolve(), result)
        return result

    try:
        if compile_passed is not True:
            raise RuntimeError("Standalone candidate application build did not pass")
        for role, role_source in {**calibration_sources, "agent": candidate}.items():
            if role_source == output.resolve() or role_source in output.resolve().parents:
                raise ValueError(f"Scorer output must be outside the {role} source tree")
            if role_source == evidence_root or role_source in evidence_root.parents:
                raise ValueError(f"Strict evidence must be outside the {role} source tree")
        smoke_before = {role: candidate_smoke(path, platform)
                        for role, path in {**calibration_sources, "agent": candidate}.items()}
        diagnostics["candidateSmoke"] = smoke_before["agent"]
        diagnostics["cleanup"] = []
        diagnostics["preRunCleanup"] = []
        for role, role_source in {**calibration_sources, "agent": candidate}.items():
            cleanup = cleanup_source_artifacts(role_source)
            cleanup["role"] = role
            diagnostics["preRunCleanup"].append(cleanup)
            if cleanup["binaryArtifactsRetained"] or not cleanup["temporaryBuildRemoved"]:
                raise RuntimeError(f"Strict {role} pre-run source cleanup was incomplete")
        runner = runtime_runner
        if not runner.interpreter.is_file():
            raise FileNotFoundError(f"Strict runtime interpreter is unavailable: {runner.interpreter}")
        if not runner.entrypoint.is_file():
            raise FileNotFoundError(f"Exact strict runtime runner is unavailable: {runner.entrypoint}")
        if evidence_root.exists():
            raise FileExistsError(f"Refusing existing strict scorer evidence: {evidence_root}")
        evidence_root.mkdir(parents=True)
        runs = {}
        for role, role_source in (("base", calibration_sources["base"]),
                                  ("final", calibration_sources["final"]), ("agent", candidate)):
            report_path = evidence_root / f"{role}.runtime.json"
            artifact_root = evidence_root / "temporary" / role
            artifact_root.mkdir(parents=True)
            budget = remaining()
            command = _command(runner, source=role_source, role=role, output=report_path,
                               artifact_root=artifact_root, timeout=budget, platform=platform)
            log_path = evidence_root / f"{role}.command.log"
            completed = None
            task11_child_verified = False
            try:
                completed = run(command, cwd=ROOT, capture_output=True, text=True,
                                timeout=remaining(), check=False)
                log_path.write_text((completed.stdout or "") + (completed.stderr or ""), encoding="utf-8")
                if completed.returncode == 0 and report_path.is_file():
                    try:
                        from .tasks10_11_runtime_evidence import attach_child, validate_report
                    except ImportError:
                        from tasks10_11_runtime_evidence import attach_child, validate_report
                    unbound_child = load(report_path)
                    if unbound_child.get("provenance", {}).get("runtimeBinding") == "task10.original-page.repository.v2":
                        try:
                            from .task10_repository_evidence import attach_child as repository_attach
                        except ImportError:
                            from task10_repository_evidence import attach_child as repository_attach
                        child = repository_attach(unbound_child, contract, artifact_root, evidence_root / f"{role}.audit")
                    elif spec.task_id == "10_media_upload_quality" and platform == "arkts":
                        try:
                            from .task10_repository_evidence import attach_control
                        except ImportError:
                            from task10_repository_evidence import attach_control
                        child = attach_control(unbound_child, contract, artifact_root, evidence_root / f"{role}.audit")
                    else:
                        child = attach_child(unbound_child, contract, artifact_root,
                                             evidence_root / f"{role}.audit")
                    validate_report(child, contract)
                    report_path = evidence_root / f"{role}.bound-runtime.json"
                    write(report_path, child)
                    if task11_raw_gate:
                        gate = {"role": role, "status": "checking", "report": _record(report_path)}
                        diagnostics.setdefault("task11RetainedIntegrity", []).append(gate)
                        try:
                            validate_runtime_report(child, contract, spec=spec, platform=platform,
                                                    role=role, source=role_source)
                            if role == "agent":
                                runtime_compile = child["runtimeCompile"]
                            remaining()
                            receipt = _verify_task11_retained_report(report_path, contract)
                            remaining()
                            receipt["contract"] = _record(contract_path)
                            receipt_path = evidence_root / f"{role}.retained-integrity.json"
                            write(receipt_path, receipt)
                            gate.update(status="passed", receipt=_record(receipt_path))
                            task11_child_verified = True
                        except Exception as error:
                            gate.update(status="failed", reason=f"{type(error).__name__}: {error}")
                            raise RuntimeError(f"Task11 {role} retained raw-integrity gate failed: {gate['reason']}") from error
            finally:
                if task11_raw_gate and not task11_child_verified:
                    try:
                        from .task11_arkts_failure_retention import retain_failed_artifacts
                    except ImportError:
                        from task11_arkts_failure_retention import retain_failed_artifacts
                    diagnostics.setdefault('task11FailedChildRetention', []).append({
                        'role': role, 'manifest': retain_failed_artifacts(
                            artifact_root, evidence_root / f'{role}.failure.raw-evidence')})
                evidence_cleanup = cleanup_evidence_artifacts(evidence_root, artifact_root)
                source_cleanup = cleanup_source_artifacts(role_source)
                cleanup = _combined_cleanup(evidence_cleanup, source_cleanup, role)
                cleanup_path = evidence_root / f"{role}.cleanup.json"
                write(cleanup_path, cleanup)
                diagnostics["cleanup"].append({**cleanup, "manifest": _record(cleanup_path)})
            if (cleanup["binaryArtifactsRetained"] or not cleanup["temporaryBuildRemoved"]
                    or not cleanup["temporaryArtifactRootRemoved"]):
                raise RuntimeError(f"Strict {role} evaluator cleanup was incomplete")
            if completed is None:
                raise RuntimeError(f"Strict {role} evaluator did not return")
            if completed.returncode != 0 or not report_path.is_file():
                raise RuntimeError(f"Strict {role} evaluator failed with exit {completed.returncode}")
            child = load(report_path)
            if role == "agent" and isinstance(child.get("runtimeCompile"), dict):
                runtime_compile = child["runtimeCompile"]
            counts = validate_runtime_report(child, contract, spec=spec, platform=platform,
                                             role=role, source=role_source)
            runs[role] = {"report": _record(report_path), "log": _record(log_path),
                          "command": command, "counts": {key: counts[key]
                          for key in ("total", "passed", "failed", "notScored")},
                          "runtimeCompile": child["runtimeCompile"], "semantic": counts,
                          "diagnostics": child.get("diagnostics", {}), "cleanup": cleanup}
            if task11_raw_gate:
                runs[role]["retainedIntegrity"] = gate["receipt"]
            if role == "final":
                expected_base = {"total": spec.case_count, "passed": 0,
                                 "failed": spec.case_count, "notScored": 0}
                expected_final = {"total": spec.case_count, "passed": spec.case_count,
                                  "failed": 0, "notScored": 0}
                if runs["base"]["counts"] != expected_base or runs["final"]["counts"] != expected_final:
                    raise RuntimeError("Dynamic base/final calibration did not meet strict polarity")
        smoke_after = {role: candidate_smoke(path, platform)
                       for role, path in {**calibration_sources, "agent": candidate}.items()}
        for role in smoke_before:
            if smoke_before[role]["inventorySha256"] != smoke_after[role]["inventorySha256"]:
                raise RuntimeError(f"Strict evaluator mutated the {role} source tree")
        calibration = {"passed": True, "base": runs["base"]["counts"],
                       "final": runs["final"]["counts"],
                       "sameEvaluator": {"interpreter": str(runner.interpreter),
                                         "entrypoint": str(runner.entrypoint)},
                       "dynamicSources": {
                           role: str(path) for role, path in calibration_sources.items()}}
        diagnostics["calibration"] = calibration
        runtime_compile = runs["agent"]["runtimeCompile"]
        agent = runs["agent"]["semantic"]
        if task11_raw_gate:
            remaining()
        result = {"schemaVersion": 2, "taskId": spec.task_id, "platform": platform,
                  "role": "agent", "target": str(candidate),
                  "observationMode": "runtime_state_transition", "compile": compile_metric,
                  "runtimeCompile": runtime_compile, "semantic": agent, "calibration": calibration,
                  "publication": {"eligible": True,
                                  "reason": "Dynamic polarity and all strict agent runtime verdicts are complete"},
                  "provenance": {**child.get("provenance", {}), "productionSourceRoot": str(candidate),
                                 "productionSources": child["provenance"]["productionSources"],
                                 "contract": _record(contract_path),
                                 "candidateSmokeBefore": smoke_before["agent"],
                                 "candidateSmokeAfter": smoke_after["agent"],
                                 "strictRuns": {role: {key: value for key, value in run_data.items()
                                     if key != "semantic"} for role, run_data in runs.items()}},
                  "diagnostics": {**runs["agent"]["diagnostics"], **diagnostics,
                                  "adapter": "ready", "totalElapsedSeconds": monotonic() - started}}
        if task11_raw_gate:
            result["publication"]["task11RetainedRawIntegrityVerified"] = True
        write(output.resolve(), result)
        return result
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError, TimeoutError) as error:
        return unavailable(f"{type(error).__name__}: {error}")


def dispatch(task_id: str, *, platform: str, source: Path, base_source: Path,
             final_source: Path, output: Path, timeout: float = 3600,
             compile_passed: bool | None = None, compile_command: str = "",
             runtime_runner: RuntimeRunner | None = None, **testing) -> dict:
    """Small integration API; the shared central entrypoint remains untouched."""
    modules = {
        "10_media_upload_quality": "task10_formal_agent",
        "11_room_upgrade_navigation": "task11_formal_agent",
    }
    module_name = modules.get(task_id)
    if module_name is None:
        raise KeyError(f"No Tasks10/11 formal scorer for {task_id}")
    package = __package__
    if package:
        module = __import__(f"{package}.{module_name}", fromlist=["score"])
    else:
        module = __import__(module_name, fromlist=["score"])
    return module.score(platform=platform, source=source, base_source=base_source,
                        final_source=final_source, output=output, timeout=timeout,
                        compile_passed=compile_passed, compile_command=compile_command,
                        runtime_runner=runtime_runner, **testing)


def main(argv: list[str] | None = None, *, task_id: str | None = None) -> int:
    """CLI for caller-owned app compile evidence and fresh dynamic runtime scoring."""
    parser = argparse.ArgumentParser(description=__doc__)
    if task_id is None:
        parser.add_argument("--task", required=True,
                            choices=("10_media_upload_quality", "11_room_upgrade_navigation"))
    parser.add_argument("--platform", required=True, choices=("android", "arkts"))
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--base-source", type=Path, required=True)
    parser.add_argument("--final-source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout", type=float, default=3600)
    parser.add_argument("--compile-passed", choices=("true", "false", "unknown"), default="unknown")
    parser.add_argument("--compile-command", default="")
    args = parser.parse_args(argv)
    compile_passed = {"true": True, "false": False, "unknown": None}[args.compile_passed]
    report = dispatch(task_id or args.task, platform=args.platform, source=args.source,
                      base_source=args.base_source, final_source=args.final_source,
                      output=args.output, timeout=args.timeout, compile_passed=compile_passed,
                      compile_command=args.compile_command)
    print(json.dumps({"output": str(args.output.resolve()), "compile": report["compile"],
                      "runtimeCompile": report["runtimeCompile"],
                      "semantic": {key: report["semantic"][key]
                                   for key in ("total", "passed", "failed", "notScored")},
                      "publication": report["publication"]}))
    return 0 if report["publication"]["eligible"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
