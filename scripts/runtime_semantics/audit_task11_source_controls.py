#!/usr/bin/env python3
"""Revalidate Task11 controls without executing devices or modifying reports."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.run_runtime_transition_matrix import validate_report as public_validate
from scripts.runtime_semantics.tasks10_11_runtime_evidence import record, validate_report

TASK = "11_room_upgrade_navigation"
EVIDENCE = ROOT / "experiment_results/runtime_transition_20261020/formal_tasks10_11_source_param_v1"
CONTROLS = ("base", "final", "base-copy", "final-copy")


def audit_one(path: Path, platform: str, control: str, contract: dict) -> dict:
    entry = {"platform": platform, "control": control, "path": str(path.resolve()),
             "publicAccepted": False, "integrityAccepted": False, "modelAgentResult": False}
    if not path.is_file():
        return {**entry, "status": "not_run", "semantic": {"passed": 0, "failed": 0, "notScored": 6},
                "reason": "No completed runtime report; no semantic failure inferred."}
    entry["report"] = record(path)
    report = json.loads(path.read_text())
    role = "agent" if control.endswith("-copy") else control
    if (report.get("taskId") != TASK or report.get("platform") != platform or
            report.get("role") != role or report.get("modelAgentResult") is not False):
        raise ValueError("Task11 control identity/role mismatch")
    public_validate(report, contract)
    validate_report(report, contract)
    rows = report["semantic"]["cases"]
    counts = {name: sum(row["status"] == status for row in rows) for name, status in
              (("passed", "pass"), ("failed", "fail"), ("notScored", "not_scored"))}
    expected = "fail" if control in ("base", "base-copy") else "pass"
    if len(rows) != 6 or any(row["status"] != expected for row in rows):
        raise ValueError("Task11 copy/calibration polarity is not closed")
    snapshots = [point["actualSnapshot"] for row in rows for point in row["checkpoints"]
                 if point.get("actualSnapshot")]
    if platform == "arkts" and len(snapshots) != 12:
        raise ValueError("Task11 ArkTS needs twelve readable actual snapshots")
    haps = [item for cleanup in report["provenance"].get("hapCleanup", []) for item in cleanup["files"]]
    if any(not item.get("deleted") or Path(item["path"]).exists() or len(item["sha256"]) != 64 for item in haps):
        raise ValueError("Task11 HAP cleanup/hash evidence incomplete")
    return {**entry, "status": "accepted", "publicAccepted": True, "integrityAccepted": True,
            "semantic": counts, "role": role, "source": report.get("target"),
            "inputKind": report.get("inputKind", "retained_source_bound_calibration"),
            "sourceInventory": report["provenance"].get("sourceInventory",
                report["provenance"].get("sourceSnapshot", {}).get("sourceInventory")),
            "productionSourceCount": len(report["provenance"]["productionSources"]),
            "actualSnapshots": snapshots, "applicationCompile": report.get("compile"),
            "runtimeCompile": report["runtimeCompile"],
            "hashedDeletedHaps": {"files": len(haps), "bytes": sum(item["bytes"] for item in haps)},
            "temporaryInputRemoved": not Path(report["target"]).exists(),
            "cleanup": report["diagnostics"]["strictRuntime"]["cleanup"].get(
                "retainedEvidenceExcludesBinaries", False)}


def build_audit(paths: dict) -> dict:
    started = time.monotonic()
    contract_path = ROOT / "benchmark_tasks" / TASK / "transitions.json"
    contract = json.loads(contract_path.read_text())
    entries = [audit_one(paths[(platform, control)], platform, control, contract)
               for platform in ("android", "arkts") for control in CONTROLS]
    copy_bindings = []
    for platform in ("android", "arkts"):
        for original in ("base", "final"):
            baseline, candidate = [next(item for item in entries if item["platform"] == platform and
                                       item["control"] == control) for control in (original, original + "-copy")]
            if baseline["status"] != "accepted" or candidate["status"] != "accepted":
                continue
            left, right = baseline["sourceInventory"], candidate["sourceInventory"]
            if (not left or not right or (left["files"], left["sha256"]) != (right["files"], right["sha256"]) or
                    baseline["source"] == candidate["source"]):
                raise ValueError("Task11 copy does not bind the matching calibration inventory and a distinct source")
            copy_bindings.append({"platform": platform, "control": original + "-copy",
                                  "matchingInventorySha256": left["sha256"], "distinctStandaloneSources": True})
    return {"taskId": TASK, "contract": record(contract_path), "reports": entries,
            "copySourceBindings": copy_bindings,
            "fourWayRuntimeControlsClosed": {platform: all(item["status"] == "accepted"
                for item in entries if item["platform"] == platform) for platform in ("android", "arkts")},
            "readinessModified": False, "centralModified": False,
            "applicationBuildStarted": False, "deviceExecutionStarted": False,
            "modelAgentResult": False, "overallElapsedSeconds": round(time.monotonic() - started, 3)}


def default_paths() -> dict:
    paths = {(platform, control): EVIDENCE / "public-audit-v6/task11" / platform /
             (control + ".runtime.json") for platform in ("android", "arkts") for control in CONTROLS}
    for control in CONTROLS:
        version = "current-controls-v2" if control == "base" else "current-controls-v1"
        paths[("arkts", control)] = EVIDENCE / version / "task11/arkts" / control / "accepted.runtime.json"
    return paths


def current_paths(android_controls: Path) -> dict:
    """Keep historical defaults reproducible; explicitly opt into a newer run."""
    paths = default_paths()
    for control in CONTROLS:
        paths[("android", control)] = android_controls / control / "accepted.runtime.json"
    return paths


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--android-controls", type=Path,
                        help="Explicit current Android control directory; never rewrites historical defaults")
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("Refusing to overwrite prior audit")
    result = build_audit(current_paths(args.android_controls) if args.android_controls else default_paths())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result["fourWayRuntimeControlsClosed"]))


if __name__ == "__main__":
    main()
