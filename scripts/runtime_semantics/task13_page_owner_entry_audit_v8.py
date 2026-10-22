"""Validate Task13 live profile-prefix failures without projecting SAS post-state."""

import copy
import hashlib
import json
from pathlib import Path
import re
import subprocess

try:
    from . import task12_13_formal_core as core
except ImportError:
    import task12_13_formal_core as core

POLICY_ID = "arkts.task13.revision5.page-owner-entry.v8"
UI_GUARD = core.ROOT / "state_tests/runtime/arkts/native/Task13UiClosure.cjs"
POLICY = core.ROOT / "experiment_results/runtime_transition_20261020/task13_page_owner_port_v1/entry_policy_v8/policy.json"
POLICY_SHA256 = "f40d2715d7d644944152327032e1f95dda00e0634c10a597d24b4344cb869b2f"
CANONICAL = core.ROOT / "benchmark_tasks/13_user_verification/transitions.json"
BINDING = core.ROOT / "migrations/13_user_verification/arkts/bindings.json"


def load_policy(contract):
    require(core.sha256(POLICY) == POLICY_SHA256, "frozen policy hash differs")
    policy = core.load(POLICY)
    require(policy.get("policyId") == POLICY_ID and
            core.sha256(CANONICAL) == policy["canonicalContractSha256"] and
            core.load(CANONICAL) == contract and
            core.sha256(BINDING) == policy["activeBindingSha256"], "canonical contract/binding differs from frozen policy")
    require(policy["caseDigests"] == {case["caseId"]: case["traceDigest"] for case in contract["cases"][:9]},
            "frozen policy case mapping differs")
    for record in policy["producerHashes"]:
        require(checked_record({key: record[key] for key in ("path", "bytes", "sha256")}) ==
                core.ROOT / record["relativePath"], "frozen producer binding differs")
    for version in ("before", "after"):
        checked_record(policy["versionAudit"][version])
    return policy


def validate_inventory(inventory):
    require(type(inventory.get("nodeCount")) is int, "native inventory count is not an integer")
    command = ["node", "-e", "const fs=require('fs');const g=require(process.argv[1]);process.stdout.write(JSON.stringify(g.validate(JSON.parse(fs.readFileSync(0,'utf8')))));", str(UI_GUARD)]
    completed = subprocess.run(command, input=json.dumps(inventory), text=True, capture_output=True, timeout=10)
    require(completed.returncode == 0, "complete UI closure/unbound-controls guard rejected: " + completed.stderr[:300])
    return json.loads(completed.stdout)


def require(value, message):
    if not value:
        raise ValueError("Task13 ArkTS common-entry audit: " + message)


def checked_record(record):
    declared = Path(record["path"])
    path = (declared if declared.is_absolute() else core.ROOT / declared).resolve()
    actual = core.file_record(path)
    require({"path", "sha256"} <= set(record) <= {"path", "bytes", "sha256"} and
            all(actual[key] == record[key] for key in record if key != "path"), "artifact hash/size changed")
    return path


def inspect_group_closure(ui, *, bundle):
    labels = ["before_event", "after_identity_change_profile", "after_identity_change_timeline",
              "after_identity_change_members", "after_identity_change_profile_restored", "after_event",
              "post_assertion_timeline_withdraw_requested", "post_assertion_timeline_sdk_updated",
              "post_assertion_verified_profile_sdk_updated", "post_assertion_unverified_profile_sdk_updated",
              "post_assertion_member_navigation_source", "post_assertion_member_search_filtered",
              "post_assertion_member_search_cleared", "post_assertion_member_navigation_destination",
              "post_assertion_original_block_control", "post_assertion_original_unblock_control"]
    frames = ui.get("frames", [])
    require([frame.get("label") for frame in frames] == labels, "whole-group UI closure frames incomplete")
    sequence = [frame.get("sequence") for frame in frames]
    require(all(type(item) is int for item in sequence) and sequence == sorted(set(sequence)),
            "whole-group frame ordering differs")
    windows = set()
    for frame in frames:
        window = frame.get("windowIdentity", {})
        require(frame.get("sessionId") == ui.get("sessionId") and frame.get("bundleName") == bundle and
                window.get("bundleName") == bundle and window.get("focused") is True and
                window.get("hostVerified") is True and window.get("routeName") == "pages/Index" and
                type(window.get("stageMainWindowId")) is int and type(window.get("lastWindowId")) is int and
                window["stageMainWindowId"] == window["lastWindowId"], "whole-group native window binding differs")
        windows.add(window["stageMainWindowId"])
        require(frame.get("uiInventory", {}).get("windowBounds") == window.get("bounds"),
                "whole-group inventory geometry differs")
    require(len(windows) == 1, "whole-group production window changed")
    by_label = dict(zip(labels, frames))

    def control(label, name):
        found = [item for item in by_label[label].get("controls", []) if item.get("name") == name]
        require(len(found) == 1, "whole-group control observation missing/duplicated")
        return found[0]

    def visible(label, name):
        return control(label, name).get("visible") is True

    pending, updated = labels[6:8]
    require(visible(pending, "timelineWarning") and not visible(updated, "timelineWarning") and
            ui.get("oldTimelinePositiveControl") == {
                "sdkEffects": [{"method": "withdrawVerification", "userId": "@alice:example.org"}],
                "warningHeldUntilSdkUpdate": True, "warningCleared": True},
            "old timeline SDK effect/independent update not established")
    require(visible(labels[8], "verifiedBadge") and not visible(labels[8], "legacyVerify") and
            control(labels[8], "profileName").get("text") == "Alice updated" and
            not visible(labels[9], "verifiedBadge") and visible(labels[9], "legacyVerify"),
            "production profile SDK stream/legacy row update missing")
    for label in (labels[10], labels[12]):
        require(visible(label, "memberAlice") and visible(label, "memberBob"), "native member list/restore incomplete")
    require(not visible(labels[11], "memberAlice") and visible(labels[11], "memberBob"),
            "native member search did not filter")
    for label, text in ((labels[11], "Bob"), (labels[12], "")):
        inputs = [node for node in by_label[label]["uiInventory"]["nodes"] if node.get("type") == "TextInput"]
        require(len(inputs) == 1 and inputs[0].get("text") == text, "actual search-input change missing")
    require(control(labels[13], "profile").get("text") == "@bob:example.org" and
            control(labels[13], "profileName").get("text") == "Bob", "member-to-profile production navigation missing")
    for label, text, expected_count, blocked in ((labels[14], "Unblock user", 2, True),
                                                  (labels[15], "Block user", 4, False)):
        calls = by_label[label].get("pageObserver", {}).get("blockCalls", [])
        require(control(label, "block").get("text") == text and len(calls) == expected_count and
                all(call.get("completed") is True and call.get("userId") == "@bob:example.org" for call in calls) and
                [call.get("method") for call in calls] == ["toggleBlocked", "setBlocked"] * (expected_count // 2) and
                calls[-1].get("sameGatewayReceiver") is True and
                calls[-1].get("after") == {"blocked": blocked, "gatewayBlocked": blocked},
                "actual original block/unblock receiver/effect missing")
    targets = ["identity_violation_surfaces", "openTimeline", "openMembers", "openProfile", "dm",
               "openTimeline", "timelineWithdraw", "openProfile", "openMembers", "memberBob", "block", "block"]
    actions = ui.get("actions", [])
    require([action.get("target") for action in actions] == targets and
            all(action.get("executed") is True and action.get("sessionId") == ui.get("sessionId")
                for action in actions), "whole-group real UI operations incomplete")
    return {"complete": True, "nativeFrames": len(frames), "actualActions": len(actions)}


def inspect_case(spec, row, *, bundle, nonce, used_sessions):
    require(isinstance(nonce, str) and re.fullmatch(r"[0-9a-f]{32}", nonce) is not None,
            "expected execution nonce is not hex")
    require(spec["key"] != "identity_violation_surfaces", "identity-change given is not an entry prefix")
    require(row.get("caseId") == spec["caseId"] and row.get("traceDigest") == spec["traceDigest"],
            "canonical case identity differs")
    require(row.get("nativeBridge", {}).get("capabilities", {}).get("execution", {}).get("nonce") == nonce,
            "native execution nonce differs")
    observations = [call.get("observation") for call in row.get("calls", [])
                    if call.get("method") == "Task13Revision5.originalProfileRuntime"]
    require(len(observations) == 1, "original profile observation missing or duplicated")
    ui = observations[0]
    require(ui.get("available") is True and ui.get("bundleName") == bundle and
            ui.get("caseId") == spec["caseId"] and ui.get("traceDigest") == spec["traceDigest"],
            "original profile identity differs")
    session = ui.get("sessionId")
    require(isinstance(session, str) and session and session not in used_sessions,
            "production case session missing or reused")
    frames = ui.get("frames", [])
    require([frame.get("label") for frame in frames] ==
            ["before_event", "after_missing_entry_attempt", "after_event"], "entry/positive-control frames missing")
    windows = []
    for frame in frames:
        window = frame.get("windowIdentity", {})
        require(frame.get("sessionId") == session and frame.get("bundleName") == bundle and
                window.get("bundleName") == bundle and window.get("focused") is True and
                window.get("hostVerified") is True and window.get("routeName") == "pages/Index",
                "original focused profile window differs")
        require(type(window.get("stageMainWindowId")) is int and type(window.get("lastWindowId")) is int and
                window["stageMainWindowId"] == window.get("lastWindowId"), "stage/window binding missing")
        windows.append(window["stageMainWindowId"])
        require(validate_inventory(frame.get("uiInventory", {})) == frame.get("uiClosure"),
                "complete original UI inventory/closure proof missing")
        require(frame["uiInventory"].get("windowBounds") == window.get("bounds"),
                "inventory belongs to a different window geometry")
        controls = {control["name"]: control for control in frame.get("controls", [])}
        require(len(controls) == len(frame.get("controls", [])), "duplicate profile controls")
        require(controls.get("profile", {}).get("visible") is True and
                controls["profile"].get("text") == "@alice:example.org", "original target profile missing")
        require(controls.get("verify", {}).get("present") is False, "verification component is not absent")
        legacy = controls.get("legacyVerify", {})
        require(legacy.get("present") is True and legacy.get("visible") is True and
                legacy.get("enabled") is False, "Android base's disabled legacy verification row missing")
        sdk = frame.get("pageObserver", {}).get("sdkState", {})
        require(sdk.get("currentUserId") == "@current:example.org" and
                sdk.get("verificationAvailable") is True and
                any(member.get("userId") == "@alice:example.org" for member in sdk.get("members", [])),
                "canonical common entry session/target/verification SDK inputs missing")
    require(len(set(windows)) == 1, "case switched production windows")
    before, after = frames[0], frames[-1]
    before_controls = {control["name"]: control for control in before["controls"]}
    require(all(before_controls.get("dm", {}).get(field) is True
                for field in ("present", "visible", "enabled", "clickable")), "healthy DM control missing")
    require(any(control.get("name") == "dmOpened" and control.get("visible") is True
                for control in after["controls"]), "real DM UI transition missing")
    require(any(node.get("text") == "Opening direct message" for node in after["uiInventory"]["nodes"]),
            "positive control absent from complete native inventory")
    attempt = ui.get("entryAttempt", {})
    require(attempt.get("sessionId") == session and attempt.get("event") == "select_verify_user" and
            attempt.get("selectorId") == "verify_user_action" and attempt.get("attempted") is True and
            attempt.get("componentFound") is False and
            attempt.get("failure") == "Task13 control unavailable: verify", "real missing-entry attempt missing")
    actions = ui.get("actions", [])
    require(len(actions) == 1 and actions[0].get("target") == "dm" and actions[0].get("executed") is True and
            actions[0].get("sessionId") == session, "unexpected or incomplete profile actions")
    require(before["sequence"] < attempt["sequence"] < frames[1]["sequence"] <
            actions[0]["sequence"] < after["sequence"], "entry attempt/positive control ordering differs")
    observer = after.get("pageObserver", {})
    require(observer.get("available") is True and observer.get("instanceCount") == 1 and
            observer.get("sameRoomReceiver") is True and
            observer.get("state") == {"userId": "@alice:example.org", "directMessageCalls": 1},
            "actual page presenter observation missing")
    calls = observer.get("calls", [])
    require(len(calls) == 2 and [call.get("owner") for call in calls] == ["presenter", "gateway"],
            "original page presenter/gateway call chain missing")
    for call in calls:
        require(call.get("method") == "startDirectMessage" and call.get("presenterId") == 1 and
                call.get("completed") is True and
                call.get("before") == {"userId": "@alice:example.org", "directMessageCalls": 0} and
                call.get("after") == observer["state"], "page-bound production DM call differs")
    require(calls[1].get("sameGatewayReceiver") is True, "separate gateway instance substituted")
    launch, cleanup = ui.get("launchEvidence", {}), ui.get("launchCleanup", {})
    require(launch.get("created") is True and launch.get("stageObserved") is True and
            cleanup.get("created") is True and cleanup.get("destroyed") is True,
            "original case creation/window/destruction unverified")
    used_sessions.add(session)
    return {"caseId": spec["caseId"], "sessionId": session, "windowId": windows[0],
            "actualMissingEntryAttempt": True, "samePageProductionPositiveControl": True,
            "observedProfileUserId": observer["state"]["userId"],
            "commonEntry": {"screen": "room_member_profile", "profileUserId": "@alice:example.org",
                            "isCurrentUser": False, "verificationAvailable": True},
            "canonicalGivenEstablished": True,
            "semanticVerdictGranted": True}


def inspect_report(raw_path, build_path, *, inventory, contract, include_entry_cases=True):
    load_policy(contract)
    raw, build = core.load(raw_path), core.load(build_path)
    require(raw.get("taskId") == contract["taskId"] == "13_user_verification" and
            raw.get("transportCompleted") is True and raw.get("candidateAbsentBeforeInstall") is True and
            raw.get("cleanup", {}).get("ownedAppUninstalled") is True, "fresh transport/cleanup missing")
    require(str(raw.get("pid", "")).isdigit() and int(raw["pid"]) > 0, "fresh native process identity missing")
    require(bool(raw.get("commands")), "device command audit missing")
    for command in raw["commands"]:
        log = (raw_path.parent / command["log"]).resolve()
        require(log.is_relative_to(raw_path.parent.resolve()) and core.sha256(log) == command.get("sha256"),
                "device command log hash/boundary differs")
    require(checked_record(raw["buildReport"]) == build_path.resolve(), "runtime used a different build")
    require(build.get("source") == inventory["source"] and
            all(build.get(key) is True for key in ("productionUnchanged", "copiedProductionUnchanged", "temporaryProjectRemoved")) and
            build.get("runtimeCompile", {}).get("passed") is True, "source-specific runtime build differs")
    require(build.get("standaloneAppCompile", {}).get("passed") is True and
            build.get("ohosTestCompile", {}).get("passed") is True, "application/runtime compile separation missing")
    for key in ("standaloneAppCompile", "ohosTestCompile"):
        artifact = build[key].get("artifact", {})
        require(type(artifact.get("bytes")) is int and artifact["bytes"] > 0 and
                isinstance(artifact.get("sha256"), str) and len(artifact["sha256"]) == 64,
                "compiled HAP hash/size missing")
    guard = [item for item in build.get("nativeUIObserver", {}).get("fixtures", [])
             if item.get("file") == str(UI_GUARD)]
    require(len(guard) == 1 and guard[0].get("sourceSha256") == core.sha256(UI_GUARD),
            "compiled native UI closure guard differs")
    for fixture in build["nativeUIObserver"]["fixtures"]:
        require(core.sha256(Path(fixture["file"])) == fixture.get("sourceSha256", fixture["sha256"]),
                "compiled original native fixture differs")
    binding = build.get("nativeUIObserver", {}).get("config", {}).get("pageBinding", {})
    require(binding.get("productionFeaturePath") and binding.get("page") == "entry/src/main/ets/pages/Index.ets" and
            binding.get("observedBinding") in {"base", "final"}, "actual page module binding missing")
    discovery = core.load(checked_record(build.get("task13Revision5", {})["entryDiscovery"]))
    require(discovery.get("pageBinding") == binding and
            discovery.get("source") == inventory["source"] and discovery.get("observedBinding") == binding["observedBinding"] and
            discovery.get("freshInstall") is True and discovery.get("ownedAppUninstalled") is True and
            discovery.get("status") == "production_common_entry_completed", "actual native entry discovery/page binding differs")
    require(discovery.get("positiveControl") == ("production_direct_message_opened" if binding["observedBinding"] == "base"
                                                else "production_verify_user_flow_opened"),
            "actual entry discovery positive control missing")
    require(discovery.get("layouts") and discovery.get("commands"), "native discovery inventory/logs missing")
    for layout in discovery["layouts"]:
        checked_record(layout["layout"])
    for command in discovery["commands"]:
        checked_record(command["log"])
    encoded = json.dumps(inventory["files"], sort_keys=True, separators=(",", ":")).encode()
    require(hashlib.sha256(encoded).hexdigest() == inventory["sha256"], "source inventory digest differs")
    sources = {item["path"]: item["sha256"] for item in inventory["files"]}
    require(binding["productionFeaturePath"] in sources and binding["page"] in sources and
            binding["productionModuleSuffix"] == binding["productionFeaturePath"].removeprefix("entry/src/main/").removesuffix(".ets"),
            "actual imported module/page outside source inventory")
    require(build.get("production") and all(sources.get(item["path"]) == item["sha256"]
                                           for item in build["production"]), "compiled production source differs")
    require({item["path"] for item in build["production"]} ==
            {path for path in sources if path.startswith("entry/src/main/")}, "compiled production closure is incomplete")
    nonce = raw.get("executionNonce")
    require(isinstance(nonce, str) and re.fullmatch(r"[0-9a-f]{32}", nonce) is not None,
            "native execution nonce missing or non-hex")
    artifacts = raw.get("rowArtifacts", [])
    require(len(artifacts) == len(contract["cases"]), "native row artifact inventory incomplete")
    artifact_rows = []
    for item in artifacts:
        artifact = {"path": item["local"], "bytes": item["bytes"], "sha256": item["sha256"]}
        artifact_rows.append(core.load(checked_record(artifact)))
        require(item.get("executionNonce") == nonce, "row artifact nonce differs")
    rows = {row["caseId"]: row for row in raw.get("rows", [])}
    require(len(rows) == len(contract["cases"]) and
            {row["caseId"]: row for row in artifact_rows} == rows, "native artifact rows differ")
    used = set()
    facts = []
    for spec in contract["cases"]:
        row = rows[spec["caseId"]]
        require(row.get("productionSources") and all(sources.get(item["path"]) == item["sha256"]
                                                     for item in row["productionSources"]), "row source binding differs")
        require(row.get("traceDigest") == spec["traceDigest"] and
                row.get("nativeBridge", {}).get("capabilities", {}).get("execution", {}).get("nonce") == nonce,
                "native case digest/nonce differs")
        ui_calls = [call.get("observation", {}) for call in row.get("calls", [])
                    if call.get("method") == "Task13Revision5.originalProfileRuntime"]
        bindings = build.get("nativeUIObserver", {}).get("sources", [])
        require(bindings and len(ui_calls) == 1 and ui_calls[0].get("productionSources") == bindings and
                all(sources.get(item["path"]) == item["sha256"] for item in bindings),
                "original UI/module SDK production binding differs")
        if binding["observedBinding"] == "base":
            for frame in ui_calls[0].get("frames", []):
                require(validate_inventory(frame.get("uiInventory", {})) == frame.get("uiClosure"),
                        "unbound native controls outside the entry prefix")
        if include_entry_cases and spec["key"] != "identity_violation_surfaces":
            facts.append(inspect_case(spec, row, bundle=build["bundleName"], nonce=nonce, used_sessions=used))
    group = None
    if binding["observedBinding"] == "base":
        last = rows[contract["cases"][-1]["caseId"]]
        group_ui = next(call["observation"] for call in last["calls"]
                        if call.get("method") == "Task13Revision5.originalProfileRuntime")
        group = inspect_group_closure(group_ui, bundle=build["bundleName"])
    return {"taskId": contract["taskId"], "scope": "live_source_bound_common_entry_prefix",
            "rawReport": core.file_record(raw_path), "buildReport": core.file_record(build_path),
            "sourceInventorySha256": inventory["sha256"], "cases": facts,
            "nativeExecutionVerified": True, "firstNineEntryValidated": include_entry_cases,
            "wholeGroupUiClosure": group, "frozenPolicy": core.file_record(POLICY)}


def entry_row(spec, raw_row, raw_path, build_path, inventory_path):
    return {
        "caseId": spec["caseId"], "key": spec["key"], "traceDigest": spec["traceDigest"],
        "status": "fail", "transitionExecuted": False,
        "given": copy.deepcopy(spec["given"]), "event": copy.deepcopy(spec["event"]),
        "observed": None, "invariantChecks": [],
        "unevaluatedInvariants": copy.deepcopy(spec["invariants"]),
        "unobservedExpectedFields": list(spec["expected"]),
        "checkpoints": copy.deepcopy(raw_row["checkpoints"]),
        "entryFailureEvidence": {
            "policyId": POLICY_ID, "canonicalGivenEstablished": True, "positiveControlCompleted": True,
            "rawReport": core.file_record(raw_path), "buildReport": core.file_record(build_path),
            "sourceInventory": core.file_record(inventory_path),
        },
        "reason": "Actual production profile exposes only disabled legacy Verify identity; enabled Verify user is absent after the canonical operation prefix and same-page DM positive control.",
    }


def validate_entry_failure(row, report, used_observation_ids, *, contract):
    require(report.get("taskId") == contract.get("taskId") == "13_user_verification" and
            report.get("platform") == "arkts" and report.get("role") in {"base", "final", "agent"},
            "task/platform/role differs")
    evidence = row.get("entryFailureEvidence", {})
    require(evidence.get("policyId") == POLICY_ID, "unrecognized entry policy")
    paths = [checked_record(evidence[key]) for key in ("rawReport", "buildReport", "sourceInventory")]
    require(all(path.is_relative_to(core.ROOT / "experiment_results") for path in paths), "artifact outside audit root")
    raw_path, build_path, inventory_path = paths
    inventory = core.load(inventory_path)
    provenance = report.get("provenance", {})
    require(inventory["source"] == provenance.get("candidateSource") and
            inventory["sha256"] == provenance.get("sourceInventorySha256"), "candidate inventory/source binding differs")
    declared = provenance.get("productionSources", [])
    require(declared == [item for item in inventory["files"] if item["path"].endswith((".kt", ".ets"))],
            "candidate production provenance differs")
    assessment = inspect_report(raw_path, build_path, inventory=inventory, contract=contract)
    spec = next((item for item in contract["cases"][:9] if item["caseId"] == row.get("caseId")), None)
    require(spec is not None, "identity-surface case cannot use the entry policy")
    raw_row = next(item for item in core.load(raw_path)["rows"] if item["caseId"] == spec["caseId"])
    expected = entry_row(spec, raw_row, raw_path, build_path, inventory_path)
    require(all(row.get(key) == value for key, value in expected.items()), "normalized entry row differs from native proof")
    case = next(item for item in assessment["cases"] if item["caseId"] == spec["caseId"])
    identity = (evidence["rawReport"]["sha256"], case["sessionId"])
    require(identity not in used_observation_ids, "production case session reused")
    used_observation_ids.add(identity)
