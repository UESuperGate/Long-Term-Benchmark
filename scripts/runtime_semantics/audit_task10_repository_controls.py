#!/usr/bin/env python3
"""Read-only public audit of Task10 alternate-architecture calibration and candidate."""
import argparse
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.run_runtime_transition_matrix import validate_report as public_validate
from scripts.runtime_semantics import task10_repository_evidence as repository
from scripts.runtime_semantics import tasks10_11_runtime_evidence as evidence

TASK = "10_media_upload_quality"
EVIDENCE = ROOT / "experiment_results/runtime_transition_20261020/task10_fresh_m3_binding_v2"


def audit_report(path, contract, *, control=None):
    report = json.loads(path.read_text())
    result = {"report": evidence.record(path), "control": control,
              "publicAccepted": False, "integrityAccepted": False,
              "semantic": {key: sum(row["status"] == status for row in report["semantic"]["cases"])
                           for key, status in (("passed", "pass"), ("failed", "fail"),
                                               ("notScored", "not_scored"))},
              "applicationCompile": report.get("compile"), "runtimeCompile": report.get("runtimeCompile"),
              "modelAgentResult": report.get("modelAgentResult", False)}
    if report.get("taskId") != TASK or report.get("platform") != "arkts":
        raise ValueError("Wrong Task10 ArkTS audit identity")
    if control:
        role = "agent" if control.endswith("-copy") else control
        expected = "fail" if control in {"base", "base-copy"} else "pass"
        if (report.get("role") != role or report.get("modelAgentResult") is not False or
                len(report["semantic"]["cases"]) != 9 or
                any(row["status"] != expected for row in report["semantic"]["cases"])):
            raise ValueError("Task10 calibration/copy control polarity or identity mismatch")
    try:
        public_validate(report, contract)
        result["publicAccepted"] = True
        if report.get("provenance", {}).get("runtimeBinding") == repository.BINDING:
            repository.validate_report(report, contract)
        else:
            evidence.validate_report(report, contract)
        result["integrityAccepted"] = True
    except ValueError as error:
        result["error"] = str(error)
        if control:
            raise
    result["sourceInventory"] = report["provenance"]["sourceInventory"]
    if control:
        result["calibrationInput"] = evidence.record(path.parent / "input.json")
    result["productionSourceCount"] = len(report["provenance"]["productionSources"])
    result["actualSnapshotCount"] = sum(bool(point.get("actualSnapshot"))
        for row in report["semantic"]["cases"] for point in row.get("checkpoints", []))
    result["temporarySourceRemoved"] = not Path(report["target"]).exists()
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, default=EVIDENCE /
        "candidate-prefix-public-v1/audit/diagnostic.pending-public.runtime.json")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("Never overwrite an earlier audit")
    started = time.monotonic()
    contract_path = ROOT / "benchmark_tasks" / TASK / "transitions.json"
    contract = json.loads(contract_path.read_text())
    controls = [audit_report(EVIDENCE / "calibration-controls-v1" / control /
                            "accepted.runtime.json", contract, control=control)
                for control in ("base", "final", "base-copy", "final-copy")]
    for left, right in ((controls[0], controls[2]), (controls[1], controls[3])):
        if any(left["sourceInventory"][key] != right["sourceInventory"][key] for key in ("files", "sha256")):
            raise ValueError("Task10 standalone copy source inventory differs from calibration")
    candidate = audit_report(args.candidate, contract)
    result = {"taskId": TASK, "platform": "arkts", "contract": evidence.record(contract_path),
              "controls": controls, "candidate": candidate,
              "currentFourWayCalibrationAccepted": all(row["publicAccepted"] and row["integrityAccepted"]
                                                        for row in controls),
              "candidateFormalAccepted": candidate["publicAccepted"] and candidate["integrityAccepted"],
              "centralModified": False, "readinessModified": False,
              "productionModified": False, "modelInvoked": False,
              "deviceExecutionStarted": False, "fullApplicationBuildStarted": False,
              "overallElapsedSeconds": round(time.monotonic() - started, 3)}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({key: result[key] for key in
                      ("currentFourWayCalibrationAccepted", "candidateFormalAccepted")}))


if __name__ == "__main__":
    main()
