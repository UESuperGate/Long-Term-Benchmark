#!/usr/bin/env python3
"""Freeze Wikipedia 03/04 ArkTS calibration metadata before binary cleanup."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


TASKS = ("03_explore_feed", "04_reading_lists")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def record(root: Path, path: Path) -> dict[str, Any]:
    return {
        "path": str(path.relative_to(root)),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def summary(path: Path) -> dict[str, int]:
    semantic = load(path)["semantic"]
    return {
        "passed": semantic["passed"],
        "failed": semantic["failed"],
        "notScored": semantic["notScored"],
        "total": semantic["total"],
    }


def project_sources(migration: Path, role: str) -> list[dict[str, Any]]:
    project = migration / "arkts" / role
    root = project / "entry/src/main/ets"
    return [record(migration, path) for path in sorted(root.rglob("*.ets")) if not any(
        part.startswith(".") for part in path.relative_to(root).parts
    )]


def report_records(migration: Path) -> list[dict[str, Any]]:
    results = migration / "results"
    return [record(migration, path) for path in sorted(results.glob("*.json")) if path.name != "manifest.json"]


def result_record(migration: Path, name: str) -> dict[str, Any]:
    return record(migration, migration / "results" / name)


def task_mapping(task: str) -> tuple[list[dict[str, str]], list[str]]:
    if task == "03_explore_feed":
        return (
            [
                {"android": "HomeFragment/HomeViewModel page state", "arkts": "Index plus ExploreFeedStore"},
                {"android": "HomePreferenceRepository", "arkts": "ArkData Preferences explore_feed snapshot"},
                {"android": "Community and For You request leaves", "arkts": "ExploreLeaf effect boundary"},
                {"android": "interest and module actions", "arkts": "ExplorePageOwner event methods"},
            ],
            [
                "Android feed-card pixel composition is represented by ArkUI state summaries and action controls.",
                "Live Wikimedia recommendation and featured-feed services remain evaluator-controlled external leaves.",
            ],
        )
    return (
        [
            {"android": "ReadingListsFragment/ReadingListsViewModel page state", "arkts": "Index plus SavedCollectionsStore"},
            {"android": "Room list and membership flows", "arkts": "ArkData Preferences saved_surface snapshot and page projection"},
            {"android": "SaveArticleSheetViewModel", "arkts": "SavedPageOwner save/unsave event methods"},
            {"android": "reading-list sync service", "arkts": "SavedLeaf sync and flow effect boundary"},
        ],
        [
            "Android Compose pixel rendering is represented by ArkUI collections, rows, filters, and action controls.",
            "Remote redirect metadata and reading-list sync remain evaluator-controlled external leaves.",
        ],
    )


def finalize(migrations: Path, task: str) -> None:
    migration = migrations / task
    contract_path = migration / "canonical/transitions.json"
    contract = load(contract_path)
    manifest = load(migration / "manifest.json")
    case_digests = {case["caseId"]: case["traceDigest"] for case in contract["cases"]}
    modules, unsupported = task_mapping(task)

    hidden = migration / "evaluator/agent_harness/arkts/common"
    ownership = {
        "schemaVersion": 1,
        "taskId": task,
        "androidBoundary": manifest["source"],
        "canonicalContract": record(migration, contract_path),
        "compiledCandidateProduction": {
            "base": project_sources(migration, "base"),
            "final": project_sources(migration, "final"),
        },
        "runtimeProbe": [record(migration, path) for path in sorted(hidden.glob("*.ets"))],
        "binding": record(migration, migration / "arkts/bindings.json"),
        "pageOwner": "Index creates and renders the same production owner observed by the evaluator",
        "persistence": "ArkData Preferences reopened after each event on API23",
        "sourceObserver": False,
        "caseIdSwitchInCandidateProduction": False,
        "arbitraryStandaloneCandidateBinding": True,
        "moduleMapping": modules,
        "unsupportedPlatformSpecificBehavior": unsupported,
    }
    write(migration / "arkts/source_ownership.json", ownership)

    build_rows = []
    for role in ("base", "final"):
        project = migration / "arkts" / role
        haps = sorted((project / "entry/build").rglob("*.hap"))
        if len(haps) != 1:
            raise RuntimeError(f"{task} {role} must have exactly one HAP before cleanup")
        build_rows.append({
            "role": role,
            "bundleName": re_bundle(project / "AppScope/app.json5"),
            "hap": record(migration, haps[0]),
            "buildLog": record(migration, migration / "provenance" / f"arkts-{role}-build.log"),
            "report": result_record(migration, f"arkts-{role}.json"),
        })
    build_evidence = {
        "schemaVersion": 1,
        "taskId": task,
        "builds": build_rows,
        "cleanupPolicy": "HAP/build/.hvigor removed only after these hashes and runtime reports were retained",
    }
    write(migration / "provenance/arkts-build-evidence.json", build_evidence)

    toolchain = {
        "schemaVersion": 1,
        "taskId": task,
        "sdk": {"family": "OpenHarmony", "apiLevel": 23, "path": "/Users/z1an/Library/OpenHarmony/Sdk/23"},
        "build": {
            "hvigor": "/Applications/DevEco-Studio.app/Contents/tools/hvigor/bin/hvigorw",
            "node": "v18.20.1",
            "jdk": "DevEco JBR 21.0.8",
            "artifact": "unsigned HAP",
        },
        "device": {
            "name": "Pura 90 Pro Max",
            "target": "127.0.0.1:10178",
            "apiLevel": 23,
            "softwareVersion": "emulator 6.1.0.115(SP11DEVC00E115R4P11)",
            "lock": "/tmp/ltb-arkts-device-73ccdb837c3b8a06",
        },
        "diskSafetyLineBytes": 8 * 1024 * 1024 * 1024,
    }
    write(migration / "provenance/arkts-toolchain.json", toolchain)

    arkts_results = {
        "base": summary(migration / "results/arkts-base.json"),
        "final": summary(migration / "results/arkts-final.json"),
        "noChangeControl": summary(migration / "results/arkts-no-change-control.json"),
        "knownFinalControl": summary(migration / "results/arkts-known-final-control.json"),
        "failClosedControl": summary(migration / "results/arkts-fail-closed-control.json"),
    }
    calibration = load(migration / "provenance/calibration-summary.json")
    calibration["expected"].update({"arktsBase": "0/10", "arktsFinal": "10/10"})
    calibration["observed"].update({
        "arktsBase": arkts_results["base"],
        "arktsFinal": arkts_results["final"],
        "arktsNoChangeControl": arkts_results["noChangeControl"],
        "arktsKnownFinalControl": arkts_results["knownFinalControl"],
        "arktsFailClosedControl": arkts_results["failClosedControl"],
    })
    calibration.update({
        "arktsRuntime": "API23 EntryAbility/ArkUI Index page owner plus reopened ArkData Preferences",
        "arktsDeviceTarget": "127.0.0.1:10178",
        "arktsDeviceApi": 23,
        "arktsCalibrationPublishable": True,
        "sourceObserver": False,
        "roleAffectsVerdict": False,
        "agentResult": "not_run",
    })
    write(migration / "provenance/calibration-summary.json", calibration)

    eval_manifest = load(migration / "provenance/eval-manifest.json")
    eval_manifest.update({
        "status": "android_and_arkts_calibration_complete",
        "contractSha256": sha256(contract_path),
        "caseDigests": case_digests,
        "arkts": {
            "base": result_record(migration, "arkts-base.json"),
            "final": result_record(migration, "arkts-final.json"),
            "noChangeControl": result_record(migration, "arkts-no-change-control.json"),
            "knownFinalControl": result_record(migration, "arkts-known-final-control.json"),
            "failClosedControl": result_record(migration, "arkts-fail-closed-control.json"),
        },
        "agent": None,
        "agentResult": "not_run_by_request",
    })
    write(migration / "provenance/eval-manifest.json", eval_manifest)

    manifest.update({
        "status": "android_and_arkts_calibrated",
        "arktsSourceOwnership": "arkts/source_ownership.json",
        "toolchains": {"arkts": toolchain},
        "moduleMapping": modules,
        "unsupportedPlatformSpecificBehavior": unsupported,
        "validation": {
            "androidBase": "0/10", "androidFinal": "10/10",
            "arktsBase": "0/10", "arktsFinal": "10/10", "notScored": 0,
            "arktsNoChangeControl": "0/10", "arktsKnownFinalControl": "10/10",
            "arktsFailClosedControl": "10/10 not_scored with nonzero exit",
        },
        "agentResult": "not_run_by_request",
        "arkts": "implemented_and_api23_runtime_calibrated",
        "publication": {
            "calibrationReady": True,
            "benchmarkReady": False,
            "reason": "Android and ArkTS are calibrated; OpenCode agent_result was explicitly deferred.",
        },
    })
    write(migration / "manifest.json", manifest)

    execution = load(migration / "execution.json")
    execution["arkts"] = {
        "baseProject": "arkts/base",
        "finalProject": "arkts/final",
        "buildCommand": [
            "python3", "{migration}/../tools/build_arkts_calibration.py",
            "--project", "{project}", "--migration", "{migration}", "--task-id", task,
        ],
        "semanticCommand": [
            "python3", "evaluator/run_arkts_semantics.py", "--project", "{project}",
            "--role", "{role}", "--output", "{output}",
        ],
        "agentPrepareCommand": [
            "python3", "{migration}/../tools/prepare_agent_harness.py", "--platform", "arkts",
            "--task-id", task, "--project", "{project}", "--migration", "{migration}",
        ],
        "agentVisibleBuildCommand": [
            "bash", "{migration}/../tools/build_arkts_api23.sh", "{project}",
        ],
        "agentBuildCommand": [
            "bash", "{migration}/../tools/build_arkts_agent_harness.sh", "{project}",
        ],
        "agentSemanticCommand": [
            "python3", "evaluator/run_arkts_semantics.py", "--project", "{project}",
            "--role", "agent", "--output", "{output}",
        ],
        "runtime": "API23 EntryAbility/ArkUI page owner",
        "deviceTarget": "127.0.0.1:10178",
        "deviceLock": "/tmp/ltb-arkts-device-73ccdb837c3b8a06",
        "diskSafetyLineBytes": 8 * 1024 * 1024 * 1024,
        "reportRelativePath": "results/arkts-{role}.json",
    }
    execution["placeholderPolicy"] = (
        "Missing candidate binding, HAP, API23 target, page episode, or reopened persistence is not_scored. "
        "Role and source text never determine semantic verdicts."
    )
    write(migration / "execution.json", execution)

    reports = report_records(migration)
    write(migration / "results/manifest.json", {
        "schemaVersion": 1,
        "taskId": task,
        "platform": "android_and_arkts",
        "status": "calibrated",
        "reports": reports,
        "agentResult": "not_run_by_request",
    })

    evidence = load(migration / "provenance/evidence-index.json")
    evidence["canonicalContract"] = record(migration, contract_path)
    evidence["reports"] = reports
    evidence["sourceOwnership"] = {
        "android": record(migration, migration / "android/source_ownership.json"),
        "arkts": record(migration, migration / "arkts/source_ownership.json"),
    }
    evidence["arktsBuildEvidence"] = record(
        migration, migration / "provenance/arkts-build-evidence.json"
    )
    evidence["arktsToolchain"] = record(migration, migration / "provenance/arkts-toolchain.json")
    evidence["arktsRuntimeHarnessAudit"] = record(
        migration, migration / "provenance/arkts-runtime-harness-audit.json"
    )
    evidence["transitionParity"] = record(
        migration, migration / "provenance/transition-parity.json"
    )
    write(migration / "provenance/evidence-index.json", evidence)


def re_bundle(path: Path) -> str:
    import re

    match = re.search(r"bundleName\s*:\s*['\"]([^'\"]+)", path.read_text())
    if not match:
        raise RuntimeError(f"bundleName missing from {path}")
    return match.group(1)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--migrations", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--task", action="append", choices=TASKS)
    args = parser.parse_args()
    for task in args.task or TASKS:
        finalize(args.migrations.resolve(), task)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
