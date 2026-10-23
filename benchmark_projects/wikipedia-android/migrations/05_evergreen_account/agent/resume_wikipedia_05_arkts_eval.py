#!/usr/bin/env python3
"""Resume ArkTS scoring from the immutable archived agent patch.

This command never invokes OpenCode. It re-exports and audits the original
recursive sessions, reconstructs the exact archived candidate tree, then runs
the standalone build and hidden native scorer under their existing locks.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import subprocess
import tarfile
import time
from datetime import datetime, timedelta
from pathlib import Path


HERE = Path(__file__).resolve().parent
RUNNER_PATH = HERE / "run_wikipedia_05_agent_eval.py"
SPEC = importlib.util.spec_from_file_location("wikipedia05_runner", RUNNER_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load Wikipedia 05 runner")
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)


def safe_extract(archive: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive, "r:gz") as stream:
        for member in stream.getmembers():
            resolved = (destination / member.name).resolve()
            if resolved != destination and destination not in resolved.parents:
                raise RuntimeError(f"unsafe archive member: {member.name}")
        stream.extractall(destination, filter="data")


def write_tree(candidate: Path) -> str:
    subprocess.run(["git", "add", "-A"], cwd=candidate, check=True)
    return subprocess.check_output(["git", "write-tree"], cwd=candidate, text=True).strip()


def artifact_or_none(path: Path):
    return RUNNER.artifact(path) if path.is_file() else None


def main() -> int:
    parser = argparse.ArgumentParser(description="Resume Wikipedia 05 ArkTS audit/build/runtime scoring without OpenCode")
    parser.add_argument("--authorize-device-scoring", action="store_true")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--hdc-target", default="127.0.0.1:10178")
    args = parser.parse_args()
    if not args.authorize_device_scoring:
        raise SystemExit("device scoring requires explicit authorization")

    run_dir = RUNNER.MIGRATION / "results/agent-runs" / args.run_id / "arkts"
    run_path = run_dir / "run.json"
    result = RUNNER.load(run_path)
    incomplete_semantics = result.get("semanticTestcase", {}).get("notScored", 0) > 0
    if result.get("availability") not in {"isolation_unverified", "evaluation_failure"} and not incomplete_semantics:
        raise SystemExit(f"unexpected prior availability: {result.get('availability')}")
    if result.get("agentTimedOut") or result.get("agentExit") != 0:
        raise SystemExit("original OpenCode run did not complete successfully")

    started_at = datetime.fromisoformat(result["startedAt"])
    hard_deadline = started_at + timedelta(seconds=RUNNER.OVERALL_TIMEOUT_SECONDS)

    def remaining(phase: str) -> float:
        seconds = (hard_deadline - datetime.now().astimezone()).total_seconds()
        if seconds <= 0:
            raise TimeoutError(f"original 3600s platform deadline exhausted during {phase}")
        return seconds

    candidate = (RUNNER.ROOT.parent / ".ltb-wikipedia-05-agent" / args.run_id / "arkts").resolve()
    expected_parent = (RUNNER.ROOT.parent / ".ltb-wikipedia-05-agent" / args.run_id).resolve()
    if candidate.parent != expected_parent:
        raise RuntimeError("candidate path escaped the task-local reconstruction root")
    shutil.rmtree(candidate, ignore_errors=True)

    initial_run = run_dir / "run.initial-isolation-unverified.json"
    initial_audit = run_dir / "isolation-audit.initial.json"
    if not initial_run.exists():
        shutil.copy2(run_path, initial_run)
    if not initial_audit.exists():
        shutil.copy2(run_dir / "isolation-audit.json", initial_audit)

    try:
        safe_extract(run_dir / "inputs/baseline.tar.gz", candidate)
        protected_before = RUNNER.protected_files(candidate)
        subprocess.run(["git", "init", "-q"], cwd=candidate, check=True)
        baseline_tree = write_tree(candidate)
        patch = run_dir / "arkts-agent.patch"
        subprocess.run(["git", "apply", "--binary", "--whitespace=nowarn", str(patch)], cwd=candidate, check=True)
        candidate_tree = write_tree(candidate)
        expected_tree = result["candidatePatch"]["tree"]
        if candidate_tree != expected_tree:
            raise RuntimeError(f"reconstructed tree mismatch: {candidate_tree} != {expected_tree}")
        protected = RUNNER.verify_protected(candidate, protected_before)
        if not protected["passed"]:
            raise RuntimeError("protected candidate inputs changed during reconstruction")
        reconstruction = {
            "schemaVersion": 1,
            "baselineArchive": RUNNER.artifact(run_dir / "inputs/baseline.tar.gz"),
            "patch": RUNNER.artifact(patch),
            "baselineTree": baseline_tree,
            "candidateTree": candidate_tree,
            "expectedCandidateTree": expected_tree,
            "exactTreeMatch": True,
            "protectedInputAudit": protected,
            "opencodeInvoked": False,
        }
        RUNNER.dump(run_dir / "candidate-reconstruction.json", reconstruction)

        audit_path = run_dir / "isolation-audit-recheck.json"
        monotonic_deadline = time.monotonic() + remaining("recursive_session_reaudit")
        isolation = RUNNER.REF.audit_sessions(
            run_dir / "opencode.jsonl", candidate, ["bash", "build-agent.sh"], audit_path, monotonic_deadline,
        )
        audit = RUNNER.load(audit_path)
        adjudication = {
            "schemaVersion": 1,
            "decision": isolation["availability"],
            "basis": "complete recursive re-export after root completion; interrupted children count as terminal only with an explicit completed aborted assistant step and all tool calls terminal; repeated references reuse one post-run full export",
            "initialAudit": RUNNER.artifact(initial_audit),
            "recheckAudit": RUNNER.artifact(audit_path),
            "complete": audit.get("complete"),
            "valid": audit.get("valid"),
            "violations": audit.get("violations"),
            "reusedSessionReferences": audit.get("reusedSessionReferences", []),
            "terminalEvidence": [{"sessionID": row.get("sessionID"), "evidence": row.get("terminalEvidence")}
                                 for row in audit.get("session_logs", [])],
            "completedOutsideCandidateAccesses": [
                row for row in audit.get("records", [])
                if row.get("status") == "completed" and any(not target.get("insideCandidate", False)
                                                               for target in row.get("targets", []))
            ],
            "networkViolations": [row for row in audit.get("violations", [])
                                  if row.get("code") == "network_tool_access"],
        }
        RUNNER.dump(run_dir / "isolation-adjudication.json", adjudication)
        if isolation["availability"] != "available":
            raise RuntimeError(f"recursive isolation remains invalid: {isolation['availability']}")
        shutil.copy2(audit_path, run_dir / "isolation-audit.json")
        result["isolationAudit"] = {**isolation, "initial": RUNNER.artifact(initial_audit),
                                    "adjudication": RUNNER.artifact(run_dir / "isolation-adjudication.json")}
        result["candidateReconstruction"] = RUNNER.artifact(run_dir / "candidate-reconstruction.json")
        result["evaluationResumedWithoutModelRerun"] = True

        build = ["bash", "build-agent.sh"]
        compile_exit = RUNNER.run_build("arkts", candidate, build, run_dir / "production-build.log",
                                        remaining("standalone_production_build"))
        result["compile"] = {"passed": compile_exit == 0, "exitCode": compile_exit, "command": build,
                             "scope": "standalone candidate application production compile"}
        RUNNER.REF.cleanup_builds(candidate, run_dir / "production-build-cleanup.json")
        result["candidateSourceManifest"] = RUNNER.source_manifest(
            "arkts", candidate, run_dir / "candidate-source-manifest.json")

        monotonic_deadline = time.monotonic() + remaining("hidden_runtime_evaluation")
        report, diagnostics = RUNNER.execute_hidden(
            "arkts", candidate, run_dir, monotonic_deadline, args.hdc_target)
        result["diagnostics"] = diagnostics
        if report is None:
            raise RuntimeError("hidden runtime scorer did not produce a report")
        metrics = RUNNER.semantic_metrics(report)
        report["codeGeneration"] = result["codeGeneration"]
        report["compile"] = result["compile"]
        report.setdefault("diagnostics", {})["runtimeCompile"] = diagnostics
        RUNNER.dump(run_dir / "semantic.json", report)
        result.update(
            availability="available", benchmarkMetricsAvailable=True,
            semanticTestcase=metrics,
            semanticReport=RUNNER.artifact(run_dir / "semantic.json"),
            rawSemanticReport=artifact_or_none(run_dir / "semantic.raw.json"),
        )
        shutil.copy2(run_dir / "semantic.json", RUNNER.MIGRATION / "results/arkts-agent.json")
        if (run_dir / "semantic.raw.json").is_file():
            shutil.copy2(run_dir / "semantic.raw.json", RUNNER.MIGRATION / "results/arkts-agent.raw.json")
        patches = RUNNER.MIGRATION / "results/agent-patches"
        patches.mkdir(parents=True, exist_ok=True)
        shutil.copy2(patch, patches / "arkts-agent.patch")
        shutil.copy2(run_dir / "arkts-agent-generated-files.json", patches / "arkts-agent-generated-files.json")
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError, TimeoutError) as error:
        result.update(availability="overall_timeout" if isinstance(error, TimeoutError) else "evaluation_failure",
                      benchmarkMetricsAvailable=False, reason=f"{type(error).__name__}: {error}")
    finally:
        cleanup_error = None
        try:
            if candidate.exists():
                RUNNER.REF.cleanup_builds(candidate, run_dir / "final-cleanup-artifacts.json")
                shutil.rmtree(candidate)
            shutil.rmtree(expected_parent, ignore_errors=True)
        except OSError as error:
            cleanup_error = str(error)
        finished = datetime.now().astimezone()
        result.update(
            finishedAt=finished.isoformat(timespec="seconds"),
            durationSeconds=round((finished - started_at).total_seconds(), 3),
            timingScope="Original top-level ArkTS cell wall time from initial start through recursive re-audit, immutable-patch reconstruction, compile, native scoring, and cleanup; subagent durations are not added.",
            cleanup={"completed": not candidate.exists(), "error": cleanup_error},
        )
        result["credentialAudit"] = RUNNER.REF.redact_secret_artifacts(run_dir)
        RUNNER.REF.finalize_metric_availability(result)
        RUNNER.dump(run_path, result)

    android = RUNNER.load(RUNNER.MIGRATION / "results/agent-runs" / args.run_id / "android/run.json")
    RUNNER.summarize([android, result], args.run_id)
    print(json.dumps({"availability": result["availability"], "compile": result.get("compile"),
                      "semantic": result.get("semanticTestcase"), "durationSeconds": result["durationSeconds"]},
                     ensure_ascii=False))
    return 0 if result.get("benchmarkMetricsAvailable") else 2


if __name__ == "__main__":
    raise SystemExit(main())
