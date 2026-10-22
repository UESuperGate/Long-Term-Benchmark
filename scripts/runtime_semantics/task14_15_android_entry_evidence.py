"""Source-bound entry failures for isolated Task14/15 production runtime probes.

Public routing API: validate_entry_failure(row, report, used_observation_ids, contract).
No canonical post-state or post-transition invariant is inferred from absence.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

try:
    from . import task14_15_android_prefix_closure as prefix_closure
except ImportError:
    import task14_15_android_prefix_closure as prefix_closure

ROOT = Path(__file__).resolve().parents[2]
POLICY_ID = "task14_15.android.isolated-production-entry.v1"
TASKS = {"14_join_room_by_address", "15_account_deactivation"}


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def row_digest(row):
    return hashlib.sha256(json.dumps(row, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def bound(record):
    path = Path(record["path"]).resolve()
    require(path.is_relative_to(ROOT / "experiment_results"), "Runtime evidence outside experiment results")
    data = path.read_bytes()
    require(("bytes" not in record or len(data) == record["bytes"]) and
            hashlib.sha256(data).hexdigest() == record["sha256"],
            "Runtime artifact digest changed")
    return data


def artifact(path):
    path = Path(path).resolve()
    return {"path": str(path), "bytes": path.stat().st_size, "sha256": digest(path)}


def _check_raw(raw, task_id, key):
    require(raw.get("key") == key, "Entry probe case key changed")
    prefix_closure.check_inventory(raw, task_id)
    points = {item["name"]: item["state"] for item in raw.get("checkpoints", [])}
    if task_id == "14_join_room_by_address":
        require(raw.get("status") == "fail", "Join entry assertion did not fail")
        require(str(raw.get("reason", "")).startswith(
            "java.lang.AssertionError: Canonical select_join_by_address requires one rendered action"),
            "Failure was not the required rendered entry assertion")
        require(raw.get("invariantChecks") == [], "Base join probe evaluated post-state invariants")
        observed = raw.get("observed", {})
        require(observed.get("caseKey") == key and observed.get("givenSurface") == "start_chat" and
                observed.get("givenSearchActive") is False and observed.get("joinActionCount") == 0 and
                observed.get("transitionExecuted") is False, "Join absence was not observed")
        before = points.get("canonical_start_chat_given", {})
        controls = points.get("real_entry_controls", {})
        after = points.get("existing_new_room_control_routes_through_production_flow", {})
        require(before.get("caseKey") == key and before.get("surface") == "start_chat" and
                before.get("searchActive") is False and before.get("query") == "", "Common start missing")
        require(controls.get("joinActionCount") == 0 and controls.get("newRoomEnabled") is True and
                controls.get("userSearchEnabled") is True and controls.get("searchActive") is False,
                "Rendered entry controls incomplete")
        ranges = controls.get("scrollRanges", [])
        require(bool(ranges) and all(item.get("value") == 0 and item.get("maxValue") == 0
                                    for item in ranges), "Entry viewport not fully explored")
        require(all(marker in controls.get("semantics", "") for marker in
                    ("[Start chat]", "[New room]", "[Invite people to Element X]")),
                "Original rendered anchors missing")
        root = [{"target": "Root", "fromState": "ACTIVE", "targetState": "ACTIVE"}]
        require(before.get("navigation") == root and controls.get("navigation") == root,
                "Entry not observed at the common production root")
        require(after.get("navigation") == [
            {"target": "Root", "fromState": "ACTIVE", "targetState": "STASHED"},
            {"target": "NewRoom", "fromState": "CREATED", "targetState": "ACTIVE"}],
            "Production NewRoom navigation positive control missing")
    else:
        require(raw.get("status") == "pass", "Settings positive-control probe did not pass")
        require(raw.get("observed") == {
            "settingsVisible": True, "positiveControl": "notification_settings_click",
            "positiveControlInvoked": True, "deactivateEntryVisible": False, "transitionExecuted": False},
            "Settings entry observation changed")
        before = points.get("common_settings_reachable", {})
        after = points.get("unchanged_notification_operation", {})
        for state in (before, after):
            require(state.get("settingsTitleVisible") is True and state.get("notificationRowVisible") is True
                    and state.get("deactivateEntryCount") == 0, "Settings entry not observed")
        require(before.get("notificationClicks") == 0 and after.get("notificationClicks") == 1,
                "Notification click positive control missing")
        require(points.get("cleanup", {}).get("activityDestroyed") is True, "Settings isolation cleanup missing")
        require(any(check.get("invariant") == "base common settings and an unchanged operation remain reachable"
                    and check.get("status") == "pass" for check in raw.get("invariantChecks", [])),
                "Settings positive-control assertion missing")


def entry_row(raw, spec, raw_report_path, sources):
    _check_raw(raw, spec["taskId"], spec["key"])
    raw_report = json.loads(Path(raw_report_path).read_text())
    proof = prefix_closure.check_prefix(raw, raw_report, spec['taskId'], sources)
    logged = [json.loads(line[len('RUNTIME_RESULT '):])
              for line in bound(raw_report['log']).decode().splitlines() if line.startswith('RUNTIME_RESULT ')]
    require(sum(item == raw for item in logged) == 1, 'Entry prefix was not executed in its isolated runtime log')
    report_record = artifact(raw_report_path)
    observation_id = f"{POLICY_ID}:{report_record['sha256']}:{spec['key']}"
    return {"caseId": spec["caseId"], "key": spec["key"], "traceDigest": spec["traceDigest"],
            "status": "fail", "failureKind": "semantic_missing_feature_entry", "failPhase": "entry",
            "transitionExecuted": False, "observed": None, "invariantChecks": [],
            "unevaluatedInvariants": copy.deepcopy(spec.get("invariants", [])),
            "checkpoints": copy.deepcopy(raw["checkpoints"]), "productionSources": copy.deepcopy(sources),
            "entryFailureEvidence": {"policyId": POLICY_ID, "report": report_record,
                                     'originalUiClosure': proof,
                                     "rawKey": spec["key"], "rawRowSha256": row_digest(raw),
                                     "observationIds": [observation_id]}}


def validate_entry_failure(row, report, used_observation_ids, contract=None):
    task_id = report.get("taskId")
    require(task_id in TASKS and report.get("platform") == "android" and report.get("role") == "agent",
            "Wrong Task14/15 entry runtime identity")
    evidence = row.get("entryFailureEvidence", {})
    require(evidence.get("policyId") == POLICY_ID, "Unrecognized isolated entry policy")
    require(row.get("status") == "fail" and row.get("failureKind") == "semantic_missing_feature_entry" and
            row.get("observed") is None and row.get("invariantChecks") == [] and
            row.get("transitionExecuted") is False, "Entry failure invented post-state or invariants")
    require(contract is not None and contract.get("taskId") == task_id, "Canonical contract is required")
    specs = [item for item in contract["cases"] if item["caseId"] == row.get("caseId")]
    require(len(specs) == 1, "Entry canonical case missing")
    spec = specs[0]
    require(all(row.get(field) == spec[field] for field in ("key", "traceDigest")) and
            row.get("unevaluatedInvariants") == spec.get("invariants", []), "Entry contract changed")
    raw_report = json.loads(bound(evidence["report"]))
    require(raw_report.get("taskId") == task_id and raw_report.get("role") == "agent" and
            raw_report.get("runtimeCompile", {}).get("status") == "passed", "Entry runtime did not compile")
    provenance = raw_report.get("provenance", {})
    primary = report.get("provenance", {})
    require(provenance.get("source") == primary.get("candidateSource") and
            provenance.get("candidateRootSha256") == primary.get("candidateRootSha256"),
            "Entry source identity mismatch")
    require(provenance.get("productionSources") == row.get("productionSources") and
            bool(row["productionSources"]), "Entry production source manifest missing or changed")
    snapshots = primary.get("productionSourceSnapshots", {})
    for source in row["productionSources"]:
        record = snapshots.get(source["path"])
        require(record is not None, "Entry production snapshot missing")
        data = bound(record)
        require(len(data) == source["bytes"] and hashlib.sha256(data).hexdigest() == source["sha256"],
                "Entry production bytes differ from executed source")
    matches = [item for item in raw_report.get("observations", []) if item.get("key") == spec["key"]]
    require(len(matches) == 1, "Entry runtime row missing or duplicated")
    raw = matches[0]
    require(row_digest(raw) == evidence.get("rawRowSha256"), "Entry raw observation digest changed")
    log_data = bound(raw_report["log"]).decode()
    logged = [json.loads(line.split("RUNTIME_RESULT ", 1)[1]) for line in log_data.splitlines()
              if line.startswith("RUNTIME_RESULT ")]
    require(sum(item == raw for item in logged) == 1, "Entry evidence not bound to isolated runtime log")
    _check_raw(raw, task_id, spec["key"])
    proof = prefix_closure.check_prefix(raw, raw_report, task_id, row['productionSources'])
    if 'originalUiClosure' in evidence:
        require(evidence['originalUiClosure'] == proof, 'Android original UI closure receipt changed')
    require(row.get("checkpoints") == raw.get("checkpoints"), "Entry checkpoints changed")
    ids = [f"{POLICY_ID}:{evidence['report']['sha256']}:{spec['key']}"]
    require(evidence.get("observationIds") == ids and not used_observation_ids.intersection(ids),
            "Entry observations reused")
    used_observation_ids.update(ids)
    return {"status": "fail", "caseId": spec["caseId"], "observationIds": ids,
            'originalUiClosure': proof}


def attach_production_evidence(report, runtime_reports, source, evidence):
    sources = {}
    snapshots = {}
    for runtime in runtime_reports.values():
        for item in runtime.get("provenance", {}).get("productionSources", []):
            previous = sources.get(item["path"])
            require(previous is None or previous == item, "Production source hash differs between runtime poles")
            path = source / item["path"]
            data = path.read_bytes()
            require(len(data) == item["bytes"] and hashlib.sha256(data).hexdigest() == item["sha256"],
                    "Production source changed after runtime")
            destination = evidence / "production-sources" / item["path"]
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(data)
            sources[item["path"]] = item
            snapshots[item["path"]] = artifact(destination)
    report["provenance"]["productionSources"] = [sources[key] for key in sorted(sources)]
    report["provenance"]["productionSourceSnapshots"] = snapshots
    report["provenance"]["retainedEvidence"]["files"] = [
        {"path": path.relative_to(evidence).as_posix(), "bytes": path.stat().st_size, "sha256": digest(path)}
        for path in sorted(evidence.rglob("*")) if path.is_file()
    ]
