#!/usr/bin/env python3
"""Fail-closed, source-parameterized formal Task08 Android evaluator wrapper."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

try:
    from .task08_android_runtime_evidence import validate_report_evidence
except ImportError:
    from task08_android_runtime_evidence import validate_report_evidence


ROOT = Path(__file__).resolve().parents[2]
TASK_ID = "08_threads"
CONTRACT_PATH = ROOT / "benchmark_tasks/08_threads/transitions.json"
TASK_PATH = ROOT / "benchmark_tasks/08_threads/task.json"
ADAPTER_PATH = ROOT / "state_tests/runtime/android/08_threads/adapter.json"
ANDROID_RUNNER = ROOT / "scripts/runtime_semantics/android_runner.py"
LEGACY_ADAPTER_WITHDRAWN = True


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def directory_digest(root):
    digest = hashlib.sha256()
    excluded = {".git", ".gradle", "build", ".idea"}
    for path in sorted(Path(root).rglob("*")):
        relative = path.relative_to(root)
        if not path.is_file() or any(part in excluded for part in relative.parts):
            continue
        name = relative.as_posix().encode()
        data = path.read_bytes()
        digest.update(len(name).to_bytes(8, "big"))
        digest.update(name)
        digest.update(len(data).to_bytes(8, "big"))
        digest.update(data)
    return digest.hexdigest()


def unavailable_rows(contract, reason):
    return [{
        "caseId": case["caseId"],
        "key": case["key"],
        "traceDigest": case["traceDigest"],
        "status": "not_scored",
        "observed": None,
        "checkpoints": [],
        "invariantChecks": [],
        "unevaluatedExpectedFields": list(case["expected"]),
        "unevaluatedInvariants": case["invariants"],
        "reason": reason,
    } for case in contract["cases"]]


def run(source, role, output, timeout):
    started = time.monotonic()
    deadline = started + timeout
    source = Path(source).resolve()
    output = Path(output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    contract = json.loads(CONTRACT_PATH.read_text())
    adapter_report_path = output.parent / "adapter-report.json"
    log_path = output.parent / "adapter-process.log"
    failure = None
    adapter_report = None

    if LEGACY_ADAPTER_WITHDRAWN:
        failure = (
            "Task08 Android legacy projection adapter withdrawn; original RoomFlow/UI "
            "runtime executor is being rebound. No old adapter fallback is permitted."
        )
    elif role == "agent" and (not source.is_dir() or (source / ".git").is_file()):
        failure = "Agent source must be a standalone candidate project directory."
    else:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            failure = "Task08 Android strict score budget expired before adapter start."
        else:
            command = [
                sys.executable, str(ANDROID_RUNNER), "--task", TASK_ID, "--role", role,
                "--source", str(source), "--output", str(adapter_report_path),
                "--timeout", str(remaining), "--no-supplemental",
            ]
            try:
                completed = subprocess.run(
                    command, cwd=ROOT, capture_output=True, text=True,
                    timeout=remaining, check=False,
                )
                log_path.write_text(completed.stdout + completed.stderr)
                if completed.returncode != 0 or not adapter_report_path.is_file():
                    failure = f"Strict Android adapter transport failed with exit {completed.returncode}."
                else:
                    adapter_report = json.loads(adapter_report_path.read_text())
            except (OSError, subprocess.SubprocessError) as error:
                failure = f"Strict Android adapter environment failed: {error}"
                log_path.write_text(str(error) + "\n")

    runtime_compile = ((adapter_report or {}).get("runtimeCompile") or {
        "passed": None,
        "status": "not_run",
        "scope": "task08_strict_production_state_transition",
    })
    candidate = {
        "candidateMode": "standalone_directory" if role == "agent" else "immutable_role_source",
        "candidateSource": str(source),
        "archivedPatchApplied": False,
    }
    if role == "agent" and source.is_dir():
        candidate["candidateRootSha256"] = directory_digest(source)

    rows = (adapter_report or {}).get("semantic", {}).get("cases", [])
    expected_identity = [(case["caseId"], case["key"], case["traceDigest"])
                         for case in contract["cases"]]
    observed_identity = [(case.get("caseId"), case.get("key"), case.get("traceDigest"))
                         for case in rows]
    adapter_ready = ((adapter_report or {}).get("diagnostics", {}).get("adapter") == "ready")
    fully_scored = (observed_identity == expected_identity and
                    all(case.get("status") in {"pass", "fail"} for case in rows))
    provenance = (adapter_report or {}).get("provenance", {})
    source_bound = True
    if role == "agent":
        source_bound = (provenance.get("candidateMode") == "standalone_directory" and
                        provenance.get("archivedPatchApplied") is False and
                        provenance.get("candidateRootSha256") == candidate.get("candidateRootSha256"))
    else:
        task = json.loads(TASK_PATH.read_text())
        expected_commit = task["android"]["baseCommit" if role == "base" else "finalCommit"]
        source_bound = provenance.get("commit") == expected_commit and bool(provenance.get("tree"))
    runtime_evidence_ready = False
    if adapter_report is not None:
        try:
            validate_report_evidence(adapter_report, contract)
            runtime_evidence_ready = fully_scored
        except ValueError as error:
            failure = str(error)
    strict_ready = (failure is None and runtime_compile.get("passed") is True and
                    adapter_ready and fully_scored and source_bound and runtime_evidence_ready)
    if not strict_ready:
        if failure is None:
            gaps = []
            if runtime_compile.get("passed") is not True:
                gaps.append("runtimeCompile")
            if not adapter_ready:
                gaps.append("adapter")
            if not fully_scored:
                gaps.append("nineCanonicalRows")
            if not source_bound:
                gaps.append("candidateProvenance")
            if not runtime_evidence_ready:
                gaps.append("reviewedRoomFlowUiRuntime")
            failure = "Strict Android evaluator incomplete: " + ", ".join(gaps)
        rows = unavailable_rows(contract, failure)

    report = {
        "schemaVersion": 2,
        "taskId": TASK_ID,
        "platform": "android",
        "role": role,
        "observationMode": "runtime_state_transition",
        "runtimeCompile": runtime_compile,
        "semantic": {"cases": rows},
        "provenance": {
            **candidate,
            "canonicalContract": {"path": str(CONTRACT_PATH), "sha256": sha256(CONTRACT_PATH)},
            "strictAdapter": {"path": str(ADAPTER_PATH), "sha256": sha256(ADAPTER_PATH)},
            "adapterReport": str(adapter_report_path) if adapter_report_path.is_file() else None,
            "runtimeAdapter": provenance,
            "runtimeEvidencePolicy": {
                "path": str(Path(__file__).with_name("task08_android_runtime_evidence.py")),
                "sha256": sha256(Path(__file__).with_name("task08_android_runtime_evidence.py")),
            },
        },
        "diagnostics": {
            "adapter": "ready" if strict_ready else "failed",
            "transport": "transport_completed" if adapter_report is not None else "failed",
            "strictReady": strict_ready,
            "publishable": strict_ready,
            "environmentFailureIsNotSemanticFailure": True,
            "reason": None if strict_ready else failure,
            "adapterDiagnostics": (adapter_report or {}).get("diagnostics"),
        },
        "durationSeconds": round(time.monotonic() - started, 3),
    }
    output.write_text(json.dumps(report, indent=2) + "\n")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--role", choices=("base", "final", "agent"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=float, default=3600)
    args = parser.parse_args()
    if args.timeout_seconds <= 0 or args.timeout_seconds > 3600:
        parser.error("--timeout-seconds must be in (0, 3600]")
    report = run(args.source, args.role, args.output, args.timeout_seconds)
    print(json.dumps({"output": str(args.output), "strictReady": report["diagnostics"]["strictReady"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
