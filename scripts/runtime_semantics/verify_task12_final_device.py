#!/usr/bin/env python3
import argparse
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "experiment_results/runtime_transition_20261020/contract_audit/revision_3/after/12_report_room/transitions.json"
BUILD = ROOT / "experiment_results/runtime_transition_20261020/task12_rebuild/build-final/build-report.json"
HAP = ROOT / "experiment_results/runtime_transition_20261020/task12_rebuild/build-final/entry-default-unsigned.hap"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def checked_file(item, label):
    path = (ROOT / item["path"]).resolve()
    require(path == ROOT or ROOT in path.parents, f"{label} escapes repository")
    require(path.is_file(), f"{label} does not exist: {path}")
    require(path.stat().st_size == item["bytes"], f"{label} byte count changed")
    require(digest(path) == item["sha256"], f"{label} digest changed")
    return path


def flatten_layout(node, result=None):
    result = [] if result is None else result
    if isinstance(node, dict):
        attributes = node.get("attributes")
        if isinstance(attributes, dict):
            result.append(attributes)
        for child in node.get("children", []):
            flatten_layout(child, result)
    return result


def one_visible(nodes, node_id):
    matches = [node for node in nodes if node.get("id") == node_id and node.get("visible") == "true"]
    require(len(matches) == 1, f"expected one visible {node_id}, found {len(matches)}")
    return matches[0]


def expected_effects(case):
    return {
        "rr_state_001_initial_form": [],
        "rr_state_002_reason_enables_report": [],
        "rr_state_003_toggle_leave": [],
        "rr_state_004_report_only_success": ["report_room"],
        "rr_state_005_report_then_leave": ["report_room", "leave_room"],
        "rr_state_006_blank_reason_disabled": [],
        "rr_state_007_report_failure_stops_leave": ["report_room"],
        "rr_state_008_leave_failure_is_partial": ["report_room", "leave_room"],
        "rr_state_009_retry_leave_only": ["report_room", "leave_room", "leave_room"],
        "rr_state_010_clear_failure_keeps_form": ["report_room"],
    }[case["caseId"]]


def verify(report_path, verified_path=None):
    report_path = Path(report_path).resolve()
    report = json.loads(report_path.read_text())
    contract = json.loads(CONTRACT.read_text())
    build = json.loads(BUILD.read_text())

    require(report["taskId"] == "12_report_room", "wrong task")
    require(report["platform"] == "arkts" and report["role"] == "final", "wrong platform or role")
    require(report["observationMode"] == "runtime_state_transition", "not a runtime transition report")
    require(report["runtime"] == "openharmony_api23_device_uitest", "wrong runtime")
    require(report["compile"]["passed"] is True and report["compile"]["scope"] == "application_hap", "application compile proof missing")
    checked_file(report["compile"]["build"], "build report")
    checked_file(report["compile"]["hap"], "HAP")
    require(build["status"] == "built_not_executed" and build["productionUnchanged"] is True, "invalid build provenance")
    require(build["hap"]["sha256"] == digest(HAP), "build report does not bind the executed HAP")
    require(report["diagnostics"]["adapter"] == "ready" and report["diagnostics"]["transport"] == "ready", "runtime diagnostics not ready")
    require(report["diagnostics"]["cleanup"] == {
        "ownedAppUninstalled": True, "reverseRemoved": True, "remoteLayoutsRemoved": report["diagnostics"]["cleanup"]["remoteLayoutsRemoved"]
    }, "cleanup flags are incomplete")
    require(report["diagnostics"]["cleanup"]["remoteLayoutsRemoved"] > 0, "no remote layouts cleaned")
    require(report["provenance"]["activeMetadataModified"] is False, "active metadata was modified")
    checked_file(report["provenance"]["contract"], "contract")
    checked_file(report["provenance"]["runner"], "runner")
    require(report["provenance"]["contract"]["sha256"] == digest(CONTRACT), "wrong staged contract")

    semantic = report["semantic"]
    require((semantic["total"], semantic["passed"], semantic["failed"], semantic["notScored"]) == (10, 10, 0, 0), "semantic totals are not 10/10")
    cases = {case["caseId"]: case for case in contract["cases"]}
    rows = semantic["cases"]
    require(len(rows) == len(cases) == 10, "case count mismatch")
    require({row["caseId"] for row in rows} == set(cases), "case set mismatch")
    run_ids = [row["caseRunId"] for row in rows]
    require(len(set(run_ids)) == 10, "case execution was not independently isolated")

    request_rows = report["diagnostics"]["serverRequests"]
    verified_layouts = []
    for row in rows:
        spec = cases[row["caseId"]]
        require(row["status"] == "pass" and row["transitionExecuted"] is True, f"{row['caseId']}: transition not passed")
        require(row["traceDigest"] == spec["traceDigest"], f"{row['caseId']}: trace digest mismatch")
        require(all(item["passed"] is True for item in row["invariantChecks"]), f"{row['caseId']}: invariant not passed")
        require([item["text"] for item in row["invariantChecks"]] == spec["invariants"], f"{row['caseId']}: invariant text mismatch")
        for key, expected in spec["expected"].items():
            require(row["observed"].get(key) == expected, f"{row['caseId']}: expected {key}={expected!r}")

        checkpoints = {item["name"]: item for item in row["checkpoints"]}
        require(set(checkpoints) == {"common_start", "post_event"}, f"{row['caseId']}: checkpoint set mismatch")
        require(checkpoints["common_start"]["state"] == {
            "roomId": "!room:example.org", "screen": "room_details", "reportEntryVisible": True
        }, f"{row['caseId']}: common start mismatch")
        common_path = checked_file(checkpoints["common_start"]["layout"], f"{row['caseId']} common layout")
        post_path = checked_file(checkpoints["post_event"]["layout"], f"{row['caseId']} post layout")
        verified_layouts.extend([str(common_path.relative_to(ROOT)), str(post_path.relative_to(ROOT))])
        common_nodes = flatten_layout(json.loads(common_path.read_text()))
        one_visible(common_nodes, "report_room_entry")
        require(one_visible(common_nodes, "room_details_id").get("text") == "!room:example.org", f"{row['caseId']}: wrong common room")

        post_nodes = flatten_layout(json.loads(post_path.read_text()))
        action = row["observed"]["reportAction"]
        if action == "success":
            one_visible(post_nodes, "room_details_id")
            if row["observed"]["leaveCalls"]:
                one_visible(post_nodes, "leave_room_success")
            else:
                one_visible(post_nodes, "report_room_entry")
        else:
            reason = one_visible(post_nodes, "report_room_reason")
            toggle = one_visible(post_nodes, "report_room_leave_toggle")
            submit = one_visible(post_nodes, "submit_report_room")
            require(reason.get("text", "") == row["observed"].get("reason", ""), f"{row['caseId']}: rendered reason mismatch")
            require((toggle.get("checked") == "true") == row["observed"]["leaveRoom"], f"{row['caseId']}: rendered toggle mismatch")
            require((submit.get("enabled") == "true") == row["observed"]["submitEnabled"], f"{row['caseId']}: submit state mismatch")
            if action == "report_failed":
                one_visible(post_nodes, "report_room_error")
            elif action == "leave_failed":
                one_visible(post_nodes, "report_room_partial_failure")
                one_visible(post_nodes, "retry_leave_room")
            else:
                require(not any(node.get("id") in {"report_room_error", "report_room_partial_failure"} and node.get("visible") == "true" for node in post_nodes),
                        f"{row['caseId']}: error remained visible")

        case_requests = [item for item in request_rows if item["caseRunId"] == row["caseRunId"]]
        require([item["url"] for item in case_requests[:3]] == [
            "/_matrix/client/v3/joined_rooms",
            "/_matrix/client/v3/rooms/!room%3Aexample.org/state",
            "/_matrix/client/versions",
        ], f"{row['caseId']}: common transport sequence mismatch")
        require(all(item["authorization"] == "Bearer runtime-token" for item in case_requests), f"{row['caseId']}: auth mismatch")
        effects = [item for item in case_requests if item.get("effect")]
        require(effects == row["externalEffects"], f"{row['caseId']}: effect rows differ")
        require([item["effect"] for item in effects] == expected_effects(spec), f"{row['caseId']}: effect ordering/count mismatch")
        require([item["sequence"] for item in effects] == sorted(item["sequence"] for item in effects), f"{row['caseId']}: unordered effects")
        for item in effects:
            require(item["method"] == "POST", f"{row['caseId']}: effect was not POST")
            if item["effect"] == "report_room":
                require(json.loads(item["body"])["reason"] == row["observed"]["reportReason"], f"{row['caseId']}: report body mismatch")

    require(len(set(verified_layouts)) == 20, "layout evidence was reused across cases")
    command_logs = [checked_file(item["log"], "command log") for item in report["diagnostics"]["commands"]]
    require(len(command_logs) >= 40, "too few device commands for fresh per-case execution")
    for case_id in cases:
        scoped = [item for item in report["diagnostics"]["commands"] if f"/{case_id}/" in item["log"]["path"]]
        args = [item["args"] for item in scoped]
        require(any(parts[:2] == ["install", "-r"] for parts in args), f"{case_id}: install command missing")
        require(any(parts[:3] == ["shell", "aa", "start"] for parts in args), f"{case_id}: launch command missing")
        require(sum(parts[:1] == ["uninstall"] for parts in args) >= 2, f"{case_id}: fresh install cleanup missing")

    result = {
        "schemaVersion": 1,
        "validated": True,
        "report": str(report_path.relative_to(ROOT)),
        "reportSha256": digest(report_path),
        "semantic": {"total": 10, "passed": 10, "failed": 0, "notScored": 0},
        "independentCaseRuns": len(set(run_ids)),
        "verifiedLayouts": len(verified_layouts),
        "verifiedCommandLogs": len(command_logs),
        "verifiedServerRequests": len(request_rows),
        "activeMetadataModified": False,
    }
    if verified_path:
        verified_path = Path(verified_path)
        verified_path.write_text(json.dumps(result, indent=2) + "\n")
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("report")
    parser.add_argument("--output")
    args = parser.parse_args()
    print(json.dumps(verify(args.report, args.output), indent=2))


if __name__ == "__main__":
    main()
