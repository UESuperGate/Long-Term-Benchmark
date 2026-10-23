#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[4]
MIGRATIONS = ROOT / "benchmark_projects/wikipedia-android/migrations"
TASKS = ROOT / "benchmark_projects/wikipedia-android/tasks"
SOURCE = ROOT / "_sources/wikipedia-android"
TASK_IDS = ("03_explore_feed", "04_reading_lists")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def record(root: Path, path: Path) -> dict[str, Any]:
    return {"path": str(path.relative_to(root)), "bytes": path.stat().st_size, "sha256": sha256(path)}


def write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def git_bytes(commit: str, path: str) -> bytes:
    return subprocess.check_output(["git", "-C", str(SOURCE), "show", f"{commit}:{path}"])


def result_counts(path: Path) -> dict[str, int]:
    semantic = json.loads(path.read_text())["semantic"]
    return {key: semantic[key] for key in ("passed", "failed", "notScored", "total")}


def main() -> int:
    for task_id in TASK_IDS:
        migration = MIGRATIONS / task_id
        task = json.loads((TASKS / task_id / "task.json").read_text())
        contract = json.loads((migration / "canonical/transitions.json").read_text())
        android = task["android"]
        write(migration / "android/task.json", task)

        snapshots = []
        for role, commit, root_name in (
            ("base", android["baseCommit"], "base/src/upstream_snapshot/kotlin"),
            ("final", android["finalCommit"], "final/src/upstream/kotlin"),
        ):
            root = migration / "android" / root_name
            for path in sorted(root.rglob("*.kt")):
                rel = path.relative_to(root)
                upstream = f"app/src/main/java/{rel}"
                source_bytes = git_bytes(commit, upstream)
                if source_bytes != path.read_bytes():
                    raise RuntimeError(f"upstream byte mismatch: {path}")
                blob = subprocess.check_output(
                    ["git", "-C", str(SOURCE), "rev-parse", f"{commit}:{upstream}"], text=True
                ).strip()
                snapshots.append({"role": role, "commit": commit, "upstreamPath": upstream,
                                  "bundledPath": str(path.relative_to(migration / "android")),
                                  "gitBlob": blob, "sha256": sha256(path), "bytes": path.stat().st_size,
                                  "byteExactVerified": True, "compiled": False})

        compiled = []
        for role in ("base", "final"):
            root = migration / "android/native" / role / "app/src/main/upstream/kotlin"
            for path in sorted(root.rglob("*.kt")):
                compiled.append({"role": role, **record(migration / "android", path), "compiled": True,
                                 "classification": "candidate_owned_focused_action_adapter"})
        write(migration / "android/source_ownership.json", {
            "schemaVersion": 3, "taskId": task_id,
            "upstreamImmutableSnapshots": snapshots,
            "compiledCandidateProduction": compiled,
            "runtimeProbe": str(next((migration / "android/shared/native_test/kotlin").rglob("*.kt")).relative_to(migration / "android")),
            "sourceObserver": False, "caseIdSwitchInCandidateProduction": False,
            "arbitraryStandaloneCandidateBinding": True,
            "scopeNote": "The immutable upstream files are retained byte-for-byte for provenance. The installable focused projects compile candidate-owned action adapters; they do not claim whole-file execution of every retained upstream UI/ViewModel source.",
        })

        execution = {
            "schemaVersion": 1, "taskId": task_id, "workingDirectory": ".",
            "android": {
                "baseProject": "android/native/base", "finalProject": "android/native/final",
                "buildCommand": ["bash", "{project}/build.sh"],
                "semanticCommand": ["python3", "evaluator/run_android_semantics.py", "--project", "{project}", "--role", "{role}", "--output", "{output}"],
                "agentScaffoldCommand": ["python3", "{migration}/../tools/prepare_visible_scaffold.py", "--task-id", task_id, "--project", "{project}", "--migration", "{migration}"],
                "agentPrepareCommand": ["python3", "{migration}/../tools/prepare_agent_harness.py", "--platform", "android", "--task-id", task_id, "--project", "{project}", "--migration", "{migration}"],
                "agentBuildCommand": ["bash", "{migration}/../tools/build_android_agent_harness.sh", "{project}"],
                "agentSemanticCommand": ["python3", "evaluator/run_android_semantics.py", "--project", "{project}/.benchmark-evaluator/android-harness", "--role", "agent", "--output", "{output}"],
                "deviceLock": "/tmp/long-term-benchmark-android-device.lock",
                "fullBuildLock": "/tmp/long-term-benchmark-android-full-build.lock",
            },
        }
        write(migration / "execution.json", execution)

        reports = [migration / "results" / name for name in (
            "android-base.json", "android-base.raw.json", "android-final.json", "android-final.raw.json",
            "android-no-change-control.json", "android-no-change-control.raw.json",
            "android-known-final-control.json", "android-known-final-control.raw.json",
        )]
        for report in reports:
            if not report.is_file():
                raise RuntimeError(f"missing report: {report}")
        artifact_records = []
        for role in ("base", "final"):
            project = migration / "android/native" / role
            for relative in ("app/build/outputs/apk/debug/app-debug.apk", "app/build/outputs/apk/androidTest/debug/app-debug-androidTest.apk"):
                artifact = project / relative
                if artifact.is_file():
                    artifact_records.append({"role": role, **record(migration, artifact)})
        write(migration / "provenance/build-evidence.json", {
            "schemaVersion": 1, "taskId": task_id, "compileSdk": 37, "deviceApi": 37,
            "artifactsBeforeCleanup": artifact_records,
            "retentionPolicy": "hash_and_size_only_after_calibration; APKs and build directories are deleted",
        })
        calibration = {
            "schemaVersion": 1, "taskId": task_id, "status": "calibrated",
            "expected": {"androidBase": "0/10", "androidFinal": "10/10"},
            "observed": {
                "androidBase": result_counts(migration / "results/android-base.json"),
                "androidFinal": result_counts(migration / "results/android-final.json"),
                "androidNoChangeControl": result_counts(migration / "results/android-no-change-control.json"),
                "androidKnownFinalControl": result_counts(migration / "results/android-known-final-control.json"),
            },
            "observationMode": "runtime_state_transition", "sourceObserver": False,
            "androidCalibrationPublishable": True,
            "wholeUpstreamBodyExecutionGate": "open_gap_focused_adapter_executes_instead_of_full_retained_upstream_files",
        }
        write(migration / "provenance/calibration-summary.json", calibration)
        write(migration / "provenance/evidence-index.json", {
            "schemaVersion": 1, "taskId": task_id,
            "canonicalContract": record(migration, migration / "canonical/transitions.json"),
            "reports": [record(migration, path) for path in reports],
            "sourceOwnership": record(migration, migration / "android/source_ownership.json"),
        })
        write(migration / "provenance/eval-manifest.json", {
            "schemaVersion": 1, "taskId": task_id, "contractSha256": sha256(migration / "canonical/transitions.json"),
            "caseDigests": {case["caseId"]: case["traceDigest"] for case in contract["cases"]},
            "android": {"base": record(migration, migration / "results/android-base.json"),
                        "final": record(migration, migration / "results/android-final.json")},
        })
        write(migration / "results/manifest.json", {
            "schemaVersion": 1, "taskId": task_id, "platform": "android",
            "reports": [record(migration / "results", path) for path in reports], "agentResult": "not_run",
        })
        write(migration / "manifest.json", {
            "schemaVersion": 1, "taskId": task_id, "status": "android_calibrated",
            "source": {key: android[key] for key in ("repository", "baseRef", "baseCommit", "finalRef", "finalCommit")},
            "canonicalContract": "canonical/transitions.json", "androidSourceOwnership": "android/source_ownership.json",
            "execution": "execution.json", "validation": {"androidBase": "0/10", "androidFinal": "10/10", "notScored": 0},
            "agentResult": "not_run", "arkts": "not_implemented_in_this_phase",
            "publication": {"calibrationReady": True, "benchmarkReady": False,
                            "reason": "agent result not run; retained full upstream bodies are provenance snapshots rather than directly compiled owners"},
        })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
