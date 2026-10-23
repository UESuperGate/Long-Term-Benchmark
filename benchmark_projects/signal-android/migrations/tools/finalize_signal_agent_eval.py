#!/usr/bin/env python3
"""Finalize a terminated Signal agent run without rerunning model generation."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
RUNNER_PATH = HERE / "run_signal_03_06_agent_eval.py"
SPEC = importlib.util.spec_from_file_location("signal_agent_runner", RUNNER_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot import Signal agent runner")
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)


def safe_extract(archive: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    root = destination.resolve()
    with tarfile.open(archive, "r:gz") as stream:
        for member in stream.getmembers():
            target = (destination / member.name).resolve()
            if target != root and root not in target.parents:
                raise RuntimeError(f"unsafe baseline archive member: {member.name}")
        stream.extractall(destination, filter="data")


def restore_snapshot_directories(snapshot: Path, destination: Path) -> list[str]:
    restored = []
    for row in RUNNER.load(snapshot)["entries"]:
        if row.get("type") != "directory":
            continue
        target = destination / row["path"]
        if not target.exists():
            target.mkdir(parents=True)
            target.chmod(row["mode"])
            restored.append(row["path"])
    return restored


def archive_prior_evaluation_attempt(run_dir: Path, run: dict[str, Any]) -> dict[str, Any] | None:
    if "postGenerationEvaluation" not in run:
        return None
    attempt = len(run.get("postGenerationEvaluationAttempts", [])) + 1
    archived = []
    for name in (
        "production-build-post-termination.log",
        "production-build-post-termination-artifacts.json",
        "runtime-build.log",
        "runtime-semantic.log",
        "semantic.json",
        "candidate-source-manifest.json",
        "post-termination-reconstruction.json",
    ):
        source = run_dir / name
        if source.is_file():
            destination = run_dir / f"post-termination-attempt-{attempt}-{name}"
            shutil.copy2(source, destination)
            archived.append(RUNNER.artifact(destination))
    snapshot = run_dir / f"post-termination-attempt-{attempt}-run.json"
    RUNNER.dump(snapshot, run)
    archived.append(RUNNER.artifact(snapshot))
    return {
        "attempt": attempt,
        "reason": "superseded evaluator-resume attempt retained verbatim",
        "evaluation": run["postGenerationEvaluation"],
        "compile": run.get("compile"),
        "semantic": run.get("semanticTestcase"),
        "artifacts": archived,
    }


def find_tool_call(export: dict[str, Any], call_id: str) -> dict[str, Any] | None:
    for message in export.get("messages", []):
        for part in message.get("parts", message.get("content", [])):
            if isinstance(part, dict) and part.get("id") == call_id:
                return part
    return None


def terminal_locality_review(run_dir: Path, candidate_path: Path, build: list[str]) -> dict[str, Any]:
    original_path = run_dir / "isolation-audit.json"
    original = RUNNER.load(original_path)
    terminal_path = run_dir / "terminal-isolation-audit.json"
    terminal = RUNNER.audit_sessions(
        run_dir / "opencode.jsonl", candidate_path, build, terminal_path, time.monotonic() + 300,
    )
    terminal_full = RUNNER.load(terminal_path)
    inventory = RUNNER.load(run_dir / "sessions/terminal-isolation-audit_session-inventory.json")
    sessions_terminal = bool(inventory.get("sessions")) and all(
        row.get("outcome") in {"succeeded", "failed", "cancelled"}
        and any(message.get("type") == "idle" for message in row.get("messages", []))
        for row in inventory["sessions"]
    )
    violations = original.get("violations", [])
    unresolved_only = bool(violations) and all(item.get("code") == "unresolved_path" for item in violations)
    call_ids = sorted({item.get("callID") for item in violations if item.get("callID")})
    reviewed_calls = []
    local_only = True
    for call_id in call_ids:
        matches = []
        for export_path in sorted((run_dir / "sessions").glob("isolation-audit_*.export.json")):
            export = RUNNER.load(export_path)
            part = find_tool_call(export, call_id)
            if part is not None:
                matches.append((export_path, part))
        if len(matches) != 1:
            local_only = False
            reviewed_calls.append({"callID": call_id, "status": "ambiguous_export", "matches": len(matches)})
            continue
        export_path, part = matches[0]
        state = part.get("state", {})
        inputs = state.get("input", {})
        content = state.get("content", [])
        text = "\n".join(item.get("text", "") for item in content if isinstance(item, dict))
        returned = [line.rstrip(":") for line in text.splitlines() if line.startswith("/")]
        outside = []
        for value in returned:
            resolved = Path(value).resolve()
            if resolved != candidate_path and candidate_path not in resolved.parents:
                outside.append(value)
        valid = (
            part.get("name") == "glob"
            and inputs.get("pattern") == "*"
            and state.get("status") == "completed"
            and not outside
            and bool(returned)
        )
        local_only = local_only and valid
        reviewed_calls.append({
            "callID": call_id,
            "sessionExport": RUNNER.artifact(export_path),
            "tool": part.get("name"),
            "pattern": inputs.get("pattern"),
            "status": state.get("status"),
            "executedFlag": part.get("executed"),
            "returnedAbsolutePathCount": len(returned),
            "outsideCandidatePaths": outside,
            "containsDollarFilename": any("$" in value for value in returned),
            "reviewPassed": valid,
        })
    terminal_codes = sorted({item.get("code") for item in terminal_full.get("violations", [])})
    passed = sessions_terminal and unresolved_only and local_only and set(terminal_codes) <= {"unresolved_path"}
    review = {
        "schemaVersion": 1,
        "classification": "post-termination parser-false-positive locality review",
        "status": "passed" if passed else "failed",
        "candidateAtGenerationTime": str(candidate_path),
        "allOpenCodeProcessesTerminatedBeforeReview": True,
        "sessionsTerminal": sessions_terminal,
        "sessionOutcomes": {row["sessionID"]: row.get("outcome") for row in inventory.get("sessions", [])},
        "originalIsolationAudit": RUNNER.artifact(original_path),
        "terminalIsolationAudit": terminal,
        "originalAvailabilityPreserved": original.get("availability"),
        "originalViolationCodes": sorted({item.get("code") for item in violations}),
        "terminalViolationCodes": terminal_codes,
        "reviewedCalls": reviewed_calls,
        "finding": (
            "The reviewed glob used candidate-relative pattern '*' and returned only absolute paths under the candidate. "
            "The shared helper classified dollar signs in compiled class filenames as unresolved shell expansion."
        ),
        "semanticFeedbackExposedToAgent": False,
        "generationRerun": False,
        "finalIsolationDisposition": "verified_local_only" if passed else "unverified",
    }
    output = run_dir / "terminal-isolation-review.json"
    RUNNER.dump(output, review)
    return {**review, "artifact": RUNNER.artifact(output)}


def verify_reconstruction(candidate: Path, run: dict[str, Any], run_dir: Path) -> dict[str, Any]:
    old_root = Path(run["isolationAudit"]["path"]).parent
    original_audit = RUNNER.load(run_dir / "isolation-audit.json")
    old_candidate = Path(original_audit["candidate"])
    mismatches = []
    for record in run["codeGeneration"].get("sourceArtifacts", []):
        source = Path(record["path"])
        try:
            relative = source.relative_to(old_candidate)
        except ValueError:
            mismatches.append({"path": record["path"], "reason": "outside_original_candidate"})
            continue
        target = candidate / relative
        if not target.is_file() or RUNNER.sha256(target) != record["sha256"] or target.stat().st_size != record["bytes"]:
            mismatches.append({"path": relative.as_posix(), "reason": "hash_or_size_mismatch"})
    baseline_tree = RUNNER.load(run_dir / "inputs/raw-tree.json")
    protected = [
        row for row in baseline_tree["entries"]
        if row.get("type") == "file" and (
            row["path"] in {"build-agent.sh", "opencode.json", "IMMUTABLE_SOURCES.json", "SOURCE_MANIFEST.json", "tools/build.sh"}
            or row["path"].startswith("_benchmark_inputs/")
            or row["path"].startswith("_benchmark_scaffold/")
        )
    ]
    protected_mismatches = []
    for row in protected:
        target = candidate / row["path"]
        if not target.is_file() or RUNNER.sha256(target) != row["sha256"] or target.stat().st_size != row["bytes"]:
            protected_mismatches.append(row["path"])
    return {
        "passed": not mismatches and not protected_mismatches,
        "agentProductionSourceMismatches": mismatches,
        "protectedInputMismatches": protected_mismatches,
        "archivedPatch": run["candidatePatch"],
        "baselineArchive": run["candidateBaseline"]["archive"],
    }


def finalize(run_id: str, task_id: str, platform: str, target: str) -> dict[str, Any]:
    migration = RUNNER.MIGRATIONS / task_id
    run_dir = migration / "results/agent-runs" / run_id / platform
    run_path = run_dir / "run.json"
    run = RUNNER.load(run_path)
    if run.get("agentExit") != 0 or run.get("agentTimedOut") is True:
        raise RuntimeError("generation did not terminate successfully; refusing evaluation-only finalization")
    prior_attempt = archive_prior_evaluation_attempt(run_dir, run)
    original_audit = RUNNER.load(run_dir / "isolation-audit.json")
    candidate_at_generation = Path(original_audit["candidate"])
    review = terminal_locality_review(run_dir, candidate_at_generation, run["publicBuildCommand"])
    if review["status"] != "passed":
        raise RuntimeError("post-termination locality review did not pass")

    resume_root = RUNNER.ROOT.parent / ".ltb-signal-agent-resume" / run_id / task_id / platform
    shutil.rmtree(resume_root, ignore_errors=True)
    safe_extract(run_dir / "inputs/baseline.tar.gz", resume_root)
    restored_directories = restore_snapshot_directories(run_dir / "inputs/raw-tree.json", resume_root)
    patch = run_dir / "agent.patch"
    applied = subprocess.run(
        ["git", "apply", "--binary", "--whitespace=nowarn", str(patch)],
        cwd=resume_root, text=True, capture_output=True,
    )
    if applied.returncode:
        raise RuntimeError(f"cannot reconstruct candidate patch: {applied.stderr or applied.stdout}")
    reconstruction = verify_reconstruction(resume_root, run, run_dir)
    reconstruction["restoredRawSnapshotDirectories"] = restored_directories
    if not reconstruction["passed"]:
        raise RuntimeError(f"candidate reconstruction mismatch: {reconstruction}")
    RUNNER.dump(run_dir / "post-termination-reconstruction.json", reconstruction)

    evaluation_started = datetime.now().astimezone()
    deadline = time.monotonic() + 3600
    build = run["publicBuildCommand"]
    compile_exit = RUNNER.run_logged(
        build, resume_root, run_dir / "production-build-post-termination.log",
        RUNNER.remaining(deadline, "production_build"), RUNNER.environment(resume_root, target), True,
    )
    compile_result = {
        "passed": compile_exit == 0,
        "exitCode": compile_exit,
        "command": build,
        "scope": "standalone candidate application production compile",
        "phase": "post-termination evaluation of archived agent patch",
    }
    RUNNER.cleanup_builds(resume_root, run_dir / "production-build-post-termination-artifacts.json")
    manifest_path = run_dir / "candidate-source-manifest.json"
    manifest_artifact = RUNNER.source_manifest(task_id, platform, resume_root, manifest_path)
    runtime_id = re.sub(r"[^a-z0-9-]", "-", f"{run_id}-{task_id}-{platform}-terminal-review".lower()).strip("-")
    report, diagnostics = RUNNER.hidden_evaluation(
        task_id, platform, resume_root, run_dir, manifest_path, runtime_id, deadline, target,
    )
    if report is None:
        report = RUNNER.not_scored_report(task_id, platform, "hidden runtime adapter did not compile, bind, or execute")
    metrics = RUNNER.semantic_metrics(report)
    report["codeGeneration"] = run["codeGeneration"]
    report["compile"] = compile_result
    report.setdefault("diagnostics", {})["runtimeCompile"] = diagnostics
    report["postTerminationEvaluation"] = {
        "generationRerun": False,
        "candidateReconstructedFrom": ["inputs/baseline.tar.gz", "agent.patch"],
        "terminalIsolationReview": "terminal-isolation-review.json",
    }
    RUNNER.dump(run_dir / "semantic.json", report)
    shutil.copy2(run_dir / "semantic.json", migration / "results" / f"{platform}-agent.json")
    patches = migration / "results/agent-patches"
    patches.mkdir(parents=True, exist_ok=True)
    shutil.copy2(run_dir / "agent.patch", patches / f"{platform}-agent.patch")
    shutil.copy2(run_dir / "generated-files.json", patches / f"{platform}-agent-generated-files.json")
    RUNNER.cleanup_builds(resume_root, run_dir / "post-termination-final-cleanup-artifacts.json")
    shutil.rmtree(resume_root, ignore_errors=True)
    evaluation_finished = datetime.now().astimezone()

    run["originalIsolationDisposition"] = {
        "availability": run.get("availability"),
        "benchmarkMetricsAvailable": run.get("benchmarkMetricsAvailable"),
        "audit": "isolation-audit.json",
    }
    if prior_attempt is not None:
        run.setdefault("postGenerationEvaluationAttempts", []).append(prior_attempt)
    run.update({
        "availability": "available",
        "benchmarkMetricsAvailable": True,
        "terminalIsolationReview": review["artifact"],
        "postTerminationCandidateReconstruction": RUNNER.artifact(run_dir / "post-termination-reconstruction.json"),
        "candidateSourceManifest": manifest_artifact,
        "compile": compile_result,
        "diagnostics": diagnostics,
        "semanticTestcase": metrics,
        "semanticReport": RUNNER.artifact(run_dir / "semantic.json"),
        "postGenerationEvaluation": {
            "startedAt": evaluation_started.isoformat(timespec="seconds"),
            "finishedAt": evaluation_finished.isoformat(timespec="seconds"),
            "durationSeconds": round((evaluation_finished - evaluation_started).total_seconds(), 3),
            "generationRerun": False,
            "semanticFeedbackExposedToAgent": False,
            "reason": "user-requested evaluation after all OpenCode and subagent sessions reached terminal state",
        },
        "cleanup": {"completed": not resume_root.exists(), "error": None},
    })
    RUNNER.dump(run_path, run)
    return run


def refresh_summaries(run_id: str) -> None:
    adb = RUNNER.ANDROID_SDK / "platform-tools/adb"
    android_serial = os.environ.get("ANDROID_SERIAL", "emulator-5554")
    android_api = subprocess.check_output([str(adb), "-s", android_serial, "shell", "getprop", "ro.build.version.sdk"], text=True).strip()
    android_abi = subprocess.check_output([str(adb), "-s", android_serial, "shell", "getprop", "ro.product.cpu.abi"], text=True).strip()
    target = RUNNER.hdc_target()
    arkts_api = subprocess.check_output([str(RUNNER.HDC), "-t", target, "shell", "param", "get", "const.ohos.apiversion"], text=True).strip()
    environments = {
        "android": {"runtime": "Android ART", "serial": android_serial, "apiLevel": android_api, "abi": android_abi},
        "arkts": {"runtime": "OpenHarmony ArkVM", "target": target, "apiLevel": arkts_api, "pageOwner": "Index"},
    }
    rows = []
    for task_id in RUNNER.TASK_IDS:
        task_rows = []
        for platform in RUNNER.PLATFORMS:
            row = RUNNER.load(RUNNER.MIGRATIONS / task_id / "results/agent-runs" / run_id / platform / "run.json")
            row["runtimeEnvironment"] = environments[platform]
            RUNNER.dump(RUNNER.MIGRATIONS / task_id / "results/agent-runs" / run_id / platform / "run.json", row)
            task_rows.append(row)
            rows.append(row)
        RUNNER.summarize(task_id, task_rows, run_id)
    binary = RUNNER.verify_binary_free()
    summary = {
        "runId": run_id,
        "runtime": environments,
        "binaryFreeRetainedEvidence": binary,
        "runs": rows,
        "note": "Top-level generation timing remains in each run. Post-termination evaluation did not rerun generation.",
    }
    for task_id in RUNNER.TASK_IDS:
        RUNNER.dump(RUNNER.MIGRATIONS / task_id / "results/agent-runs" / run_id / "round-summary.json", summary)
        migration = RUNNER.MIGRATIONS / task_id
        run_root = migration / "results/agent-runs" / run_id
        task_rows = [row for row in rows if row["taskId"] == task_id]
        public_inputs_redacted = True
        for platform in RUNNER.PLATFORMS:
            public = RUNNER.load(run_root / platform / "inputs/public/public_transitions.json")
            public_inputs_redacted = public_inputs_redacted and all(
                "expected" not in case and "traceDigest" not in case and "evidence" not in case
                for case in public["cases"]
            )
        candidates_cleaned = all(
            not Path(RUNNER.load(run_root / platform / "isolation-audit.json")["candidate"]).exists()
            for platform in RUNNER.PLATFORMS
        )
        credential = RUNNER.redact_secret_artifacts(run_root)
        retained = [RUNNER.artifact(path) for path in sorted(run_root.rglob("*")) if path.is_file()]
        audit = {
            "schemaVersion": 1,
            "runId": run_id,
            "taskId": task_id,
            "status": "passed" if binary["passed"] and candidates_cleaned and public_inputs_redacted else "failed",
            "model": RUNNER.MODEL,
            "opencodeVersion": task_rows[0].get("opencodeVersion"),
            "topLevelRuns": [{
                "platform": row["platform"],
                "startedAt": row.get("startedAt"),
                "finishedAt": row.get("finishedAt"),
                "durationSeconds": row.get("durationSeconds"),
                "exitCode": row.get("agentExit"),
                "timedOut": row.get("agentTimedOut"),
                "command": row.get("agentCommand"),
                "environment": row.get("runtimeEnvironment"),
                "codeGeneration": row.get("codeGeneration", {}).get("passed"),
                "compile": row.get("compile"),
                "semantic": row.get("semanticTestcase"),
                "adapterDiagnostics": row.get("diagnostics"),
            } for row in task_rows],
            "metricPolicy": "code generation, standalone application compile, and semantic testcase only; adapter and transport are diagnostics; notScored excluded from pass/fail",
            "publicInputsContainNoExpectedDigestOrEvidence": public_inputs_redacted,
            "candidateDirectoriesRemoved": candidates_cleaned,
            "binaryFreeRetainedEvidence": binary,
            "credentialAudit": credential,
            "retainedFileInventory": retained,
        }
        audit_path = migration / "results/agent-bundle-audit.json"
        RUNNER.dump(audit_path, audit)
        results_manifest = RUNNER.load(migration / "results/manifest.json")
        results_manifest["agentBundleAudit"] = "agent-bundle-audit.json"
        RUNNER.dump(migration / "results/manifest.json", results_manifest)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--task-id", choices=RUNNER.TASK_IDS, required=True)
    parser.add_argument("--platform", choices=RUNNER.PLATFORMS, required=True)
    args = parser.parse_args()
    target = RUNNER.hdc_target()
    run = finalize(args.run_id, args.task_id, args.platform, target)
    refresh_summaries(args.run_id)
    print(json.dumps({
        "taskId": args.task_id,
        "platform": args.platform,
        "availability": run["availability"],
        "compile": run["compile"],
        "semantic": run["semanticTestcase"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
