#!/usr/bin/env python3
"""Task09 source-bound Android runtime scorer with strict supplemental closure."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import time
import re


ROOT = Path(__file__).resolve().parents[2]
TASK = "09_spaces_lifecycle"
CONTRACT = ROOT / "benchmark_tasks" / TASK / "transitions.json"
PRIMARY = ROOT / "scripts/runtime_semantics/android_runner.py"
RENDERED = ROOT / "state_tests/runtime/android/09_spaces_lifecycle/rendered/run.py"
NAVIGATION = ROOT / "state_tests/runtime/android/09_spaces_lifecycle/navigation/run.py"
ENTRY_RUNNER = ROOT / 'state_tests/runtime/android/09_spaces_lifecycle/actual_render_prefix/run.py'
_ENTRY_SPEC = importlib.util.spec_from_file_location('task09_android_reviewed_entry',
    Path(__file__).with_name('task09_android_entry_evidence.py'))
entry_policy = importlib.util.module_from_spec(_ENTRY_SPEC)
_ENTRY_SPEC.loader.exec_module(entry_policy)


def entry_adapter_compatible(source: Path, role: str) -> bool:
    """Select compile-compatible API plumbing only; no semantic verdict by source shape."""
    path = 'features/home/impl/src/main/kotlin/io/element/android/features/home/impl/HomePresenter.kt'
    try:
        if (source / 'gradlew').is_file():
            text = (source / path).read_text()
        else:
            if role == 'agent':
                return False
            task = load(ROOT / 'benchmark_tasks' / TASK / 'task.json')
            ref = task['android']['finalCommit' if role == 'final' else 'baseCommit']
            text = subprocess.check_output(['git', '-C', str(source), 'show', f'{ref}:{path}'], text=True)
        match = re.search(r'class\s+HomePresenter[^\{]*?\((.*?)\)\s*:\s*Presenter<HomeState>', text, re.S)
        return bool(match and re.findall(r'private\s+val\s+(\w+)\s*:', match[1]) == [
            'client', 'syncService', 'snackbarDispatcher', 'indicatorService', 'roomListPresenter',
            'logoutPresenter', 'rageshakeFeatureAvailability', 'featureFlagService'])
    except (OSError, ValueError, subprocess.SubprocessError):
        return False


def actual_entry_report(raw: dict, raw_path: Path, report: dict, contract: dict,
                        binding_record=None) -> bool:
    """Only complete real render evidence can short-circuit lifecycle execution."""
    if raw.get('status') != 'passed':
        return False
    rows = entry_policy.entry_rows(raw, raw_path, contract, binding_record=binding_record)
    failed = sum(row['status'] == 'fail' for row in rows)
    unscored = len(rows) - failed
    report.update(provenance=raw['provenance'], semantic={'total': len(rows), 'passed': 0, 'failed': failed,
        'notScored': unscored, 'cases': rows}, runtimeCompile={'passed': True, 'status': 'passed',
        'scope': 'original HomeView/Scaffold/HomePresenter actual Compose rendering'},
        diagnostics={'adapter': 'unbound_ui' if unscored else 'ready', 'uiCoverage': not unscored,
                     'entryRuntime': record(raw_path),
                     'canonicalPostStateObserved': False, 'canonicalInvariantsEvaluated': False},
        status='not_publishable' if unscored else 'scored', publication={'eligible': not unscored,
            'reason': 'Unknown UI/input closure is not evidence of missing functionality.' if unscored else
                      'Independent real click prefixes with closed original UI/input binding establish unavailable entry.'})
    used = set()
    for row in rows:
        if row['status'] == 'fail':
            entry_policy.validate_entry_failure(row, report, used, contract)
    return True


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def record(path: Path) -> dict:
    data = path.read_bytes()
    return {"path": str(path.resolve()), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def canonical_ns(contract: dict, reason: str) -> list[dict]:
    return [{"caseId": case["caseId"], "key": case["key"], "traceDigest": case["traceDigest"],
             "status": "not_scored", "reason": reason, "observed": {}, "checkpoints": [],
             "invariantChecks": []} for case in contract["cases"]]


def validated_supplemental_row(report: dict, *, key: str, role: str, source: Path,
                               contract: dict, contract_sha256: str) -> dict:
    if report.get("taskId") != TASK or report.get("platform") != "android" or report.get("role") != role:
        raise RuntimeError(f"Task09 {key} supplemental identity mismatch")
    provenance = report.get("provenance", {})
    declared_source = report.get("source") or report.get("target") or provenance.get("source")
    if declared_source is None or Path(declared_source).resolve() != source:
        raise RuntimeError(f"Task09 {key} supplemental is not bound to the candidate source")
    declared_contract = report.get("contractSha256") or provenance.get("contractSha256") or \
        provenance.get("canonicalContract", {}).get("sha256")
    if declared_contract != contract_sha256:
        raise RuntimeError(f"Task09 {key} supplemental contract hash mismatch")
    if report.get("runtimeCompile", {}).get("status") != "passed":
        raise RuntimeError(f"Task09 {key} supplemental packaging/runtime execution failed")
    rows = report.get("semantic", {}).get("cases", [])
    matches = [row for row in rows if row.get("key") == key]
    if len(matches) != 1:
        raise RuntimeError(f"Task09 {key} supplemental did not return exactly one canonical row")
    row = matches[0]
    spec = next(case for case in contract["cases"] if case["key"] == key)
    if row.get("caseId") != spec["caseId"] or row.get("traceDigest") != spec["traceDigest"] or \
            row.get("status") not in {"pass", "fail"}:
        raise RuntimeError(f"Task09 {key} supplemental row is not a scored canonical verdict")
    return row


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--role", required=True, choices=("base", "final", "agent"))
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--timeout", type=float, default=3600)
    args = parser.parse_args()
    started = time.monotonic()
    source = args.source.resolve()
    output = args.output.resolve()
    evidence = output.with_suffix(".evidence")
    contract = load(CONTRACT)
    if output.exists() or evidence.exists():
        raise FileExistsError(f"Refusing existing Task09 Android evidence: {output}")
    evidence.mkdir(parents=True)
    commands = []

    def remaining() -> float:
        value = args.timeout - (time.monotonic() - started)
        if value <= 0:
            raise TimeoutError("Task09 Android score exhausted its total monotonic budget")
        return value

    def run(name: str, command: list[str]) -> tuple[subprocess.CompletedProcess, Path]:
        budget = remaining()
        completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True,
                                   timeout=budget, check=False)
        log = evidence / f"{name}.log"
        log.write_text((completed.stdout or "") + (completed.stderr or ""), encoding="utf-8")
        commands.append({"name": name, "command": command, "budgetSeconds": budget,
                         "exitCode": completed.returncode, "log": record(log)})
        return completed, log

    report = {"schemaVersion": 2, "taskId": TASK, "platform": "android", "role": args.role,
              "source": str(source), "target": str(source), "observationMode": "runtime_state_transition",
              "timeoutSeconds": args.timeout, "budgetClock": "time.monotonic remaining across all runtime slices",
              "contract": record(CONTRACT), "compile": {"passed": None, "status": "not_provided",
                  "scope": "standalone application build supplied by caller"},
              "runtimeCompile": {"passed": False, "status": "not_run",
                  "scope": "candidate production slices and evaluator packaging"},
              "commands": commands, "publication": {"eligible": False}}
    exit_code = 0
    try:
        if not source.is_dir():
            raise FileNotFoundError("Task09 Android candidate source directory is unavailable")
        if entry_adapter_compatible(source, args.role):
            guard = entry_policy.binding_guard
            before = None
            if (source / 'gradlew').is_file():
                before = guard.write_inventory(source, evidence / 'candidate-inputs-before.json',
                                               deadline=started + args.timeout)
            prefix_file = evidence / 'actual-home-entry/runtime.json'
            command = [sys.executable, str(ENTRY_RUNNER), '--source', str(source), '--role', args.role,
                       '--output', str(prefix_file), '--timeout', str(max(1, int(remaining())))]
            run('actual-home-entry', command)
            if prefix_file.is_file():
                prefix = load(prefix_file)
                binding = None
                if prefix.get('status') == 'passed':
                    binding_path = evidence / 'candidate-inputs-binding.json'
                    if before is not None:
                        after = guard.write_inventory(source, evidence / 'candidate-inputs-after.json',
                                                      deadline=started + args.timeout)
                        binding = guard.seal_live_binding(source, prefix_file, before, after, binding_path)
                    else:
                        binding = guard.immutable_binding(prefix, prefix_file, binding_path)
                if actual_entry_report(prefix, prefix_file, report, contract, binding_record=binding):
                    # An unknown, even healthy placeholder UI must not fall through
                    # to another adapter and become a synthetic feature failure.
                    return 0 if report['publication']['eligible'] else 1
        primary_file = evidence / "primary.json"
        primary_command = [sys.executable, str(PRIMARY), "--task", TASK, "--role", args.role,
                           "--source", str(source), "--output", str(primary_file),
                           "--timeout", str(max(1, int(remaining())))]
        completed, _ = run("primary", primary_command)
        if not primary_file.is_file():
            raise RuntimeError(f"Primary Task09 runtime produced no report (exit {completed.returncode})")
        primary = load(primary_file)
        if primary.get("runtimeCompile", {}).get("passed") is not True or \
                primary.get("diagnostics", {}).get("adapter") not in {"ready", "runtime_failed"}:
            raise RuntimeError("Primary Task09 evaluator packaging/runtime compilation failed")
        rows = {row["key"]: dict(row) for row in primary["semantic"]["cases"]}
        if any(entry_policy.legacy_projection(row) for row in rows.values()):
            raise RuntimeError('Withdrawn Task09 Android synthetic base projection; actual HomeView entry proof required')
        contract_sha256 = report["contract"]["sha256"]
        case7 = rows["bulk_and_toggle_selection"]
        if case7.get("status") == "not_scored" and args.role != "base":
            rendered_file = evidence / "rendered.json"
            rendered_command = [sys.executable, str(RENDERED), "--source", str(source),
                                "--role", args.role, "--output", str(rendered_file),
                                "--timeout", str(max(1, int(remaining())))]
            rendered_completed, _ = run("rendered", rendered_command)
            if not rendered_file.is_file():
                raise RuntimeError(
                    f"Task09 rendered evaluator produced no report (exit {rendered_completed.returncode})")
            rendered = load(rendered_file)
            rows["bulk_and_toggle_selection"] = validated_supplemental_row(
                rendered, key="bulk_and_toggle_selection", role=args.role, source=source,
                contract=contract, contract_sha256=contract_sha256)
            report["rendered"] = {"report": record(rendered_file),
                                  "runtimeCompile": rendered.get("runtimeCompile")}
        case9 = rows["leave_selected_rooms"]
        if case9.get("status") == "not_scored" and args.role != "base":
            navigation_file = evidence / "navigation.json"
            navigation_command = [sys.executable, str(NAVIGATION), "--source", str(source),
                                  "--role", args.role, "--output", str(navigation_file),
                                  "--timeout", str(max(1, int(remaining())))]
            nav_completed, _ = run("navigation", navigation_command)
            if not navigation_file.is_file():
                raise RuntimeError(f"Task09 navigation evaluator produced no report (exit {nav_completed.returncode})")
            navigation = load(navigation_file)
            rows["leave_selected_rooms"] = validated_supplemental_row(
                navigation, key="leave_selected_rooms", role=args.role, source=source,
                contract=contract, contract_sha256=contract_sha256)
            report["navigation"] = {"report": record(navigation_file),
                                    "runtimeCompile": navigation.get("runtimeCompile")}
        ordered = [rows[case["key"]] for case in contract["cases"]]
        if any(row.get("status") not in {"pass", "fail"} for row in ordered):
            raise RuntimeError("Task09 strict Android evaluator lacks one or more pass/fail verdicts")
        counts = {"total": 9, "passed": sum(row["status"] == "pass" for row in ordered),
                  "failed": sum(row["status"] == "fail" for row in ordered), "notScored": 0,
                  "cases": ordered}
        report.update(provenance=primary.get("provenance", {}), semantic=counts,
                      diagnostics={**primary.get("diagnostics", {}), "adapter": "ready",
                                   "primaryReport": record(primary_file)},
                      runtimeCompile={"passed": True, "status": "passed",
                                      "scope": "candidate production slices and evaluator packaging"},
                      status="scored", publication={"eligible": True,
                          "reason": "All nine source-bound runtime verdicts are available"})
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError, TimeoutError) as error:
        reason = f"{type(error).__name__}: {error}"
        report.update(status="not_publishable", error=reason,
                      semantic={"total": 9, "passed": 0, "failed": 0, "notScored": 9,
                                "cases": canonical_ns(contract, reason)},
                      diagnostics={"adapter": "failed", "reason": reason},
                      publication={"eligible": False, "reason": reason})
        exit_code = 1
    finally:
        report["elapsedSeconds"] = round(time.monotonic() - started, 3)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        (evidence / "matrix.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), "semantic": {key: report["semantic"][key]
          for key in ("passed", "failed", "notScored")}, "elapsedSeconds": report["elapsedSeconds"]}))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
