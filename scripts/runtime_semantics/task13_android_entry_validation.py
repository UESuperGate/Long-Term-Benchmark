"""Validate fresh Task13 Android revision-5 missing-entry execution evidence."""

from __future__ import annotations

import copy
from pathlib import Path

try:
    from . import task12_13_formal_core as core
except ImportError:
    import task12_13_formal_core as core


POLICY_ID = "android.task13.revision5.live-profile-entry.v1"
REACHABILITY = "base common room-member profile remains reachable before the missing feature entry"


def require(value, message):
    if not value:
        raise ValueError("Task13 entry evidence: " + message)


def validate_raw(row):
    require(row.get("status") == "fail", "missing entry must be an executed assertion failure")
    observed = row.get("observed", {})
    require(all(observed.get(key) is value for key, value in {
        "profilePositiveControl": True, "verifyUserActionVisible": False,
        "legacyVerifyIdentityVisible": True, "legacyVerifyIdentityEnabled": False,
    }.items()), "profile positive controls or missing entry differ")
    require(observed.get("targetUserId") == "@alice:example.org" and
            observed.get("prefixStatus") == "missing_verify_user_action", "given/prefix differs")
    points = {item["name"]: item["state"] for item in row.get("checkpoints", [])}
    require({"common_profile_positive_control", "after_revision5_action_prefix", "cleanup"} <= points.keys(),
            "ordered execution checkpoints missing")
    before = points["common_profile_positive_control"]
    after = points["after_revision5_action_prefix"]
    require(all(before.get(key) is True for key in ("aliceVisible", "messageActionEnabled", "shareActionEnabled")),
            "common profile is not reachable")
    require(after.get("actions") == ["open_room_member_profile", "select_verify_user"] and
            after.get("verifyUserActionCount") == 0, "real action prefix was not observed")
    require("Revision-5 action prefix requires an enabled Verify user action" in (row.get("reason") or ""),
            "failure is not the reviewed entry assertion")
    require(any(item.get("invariant") == REACHABILITY and item.get("status") == "pass"
                for item in row.get("invariantChecks", [])), "positive-control check missing")
    run_id = before.get("caseRunId")
    require(isinstance(run_id, str) and bool(run_id), "fresh production instance ID missing")
    return run_id


def entry_row(spec, raw, raw_path):
    run_id = validate_raw(raw)
    return {
        "caseId": spec["caseId"], "key": spec["key"], "traceDigest": spec["traceDigest"],
        "status": "fail", "transitionExecuted": False,
        "given": copy.deepcopy(spec["given"]), "event": copy.deepcopy(spec["event"]),
        "observed": None, "invariantChecks": [],
        "unevaluatedInvariants": copy.deepcopy(spec["invariants"]),
        "unobservedExpectedFields": list(spec["expected"]),
        "checkpoints": copy.deepcopy(raw["checkpoints"]),
        "entryFailureEvidence": {
            "policyId": POLICY_ID, "canonicalGivenEstablished": True,
            "positiveControlCompleted": True, "rawReport": core.file_record(raw_path),
            "caseRunId": run_id,
        },
        "reason": raw["reason"],
    }


def validate_entry_failure(row, report, used_observation_ids, *, contract):
    require((report.get("taskId"), report.get("platform")) ==
            ("13_user_verification", "android") and report.get("role") in {"base", "final", "agent"},
            "wrong task/platform/role")
    specs = {case["caseId"]: case for case in contract["cases"][:9]}
    require(row.get("caseId") in specs, "case is not a reviewed missing-entry case")
    spec = specs[row["caseId"]]
    evidence = row.get("entryFailureEvidence", {})
    require(evidence.get("policyId") == POLICY_ID, "unknown policy")
    record = evidence["rawReport"]
    raw_path = Path(record["path"]).resolve()
    require(raw_path.is_relative_to(core.ROOT / "experiment_results"), "raw report outside audit root")
    require(core.file_record(raw_path) == record, "raw execution report hash changed")
    raw_report = core.load(raw_path)
    require(raw_report.get("taskId") == report["taskId"] and raw_report.get("role") == report["role"],
            "raw task/role differs")
    require(raw_report.get("runtimeCompile", {}).get("status") == "passed", "runtime compile did not pass")
    require(raw_report.get("provenance", {}).get("source") ==
            report.get("provenance", {}).get("candidateSource"), "source binding differs")
    sources = raw_report.get("provenance", {}).get("productionSources", [])
    require(bool(sources) and all(item.get("sha256") and item.get("bytes") is not None for item in sources),
            "production hashes missing")
    inventory = {item["path"]: item for item in report.get("provenance", {}).get("productionSources", [])}
    require(bool(inventory), "scored report production provenance missing")
    require(all(inventory.get(item["path"]) == item for item in sources if item["path"].endswith(".kt")),
            "executed production closure differs from source inventory")
    matches = [item for item in raw_report.get("observations", []) if item.get("key") == spec["key"]]
    require(len(matches) == 1, "raw case missing or duplicated")
    expected = entry_row(spec, matches[0], raw_path)
    for key, value in expected.items():
        require(row.get(key) == value, "normalized entry field differs: " + key)
    observation_id = (record["sha256"], evidence["caseRunId"])
    require(observation_id not in used_observation_ids, "production instance evidence reused")
    used_observation_ids.add(observation_id)
