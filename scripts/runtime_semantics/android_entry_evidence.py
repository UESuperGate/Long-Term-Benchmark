"""One reviewed Android entry assertion; never infer post-state from missing APIs.

validate_entry_failure raises ValueError on rejection and reserves the observation
ID only on success. build_entry_failure returns an NS row on any evidence gap.
No shared matrix behavior, original reports, or application files are modified.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

from . import android_supplemental as supplemental

ROOT = Path(__file__).resolve().parents[2]
DIRECTORY = ROOT / "experiment_results/runtime_transition_20261019/android_followup_14/baseline_entry"
EVIDENCE = DIRECTORY / "base.json"
POLICY = DIRECTORY / "initial-entry.reviewed-policy.json"
POLICY_SHA256 = "6051665c72b0bd18dd03e94b7547d4a8c3f0b1d985c7129b14d082df6782a666"
TASK = "14_join_room_by_address"
CASE = "jr_state_001_entry_opens_address_flow"
KEY = "entry_opens_address_flow"


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _equal(actual, expected, message):
    # JSON serialization distinguishes false from 0, unlike Python equality.
    _require(json.dumps(actual, sort_keys=True) == json.dumps(expected, sort_keys=True), message)


def _read_bound(path, digest):
    data = path.read_bytes()
    _require(hashlib.sha256(data).hexdigest() == digest, f"Artifact digest changed: {path}")
    return json.loads(data)


def _load_verified(primary):
    policy = _read_bound(POLICY, POLICY_SHA256)
    source = _read_bound(EVIDENCE, policy["reportSha256"])
    contract = _read_bound(ROOT / "benchmark_tasks" / TASK / "transitions.json", policy["contractSha256"])
    specs = [case for case in contract["cases"] if case["caseId"] == CASE]
    _require(len(specs) == 1 and contract["taskId"] == TASK, "Canonical case missing or ambiguous")
    spec = specs[0]
    for field in ("taskId", "caseId", "key", "traceDigest", "given", "event"):
        _equal(spec[field], policy[field], f"Reviewed canonical {field} differs")
    for report in (source, primary):
        _require(report["platform"] == "android", "Wrong platform")
        _require(report["observationMode"] == "runtime_state_transition", "Wrong observation mode")
        errors = supplemental._identity_errors(report, TASK, "base", policy["contractSha256"], source)
        _require(not errors, "; ".join(errors))
        for field in ("tree", "commit"):
            _require(report["provenance"][field] == policy[field], f"Reviewed {field} differs")
    _require(source["executionEnvironment"] == "host_jvm_robolectric_rendered_compose", "Wrong execution scope")
    _require(source["runtimeCompile"]["status"] == "passed", "Fixture did not compile")
    _require(source["status"] == "failed", "Expected entry assertion did not fail")
    manifest = source["provenance"]["productionSources"]
    for record in policy["reviewedSourceClosure"]:
        matches = [item for item in manifest if item["path"] == record["path"]]
        _require(len(matches) == 1 and matches[0]["sha256"] == record["sha256"], "Reviewed closure missing or changed")
    errors = supplemental._validate_artifacts(source)
    _require(not errors, "; ".join(errors))
    _check_observations(source, spec)
    return policy, source, spec


def _check_observations(source, spec):
    _require(len(source["observations"]) == 1 and len(source["semantic"]["cases"]) == 1,
             "Entry probe must contain exactly one case")
    raw, normalized = source["observations"][0], source["semantic"]["cases"][0]
    for field in ("key", "caseId", "traceDigest"):
        _equal(normalized[field], spec[field], f"Evidence {field} differs")
    _require(raw["key"] == KEY and raw["status"] == "fail", "Wrong raw case outcome")
    _require(normalized["status"] == "not_scored", "Original probe classification changed")
    _require(raw["reason"].startswith("java.lang.AssertionError: Canonical select_join_by_address requires one rendered action expected:<1> but was:<0>\n"),
             "Not the reviewed required-entry assertion")
    for field in ("checkpoints", "observed", "invariantChecks"):
        _equal(raw[field], normalized[field], f"Raw/normalized {field} differs")
    log = Path(source["log"]["path"]).read_text()
    logged = [json.loads(line.split("RUNTIME_RESULT ", 1)[1]) for line in log.splitlines() if "RUNTIME_RESULT " in line]
    _equal(logged, [raw], "Raw observation differs from runtime log")
    _equal(raw["invariantChecks"], [], "Post-transition invariants were not evaluated")
    _equal(raw["observed"], {"givenSurface": "start_chat", "givenSearchActive": False,
                            "joinActionCount": 0, "transitionExecuted": False}, "Wrong entry observation")
    points = raw["checkpoints"]
    _equal([item["name"] for item in points], ["canonical_start_chat_given", "real_entry_controls",
           "existing_new_room_control_routes_through_production_flow"], "Wrong checkpoint sequence")
    before, controls, after = [item["state"] for item in points]
    _equal({key: before[key] for key in spec["given"]}, spec["given"], "Givens not established")
    _equal(before["query"], "", "Search query not empty")
    root = [{"target": "Root", "fromState": "ACTIVE", "targetState": "ACTIVE"}]
    _equal(before["navigation"], root, "Root not active")
    _equal(controls["navigation"], root, "Controls not observed at same root")
    for field, value in (("joinActionCount", 0), ("newRoomEnabled", True),
                         ("userSearchEnabled", True), ("searchActive", False)):
        _equal(controls[field], value, f"Entry prerequisite {field} not established")
    ranges = controls["scrollRanges"]
    _require(bool(ranges), "No complete viewport evidence")
    for item in ranges:
        _require(type(item["value"]) in (float, int) and type(item["maxValue"]) in (float, int)
                 and item["value"] == 0 and item["maxValue"] == 0, "Unexplored scroll content")
    tree = controls["semantics"]
    for marker in ("[Start chat]", "[New room]", "[Invite people to Element X]", "Focused = 'false'", "EditableText = ''"):
        _require(marker in tree, f"Rendered anchor missing: {marker}")
    _equal(after["navigation"], [{"target": "Root", "fromState": "ACTIVE", "targetState": "STASHED"},
                                {"target": "NewRoom", "fromState": "CREATED", "targetState": "ACTIVE"}],
           "Same-flow positive control did not navigate")


def _scored_row(policy, source, spec):
    return {
        "taskId": TASK, "platform": "android", "role": "base", "caseId": CASE,
        "key": KEY, "traceDigest": spec["traceDigest"], "status": "fail", "failPhase": "entry",
        "transitionExecuted": False, "canonicalEventAttempted": False,
        "given": copy.deepcopy(spec["given"]), "event": copy.deepcopy(spec["event"]),
        "observed": None, "invariantChecks": [], "unevaluatedInvariants": copy.deepcopy(spec["invariants"]),
        "reason": "Reviewed rendered initial entry is absent after established givens; no post-state or invariant result claimed.",
        "executionEnvironment": source["executionEnvironment"],
        "entryFailureEvidence": {
            "policyId": policy["policyId"], "policySha256": POLICY_SHA256,
            "report": str(EVIDENCE), "reportSha256": policy["reportSha256"],
            "observationIds": [f"android-entry:{policy['reportSha256']}:{CASE}"],
        },
        "productionSources": copy.deepcopy(policy["reviewedSourceClosure"]),
        "checkpoints": copy.deepcopy(source["observations"][0]["checkpoints"]),
    }


def validate_entry_failure(row, report, usedids):
    """Raise ValueError on any gap; reserve IDs only after complete validation."""
    try:
        policy, source, spec = _load_verified(report)
        expected = _scored_row(policy, source, spec)
        _equal(row, expected, "Entry row differs from independently verified evidence")
        ids = expected["entryFailureEvidence"]["observationIds"]
        _require(not set(ids).intersection(usedids), "Entry observation already used")
        usedids.update(ids)
        return {"status": "fail", "caseId": CASE, "observationIds": ids}
    except Exception as error:
        raise ValueError(f"Android entry evidence rejected: {error}") from error


def build_entry_failure(primary_report):
    """Return the single scored row, or an explicit NS diagnostic on rejection."""
    try:
        return _scored_row(*_load_verified(primary_report))
    except Exception as error:
        return {"taskId": TASK, "platform": "android", "role": "base", "caseId": CASE,
                "key": KEY, "status": "not_scored", "observed": None, "invariantChecks": [],
                "transitionExecuted": False, "reason": f"Android entry evidence rejected: {error}"}


def merge_entry_failure(primary_report):
    """Copy the primary report and replace only its unique, unscored initial row.

    Compilation and all other rows are preserved. Conflicts/gaps are diagnostics,
    never a downgrade or blanket baseline promotion. No files are written.
    """
    merged = copy.deepcopy(primary_report)
    row = build_entry_failure(primary_report)
    cases = merged.get("semantic", {}).get("cases", [])
    matches = [item for item in cases if item.get("caseId") == CASE]
    reason = row.get("reason")
    if len(matches) != 1 or matches[0].get("status") != "not_scored":
        reason = "Initial case missing, duplicated, or already scored; explicit conflict review required"
    elif row["status"] == "fail" and matches[0].get("traceDigest") == row["traceDigest"]:
        index = cases.index(matches[0])
        cases[index] = row
        semantic = merged["semantic"]
        for field, status in (("passed", "pass"), ("failed", "fail"), ("notScored", "not_scored")):
            semantic[field] = sum(item.get("status") == status for item in cases)
        return merged
    elif row["status"] == "fail":
        reason = "Primary initial case digest differs"
    merged.setdefault("diagnostics", {})["androidEntryEvidenceRejected"] = reason
    return merged
