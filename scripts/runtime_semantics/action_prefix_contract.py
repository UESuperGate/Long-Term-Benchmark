"""Versioned task12 setup recipes; old given remains the event-boundary assertion."""
from __future__ import annotations

import copy
import hashlib
import json

TASK = "12_report_room"


def digest(case):
    fields = ["taskId", "key", "given", "event", "expected"]
    if "setup" in case:
        fields.append("setup")
    if "setup" in case or case.get("traceSchemaVersion") == 2:
        fields.append("invariants")
    if case.get("traceSchemaVersion") == 2:
        fields.append("traceSchemaVersion")
    payload = {field: case[field] for field in fields}
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def task12_recipe(case):
    """Describe real operations, never writes to a production state field."""
    if case["taskId"] != TASK:
        raise ValueError("Unreviewed task for action-prefix revision")
    given, key = case["given"], case["key"]
    actions = []
    responses = {}
    if key != "initial_form":
        actions.append({"name": "open_report_room"})
        if given.get("reason"):
            actions.append({"name": "update_reason", "reason": given["reason"]})
        if given.get("leaveRoom"):
            actions.append({"name": "toggle_leave_room"})
        for field, effect in (("reportResult", "report_room"), ("leaveResult", "leave_room")):
            if field in given:
                responses[effect] = [given[field]]
        if given.get("reportAction") in {"leave_failed", "report_failed"}:
            failed_effect = "leave_room" if given["reportAction"] == "leave_failed" else "report_room"
            responses[failed_effect] = ["failure", "success"]
            actions.append({"name": "report"})
    return {
        "schemaVersion": 1,
        "initialState": {"roomId": "!room:example.org", "screen": "room_details"},
        "externalResponses": responses,
        "actions": actions,
        "requiredBeforeEvent": copy.deepcopy(given),
        "executionIsolation": "fresh_production_instances_per_case",
    }


def revise_task12(previous):
    if previous["taskId"] != TASK or any("setup" in case for case in previous["cases"]):
        raise ValueError("Expected original task12 contract, not an already revised candidate")
    revised = copy.deepcopy(previous)
    revised["schemaVersion"] = 2
    revised["revision"] = 3
    revised["executionModel"] = "common_start_then_actions_then_original_transition"
    for case in revised["cases"]:
        case["setup"] = task12_recipe(case)
        case["traceDigest"] = digest(case)
    validate_revision(previous, revised)
    return revised


def validate_revision(previous, revised):
    if len(previous["cases"]) != len(revised["cases"]):
        raise ValueError("Original cases must be retained")
    for old, new in zip(previous["cases"], revised["cases"]):
        expected = copy.deepcopy(old)
        expected["setup"] = task12_recipe(old)
        expected["traceDigest"] = digest(expected)
        if new != expected:
            raise ValueError("Action-prefix revision changed an original assertion or recipe")
    expected_meta = {key: value for key, value in previous.items() if key != "cases"}
    expected_meta.update(schemaVersion=2, revision=3,
                         executionModel="common_start_then_actions_then_original_transition")
    if {key: value for key, value in revised.items() if key != "cases"} != expected_meta:
        raise ValueError("Unexpected contract metadata revision")
