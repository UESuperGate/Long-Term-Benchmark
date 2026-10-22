"""One approved task12 base Presenter/UI entry assertion, not a generic scorer."""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from pathlib import Path

from . import android_supplemental

ROOT = Path(__file__).resolve().parents[2]
TASK = "12_report_room"
CASE = "rr_state_001_initial_form"
KEY = "initial_form"
DIRECTORY = ROOT / "experiment_results/runtime_transition_20261019/android_base_followup/task12-presenter"
POLICY = DIRECTORY / "reviewed-policy.json"
REPORT = DIRECTORY / "base-v4.json"
CONTRACT = ROOT / "benchmark_tasks" / TASK / "transitions.json"
VERIFIER = ROOT / "state_tests/runtime/android/12_report_room/baseline_presenter/verify.py"
POLICY_SHA256 = "367af917fac256a2621e93cd82f7d18430852b36750bc0022e893876f6d84510"
REPORT_SHA256 = "8e0527e37079af19d69edc17371403f50792b9c8d92faabd76dd3a5894ddffe6"
VERIFIER_SHA256 = "5f7ed6863eced3f52640b64e9b8220abff9cf3d02d243270ddd94f85799cd350"
POLICY_ID = "android.task12.base.initial.presenter-ui.entry.reviewed.v1"


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _equal(actual, expected, message):
    _require(json.dumps(actual, sort_keys=True) == json.dumps(expected, sort_keys=True), message)


def _bound(path, digest):
    data = path.read_bytes()
    _require(hashlib.sha256(data).hexdigest() == digest, f"Changed reviewed artifact: {path}")
    return data


def _fixed_inputs(primary, contract=None):
    policy = json.loads(_bound(POLICY, POLICY_SHA256))
    source = json.loads(_bound(REPORT, REPORT_SHA256))
    canonical = json.loads(_bound(CONTRACT, policy["contractSha256"]))
    _bound(VERIFIER, VERIFIER_SHA256)
    _equal({key: policy[key] for key in ("schemaVersion", "policyId", "taskId", "role", "platform", "caseId", "key")},
           {"schemaVersion": 1, "policyId": POLICY_ID, "taskId": TASK, "role": "base", "platform": "android",
            "caseId": CASE, "key": KEY}, "Unreviewed policy identity")
    _equal(policy["report"], {"path": str(REPORT), "sha256": REPORT_SHA256}, "Wrong fixed report")
    _equal(policy["verifier"], {"path": str(VERIFIER), "sha256": VERIFIER_SHA256}, "Wrong fixed verifier")
    if contract is not None:
        _equal(contract, canonical, "Supplied canonical contract differs from reviewed version")
    specs = [spec for spec in canonical["cases"] if spec["caseId"] == CASE]
    _require(len(specs) == 1 and canonical["taskId"] == TASK, "Wrong canonical case")
    spec = specs[0]
    for field in ("taskId", "caseId", "key", "traceDigest", "given", "event", "expected", "invariants"):
        _equal(spec[field], policy[field], f"Reviewed canonical {field} differs")
    _equal(primary["schemaVersion"], 1, "Unreviewed primary schema")
    for report in (primary, source):
        _require(report["platform"] == "android" and report["observationMode"] == "runtime_state_transition", "Wrong runtime identity")
        errors = android_supplemental._identity_errors(report, TASK, "base", policy["contractSha256"], source)
        _require(not errors, "; ".join(errors))
        for field in ("commit", "tree"):
            _equal(report["provenance"][field], policy[field], f"Reviewed candidate {field} differs")
    _equal(primary["provenance"]["source"], source["provenance"]["source"], "Candidate source location differs")
    _equal(source["executionEnvironment"], policy["executionEnvironment"], "Execution scope differs")
    _equal(source["log"], policy["runtimeLog"], "Runtime log binding differs")
    for field in ("evaluatorSources", "renderedRunner", "packagingSources"):
        _equal(source["provenance"][field], policy[field], f"Pinned {field} differs")
    manifest = {record["path"]: record for record in source["provenance"]["productionSources"]}
    for record in policy["reviewedSourceClosure"]:
        _equal(manifest.get(record["path"]), record, "Reviewed production closure differs")
    points = source["observations"][0]["checkpoints"]
    _equal([point["name"] for point in points], policy["prerequisiteCheckpoints"], "Prerequisite sequence differs")
    _equal([point["state"]["pixels"] for point in points if point["state"].get("pixels")], policy["pixels"], "Pixels binding differs")
    _equal(sorted((row["caseId"], row["traceDigest"]) for row in primary["semantic"]["cases"]),
           sorted((case["caseId"], case["traceDigest"]) for case in canonical["cases"]), "Primary canonical case set differs")
    return policy, source, canonical


def _verify_existing():
    # The pinned verifier checks all source blobs, evaluator/log bytes, PNGs,
    # same-instance production sinks, full viewport, and actual dialog roundtrip.
    _bound(VERIFIER, VERIFIER_SHA256)
    spec = importlib.util.spec_from_file_location("_reviewed_android12_presenter_verifier", VERIFIER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.verify()


def _check_assessment(assessment, policy):
    _equal(assessment["status"], "verified_presenter_entry_probe_pending_review", "Unexpected underlying probe classification")
    _equal(assessment["canonicalStatus"], "not_scored", "Original probe must remain unscored")
    for field in ("caseId", "traceDigest", "given", "event"):
        _equal(assessment[field], policy[field], f"Independent assessment {field} differs")
    _equal(assessment["unobservedExpectedFields"], list(policy["expected"]), "Unknown field set differs")
    _require(assessment["observed"] is None and assessment["transitionExecuted"] is False and
             assessment["invariantChecks"] == [], "Verifier invented poststate")
    _equal(assessment["reportArtifact"]["sha256"], REPORT_SHA256, "Verified report differs")
    _equal(assessment["verifier"]["sha256"], VERIFIER_SHA256, "Verifier identity differs")
    _equal(assessment["runtimeLog"], policy["runtimeLog"], "Verified log differs")


def _row(policy, source):
    return {
        "schemaVersion": 1, "kind": "reviewed_presenter_ui_entry_failure", "taskId": TASK, "platform": "android", "role": "base",
        "caseId": CASE, "key": KEY, "traceDigest": policy["traceDigest"], "status": "fail", "failPhase": "entry",
        "transitionExecuted": False, "entryActionAttempted": True, "canonicalEventExecuted": False,
        "given": copy.deepcopy(policy["given"]), "event": copy.deepcopy(policy["event"]), "observed": None,
        "unobservedExpectedFields": list(policy["expected"]), "invariantChecks": [],
        "unevaluatedInvariants": copy.deepcopy(policy["invariants"]),
        "scope": {"productionPresenterAndView": True, "externalPortsControlled": True,
                  "fullApp": False, "nodeMounted": False, "backstackVerified": False},
        "prerequisiteChecks": [
            {"name": "room_id_from_original_presenter", "passed": True, "checkpoint": "canonical_given_from_production_presenter"},
            {"name": "complete_original_viewport", "passed": True, "checkpoint": "before_entry_attempt"},
            {"name": "real_report_entry_action_attempt", "passed": True, "checkpoint": "canonical_entry_attempt"},
            {"name": "same_receiver_production_leave_dialog", "passed": True, "checkpoint": "production_leave_confirmation_visible"},
            {"name": "original_cancel_restores_same_root", "passed": True, "checkpoint": "production_cancel_restores_root"}],
        "entryAssertion": {"requiredEntryCount": 1, "actualEntryCount": 0, "passed": False},
        "checkpoints": copy.deepcopy(source["observations"][0]["checkpoints"]),
        "productionSources": copy.deepcopy(policy["reviewedSourceClosure"]), "provenance": copy.deepcopy(source["provenance"]),
        "runtime": {"executionEnvironment": source["executionEnvironment"], "runtimeCompileStatus": source["runtimeCompile"]["status"],
                    "log": copy.deepcopy(source["log"]), "report": copy.deepcopy(policy["report"])},
        "entryFailureEvidence": {"schemaVersion": 1, "policyId": POLICY_ID,
            "policy": {"path": str(POLICY), "sha256": POLICY_SHA256}, "report": copy.deepcopy(policy["report"]),
            "verifier": copy.deepcopy(policy["verifier"]), "observationIds": [f"android-task12-entry:{REPORT_SHA256}:{CASE}"]},
        "reason": "Approved initial Presenter/UI entry assertion: canonical roomId established, actual report entry absent; same-receiver production Leave/Cancel positive control completed. No canonical poststate or invariant result claimed.",
    }


def build_entry_failure(primary, contract=None):
    try:
        policy, source, _ = _fixed_inputs(primary, contract)
        _check_assessment(_verify_existing(), policy)
        return _row(policy, source)
    except Exception as error:
        raise ValueError(f"Task12 entry evidence rejected: {error}") from error


def validate_entry_failure(row, report, usedids, contract=None):
    """Reject every deviation; reserve the one observation only after verification."""
    try:
        policy, source, _ = _fixed_inputs(report, contract)
        expected = _row(policy, source)
        _equal(row, expected, "Entry row differs from fixed reviewed evidence")
        ids = set(expected["entryFailureEvidence"]["observationIds"])
        _require(not ids.intersection(usedids), "Entry observation already used")
        _check_assessment(_verify_existing(), policy)
        usedids.update(ids)
    except Exception as error:
        raise ValueError(f"Task12 entry evidence rejected: {error}") from error


def merge_entry_failure(primary, contract=None):
    """Return a copy with only case001 replaced. Any conflict raises, never scores."""
    try:
        _fixed_inputs(primary, contract)
        previous = next(row for row in primary["semantic"]["cases"] if row["caseId"] == CASE)
        _require(previous["status"] == "not_scored", "Existing scored case requires conflict review")
        row = build_entry_failure(primary, contract)
        merged = copy.deepcopy(primary)
        merged["semantic"]["cases"] = [row if item["caseId"] == CASE else item for item in merged["semantic"]["cases"]]
        for field, status in (("passed", "pass"), ("failed", "fail"), ("notScored", "not_scored")):
            merged["semantic"][field] = sum(item["status"] == status for item in merged["semantic"]["cases"])
        merged["semantic"]["total"] = len(merged["semantic"]["cases"])
        merged.setdefault("diagnostics", {})["androidTask12EntryEvidence"] = {
            "previous": copy.deepcopy(previous), "evidence": copy.deepcopy(row["entryFailureEvidence"])}
        return merged
    except Exception as error:
        raise ValueError(f"Task12 entry merge rejected: {error}") from error
