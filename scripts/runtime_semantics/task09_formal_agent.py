#!/usr/bin/env python3
"""Source-bound formal agent scorer for Task09.

The shared runtime entrypoint dispatches Task09 agent scoring here. This module
accepts exactly one candidate tree and preserves standalone application build
status separately from evaluator packaging/runtime compilation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TASK_ID = "09_spaces_lifecycle"
CONTRACT = ROOT / "benchmark_tasks" / TASK_ID / "transitions.json"
ANDROID_RUNNER = ROOT / "scripts" / "runtime_semantics" / "task09_android_strict_runner.py"
ARKTS_RUNNER = ROOT / "scripts" / "runtime_semantics" / "task09_arkts_strict_runner.cjs"
NODE = Path("/Applications/DevEco-Studio.app/Contents/tools/node/bin/node")


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def file_record(path: Path) -> dict:
    content = path.read_bytes()
    return {"path": str(path.resolve()), "bytes": len(content),
            "sha256": hashlib.sha256(content).hexdigest()}


def canonical_rows(contract: dict, reason: str) -> list[dict]:
    return [{
        "caseId": case["caseId"],
        "key": case["key"],
        "traceDigest": case["traceDigest"],
        "status": "not_scored",
        "reason": reason,
        "checkpoints": [],
        "observed": {},
        "invariantChecks": [],
    } for case in contract["cases"]]


def validate_runtime_report(report: dict, contract: dict, candidate: Path, platform: str) -> None:
    expected = [(case["caseId"], case["traceDigest"]) for case in contract["cases"]]
    rows = report.get("semantic", {}).get("cases", [])
    actual = [(row.get("caseId"), row.get("traceDigest")) for row in rows]
    if report.get("taskId") != TASK_ID or report.get("platform") != platform:
        raise ValueError("runtime report task/platform identity mismatch")
    if report.get("role") != "agent" or report.get("observationMode") != "runtime_state_transition":
        raise ValueError("runtime report is not an agent runtime-state-transition result")
    if actual != expected or len(rows) != 9:
        raise ValueError("runtime report does not contain the nine canonical Task09 cases in order")
    if any(row.get("status") not in {"pass", "fail"} for row in rows):
        raise ValueError("formal Task09 agent result requires nine pass/fail verdicts")
    target = report.get("target") or report.get("source") or report.get("provenance", {}).get("source")
    if target is None or Path(target).resolve() != candidate:
        raise ValueError("runtime report is not bound to the supplied candidate")
    if report.get("diagnostics", {}).get("adapter") in {"failed", "adapter_failed", "incomplete"}:
        raise ValueError("runtime adapter/transport was not ready")
    if report.get("publication", {}).get("eligible") is False:
        raise ValueError("runtime publication/cleanup gate failed")
    lease = report.get("deviceLease")
    if lease is not None and (len(lease.get("acquisitions", [])) != 9 or
                              len(lease.get("releases", [])) != 9 or
                              report.get("deviceLocksPresentAfter") != []):
        raise ValueError("runtime device lease cleanup is incomplete")


def retain_incomplete_runtime(report: dict, contract: dict, candidate: Path,
                              platform: str, diagnostics: dict) -> dict:
    """Retain source-bound diagnostics without converting partial rows into scores."""
    target = report.get("target") or report.get("source") or report.get("provenance", {}).get("source")
    if (report.get("taskId") != TASK_ID or report.get("platform") != platform or
            report.get("role") != "agent" or target is None or Path(target).resolve() != candidate):
        raise ValueError("incomplete runtime report identity/candidate binding mismatch")
    expected = {case["caseId"]: case["traceDigest"] for case in contract["cases"]}
    retained = []
    for row in report.get("rows", []):
        case_id = row.get("caseId")
        if case_id not in expected or row.get("traceDigest") != expected[case_id]:
            raise ValueError("incomplete runtime report contains an unbound row")
        retained.append({
            "caseId": case_id,
            "traceDigest": row["traceDigest"],
            "status": row.get("status"),
            "execution": row.get("execution"),
            "transportAttempts": row.get("transportAttempts", []),
        })
    diagnostics.update({
        "runtimeStatus": report.get("status"),
        "runtimeError": report.get("error"),
        "runtimePublication": report.get("publication"),
        "completedRuntimeRows": retained,
        "completedRuntimeRowCount": len(retained),
        "runtimeHapCleanup": report.get("hapCleanup", []),
        "partialRowsAreDiagnosticOnly": True,
    })
    child_runtime_compile = report.get("runtimeCompile")
    if isinstance(child_runtime_compile, dict):
        return child_runtime_compile
    return {"passed": None, "status": "missing",
            "scope": "evaluator_test_packaging_and_runtime_build"}


def unavailable(contract: dict, platform: str, candidate: Path, compile_result: dict,
                runtime_compile: dict, reason: str, diagnostics: dict, elapsed: float) -> dict:
    return {
        "schemaVersion": 2,
        "taskId": TASK_ID,
        "platform": platform,
        "role": "agent",
        "target": str(candidate),
        "observationMode": "runtime_state_transition",
        "compile": compile_result,
        "runtimeCompile": runtime_compile,
        "semantic": {"total": 9, "passed": 0, "failed": 0, "notScored": 9,
                     "cases": canonical_rows(contract, reason)},
        "publication": {"eligible": False, "reason": reason},
        "diagnostics": {**diagnostics, "adapter": "failed", "reason": reason,
                        "totalElapsedSeconds": elapsed},
    }


def score(*, platform: str, source: Path, output: Path, timeout: float,
          compile_passed: bool | None, compile_command: str,
          run=subprocess.run, monotonic=time.monotonic) -> dict:
    started = monotonic()
    contract = load(CONTRACT)
    candidate = source.resolve()
    compile_result = {
        "passed": compile_passed,
        "status": "passed" if compile_passed is True else "failed" if compile_passed is False else "not_provided",
        "scope": "standalone_candidate_application_build",
        "command": compile_command,
        "source": "formal_scorer_cli",
    }
    diagnostics = {"candidate": str(candidate), "timeoutSeconds": timeout,
                   "budgetClock": "time.monotonic", "runtimeReport": str(output.with_suffix(".runtime.json"))}
    runtime_compile = {"passed": None, "status": "not_run", "scope": "evaluator_test_packaging_and_runtime_build"}

    def remaining() -> float:
        value = timeout - (monotonic() - started)
        if value <= 0:
            raise TimeoutError("Task09 formal score exhausted its total monotonic budget")
        return value

    reason = None
    if not candidate.is_dir():
        reason = "Candidate source directory is unavailable"
    elif compile_passed is not True:
        reason = "Standalone candidate application build did not pass; semantic result is not publishable"
    if reason:
        return unavailable(contract, platform, candidate, compile_result, runtime_compile, reason,
                           diagnostics, monotonic() - started)

    runtime_output = output.with_suffix(".runtime.json")
    if platform == "android":
        command = [sys.executable, str(ANDROID_RUNNER), "--role", "agent",
                   "--source", str(candidate), "--output", str(runtime_output)]
    elif platform == "arkts":
        command = [str(NODE), str(ARKTS_RUNNER), "--role", "agent", "--source", str(candidate),
                   "--output", str(runtime_output)]
    else:
        raise ValueError("platform must be android or arkts")
    budget = remaining()
    command += ["--timeout", str(max(1, int(budget)))]
    diagnostics["runtimeCommand"] = command
    diagnostics["runtimeBudgetSeconds"] = budget
    try:
        completed = run(command, timeout=remaining(), check=False, capture_output=True, text=True)
        diagnostics["runtimeExitCode"] = completed.returncode
        diagnostics["runtimeStdout"] = completed.stdout
        diagnostics["runtimeStderr"] = completed.stderr
        runtime = None
        if runtime_output.is_file():
            diagnostics["runtimeReportArtifact"] = file_record(runtime_output)
            try:
                runtime = load(runtime_output)
                runtime_compile = retain_incomplete_runtime(
                    runtime, contract, candidate, platform, diagnostics)
                diagnostics["runtimeReportedCompile"] = runtime.get("compile")
            except (OSError, ValueError, json.JSONDecodeError) as report_error:
                diagnostics["runtimeReportReadError"] = f"{type(report_error).__name__}: {report_error}"
                runtime = None
        if completed.returncode != 0 or runtime is None:
            detail = diagnostics.get("runtimeError") or diagnostics.get("runtimeReportReadError")
            suffix = f": {detail}" if detail else ""
            raise RuntimeError(f"Task09 runtime evaluator failed with exit {completed.returncode}{suffix}")
        if runtime_compile.get("passed") is not True or runtime_compile.get("status") != "passed":
            raise RuntimeError("Task09 evaluator test packaging/runtime build did not pass")
        validate_runtime_report(runtime, contract, candidate, platform)
        rows = runtime["semantic"]["cases"]
        passed = sum(row["status"] == "pass" for row in rows)
        failed = sum(row["status"] == "fail" for row in rows)
        result = {
            **runtime,
            "compile": compile_result,
            "runtimeCompile": runtime_compile,
            "target": str(candidate),
            "semantic": {"total": 9, "passed": passed, "failed": failed, "notScored": 0, "cases": rows},
            "publication": {"eligible": True, "reason": "Standalone application build and all nine runtime verdicts are available"},
            "diagnostics": {**runtime.get("diagnostics", {}), **diagnostics,
                            "adapter": "ready", "totalElapsedSeconds": monotonic() - started},
        }
        return result
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError, TimeoutError) as error:
        reason = f"{type(error).__name__}: {error}"
        return unavailable(contract, platform, candidate, compile_result, runtime_compile, reason,
                           diagnostics, monotonic() - started)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--platform", required=True, choices=("android", "arkts"))
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--timeout", type=float, default=3600)
    parser.add_argument("--compile-passed", choices=("true", "false"), required=True)
    parser.add_argument("--compile-command", default="not recorded")
    args = parser.parse_args()
    report = score(platform=args.platform, source=args.source, output=args.output.resolve(), timeout=args.timeout,
                   compile_passed=args.compile_passed == "true", compile_command=args.compile_command)
    write(args.output.resolve(), report)
    print(json.dumps({"output": str(args.output.resolve()), "semantic": {
        key: report["semantic"][key] for key in ("passed", "failed", "notScored")},
        "publishable": report["publication"]["eligible"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
