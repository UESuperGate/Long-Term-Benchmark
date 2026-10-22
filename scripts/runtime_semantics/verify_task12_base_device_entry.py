#!/usr/bin/env python3
"""Independently verify Task12 ArkTS base entry-absence device evidence."""

import argparse
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BUNDLE = "com.qingyu.elementx.reportroom.base.rebuilt"
ROOM_ID = "!room:example.org"
REPORT_IDS = {"report_room_entry", "report_room_reason", "submit_report_room"}


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify_record(item):
    path = ROOT / item["path"]
    data = path.read_bytes()
    require(len(data) == item["bytes"], "Artifact length changed: " + str(path))
    require(hashlib.sha256(data).hexdigest() == item["sha256"], "Artifact hash changed: " + str(path))
    return path


def nodes(layout):
    result = []

    def visit(node):
        if "attributes" in node:
            result.append(node["attributes"])
        for child in node.get("children", []):
            visit(child)

    visit(layout)
    return result


def one(items, node_id):
    matches = [item for item in items if item.get("id") == node_id and item.get("visible") == "true"]
    require(len(matches) == 1, f"Expected one visible {node_id}, found {len(matches)}")
    return matches[0]


def verify_layout(record, kind):
    path = verify_record(record)
    items = nodes(load(path))
    roots = [item for item in items if item.get("type") == "root"]
    require(len(roots) == 1 and roots[0].get("bundleName") == BUNDLE and
            roots[0].get("pagePath") == "pages/Index" and roots[0].get("focused") == "true",
            "Layout is not the focused candidate page")
    if kind in {"details", "stable", "restored"}:
        require(one(items, "room_details_id").get("text") == ROOM_ID, "Wrong room identity")
        require(one(items, "room_details_name").get("text") == "Runtime room", "Wrong room name")
        require(one(items, "room_member_count").get("text") == "1 members", "Wrong member count")
        require(one(items, "leave_room").get("enabled") == "true", "Leave positive control unavailable")
        require(not [item for item in items if item.get("id") in REPORT_IDS or item.get("text") == "Report room"],
                "Report entry/form unexpectedly exists in base")
    elif kind == "confirmation":
        one(items, "leave_room_confirmation")
        require(one(items, "cancel_leave_room").get("enabled") == "true", "Cancel positive control unavailable")
    return path


def verify(report_path):
    report_path = Path(report_path).resolve()
    report = load(report_path)
    require(report.get("taskId") == "12_report_room" and report.get("platform") == "arkts" and
            report.get("role") == "base", "Wrong report identity")
    require(report.get("runtime") == "openharmony_api23_device_uitest", "Wrong runtime scope")
    require(report.get("compile", {}).get("passed") is True, "Application compile not established")
    for item in (report["compile"]["build"], report["compile"]["hap"], report["provenance"]["contract"],
                 report["provenance"]["runner"]):
        verify_record(item)
    contract = load(verify_record(report["provenance"]["contract"]))
    require(contract.get("revision") == 3 and len(contract.get("cases", [])) == 10, "Wrong staged contract")
    expected = {item["caseId"]: item for item in contract["cases"]}
    rows = report["semantic"]["cases"]
    require(report["semantic"] == {"total": 10, "passed": 0, "failed": 10, "notScored": 0, "cases": rows},
            "Wrong base polarity counts")
    require({row["caseId"] for row in rows} == set(expected) and len(rows) == 10, "Incomplete case matrix")
    run_ids = set()
    layout_paths = set()
    request_rows = []
    for row in rows:
        spec = expected[row["caseId"]]
        require(row["traceDigest"] == spec["traceDigest"] and row["status"] == "fail", "Case identity/status mismatch")
        require(row.get("transitionExecuted") is False and row.get("observed") is None and row.get("invariantChecks") == [],
                "Entry failure fabricated downstream observations")
        evidence = row.get("entryFailureEvidence", {})
        require(evidence.get("schemaVersion") == 1 and evidence.get("canonicalGivenEstablished") is True and
                evidence.get("candidateBundle") == BUNDLE and evidence.get("candidateRoute") == "pages/Index" and
                evidence.get("reportEntryCount") == 0 and evidence.get("positiveControl") == "leave_confirmation_and_cancel",
                "Incomplete entry failure evidence")
        expected_action = spec["setup"]["actions"][0] if spec["setup"]["actions"] else spec["event"]
        require(evidence.get("requestedAction") == expected_action and
                evidence.get("failedAt") == ("setup.actions[0]" if spec["setup"]["actions"] else "event"),
                "Wrong action-prefix failure boundary")
        run_id = evidence.get("caseRunId")
        require(isinstance(run_id, str) and run_id.startswith(row["caseId"] + "-") and run_id not in run_ids,
                "Device execution identity missing or reused")
        run_ids.add(run_id)
        case_requests = evidence.get("requests", [])
        require([item.get("url") for item in case_requests] == [
            "/_matrix/client/v3/joined_rooms", "/_matrix/client/v3/rooms/!room%3Aexample.org/state"],
            "Common-start HTTP sequence changed")
        require(all(item.get("caseRunId") == run_id and item.get("method") == "GET" and
                    item.get("authorization") == "Bearer runtime-token" for item in case_requests),
                "HTTP request is not bound to this fresh case")
        request_rows.extend(case_requests)
        points = {item["name"]: item for item in row.get("checkpoints", [])}
        require(set(points) == {"common_start", "entry_absence_stable", "positive_leave_control", "common_start_restored"},
                "Incomplete entry checkpoints")
        require(points["common_start"]["state"] == {"roomId": ROOM_ID, "screen": "room_details",
                "roomName": "Runtime room", "memberCount": 1, "leaveControlEnabled": True, "reportEntryCount": 0},
                "Common start changed")
        require(points["entry_absence_stable"]["state"] == {"reportEntryCount": 0, "samples": 2},
                "Stable absence was not sampled twice")
        require(points["positive_leave_control"]["state"] == {"confirmationVisible": True, "cancelEnabled": True},
                "Positive control changed")
        for name, kind in (("common_start", "details"), ("entry_absence_stable", "stable"),
                           ("positive_leave_control", "confirmation"), ("common_start_restored", "restored")):
            artifact = verify_layout(points[name]["layout"], kind)
            require(artifact not in layout_paths, "A UI tree was reused by multiple canonical cases")
            layout_paths.add(artifact)
    require(report["diagnostics"]["serverRequests"] == request_rows and len(request_rows) == 20,
            "Server request ledger differs from case evidence")
    commands = report["diagnostics"].get("commands", [])
    require(commands and all(command.get("exitCode") in (0, 255) for command in commands), "Device command failed")
    for command in commands:
        verify_record(command["log"])
    require(sum(command["args"][:2] == ["install", "-r"] for command in commands) == 10, "Expected ten fresh installs")
    require(sum(command["args"][:3] == ["shell", "aa", "start"] for command in commands) == 10,
            "Expected ten fresh ability starts")
    cleanup = report["diagnostics"]["cleanup"]
    require(cleanup.get("ownedAppUninstalled") is True and cleanup.get("reverseRemoved") is True and
            cleanup.get("remoteLayoutsRemoved", 0) > 0, "Owned device cleanup incomplete")
    task = load(ROOT / "benchmark_tasks/12_report_room/task.json")
    require(task["android"]["finalRef"] == "v25.05.4" and
            task["android"]["finalCommit"] == "0fab33ae06dbb0499491c8edc2f24af38d2725e2" and
            task["arkts"]["basePath"] == "12_report_room_base_25_04_3_rebuilt" and
            task["arkts"]["finalPath"] == "final_dev_nodes/12_report_room_final_25_05_4" and
            digest(ROOT / "benchmark_tasks/12_report_room/transitions.json") ==
            "365670eba603c9762842a836b3b5385c37f925abdf3e88cc1d3d355b3f64531e",
            "Active benchmark metadata differs from the reviewed boundary")
    return {"validated": True, "semantic": {"passed": 0, "failed": 10, "notScored": 0},
            "independentCaseRuns": len(run_ids), "verifiedLayouts": len(layout_paths),
            "matrixRequests": len(request_rows), "report": str(report_path)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = verify(args.report)
    if args.output:
        with args.output.open("x", encoding="utf-8") as stream:
            json.dump(result, stream, indent=2)
            stream.write("\n")
    print(json.dumps(result))
