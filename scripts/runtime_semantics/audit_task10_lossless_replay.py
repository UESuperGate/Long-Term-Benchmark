#!/usr/bin/env python3
"""Read-only audit of fresh Task10 lossless candidate and four device controls."""
import argparse
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.run_runtime_transition_matrix import validate_report as public_validate
from scripts.runtime_semantics import task10_native_artifacts as native
from scripts.runtime_semantics import task10_repository_evidence as repository
from scripts.runtime_semantics import tasks10_11_runtime_evidence as shared


def audit_one(path, contract, *, control=None):
    report = json.loads(path.read_text())
    public_validate(report, contract)
    if control is None:
        repository.validate_report(report, contract)
    else:
        shared.validate_report(report, contract)
    native_counts, pairs, results = {}, {}, []
    rows = report["semantic"]["cases"]
    for row in rows:
        original = (native.verify_repository_row(row, report) if control is None else
                    native.verify_device_ui_row(row, report))
        native_counts[original["status"]] = native_counts.get(original["status"], 0) + 1
        bundle = row["nativeArtifacts"]
        for pair in [bundle["execution"], bundle["build"], bundle["nativeResult"], *bundle["commandLogs"],
                     *bundle.get("layouts", []), *bundle.get("executionAttempts", [])]:
            native.read_native_artifact(pair)
            pairs[pair["retained"]["path"]] = pair
        results.append({"caseId": row["caseId"], "status": row["status"], "originalNativeStatus": original["status"],
                        "nativeResult": bundle["nativeResult"], "backend": bundle["backend"]})
    if len(rows) != len(contract["cases"]) or any(row["status"] not in {"pass", "fail"} for row in rows):
        raise ValueError("Incomplete Task10 scored case coverage")
    if control:
        expected = "fail" if control in {"base", "base-copy"} else "pass"
        if any(row["status"] != expected for row in rows) or report.get("modelAgentResult") is not False:
            raise ValueError("Task10 control polarity/model identity mismatch")
    return {"control": control, "report": shared.record(path), "publicAccepted": True,
            "losslessRawAccepted": True, "cases": results, "originalNativeCounts": native_counts,
            "semantic": {key: sum(row["status"] == status for row in rows)
                         for key, status in (("passed", "pass"), ("failed", "fail"), ("notScored", "not_scored"))},
            "sourceInventory": report["provenance"]["sourceInventory"],
            "applicationCompile": report["compile"], "runtimeCompile": report["runtimeCompile"],
            "temporarySourceRemoved": not Path(report["target"]).exists(),
            "uniqueRetainedFiles": len(pairs),
            "compressedBytes": sum(pair["retained"]["bytes"] for pair in pairs.values()),
            "uncompressedOriginalBytes": sum(pair["original"]["bytes"] for pair in pairs.values())}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("Refusing previous audit")
    started = time.monotonic()
    contract_path = ROOT / "benchmark_tasks/10_media_upload_quality/transitions.json"
    contract = json.loads(contract_path.read_text())
    reports = [audit_one(args.run_root / "candidate/accepted/accepted.runtime.json", contract)]
    reports += [audit_one(args.run_root / "controls" / name / "accepted.runtime.json", contract, control=name)
                for name in ("base", "final", "base-copy", "final-copy")]
    for left, right in ((reports[1], reports[3]), (reports[2], reports[4])):
        if any(left["sourceInventory"][key] != right["sourceInventory"][key] for key in ("files", "sha256")):
            raise ValueError("Control standalone copy does not match the calibration inventory")
    result = {"taskId": contract["taskId"], "platform": "arkts", "contract": shared.record(contract_path),
              "reports": reports, "publicAndLosslessRawAccepted": True,
              "parentIndependentReviewRequired": True, "publicationPromoted": False,
              "centralModified": False, "readinessModified": False, "modelInvoked": False,
              "overallAuditElapsedSeconds": round(time.monotonic() - started, 3)}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"reports": [{"control": row["control"], "semantic": row["semantic"]} for row in reports],
                      "parentIndependentReviewRequired": True}))


if __name__ == "__main__":
    main()
