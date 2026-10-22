#!/usr/bin/env python3
"""Revalidate retained Task10/11 execution evidence through the public validator.

Only the audited source-bound entry envelope is rebound. Runtime observations,
assertions and candidate hashes are never regenerated from source or role.
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
from scripts.run_runtime_transition_matrix import validate_report as public_validate
from scripts.runtime_semantics import tasks10_11_runtime_evidence as evidence


def refresh(original, contract):
    report = copy.deepcopy(original)
    entries = [row for row in report["semantic"]["cases"] if row.get("entryFailureEvidence")]
    if entries and report["platform"] == "android":
        logs = sorted({Path(row["entryFailureEvidence"]["log"]["path"]) for row in entries})
        report = evidence.bind_report(report, contract, sources=report["provenance"]["productionSources"],
                                      logs=logs, commit=report["provenance"]["commit"],
                                      tree=report["provenance"]["tree"])
    elif entries and report["taskId"] == "10_media_upload_quality" and report["platform"] == "arkts":
        report = evidence.bind_arkts_base(report, contract, entries[0]["entryFailureEvidence"]["device"])
    before = [(r["caseId"], r["status"], r["traceDigest"]) for r in original["semantic"]["cases"]]
    after = [(r["caseId"], r["status"], r["traceDigest"]) for r in report["semantic"]["cases"]]
    evidence.require(before == after, "Metadata refresh altered runtime verdicts")
    return report


def audit(report, contract):
    result = {"publicAccepted": False, "formalEvidenceAccepted": False}
    try:
        public_validate(report, contract)
        result["publicAccepted"] = True
    except (ValueError, OSError, KeyError, StopIteration) as error:
        result["publicError"] = str(error)
    try:
        evidence.validate_report(report, contract)
        result["formalEvidenceAccepted"] = True
    except (ValueError, OSError, KeyError, StopIteration) as error:
        result["formalEvidenceError"] = str(error)
    result["recordedCounts"] = {name: sum(row["status"] == status for row in report["semantic"]["cases"])
                                for name, status in (("passed", "pass"), ("failed", "fail"), ("notScored", "not_scored"))}
    result["acceptedCounts"] = result["recordedCounts"] if result["formalEvidenceAccepted"] else {
        "passed": 0, "failed": 0, "notScored": len(contract["cases"])}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", action="append", nargs=4, metavar=("TASK", "PLATFORM", "CONTROL", "PATH"), required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=False)
    entries = []
    for task, platform, control, name in args.report:
        path = Path(name).resolve()
        original = json.loads(path.read_text())
        contract = json.loads((ROOT / "benchmark_tasks" / original["taskId"] / "transitions.json").read_text())
        report = refresh(original, contract)
        target = args.output_dir / f"task{task}" / platform / f"{control}.runtime.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report, indent=2) + "\n")
        entries.append({"task": task, "platform": platform, "control": control,
                        "original": evidence.record(path), "report": evidence.record(target),
                        **audit(report, contract)})
    (args.output_dir / "public-validation.json").write_text(json.dumps({
        "validator": "scripts.run_runtime_transition_matrix.validate_report",
        "policyImplementation": evidence.record(Path(evidence.__file__)), "reports": entries,
        "newBuildsStarted": False}, indent=2) + "\n")
    print(json.dumps([{k: v for k, v in row.items() if k not in {"original", "report"}} for row in entries], indent=2))


if __name__ == "__main__":
    main()
