"""The single reviewed Android11 base post-render counterexample.

No arbitrary policy/report input and no generic NS-to-FAIL promotion. The fixed
verifier independently checks original production, evaluator, log and PNG bytes.
Unknown fields stay absent. Every rejection raises ValueError before mutation.
"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from pathlib import Path

from . import android_supplemental

ROOT = Path(__file__).resolve().parents[2]
TASK = "11_room_upgrade_navigation"
CASE = "ru_state_005_room_list_tombstone_preview"
KEY = "room_list_tombstone_preview"
DIRECTORY = ROOT / "experiment_results/runtime_transition_20261019/android_base_followup/task11-preview"
POLICY = DIRECTORY / "reviewed-policy.json"
REPORT = DIRECTORY / "base-v2.json"
CONTRACT = ROOT / "benchmark_tasks" / TASK / "transitions.json"
VERIFIER = ROOT / "state_tests/runtime/android/11_room_upgrade_navigation/base_assertion/verify.py"
POLICY_SHA256 = "19629e67d842abbf5e74032b7e26e9db7ba94a77d807e2d706eff3825b2a6f77"
REPORT_SHA256 = "1c56519171e17c3568f74b1ceb7b9d5abb2fb5e554e8c18633f0fc61e35a0399"
VERIFIER_SHA256 = "972ef1e3050853fb339a377376cffc39581c46dc8f1e96c3683f951a73fdaff6"


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _equal(actual, expected, message):
    _require(json.dumps(actual, sort_keys=True) == json.dumps(expected, sort_keys=True), message)


def _bound_bytes(path, digest):
    data = path.read_bytes()
    _require(hashlib.sha256(data).hexdigest() == digest, f"Changed reviewed artifact: {path}")
    return data


def _fixed_inputs(primary, contract):
    policy = json.loads(_bound_bytes(POLICY, POLICY_SHA256))
    source = json.loads(_bound_bytes(REPORT, REPORT_SHA256))
    canonical = json.loads(_bound_bytes(CONTRACT, policy["contractSha256"]))
    _bound_bytes(VERIFIER, VERIFIER_SHA256)
    _require(policy["schemaVersion"] == 1 and policy["reportSha256"] == REPORT_SHA256, "Unreviewed policy version/report")
    _equal({field: policy[field] for field in ("taskId", "role", "platform", "caseId", "key", "kind")},
           {"taskId": TASK, "role": "base", "platform": "android", "caseId": CASE, "key": KEY,
            "kind": "canonical_conjunct_failure"}, "Unreviewed conjunct identity")
    if contract is not None:
        _equal(contract, canonical, "Supplied canonical contract differs from reviewed version")
    spec = next(case for case in canonical["cases"] if case["caseId"] == CASE)
    _equal({field: spec[field] for field in ("taskId", "caseId", "key", "traceDigest", "given", "event")},
           {field: policy[field] for field in ("taskId", "caseId", "key", "traceDigest", "given", "event")}, "Case inputs/digest differ")
    _equal(policy["assertedExpected"], {"preview": spec["expected"]["preview"]}, "Reviewed oracle differs")
    _equal(policy["unobservedExpectedFields"], ["isTombstoned", "avatarMarkedTombstoned"], "Unknown fields changed")
    _equal(primary["schemaVersion"], 1, "Unreviewed primary report schema version")
    _require(primary["platform"] == "android" and primary["observationMode"] == "runtime_state_transition", "Wrong primary runtime identity")
    errors = android_supplemental._identity_errors(primary, TASK, "base", policy["contractSha256"], source)
    _require(not errors, "; ".join(errors))
    for field in ("commit", "tree"):
        _equal(primary["provenance"][field], policy[field], f"Reviewed candidate {field} differs")
    _equal(primary["provenance"]["source"], source["provenance"]["source"], "Candidate source location differs")
    return policy, source, canonical


def _verify_existing(primary):
    _bound_bytes(VERIFIER, VERIFIER_SHA256)
    spec = importlib.util.spec_from_file_location("_reviewed_android11_conjunct_verifier", VERIFIER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.verified_assessment(primary)


def _row(policy, source):
    raw = source["observations"][0]
    report_ref = {"path": str(REPORT), "sha256": REPORT_SHA256}
    return {
        "schemaVersion": 1, "kind": "canonical_conjunct_failure", "taskId": TASK, "platform": "android", "role": "base",
        "caseId": CASE, "key": KEY, "traceDigest": policy["traceDigest"], "status": "fail",
        "failPhase": "post_event_assertion", "transitionExecuted": True,
        "given": copy.deepcopy(policy["given"]), "event": copy.deepcopy(policy["event"]),
        "observed": copy.deepcopy(raw["observed"]), "assertedExpected": copy.deepcopy(policy["assertedExpected"]),
        "unobservedExpectedFields": copy.deepcopy(policy["unobservedExpectedFields"]),
        "invariantChecks": copy.deepcopy(raw["invariantChecks"]), "checkpoints": copy.deepcopy(raw["checkpoints"]),
        "productionSources": copy.deepcopy(policy["reviewedSourceClosure"]), "provenance": copy.deepcopy(source["provenance"]),
        "runtime": {"executionEnvironment": source["executionEnvironment"], "runtimeCompileStatus": source["runtimeCompile"]["status"],
                    "log": copy.deepcopy(source["log"]), "report": report_ref},
        "conjunctFailureEvidence": {
            "schemaVersion": 1, "policyId": policy["policyId"],
            "policy": {"path": str(POLICY), "sha256": POLICY_SHA256}, "report": report_ref,
            "verifier": {"path": str(VERIFIER), "sha256": VERIFIER_SHA256},
            "observationIds": [f"android-rendered:{REPORT_SHA256}:{CASE}:preview"],
        },
        "reason": "Reviewed original rendered preview contradicts one canonical conjunct; other expected fields remain unobserved.",
    }


def _check_assessment(assessment, row):
    for field in ("schemaVersion", "kind", "status", "failPhase", "taskId", "platform", "role", "caseId", "traceDigest",
                  "given", "event", "transitionExecuted", "observed", "assertedExpected", "unobservedExpectedFields", "invariantChecks"):
        _equal(assessment[field], row[field], f"Independent assessment {field} differs")
    _equal(assessment["observationIds"], row["conjunctFailureEvidence"]["observationIds"], "Observation identity differs")
    _equal(assessment["runtimeReport"], row["conjunctFailureEvidence"]["report"], "Independent runtime report differs")
    _equal(assessment["policy"], dict(row["conjunctFailureEvidence"]["policy"], id=row["conjunctFailureEvidence"]["policyId"]), "Independent policy differs")
    _require(row["observed"] == {"preview": "Earlier message"} and row["assertedExpected"] == {"preview": "room_replaced"},
             "No reviewed actual wrong value")


def build_conjunct_failure(primary, contract=None):
    """Build only the reviewed task11 base row, or raise ValueError on any gap."""
    try:
        policy, source, _ = _fixed_inputs(primary, contract)
        row = _row(policy, source)
        _check_assessment(_verify_existing(primary), row)
        return row
    except Exception as error:
        raise ValueError(f"Android conjunct evidence rejected: {error}") from error


def validate_conjunct_failure(row, report, usedids, contract=None):
    """Independently reverify; reserve the observation only after full success."""
    try:
        policy, source, _ = _fixed_inputs(report, contract)
        expected = _row(policy, source)
        _equal(row, expected, "Conjunct row differs from bound runtime evidence")
        ids = set(expected["conjunctFailureEvidence"]["observationIds"])
        _require(not ids.intersection(usedids), "Conjunct observation already used")
        _check_assessment(_verify_existing(report), expected)
        usedids.update(ids)
    except Exception as error:
        raise ValueError(f"Android conjunct evidence rejected: {error}") from error


def merge_conjunct_failure(primary, contract=None):
    """Copy and promote only the unique unscored reviewed row; preserve all else."""
    try:
        _, _, canonical = _fixed_inputs(primary, contract)
        cases = primary["semantic"]["cases"]
        _equal(sorted((case["caseId"], case["traceDigest"]) for case in cases),
               sorted((case["caseId"], case["traceDigest"]) for case in canonical["cases"]), "Primary canonical case set differs")
        previous = next(case for case in cases if case["caseId"] == CASE)
        _require(previous["status"] == "not_scored", "Existing scored case requires conflict review")
        row = build_conjunct_failure(primary, canonical)
        merged = copy.deepcopy(primary)
        merged["semantic"]["cases"] = [row if case["caseId"] == CASE else case for case in merged["semantic"]["cases"]]
        for key, status in (("passed", "pass"), ("failed", "fail"), ("notScored", "not_scored")):
            merged["semantic"][key] = sum(case["status"] == status for case in merged["semantic"]["cases"])
        merged["semantic"]["total"] = len(cases)
        merged.setdefault("diagnostics", {}).setdefault("androidConjunctEvidence", []).append({
            "caseId": CASE, "previous": copy.deepcopy(previous), "evidence": copy.deepcopy(row["conjunctFailureEvidence"])})
        return merged
    except Exception as error:
        raise ValueError(f"Android conjunct merge rejected: {error}") from error
