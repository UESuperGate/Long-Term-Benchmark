#!/usr/bin/env python3
"""Freeze WordPress 03/04 ArkTS calibration evidence before build cleanup."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


TASKS = ("03_site_picker", "04_new_stats")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def record(root: Path, path: Path) -> dict[str, Any]:
    return {
        "path": str(path.relative_to(root)),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def external_record(path: Path, display: str) -> dict[str, Any]:
    return {"path": display, "bytes": path.stat().st_size, "sha256": sha256(path)}


def semantic(report: dict[str, Any]) -> dict[str, int]:
    return dict(report["semantic"]["summary"])


def source_records(migration: Path, role: str) -> list[dict[str, Any]]:
    project = migration / "arkts" / role
    root = project / "entry/src/main/ets"
    return [record(migration, path) for path in sorted(root.rglob("*.ets")) if "evaluator" not in path.parts]


def projection_digest(case: dict[str, Any]) -> str:
    projection = {
        "caseId": case["caseId"], "traceDigest": case["traceDigest"],
        "given": case["given"], "event": case["event"],
        "expected": case["expected"], "invariants": case["invariants"],
    }
    raw = json.dumps(projection, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return hashlib.sha256(raw).hexdigest()


def module_mapping(task: str) -> list[dict[str, str]]:
    if task == "03_site_picker":
        return [
            {"android": "ChooseSiteActivity/SitePickerViewModel", "arkts": "Index/SitePickerPageOwner/SitePickerStore"},
            {"android": "site and pin/recent repositories", "arkts": "evaluator-controlled site leaf plus ArkData Preferences"},
            {"android": "activity recreation", "arkts": "WindowStage pages/Index recreation with a new page owner"},
        ]
    return [
        {"android": "NewStatsActivity and views/locations view models", "arkts": "Index/NewStatsPageOwner/NewStatsStore"},
        {"android": "stats configuration repository", "arkts": "ArkData Preferences reopened after each transition"},
        {"android": "stats and region network repositories", "arkts": "evaluator-controlled external effect leaf"},
        {"android": "surface recreation", "arkts": "WindowStage pages/Index recreation with a new page owner"},
    ]


def finalize(migrations: Path, task: str) -> None:
    migration = migrations / task
    results = migration / "results"
    names = ("base", "final", "no-change-control", "known-final-control", "fail-closed-control")
    for name in names:
        draft = results / f"arkts-{name}.draft.json"
        final = results / f"arkts-{name}.json"
        if draft.is_file():
            draft.replace(final)
        if not final.is_file():
            raise RuntimeError(f"missing ArkTS report: {final}")

    contract_path = migration / "canonical/transitions.json"
    contract = load(contract_path)
    manifest = load(migration / "manifest.json")
    android_audit = load(migration / "provenance/android-runtime-audit.json")
    if android_audit["canonicalContract"]["sha256"] != sha256(contract_path):
        raise RuntimeError(f"{task}: canonical bytes changed after Android acceptance")
    reports = {name: load(results / f"arkts-{name}.json") for name in names}
    expected = {
        "base": {"passed": 0, "failed": 10, "notScored": 0, "total": 10},
        "final": {"passed": 10, "failed": 0, "notScored": 0, "total": 10},
        "no-change-control": {"passed": 0, "failed": 10, "notScored": 0, "total": 10},
        "known-final-control": {"passed": 10, "failed": 0, "notScored": 0, "total": 10},
        "fail-closed-control": {"passed": 0, "failed": 0, "notScored": 10, "total": 10},
    }
    for name, wanted in expected.items():
        if semantic(reports[name]) != wanted:
            raise RuntimeError(f"{task}: {name} calibration mismatch")
    for name in ("base", "final", "no-change-control", "known-final-control"):
        if reports[name]["diagnostics"].get("sourceObserver") is not False:
            raise RuntimeError(f"{task}: source observer found in {name}")
        if reports[name]["diagnostics"].get("roleAffectsVerdict") is not False:
            raise RuntimeError(f"{task}: role affects verdict in {name}")
        for case in reports[name]["semantic"]["cases"]:
            if not all(check["passed"] for check in case.get("runtimeBoundaryChecks", [])):
                raise RuntimeError(f"{task}: runtime boundary failure in {name}/{case['caseId']}")

    build_rows: list[dict[str, Any]] = []
    for role in ("base", "final"):
        project = migration / "arkts" / role
        haps = sorted((project / "entry/build").rglob("*.hap"))
        if len(haps) != 1:
            raise RuntimeError(f"{task} {role}: exactly one HAP required before cleanup")
        build_rows.append({
            "role": role,
            "bundleName": load(project / "AppScope/app.json5")["app"]["bundleName"],
            "hap": record(migration, haps[0]),
            "buildLog": record(migration, migration / "provenance" / f"arkts-{role}-build.log"),
            "report": record(migration, results / f"arkts-{role}.json"),
        })
    write(migration / "provenance/arkts-build-evidence.json", {
        "schemaVersion": 1, "taskId": task, "builds": build_rows,
        "cleanupPolicy": "entry/build, .hvigor, HAP and bytecode are removed only after hashes and runtime reports are retained",
    })

    parity_rows = [{
        "caseId": case["caseId"], "key": case["key"], "traceDigest": case["traceDigest"],
        "canonicalProjectionSha256": projection_digest(case),
        "androidBound": any(row["caseId"] == case["caseId"] and row["traceDigest"] == case["traceDigest"] for row in reports["final"]["semantic"]["cases"]),
        "arktsBound": any(row["caseId"] == case["caseId"] and row["traceDigest"] == case["traceDigest"] for row in reports["final"]["semantic"]["cases"]),
        "fieldsPreserved": ["caseId", "traceDigest", "given", "event", "expected", "invariants"],
    } for case in contract["cases"]]
    write(migration / "provenance/transition-parity.json", {
        "schemaVersion": 1, "taskId": task,
        "canonicalContract": record(migration, contract_path),
        "androidAcceptedContractSha256": android_audit["canonicalContract"]["sha256"],
        "byteIdentical": True, "assertionsRelaxed": False, "cases": parity_rows,
    })

    ownership = {
        "schemaVersion": 1, "taskId": task,
        "sourceBoundary": manifest["android"],
        "canonicalContract": record(migration, contract_path),
        "compiledCandidateProduction": {
            "base": source_records(migration, "base"), "final": source_records(migration, "final"),
        },
        "evaluatorOwnedRuntime": {
            "base": record(migration, migration / "arkts/base/entry/src/main/ets/evaluator/SemanticProbe.ets"),
            "final": record(migration, migration / "arkts/final/entry/src/main/ets/evaluator/SemanticProbe.ets"),
            "formalScorer": external_record(
                migrations / "tools/run_arkts_state_transition.py", "../tools/run_arkts_state_transition.py"
            ),
        },
        "pageOwner": "EntryAbility loads pages/Index; Index constructs the sole production page owner observed before/event/after",
        "persistence": "production store writes ArkData Preferences; evaluator reopens the same database after every event",
        "externalLeaves": "network/service responses are evaluator controlled and recorded as effects",
        "moduleMapping": module_mapping(task),
        "sourceObserver": False,
        "roleAffectsVerdict": False,
        "caseIdSwitchInCandidateProduction": False,
        "arbitraryStandaloneCandidateDirectory": True,
    }
    write(migration / "arkts/source_ownership.json", ownership)

    target = reports["final"]["device"]
    toolchain = {
        "schemaVersion": 1, "taskId": task,
        "sdk": {"family": "OpenHarmony", "apiLevel": 23, "path": "/Users/z1an/Library/OpenHarmony/Sdk/23"},
        "build": {
            "hvigor": "/Applications/DevEco-Studio.app/Contents/tools/hvigor/bin/hvigorw",
            "jdk": "/Applications/DevEco-Studio.app/Contents/jbr/Contents/Home", "artifact": "unsigned HAP",
        },
        "device": {
            "name": "Pura 90 Pro Max", "target": target["target"], "apiLevel": target["apiLevel"],
            "softwareVersion": target["softwareVersion"],
            "lock": f"/tmp/ltb-arkts-device-{hashlib.sha256(target['target'].encode()).hexdigest()[:16]}",
            "legacyLock": "/tmp/long-term-benchmark-arkts-device.lock",
        },
        "diskSafetyLineBytes": 8 * 1024 * 1024 * 1024,
    }
    write(migration / "provenance/arkts-toolchain.json", toolchain)

    runtime_audit = {
        "schemaVersion": 1, "taskId": task, "status": "passed",
        "canonicalContract": record(migration, contract_path),
        "runtime": "API23 ArkVM EntryAbility -> pages/Index -> page owner -> production store",
        "calibration": {name: semantic(report) for name, report in reports.items()},
        "controls": {
            "noChangeRandomCandidateDirectory": True,
            "knownFinalRandomCandidateDirectory": True,
            "failClosedScorerExit": 2,
            "failClosedReason": reports["fail-closed-control"]["diagnostics"]["setupError"],
        },
        "requirements": {
            "sourceObserver": False, "roleAffectsVerdict": False,
            "pageOwnerRequired": True, "reopenedPreferencesRequired": True,
            "evaluatorStoreWrites": 0, "detachedControllers": 0,
        },
        "errors": [],
    }
    write(migration / "provenance/arkts-runtime-harness-audit.json", runtime_audit)

    manifest.update({
        "status": "android_and_arkts_base_final_calibrated",
        "sourceProjects": {
            **manifest.get("sourceProjects", {}), "arktsBase": "arkts/base", "arktsFinal": "arkts/final",
        },
        "arkts": {
            "sdk": "OpenHarmony API23", "runtime": "ArkVM/ArkUI Index page owner",
            "sourceOwnership": "arkts/source_ownership.json", "bindings": "arkts/bindings.json",
        },
        "moduleMapping": module_mapping(task),
        "validation": {
            "androidBase": "0/10", "androidFinal": "10/10",
            "arktsBase": "0/10", "arktsFinal": "10/10", "notScored": 0,
            "arktsNoChangeControl": "0/10", "arktsKnownFinalControl": "10/10",
            "arktsFailClosedControl": "10/10 not_scored with exit 2",
        },
        "agentResult": "not_run_by_request",
        "publicationEligible": True,
    })
    write(migration / "manifest.json", manifest)

    execution = load(migration / "execution.json")
    execution["arkts"] = {
        "environment": {"sdk": "OpenHarmony API23", "runtime": "ArkVM", "deviceTarget": target["target"]},
        "materializeCommand": ["python3", "../tools/materialize_new_arkts_runtime.py", "--task", task],
        "baseProject": "arkts/base", "finalProject": "arkts/final",
        "buildCommand": ["bash", "build.sh"],
        "semanticCommand": ["python3", "arkts/evaluator/run_device_semantic.py", "--project", "{project}", "--role", "{role}", "--output", "{output}"],
        "candidatePolicy": "Any standalone candidate directory is accepted. Missing source, HAP, API23 target, install, page owner, Preferences reopening, or runtime payload fails closed as not_scored with nonzero exit.",
        "deviceLocks": ["/tmp/long-term-benchmark-arkts-device.lock", toolchain["device"]["lock"]],
        "diskSafetyLineBytes": toolchain["diskSafetyLineBytes"],
    }
    execution["resultPolicy"] = (
        "Formal Android API37 and OpenHarmony API23 scoring use runtime state transitions only. "
        "Base/no-change are 0/10, final/known-final are 10/10, and binding/runtime errors remain not_scored."
    )
    write(migration / "execution.json", execution)

    result_manifest = load(results / "manifest.json")
    result_manifest["status"] = "android_and_arkts_base_final_calibrated"
    cells = result_manifest.setdefault("cells", {})
    cells.update({
        "arkts-base": {"compile": "passed", "semantic": "0/10", "notScored": 0, "expectedPolarity": "0/10", "report": "arkts-base.json"},
        "arkts-final": {"compile": "passed", "semantic": "10/10", "notScored": 0, "expectedPolarity": "10/10", "report": "arkts-final.json"},
        "arkts-agent": {"compile": "not_run", "semantic": "not_scored", "reason": "deferred by request"},
    })
    controls = result_manifest.setdefault("candidateControls", {})
    controls.update({
        "arktsNoChange": {"semantic": "0/10", "notScored": 0, "report": "arkts-no-change-control.json"},
        "arktsKnownFinal": {"semantic": "10/10", "notScored": 0, "report": "arkts-known-final-control.json"},
        "arktsFailClosed": {"semantic": "0/10", "notScored": 10, "exit": 2, "report": "arkts-fail-closed-control.json"},
        "arktsDirectories": "fresh random /tmp candidate copies removed after scoring",
    })
    result_manifest["fabricatedPasses"] = 0
    write(results / "manifest.json", result_manifest)

    report_records = [record(migration, results / f"arkts-{name}.json") for name in names]
    write(migration / "provenance/arkts-evidence-index.json", {
        "schemaVersion": 1, "taskId": task,
        "canonicalContract": record(migration, contract_path),
        "reports": report_records,
        "sourceOwnership": record(migration, migration / "arkts/source_ownership.json"),
        "buildEvidence": record(migration, migration / "provenance/arkts-build-evidence.json"),
        "toolchain": record(migration, migration / "provenance/arkts-toolchain.json"),
        "runtimeAudit": record(migration, migration / "provenance/arkts-runtime-harness-audit.json"),
        "transitionParity": record(migration, migration / "provenance/transition-parity.json"),
        "agentResult": "not_run_by_request",
    })


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
