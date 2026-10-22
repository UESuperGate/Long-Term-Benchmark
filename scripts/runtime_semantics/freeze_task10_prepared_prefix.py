#!/usr/bin/env python3
"""Freeze a stricter review draft from retained real evidence, without device replay."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.runtime_semantics import task10_repository_prefix_policy as policy
from scripts.runtime_semantics import tasks10_11_runtime_evidence as evidence
from scripts.run_runtime_transition_matrix import validate_report as public_validate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-bound", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists():
        raise ValueError("Never overwrite a reviewed draft")
    started = time.monotonic()
    output = args.output_dir.resolve()
    output.mkdir(parents=True)
    report = json.loads(args.input_bound.read_text())
    contract_path = ROOT / "benchmark_tasks/10_media_upload_quality/transitions.json"
    contract = json.loads(contract_path.read_text())
    previous = next(row for row in report["semantic"]["cases"] if row["caseId"] == policy.CASE)
    old_proof = previous["entryFailureEvidence"]
    native_path = output / "original-native-row.json"
    native_path.write_bytes(evidence.read_record(old_proof["nativeRow"]))
    build_path = output / "original-build.json"
    build_path.write_bytes(evidence.read_record(old_proof["build"]))
    summary = json.loads(evidence.read_record(old_proof["executionSummary"]))
    # Only a deleted build's storage location is rebound. Actual transport fields stay exact.
    original_transport = copy.deepcopy(summary)
    summary["priorRetainedExecutionSummary"] = old_proof["executionSummary"]
    summary["originalDeviceExecution"] = summary.get("originalExecution")
    summary["buildReport"] = evidence.record(build_path)
    if {key: value for key, value in summary.items() if key not in {
            "buildReport", "priorRetainedExecutionSummary", "originalDeviceExecution"}} != {
            key: value for key, value in original_transport.items() if key not in {
                "buildReport", "priorRetainedExecutionSummary", "originalDeviceExecution"}}:
        raise ValueError("Transport receipt was modified while relocating retained build")
    execution_path = output / "retained-execution-input.json"
    execution_path.write_text(json.dumps(summary, indent=2) + "\n")
    rebound = policy.bind(previous, report, contract, native_path, execution_path, output / "prepared-prefix")
    policy.validate_entry_failure(rebound, report, set(), contract=contract)
    report["semantic"]["cases"] = [rebound if row["caseId"] == policy.CASE else row
                                     for row in report["semantic"]["cases"]]
    for old, new in zip(json.loads(args.input_bound.read_text())["semantic"]["cases"], report["semantic"]["cases"]):
        if new["caseId"] != policy.CASE and old != new:
            raise ValueError("Unrelated runtime row changed")
    target = output / "review.runtime.json"
    target.write_text(json.dumps(report, indent=2) + "\n")
    source_path = Path(policy.__file__)
    frozen_policy = output / source_path.name
    frozen_policy.write_bytes(source_path.read_bytes())
    result = {"policyId": policy.POLICY, "policy": evidence.record(source_path),
              "retainedPolicy": evidence.record(frozen_policy), "previousReview": evidence.record(args.input_bound),
              "reviewReport": evidence.record(target), "contract": evidence.record(contract_path),
              "nativeRow": evidence.record(native_path), "build": evidence.record(build_path),
              "nativeBytesUnchanged": evidence.record(native_path)["sha256"] == old_proof["nativeRow"]["sha256"],
              "transportReceiptFieldsUnchanged": True, "onlyRetainedBuildLocationRebound": True,
              "windowId": next(point["state"]["windowId"] for point in json.loads(native_path.read_text())["checkpoints"]
                               if point["label"] == "prefix:caption-and-quality"),
              "executionNonce": summary["executionNonce"],
              "originalCanonicalAssertionsUnchanged": True, "originalFinalOnlyAssertionsEvaluated": False,
              "absenceScope": "only_prepared_upload_paths_actually_listed_by_original_gateway",
              "sourceInventory": report["provenance"]["sourceInventory"],
              "deviceExecutionStarted": False, "modelInvoked": False,
              "publicAccepted": False, "independentPrefixAccepted": True,
              "semanticDraftOnly": {key: report["semantic"][key] for key in ("passed", "failed", "notScored")}}
    try:
        public_validate(report, contract)
        evidence.validate_report(report, contract)
        result["publicAccepted"] = True
    except ValueError as error:
        result["publicError"] = str(error)
    result["overallElapsedSeconds"] = round(time.monotonic() - started, 3)
    # Pin review inputs even while awaiting central policy review. This is not publication.
    result["freezeObjectSha256"] = hashlib.sha256(json.dumps(result, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    (output / "freeze.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
