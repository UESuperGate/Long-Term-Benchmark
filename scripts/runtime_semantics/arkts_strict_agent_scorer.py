#!/usr/bin/env python3
"""Shared fail-closed device scorer for source-parameterized Task16/17 ArkTS agents."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Optional, Tuple

try:
    from .tasks16_17_arkts_entry_evidence import attach_entries, validate_entry_failure
    from . import tasks16_17_arkts_entry_binding_v2 as input_guard
except ImportError:
    from tasks16_17_arkts_entry_evidence import attach_entries, validate_entry_failure
    import tasks16_17_arkts_entry_binding_v2 as input_guard


ROOT = Path(__file__).resolve().parents[2]
NODE = "/Applications/DevEco-Studio.app/Contents/tools/node/bin/node"
HDC = Path.home() / "Library/OpenHarmony/Sdk/23/toolchains/hdc"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def remaining(deadline: float, phase: str) -> float:
    value = deadline - time.monotonic()
    if value <= 0:
        raise subprocess.TimeoutExpired(phase, 0)
    return value


def discover_device(requested: Optional[str], deadline: float) -> str:
    if requested:
        return requested
    process = subprocess.run([str(HDC), "list", "targets"], capture_output=True, text=True,
                             timeout=min(30, remaining(deadline, "OpenHarmony device discovery")), check=False)
    targets = [line.strip() for line in process.stdout.splitlines() if line.strip() and line.strip() != "[Empty]"]
    if process.returncode or len(targets) != 1:
        raise RuntimeError(f"Expected one connected API23 target, found {targets!r}")
    return targets[0]


def device_locks(serial: str) -> Tuple[Path, Path]:
    name = "ltb-arkts-device-" + hashlib.sha256(serial.encode()).hexdigest()[:16]
    return Path("/tmp") / name, Path(tempfile.gettempdir()) / name


def acquire_device(serial: str, deadline: float) -> Path:
    coordination, transport = device_locks(serial)
    while True:
        remaining(deadline, "shared OpenHarmony device lock")
        if coordination.exists() or transport.exists():
            time.sleep(min(2, remaining(deadline, "shared OpenHarmony device lock")))
            continue
        try:
            coordination.mkdir()
            return coordination
        except FileExistsError:
            time.sleep(min(2, remaining(deadline, "shared OpenHarmony device lock")))


def unavailable_rows(contract: dict, reason: str) -> list[dict]:
    return [{"caseId": case["caseId"], "key": case["key"], "traceDigest": case["traceDigest"],
             "status": "not_scored", "reason": reason} for case in contract["cases"]]


def retain_evidence(temporary: Path, output: Path, task_id: str, removed_binaries=None) -> dict:
    if output.exists():
        raise FileExistsError(f"Refusing existing strict evidence: {output}")
    binary_suffixes = {".hap", ".har", ".app", ".apk", ".abc", ".so"}
    binaries = list(removed_binaries or [])
    for item in sorted(path for path in temporary.rglob("*") if path.is_file() and path.suffix.lower() in binary_suffixes):
        binaries.append({"path": str(item.relative_to(temporary)), "bytes": item.stat().st_size,
                         "sha256": sha256(item)})
    shutil.copytree(temporary, output, ignore=shutil.ignore_patterns("*.hap", "*.har", "*.app", "*.apk", "*.abc", "*.so"))
    files = []
    for item in sorted(path for path in output.rglob("*") if path.is_file()):
        files.append({"path": str(item.relative_to(output)), "bytes": item.stat().st_size,
                      "sha256": sha256(item)})
    manifest = {"schemaVersion": 1, "taskId": task_id, "platform": "arkts", "role": "agent",
                "binariesRetained": False, "temporaryBuildRemoved": True,
                "removedBinaryArtifacts": binaries, "files": files}
    manifest_path = output / "evidence-manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    return {"path": str(output), "manifest": str(manifest_path), "manifestSha256": sha256(manifest_path)}


def refresh_evidence_manifest(retained: dict) -> None:
    root = Path(retained['path'])
    path = Path(retained['manifest'])
    manifest = json.loads(path.read_text())
    manifest['files'] = [{**input_guard.record(item), 'path': item.relative_to(root).as_posix()}
                         for item in sorted(root.rglob('*')) if item.is_file() and item != path]
    path.write_text(json.dumps(manifest, indent=2) + '\n')
    retained['manifestSha256'] = sha256(path)


def unscored_input_row(case: dict, reason: str) -> dict:
    # Raw runtime artifacts remain retained; do not leave a prefix in `evidence`
    # that could be reinterpreted through a legacy default input attestation.
    return {'caseId': case['caseId'], 'key': case['key'], 'traceDigest': case['traceDigest'],
            'status': 'not_scored', 'reason': reason, 'failureKind': 'unverified_prospective_inputs',
            'transitionExecuted': False, 'observed': None, 'invariantChecks': [],
            'unevaluatedInvariants': case.get('invariants', []),
            'unobservedExpectedFields': list(case.get('expected', {}))}


def validate_input_pair(build_path: Path, before: dict, after: dict) -> None:
    """Continuity for any actual candidate, not only the calibrated missing-entry UI."""
    build = json.loads(build_path.read_text())
    first, last = input_guard.bound(before), input_guard.bound(after)
    for captured, phase in ((first, 'before_runtime'), (last, 'after_runtime')):
        if (captured.get('phase') != phase or captured.get('complete') is not True or
                captured.get('producer') != input_guard.record(input_guard.__file__) or
                Path(captured['candidateSource']).resolve() != Path(build['source']).resolve()):
            raise ValueError('Prospective input acquisition phase/source/producer differs')
        input_guard.ordered(captured['files'])
    if first['files'] != last['files']:
        raise ValueError('Complete enclosing candidate inputs changed during packaging/runtime')
    production = [{key: item[key] for key in ('path', 'sha256')} for item in first['files']
                  if item['path'].startswith('entry/src/main/')]
    if (input_guard.ordered(production) != input_guard.ordered(build['production']) or
            input_guard.ordered(build['nativeUIObserver']['production']) != input_guard.ordered(production)):
        raise ValueError('Actual packaged production differs from prospective complete input inventory')


def retain_input_bindings(retained: dict, captures: dict, contract: dict, deadline: float) -> tuple[dict, dict]:
    """Seal actual retained paths only after copies are verified; never recapture inputs."""
    root = Path(retained['path'])
    bindings, issues = {}, {}
    for case in contract['cases']:
        key = case['caseId']
        capture = captures.get(key, {})
        try:
            remaining(deadline, 'retained prospective input binding')
            if capture.get('error'):
                raise ValueError(capture['error'])
            refs = {}
            for phase in ('before', 'after'):
                saved = capture[phase]
                path = root / saved['relativePath']
                if not path.resolve().is_relative_to(root.resolve()):
                    raise ValueError('Prospective capture escapes retained evidence')
                current = input_guard.record(path)
                if any(current[name] != saved['artifact'][name] for name in ('bytes', 'sha256')):
                    raise ValueError('Prospective capture changed during evidence retention')
                refs[phase] = current
            build = root / key / 'device-build-report.json'
            validate_input_pair(build, refs['before'], refs['after'])
            path = root / 'prospective-inputs' / key / 'binding.json'
            binding = input_guard.seal_inputs(build, refs['before'], refs['after'], path)
            sealed = input_guard.bound(binding)
            if (sealed.get('before') != refs['before'] or sealed.get('after') != refs['after'] or
                    sealed.get('build') != input_guard.record(build)):
                raise ValueError('Retained prospective seal differs from actual build/captures')
            bindings[key] = binding
        except (OSError, ValueError, TypeError, KeyError, TimeoutError, subprocess.SubprocessError) as error:
            issues[key] = f'{type(error).__name__}: {error}'
    refresh_evidence_manifest(retained)
    return bindings, issues


def validate_build(report: dict, task_id: str, case: dict) -> None:
    if report.get("taskId") != task_id or report.get("role") != "agent" or report.get("caseId") != case["caseId"]:
        raise RuntimeError(f"Strict build identity mismatch for {case['caseId']}")
    if report.get("status") != "built_not_executed" or report.get("runtimeCompile", {}).get("passed") is not True:
        raise RuntimeError(f"Strict runtime packaging failed for {case['caseId']}")
    if report.get("productionUnchanged") is not True or report.get("copiedProductionUnchanged") is not True:
        raise RuntimeError(f"Evaluator changed candidate production for {case['caseId']}")
    if report.get("nativeUIObserver", {}).get("productionUnchanged") is not True:
        raise RuntimeError(f"Native evaluator provenance incomplete for {case['caseId']}")


def extract_row(execution: dict, case: dict) -> dict:
    if execution.get("status") != "transport_completed" or execution.get("transportCompleted") is not True:
        raise RuntimeError(f"Device transport incomplete for {case['caseId']}")
    if execution.get("candidateAbsentBeforeInstall") is not True:
        raise RuntimeError(f"Fresh install was not established for {case['caseId']}")
    if execution.get("cleanup", {}).get("ownedAppUninstalled") is not True:
        raise RuntimeError(f"Owned candidate app was not removed for {case['caseId']}")
    rows = [row for row in execution.get("rows", []) if row.get("caseId") == case["caseId"] and
            row.get("traceDigest") == case["traceDigest"]]
    if len(rows) != 1 or rows[0].get("status") not in {"pass", "fail", "not_scored"}:
        raise RuntimeError(f"Canonical row missing for {case['caseId']}")
    return rows[0]


def retryable_environment_failure(execution: dict) -> bool:
    error = str(execution.get("error", ""))
    return (execution.get("cleanup", {}).get("ownedAppUninstalled") is True and
            any(token in error for token in (
                "Unexpected end of JSON input",
                "ui-preflight-tree command failed",
                "ui-preflight-dump command failed",
            )))


def score(*, task_id: str, source: Path, output: Path, deadline: float, contract_path: Path,
          build_script: Path, device_serial: Optional[str] = None) -> dict:
    source, output = source.resolve(), output.resolve()
    contract_path, build_script = contract_path.resolve(), build_script.resolve()
    contract = json.loads(contract_path.read_text())
    if contract.get("taskId") != task_id:
        raise ValueError("Strict contract task identity mismatch")
    evidence_output = output.with_name(output.stem + "_evidence")
    if output.exists() or evidence_output.exists():
        raise FileExistsError("Refusing to overwrite scorer output or evidence")
    runtime_compile = False
    transport = "not_run"
    rows: list[dict] = []
    failure = None
    executions = []
    removed_binaries = []
    prospective = task_id in {'16_identity_reset', '17_pinned_messages'}
    captures: dict[str, dict] = {}
    input_bindings, input_issues = {}, {}
    built_cases = 0
    with tempfile.TemporaryDirectory(prefix=f"ltb-{task_id}-arkts-agent-") as raw:
        temporary = Path(raw)
        try:
            serial = None
            for case in contract["cases"]:
                if shutil.disk_usage(temporary).free < 8 * 1024 ** 3:
                    raise RuntimeError('Storage protection: less than 8 GiB free before strict device packaging')
                if prospective:
                    capture = captures.setdefault(case['caseId'], {})
                    capture_root = temporary / 'prospective-inputs' / case['caseId']
                    capture_root.mkdir(parents=True)
                    try:
                        remaining(deadline, 'before-runtime complete candidate inventory')
                        before_path = capture_root / 'before.json'
                        before = input_guard.capture_inputs(source, before_path, phase='before_runtime', deadline=deadline)
                        capture['before'] = {'relativePath': before_path.relative_to(temporary).as_posix(), 'artifact': before}
                    except (OSError, ValueError, TimeoutError, subprocess.SubprocessError) as error:
                        capture['error'] = f'Before-runtime capture failed: {type(error).__name__}: {error}'
                        rows.append(unscored_input_row(case, capture['error']))
                        continue
                case_root = temporary / case["caseId"]
                command = [NODE, str(build_script), "--source", str(source), "--role", "agent",
                           "--case", case["caseId"], "--output-dir", str(case_root)]
                process = subprocess.run(command, cwd=ROOT, timeout=remaining(deadline, "strict ArkTS build"), check=False)
                report_path = case_root / "device-build-report.json"
                if process.returncode or not report_path.is_file():
                    raise RuntimeError(f"Strict build process failed for {case['caseId']}: {process.returncode}")
                report = json.loads(report_path.read_text())
                validate_build(report, task_id, case)
                built_cases += 1
                if serial is None:
                    serial = discover_device(device_serial, deadline)
                execution = None
                execution_path = None
                for attempt in range(1, 21):
                    lock = acquire_device(serial, deadline)
                    try:
                        execution_root = report_path.parent / f"execute-attempt-{attempt}"
                        command = [NODE, str(ROOT / "scripts/runtime_semantics/arkts_device_execute.cjs"),
                                   str(report_path), serial, str(execution_root)]
                        environment = dict(os.environ)
                        environment["LTB_DEVICE_LOCK_PREACQUIRED"] = "1"
                        process = subprocess.run(command, cwd=ROOT, env=environment,
                                                 timeout=remaining(deadline, "strict ArkTS device execution"),
                                                 check=False)
                        candidate_path = execution_root / "device-execution.json"
                        candidate = json.loads(candidate_path.read_text()) if candidate_path.is_file() else {}
                    finally:
                        if lock.exists():
                            lock.rmdir()
                    if process.returncode == 0 and candidate_path.is_file():
                        execution, execution_path = candidate, candidate_path
                        break
                    if ("EEXIST" in str(candidate.get("error", "")) or
                            retryable_environment_failure(candidate)) and attempt < 20:
                        continue
                    raise RuntimeError(f"Strict execution failed for {case['caseId']}: " +
                                       str(candidate.get("error", process.returncode)))
                if execution is None or execution_path is None:
                    raise RuntimeError(f"Device lock retries exhausted for {case['caseId']}")
                row = extract_row(execution, case)
                if prospective:
                    try:
                        remaining(deadline, 'after-runtime complete candidate inventory')
                        after_path = capture_root / 'after.json'
                        after = input_guard.capture_inputs(source, after_path, phase='after_runtime', deadline=deadline)
                        capture['after'] = {'relativePath': after_path.relative_to(temporary).as_posix(), 'artifact': after}
                    except (OSError, ValueError, TimeoutError, subprocess.SubprocessError) as error:
                        capture['error'] = f'After-runtime capture failed: {type(error).__name__}: {error}'
                        row = unscored_input_row(case, capture['error'])
                rows.append(row)
                executions.append({"caseId": case["caseId"], "report": str(execution_path.relative_to(temporary))})
                binary_suffixes = {".hap", ".har", ".app", ".apk", ".abc", ".so"}
                for artifact in sorted(path for path in case_root.rglob("*")
                                       if path.is_file() and path.suffix.lower() in binary_suffixes):
                    removed_binaries.append({"path": str(artifact.relative_to(temporary)),
                                             "bytes": artifact.stat().st_size,
                                             "sha256": sha256(artifact)})
                    artifact.unlink()
            runtime_compile = built_cases == len(contract['cases'])
            transport = ('transport_completed' if len(executions) == len(contract['cases']) else
                         'partial' if executions else 'not_run')
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
            failure = f"{type(error).__name__}: {error}"
        retained = retain_evidence(temporary, evidence_output, task_id, removed_binaries)
        if prospective:
            input_bindings, input_issues = retain_input_bindings(retained, captures, contract, deadline)

    if failure:
        rows = unavailable_rows(contract, failure)
    elif prospective:
        rows = [unscored_input_row(case, input_issues[case['caseId']]) if case['caseId'] in input_issues else row
                for case, row in zip(contract['cases'], rows)]
    publishable = (failure is None and runtime_compile and transport == "transport_completed" and
                   len(rows) == len(contract["cases"]) and all(row["status"] in {"pass", "fail"} for row in rows))
    report = {
        "schemaVersion": 2, "taskId": task_id, "platform": "arkts", "role": "agent",
        "observationMode": "runtime_state_transition",
        "runtimeCompile": {"passed": runtime_compile, "status": "passed" if runtime_compile else "failed",
                           "scope": "strict evaluator candidate application and ohosTest packaging",
                           "builds": built_cases, "artifactsRetained": False},
        "semantic": {"cases": rows},
        "provenance": {"candidateMode": "standalone_directory", "candidateSource": str(source),
                       "canonicalContract": {"path": str(contract_path), "sha256": sha256(contract_path)},
                       "strictEvidence": retained, "executions": executions},
        "diagnostics": {"adapter": "ready" if failure is None else "failed", "transport": transport,
                        "publishableWithoutApplicationCompile": publishable,
                        "applicationCompileOwnedByParentRunner": True,
                        "environmentFailureIsNotSemanticFailure": True,
                        "cleanup": {"temporaryBuildRemoved": True, "binariesRetained": False},
                        "reason": failure},
    }
    if prospective:
        report['provenance'].update(entryInputBindingMode='prospective_required',
                                   entryInputBindings=input_bindings,
                                   entryInputProducer=input_guard.record(__file__))
        report['diagnostics']['prospectiveInputIssues'] = input_issues
    if failure is None:
        try:
            if prospective:
                attach_entries(report, contract, input_bindings=input_bindings)
            else:
                attach_entries(report, contract)
            used = set()
            for row in report['semantic']['cases']:
                if row.get('entryFailureEvidence'):
                    validate_entry_failure(row, report, used, contract=contract)
            report['diagnostics']['publishableWithoutApplicationCompile'] = all(
                row['status'] in {'pass', 'fail'} for row in report['semantic']['cases'])
        except (KeyError, OSError, ValueError) as error:
            failure = 'Runtime entry verification failed: ' + str(error)
            report['semantic']['cases'] = unavailable_rows(contract, failure)
            report['diagnostics'].update(publishableWithoutApplicationCompile=False,
                                         adapter='failed', reason=failure)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n")
    return report
