"""Verify Task14/15 absent-entry assertions from isolated API23 UI executions."""
from __future__ import annotations

import copy
import json
from pathlib import Path

try:
    from . import task14_15_arkts_artifacts as artifacts
    from . import task14_15_arkts_layout_closure as closure
except ImportError:
    import task14_15_arkts_artifacts as artifacts
    import task14_15_arkts_layout_closure as closure

ROOT = artifacts.ROOT
POLICY_ID = "task14_15.arkts.isolated-production-entry.v1"
FINAL_IDS = {"join_room_by_address", "room_address_input", "join_room_continue", "join_room_cancel"}
DEACTIVATION_IDS = {"deactivate_account_entry", "deactivation_password", "deactivate_submit",
                    "deactivation_loading_dialog", "deactivation_loading_message"}
DEACTIVATION_TEXTS = {"Deactivate account", "Are you sure you want to deactivate this account?",
                      "Confirm deactivation", "Account deactivated"}


def flatten(layout):
    nodes = []
    if layout.get("attributes", {}).get("visible") == "true":
        nodes.append(layout["attributes"])
    for child in layout.get("children", []):
        nodes.extend(flatten(child))
    return nodes


def check_raw(raw, raw_report, task_id):
    artifacts.require(raw.get("status") == "fail" and raw.get("transitionExecuted") is False and
                      raw.get("failureKind") == "semantic_missing_feature_entry", "No device entry assertion")
    artifacts.require(raw.get("invariantChecks") == [], "Device entry probe invented failed post-state invariants")
    closure.check_layouts(raw, task_id)
    points = {point["name"]: flatten(json.loads(artifacts.bound(point["layout"])))
              for point in raw["checkpoints"]}
    if task_id.startswith("14"):
        start = points["reachable_common_start_chat"]
        returned = points["returned_common_start_chat"]
        for nodes in (start, returned):
            ids = {node.get("id") for node in nodes}
            artifacts.require({"create_room_action", "person_@alice:demo.local"} <= ids and
                              not FINAL_IDS.intersection(ids), "Common start or join entry absence missing")
        create_ids = {node.get("id") for node in points["create_room_route"]}
        artifacts.require({"create_room_title", "create_room_cancel"} <= create_ids,
                          "Real create-room positive control missing")
        direct = points["stored_direct_room_route"]
        room = [node for node in direct if node.get("id") == "room_id"]
        members = [node for node in direct if node.get("id") == "room_members"]
        artifacts.require(len(room) == len(members) == 1 and room[0].get("text", "").startswith("!local-") and
                          "@alice:demo.local" in members[0].get("text", ""), "Real direct-room positive control missing")
        observed = raw.get("observed", {})
        artifacts.require(observed.get("createRoomRouteReached") is True and
                          observed.get("directMessageRouteReached") is True and
                          observed.get("storedDirectRoomId") == room[0]["text"], "Positive-control state differs from UI")
    else:
        for name in ("common_settings_ready", "common_settings_stable", "notification_settings_positive_control"):
            nodes = points[name]
            ids = {node.get("id") for node in nodes}
            texts = {node.get("text") for node in nodes}
            artifacts.require(not ids.intersection(DEACTIVATION_IDS) and not texts.intersection(DEACTIVATION_TEXTS),
                              "Deactivation UI entry was not absent")
            artifacts.require("account_homeserver" in ids and "Blocked users" in texts,
                              "Common original settings UI missing")
        artifacts.require(any(node.get("text") == "Notification settings opened"
                              for node in points["notification_settings_positive_control"]),
                          "Notification positive control missing")
        observed = raw.get("observed", {})
        artifacts.require(observed.get("commonSettingsMounted") is True and
                          observed.get("notificationSettingsEventExecuted") is True,
                          "Device settings positive control was not observed")
    commands = [command for command in raw_report["diagnostics"]["commands"]
                if command.get("caseId") == raw["caseId"]]
    artifacts.require(sum(command.get("args", [])[:3] == ["shell", "aa", "start"]
                          for command in commands) == 1, "Original application launch is missing")
    artifacts.require(sum(command.get("args", [])[:4] == ["shell", "uitest", "uiInput", "click"]
                          for command in commands) >= (3 if task_id.startswith("14") else 1),
                      "Positive-control UI input commands are missing")
    artifacts.require(all(command.get("exitCode") == 0 for command in commands),
                      "Device command/environment failure cannot establish semantic failure")
    for operation in ("install", "uninstall"):
        matching = [command for command in commands if command.get("args", [None])[0] == operation]
        artifacts.require(len(matching) == 1 and matching[0].get("exitCode") == 0,
                          "Case was not isolated by fresh installation and uninstall")
        artifacts.bound(matching[0]["log"])


def entry_row(raw, spec, raw_report_path, sources):
    # Reject an unbound candidate before producing any scoreable FAIL row.
    try:
        from . import task14_15_formal_core as core
    except ImportError:
        import task14_15_formal_core as core
    raw_report = json.loads(Path(raw_report_path).read_text())
    check_raw(raw, raw_report, spec['taskId'])
    source = Path(raw_report['provenance']['source'])
    source = source if source.is_absolute() else ROOT / source
    proof = closure.check_prefix(raw, raw_report, spec['taskId'], sources,
                                candidate_root_sha256=core.directory_digest(source))
    record = artifacts.artifact(raw_report_path)
    return {"caseId": spec["caseId"], "key": spec["key"], "traceDigest": spec["traceDigest"],
            "status": "fail", "failureKind": "semantic_missing_feature_entry", "failPhase": "entry",
            "transitionExecuted": False, "observed": None, "invariantChecks": [],
            "unevaluatedInvariants": copy.deepcopy(spec.get("invariants", [])),
            "productionSources": copy.deepcopy(sources), "checkpoints": copy.deepcopy(raw["checkpoints"]),
            "runtime": "openharmony_api23_device_missing_entry",
            "entryFailureEvidence": {"policyId": POLICY_ID, "report": record,
                "nativeLayoutClosure": proof,
                "rawRowSha256": artifacts.row_digest(raw),
                "observationIds": [f"{POLICY_ID}:{record['sha256']}:{spec['caseId']}"]}}


def validate_entry_failure(row, report, used_observation_ids, contract=None):
    artifacts.require(report.get("platform") == "arkts" and report.get("role") == "agent" and
                      report.get("taskId") in artifacts.TASKS, "Wrong ArkTS entry identity")
    evidence = row["entryFailureEvidence"]
    artifacts.require(evidence.get("policyId") == POLICY_ID, "Unknown API23 entry policy")
    artifacts.require(row.get("observed") is None and row.get("invariantChecks") == [] and
                      row.get("transitionExecuted") is False and row.get("status") == "fail",
                      "Device entry assertion invented post-state or evaluated invariants")
    artifacts.require(contract is not None and contract["taskId"] == report["taskId"], "Canonical contract missing")
    spec = next(case for case in contract["cases"] if case["caseId"] == row["caseId"])
    artifacts.require(row["key"] == spec["key"] and row["traceDigest"] == spec["traceDigest"] and
                      row["unevaluatedInvariants"] == spec.get("invariants", []), "Device entry contract differs")
    raw_report = json.loads(artifacts.bound(evidence["report"]))
    artifacts.require(raw_report.get("status") == "passed" and raw_report.get("role") == "agent" and
                      raw_report.get("taskId") == report["taskId"], "Base device runtime incomplete")
    source_path = Path(raw_report["provenance"]["source"])
    if not source_path.is_absolute():
        source_path = ROOT / source_path
    artifacts.require(source_path.resolve() == Path(report["provenance"]["candidateSource"]).resolve(),
                      "Device entry source differs from candidate")
    raw_rows = [value for value in raw_report["semantic"]["cases"] if value["caseId"] == row["caseId"]]
    artifacts.require(len(raw_rows) == 1, "Device entry execution missing or duplicated")
    raw = raw_rows[0]
    artifacts.require(artifacts.row_digest(raw) == evidence["rawRowSha256"] and
                      row["checkpoints"] == raw["checkpoints"], "Device entry evidence changed")
    build = json.loads(artifacts.bound(raw_report["compile"]["build"]))
    sources = build.get("sources", [])
    artifacts.require(build.get("passed") is True and build.get("copiedProductionUnchanged") is True and
                      build.get("temporaryProjectRemoved") is True and bool(sources) and
                      row["productionSources"] == sources, "Device application provenance incomplete")
    for source in sources:
        record = report["provenance"]["productionSourceSnapshots"][source["path"]]
        data = artifacts.bound(record)
        artifacts.require(len(data) == source["bytes"] and record["sha256"] == source["sha256"],
                          "Device source snapshot changed")
    check_raw(raw, raw_report, report["taskId"])
    proof = closure.check_prefix(raw, raw_report, report['taskId'], sources,
                                candidate_root_sha256=report['provenance']['candidateRootSha256'])
    if 'nativeLayoutClosure' in evidence:
        artifacts.require(evidence['nativeLayoutClosure'] == proof, 'Native prefix closure receipt changed')
    ids = [f"{POLICY_ID}:{evidence['report']['sha256']}:{row['caseId']}"]
    artifacts.require(evidence.get("observationIds") == ids and not used_observation_ids.intersection(ids),
                      "Device entry observations reused")
    used_observation_ids.update(ids)
    return {"status": "fail", "caseId": row["caseId"], "observationIds": ids,
            'nativeLayoutClosure': proof}
