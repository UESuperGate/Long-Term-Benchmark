#!/usr/bin/env python3
"""Rescore frozen Signal 06 candidates after evaluator-only adapter repairs."""

from __future__ import annotations

import importlib.util
import json
import os
import re
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
FINALIZER_PATH = HERE / "finalize_signal_agent_eval.py"
SPEC = importlib.util.spec_from_file_location("signal_eval_finalizer", FINALIZER_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot import Signal evaluation finalizer")
FINALIZER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(FINALIZER)
RUNNER = FINALIZER.RUNNER

RUN_ID = "signal-03-06-minimax-m3-20261023"
TASK_ID = "06_numberless_registration"
MIGRATION = RUNNER.MIGRATIONS / TASK_ID
RUN_ROOT = MIGRATION / "results/agent-runs" / RUN_ID
REPAIR_ROOT = RUNNER.ROOT.parent / ".ltb-signal-adapter-repair-final" / RUN_ID / TASK_ID


def frozen_snapshot() -> dict[str, Any]:
    snapshot: dict[str, Any] = {}
    for platform in RUNNER.PLATFORMS:
        run_dir = RUN_ROOT / platform
        run = RUNNER.load(run_dir / "run.json")
        snapshot[platform] = {
            "agentPatch": RUNNER.artifact(run_dir / "agent.patch"),
            "generatedFiles": RUNNER.artifact(run_dir / "generated-files.json"),
            "baselineArchive": RUNNER.artifact(run_dir / "inputs/baseline.tar.gz"),
            "opencodeLog": RUNNER.artifact(run_dir / "opencode.jsonl"),
            "candidateSourceManifest": RUNNER.artifact(run_dir / "candidate-source-manifest.json"),
            "generationTiming": {
                "startedAt": run.get("startedAt"),
                "finishedAt": run.get("finishedAt"),
                "durationSeconds": run.get("durationSeconds"),
                "timingScope": run.get("timingScope"),
            },
            "compile": run.get("compile"),
            "candidatePatchRecord": run.get("candidatePatch"),
            "codeGeneration": run.get("codeGeneration"),
        }
    return snapshot


def archive_previous(run_dir: Path) -> list[dict[str, Any]]:
    archived = []
    attempt = 1
    while (run_dir / ("adapter-repair-prior-run.json" if attempt == 1 else f"adapter-repair-attempt-{attempt}-run.json")).exists():
        attempt += 1
    prefix = "adapter-repair-prior-" if attempt == 1 else f"adapter-repair-attempt-{attempt}-"
    for name in ("semantic.json", "runtime-build.log", "runtime-semantic.log"):
        source = run_dir / name
        if source.is_file():
            destination = run_dir / f"{prefix}{name}"
            shutil.copy2(source, destination)
            archived.append(RUNNER.artifact(destination))
    previous_run = run_dir / f"{prefix}run.json"
    shutil.copy2(run_dir / "run.json", previous_run)
    archived.append(RUNNER.artifact(previous_run))
    return archived


def reconstruct(platform: str, run: dict[str, Any]) -> tuple[Path, dict[str, Any]]:
    run_dir = RUN_ROOT / platform
    candidate = REPAIR_ROOT / platform
    if candidate.exists():
        shutil.rmtree(candidate)
    FINALIZER.safe_extract(run_dir / "inputs/baseline.tar.gz", candidate)
    restored = FINALIZER.restore_snapshot_directories(run_dir / "inputs/raw-tree.json", candidate)
    applied = subprocess.run(
        ["git", "apply", "--binary", "--whitespace=nowarn", str(run_dir / "agent.patch")],
        cwd=candidate,
        text=True,
        capture_output=True,
    )
    if applied.returncode:
        raise RuntimeError(f"cannot reconstruct {platform} candidate: {applied.stderr or applied.stdout}")
    verification = FINALIZER.verify_reconstruction(candidate, run, run_dir)
    verification["restoredRawSnapshotDirectories"] = restored
    if not verification["passed"]:
        raise RuntimeError(f"{platform} frozen patch reconstruction mismatch: {verification}")
    return candidate, verification


def rescore(platform: str, target: str, before: dict[str, Any]) -> dict[str, Any]:
    run_dir = RUN_ROOT / platform
    run = RUNNER.load(run_dir / "run.json")
    archived = archive_previous(run_dir)
    candidate, reconstruction = reconstruct(platform, run)
    RUNNER.dump(run_dir / "adapter-repair-reconstruction.json", reconstruction)
    manifest = run_dir / "candidate-source-manifest.json"
    runtime_id = re.sub(r"[^a-z0-9-]", "-", f"{RUN_ID}-{TASK_ID}-{platform}".lower()).strip("-")
    started = datetime.now().astimezone()
    report, diagnostics = RUNNER.hidden_evaluation(
        TASK_ID,
        platform,
        candidate,
        run_dir,
        manifest,
        runtime_id,
        time.monotonic() + 3600,
        target,
    )
    if report is None:
        raise RuntimeError(f"{platform} hidden evaluator did not produce a report after adapter repair")
    metrics = RUNNER.semantic_metrics(report)
    if metrics["total"] != 10 or metrics["scored"] != 10 or metrics["notScored"] != 0:
        raise RuntimeError(f"{platform} repair did not fully score all cases: {metrics}")
    report["codeGeneration"] = before[platform]["codeGeneration"]
    report["compile"] = before[platform]["compile"]
    report.setdefault("diagnostics", {})["runtimeCompile"] = diagnostics
    report["evaluatorRepair"] = {
        "generationRerun": False,
        "standaloneCompileRerun": False,
        "candidateReconstructedFrom": ["inputs/baseline.tar.gz", "agent.patch"],
        "priorEvaluationArtifacts": archived,
        "classification": "evaluator/adapter repair only",
    }
    RUNNER.dump(run_dir / "semantic.json", report)
    shutil.copy2(run_dir / "semantic.json", MIGRATION / "results" / f"{platform}-agent.json")
    cleanup_path = run_dir / "adapter-repair-cleanup-artifacts.json"
    RUNNER.cleanup_builds(candidate, cleanup_path)
    shutil.rmtree(candidate)
    finished = datetime.now().astimezone()

    run.update({
        "availability": "available",
        "benchmarkMetricsAvailable": True,
        "diagnostics": diagnostics,
        "semanticTestcase": metrics,
        "semanticReport": RUNNER.artifact(run_dir / "semantic.json"),
        "evaluatorRepair": {
            "startedAt": started.isoformat(timespec="seconds"),
            "finishedAt": finished.isoformat(timespec="seconds"),
            "durationSeconds": round((finished - started).total_seconds(), 3),
            "generationRerun": False,
            "standaloneCompileRerun": False,
            "semanticFeedbackExposedToAgent": False,
            "candidateReconstruction": RUNNER.artifact(run_dir / "adapter-repair-reconstruction.json"),
            "cleanup": RUNNER.artifact(cleanup_path),
            "priorEvaluationArtifacts": archived,
        },
    })
    RUNNER.dump(run_dir / "run.json", run)
    return run


def refresh_bundle(rows: list[dict[str, Any]], target: str, repair_audit: Path) -> None:
    RUNNER.summarize(TASK_ID, rows, RUN_ID)
    adb = RUNNER.ANDROID_SDK / "platform-tools/adb"
    serial = os.environ.get("ANDROID_SERIAL", "emulator-5554")
    android_api = subprocess.check_output([str(adb), "-s", serial, "shell", "getprop", "ro.build.version.sdk"], text=True).strip()
    android_abi = subprocess.check_output([str(adb), "-s", serial, "shell", "getprop", "ro.product.cpu.abi"], text=True).strip()
    arkts_api = subprocess.check_output([str(RUNNER.HDC), "-t", target, "shell", "param", "get", "const.ohos.apiversion"], text=True).strip()
    environments = {
        "android": {"runtime": "Android ART", "serial": serial, "apiLevel": android_api, "abi": android_abi},
        "arkts": {"runtime": "OpenHarmony ArkVM", "target": target, "apiLevel": arkts_api, "pageOwner": "Index"},
    }
    for row in rows:
        row["runtimeEnvironment"] = environments[row["platform"]]
        RUNNER.dump(RUN_ROOT / row["platform"] / "run.json", row)
    round_path = RUN_ROOT / "round-summary.json"
    round_summary = RUNNER.load(round_path)
    round_summary["runtime"] = environments
    round_summary["runs"] = [
        next((row for row in rows if old.get("taskId") == TASK_ID and old.get("platform") == row["platform"]), old)
        if old.get("taskId") == TASK_ID else old
        for old in round_summary.get("runs", [])
    ]
    round_summary["note"] = "Top-level generation timing and standalone compile results are frozen; evaluator-only repair rebuilt baseline plus archived patch and reran hidden native scoring."
    RUNNER.dump(round_path, round_summary)

    public_redacted = all(
        all("expected" not in case and "traceDigest" not in case and "evidence" not in case for case in RUNNER.load(RUN_ROOT / platform / "inputs/public/public_transitions.json")["cases"])
        for platform in RUNNER.PLATFORMS
    )
    original_candidates_removed = all(not Path(RUNNER.load(RUN_ROOT / platform / "isolation-audit.json")["candidate"]).exists() for platform in RUNNER.PLATFORMS)
    binary = RUNNER.verify_binary_free()
    credential = RUNNER.redact_secret_artifacts(RUN_ROOT)
    retained = [RUNNER.artifact(path) for path in sorted(RUN_ROOT.rglob("*")) if path.is_file()]
    audit = {
        "schemaVersion": 1,
        "runId": RUN_ID,
        "taskId": TASK_ID,
        "status": "passed" if binary["passed"] and original_candidates_removed and public_redacted and not REPAIR_ROOT.exists() else "failed",
        "model": RUNNER.MODEL,
        "opencodeVersion": rows[0].get("opencodeVersion"),
        "topLevelRuns": [{
            "platform": row["platform"],
            "startedAt": row.get("startedAt"),
            "finishedAt": row.get("finishedAt"),
            "durationSeconds": row.get("durationSeconds"),
            "exitCode": row.get("agentExit"),
            "timedOut": row.get("agentTimedOut"),
            "command": row.get("agentCommand"),
            "environment": environments[row["platform"]],
            "codeGeneration": row.get("codeGeneration", {}).get("passed"),
            "compile": row.get("compile"),
            "semantic": row.get("semanticTestcase"),
            "adapterDiagnostics": row.get("diagnostics"),
            "evaluatorRepair": row.get("evaluatorRepair"),
        } for row in rows],
        "metricPolicy": "code generation, standalone application compile, and semantic testcase only; adapter and transport are diagnostics; notScored excluded from pass/fail",
        "publicInputsContainNoExpectedDigestOrEvidence": public_redacted,
        "candidateDirectoriesRemoved": original_candidates_removed and not REPAIR_ROOT.exists(),
        "binaryFreeRetainedEvidence": binary,
        "credentialAudit": credential,
        "adapterRepairAudit": RUNNER.artifact(repair_audit),
        "retainedFileInventory": retained,
    }
    RUNNER.dump(MIGRATION / "results/agent-bundle-audit.json", audit)
    results_manifest = RUNNER.load(MIGRATION / "results/manifest.json")
    results_manifest["generatedAt"] = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    results_manifest["agentBundleAudit"] = "agent-bundle-audit.json"
    results_manifest["adapterRepairAudit"] = f"agent-runs/{RUN_ID}/adapter-repair-audit.json"
    RUNNER.dump(MIGRATION / "results/manifest.json", results_manifest)


def main() -> int:
    RUNNER.require_space(RUNNER.ROOT)
    before = frozen_snapshot()
    target = RUNNER.hdc_target()
    rows = [rescore(platform, target, before) for platform in RUNNER.PLATFORMS]
    if REPAIR_ROOT.exists():
        shutil.rmtree(REPAIR_ROOT)
    after = frozen_snapshot()
    frozen_equal = all(before[platform] == after[platform] for platform in RUNNER.PLATFORMS)
    if not frozen_equal:
        raise RuntimeError("frozen generation, patch, or compile evidence changed during evaluator repair")
    evaluator_paths = [
        MIGRATION / "android/evaluator/probe-candidates.tsv",
        MIGRATION / "android/evaluator/agent-public-api/NumberlessRegistrationAgentProbe.kt",
        MIGRATION / "arkts/evaluator/RuntimeObserver.ets",
        HERE / "android-harness/evaluator/harness/HarnessActivity.java",
        HERE / "inject_arkts_focused_observer.mjs",
        HERE / "run_arkts_focused_candidate.mjs",
        Path(__file__).resolve(),
    ]
    audit_path = RUN_ROOT / "adapter-repair-audit.json"
    audit = {
        "schemaVersion": 1,
        "runId": RUN_ID,
        "taskId": TASK_ID,
        "status": "passed",
        "scope": "hidden evaluator/adapter repair and native semantic rescore only",
        "generationRerun": False,
        "standaloneCompileRerun": False,
        "canonicalContractModified": False,
        "frozenEvidenceUnchanged": frozen_equal,
        "frozenBefore": before,
        "frozenAfter": after,
        "evaluatorFiles": [RUNNER.artifact(path) for path in evaluator_paths],
        "runtime": {
            "android": rows[0]["runtimeEnvironment"] if "runtimeEnvironment" in rows[0] else {"apiLevel": 37},
            "arkts": {"target": target, "apiLevel": 23, "pageOwner": "Index", "sourceObserver": False},
        },
        "semantic": {row["platform"]: row["semanticTestcase"] for row in rows},
        "candidateReconstruction": {row["platform"]: row["evaluatorRepair"]["candidateReconstruction"] for row in rows},
        "cleanup": {"repairCandidateRootRemoved": not REPAIR_ROOT.exists()},
    }
    RUNNER.dump(audit_path, audit)
    refresh_bundle(rows, target, audit_path)
    # Refresh the audit once more so its runtime section contains the persisted environment records.
    persisted = {platform: RUNNER.load(RUN_ROOT / platform / "run.json") for platform in RUNNER.PLATFORMS}
    audit["runtime"] = {platform: persisted[platform]["runtimeEnvironment"] for platform in RUNNER.PLATFORMS}
    RUNNER.dump(audit_path, audit)
    refresh_bundle([persisted[platform] for platform in RUNNER.PLATFORMS], target, audit_path)
    print(json.dumps({
        "taskId": TASK_ID,
        "generationRerun": False,
        "standaloneCompileRerun": False,
        "frozenEvidenceUnchanged": frozen_equal,
        "semantic": {row["platform"]: row["semanticTestcase"] for row in rows},
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
