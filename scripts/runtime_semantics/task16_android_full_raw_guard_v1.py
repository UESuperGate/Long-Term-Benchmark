"""Independent diagnostic full10 guard. Missing provenance is NEVER semantic FAIL.

No role/ref/path-name outcome oracle. Current reviewed evaluator bytes AND a
caller-pinned request/full-input binding are required by verify_bundle. Pure
derive functions support negative unit fixtures; those are not runtime proof.
No public readiness or formal benchmark metrics are emitted here.
"""
from collections import Counter
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import tarfile

from . import task16_android_standalone_inputs_v2 as inputs

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "state_tests/runtime/android/16_identity_reset/page_owner_sdk_v3"
RESET = "io.element.android.features.securebackup.impl.reset."
RUST = "io.element.android.libraries.matrix.impl."
COMPANION = "cancel_cleans_up_lifecycle_return"


class EvidenceGap(ValueError):
    pass


def need(condition, reason):
    if not condition:
        raise EvidenceGap(reason)


def record(path):
    path = Path(path)
    data = path.read_bytes()
    return {"path": str(path.resolve()), "bytes": len(data), "sha256": inputs.digest(data)}


def load_current(name):
    spec = importlib.util.spec_from_file_location("task16_reviewed_" + name, FIXTURE / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def stack(call, *parts):
    return all(any(part in frame for frame in call.get("stack", [])) for part in parts)


def select(calls, method=None, kind=None):
    return [call for call in calls if (method is None or call.get("method") == method) and (kind is None or call.get("kind") == kind)]


def one(values, why):
    need(len(values) == 1, why)
    return values[0]


def ui_closure(point):
    """Fail closed for any extra/renamed/unbound actionable visible control."""
    need(type(point.get("uiAvailable")) is bool, "Actual UI availability missing")
    if not point["uiAvailable"]:
        need(point.get("semanticsInventory") is None, "Destroyed owner has invented native UI")
        return
    inventory = point.get("semanticsInventory")
    need(isinstance(inventory, list) and inventory, "Complete actual native inventory missing")
    need(len({node.get("id") for node in inventory}) == len(inventory) and all(node.get("id") is not None for node in inventory), "Duplicate/unidentified native nodes")
    bindings = point.get("selectorBindings", {})
    need(set(bindings) == {"continue", "cancel", "confirm", "password_submit"} and all(isinstance(v, str) and v for v in bindings.values()), "Missing reviewed selector bindings")
    # These ancillary controls are not feature-missing or pass/fail evidence.
    # Unknown variants remain unbound/NS until explicitly reviewed, not auto-trusted.
    labels = set(bindings.values()) | {"Back", "Close", "Show password", "Hide password"}
    allowed_actions = {"OnClick", "OnLongClick", "SetText", "SetSelection", "RequestFocus", "GetTextLayoutResult",
                       "CopyText", "CutText", "PasteText", "InsertTextAtCursor", "ImeAction", "OnImeAction", "ScrollBy", "ScrollToIndex", "SetProgress"}
    clicks, edits = Counter(), 0
    for node in inventory:
        need(type(node.get("displayed")) is bool and type(node.get("enabled")) is bool, "Unknown native visibility/eligibility")
        if not node["displayed"]:
            continue
        actions = set(node.get("actions", []))
        need(actions <= allowed_actions, "Unbound native semantics action")
        need(not actions or actions <= {"GetTextLayoutResult"} or "OnClick" in actions or "SetText" in actions,
             "Interactive control has no reviewed selector/owner binding")
        if "OnClick" in actions and "SetText" not in actions:
            text = tuple(node.get("text", []) + node.get("description", []))
            matched = {value for value in text if value in labels}
            need(matched, "Extra/renamed unbound clickable control")
            # A duplicate known label must not conceal a second feature entry.
            signature = tuple(sorted(matched))
            clicks[signature] += 1
            need(clicks[signature] == 1, "Duplicate bound control; inventory closure unknown")
        if "SetText" in actions:
            edits += 1
            need(point.get("passwordNodeId") is not None, "Editable control outside bound password owner")
    need(edits <= 1, "Extra editable feature control")


def points_for(row):
    points, ordered, seen_names = {}, [], set()
    for item in row.get("checkpoints", []):
        name = item.get("name")
        need(name not in seen_names, "Duplicate checkpoint name")
        seen_names.add(name)
        point = item.get("state", {}).get("pageOwner")
        if point is not None:
            points[name] = point
            ordered.append(point)
    for name in ("recovery_positive_ui", "recovery_returned_original_verification", "reset_root_reached"):
        need(name in points, "Real common UI/SDK positive control missing: " + name)
    canonical = ordered[ordered.index(points["reset_root_reached"]):]
    need(canonical, "No canonical mounted page")
    owner = canonical[0]
    history = []
    for point in ordered:
        calls = point.get("calls", [])
        need(calls[:len(history)] == history, "Warmup/actual call history dropped or rewritten")
        need(all(call.get("sequence") == index and call.get("episode") == point.get("episode") for index, call in enumerate(calls)), "Cross-episode/noncontiguous calls")
        history = calls
    for point in canonical:
        for key in ("episode", "activityId", "rootId", "presenterId", "flowId", "managerId", "callbackId", "clientId", "encryptionId", "scopeJobId", "sessionVerificationServiceId"):
            need(owner.get(key) is not None and owner[key] == point.get(key), "Detached owner/service: " + key)
        need(point.get("injectedManagerId") == point["managerId"] and point.get("rootParentId") == point["flowId"] == point.get("callbackOwnerId"), "Original page/flow/manager wiring missing")
        need(point.get("injectedVerificationServiceId") == point["sessionVerificationServiceId"], "Verification service not the original manager delegate")
        need(point.get("encryptionClass") == RUST + "encryption.RustEncryptionService" and
             point.get("sessionVerificationClass") == RUST + "verification.RustSessionVerificationService", "App-level service fake instead of original SDK bridge")
        tree = {node["id"]: node for node in point.get("nodeTree", [])}
        need(tree.get(point["flowId"], {}).get("class") == RESET + "ResetIdentityFlowNode" and
             tree.get(point["rootId"], {}).get("class") == RESET + "root.ResetIdentityRootNode", "Actual original Node tree absent")
        backup = tree.get(tree[point["flowId"]].get("parentId"), {})
        need(backup.get("class") == "io.element.android.features.securebackup.impl.SecureBackupFlowNode" and
             tree.get(backup.get("parentId"), {}).get("class") == "io.element.android.features.ftue.impl.sessionverification.FtueSessionVerificationFlowNode", "Original FTUE/secure-backup parent chain missing")
        if point.get("uiAvailable") is False:
            need(any(call.get("kind") == "actual_activity_lifecycle_return" and call.get("event") == "destroy" and call.get("destroyed") is True for call in point["calls"]), "Native UI absent without real Activity destruction")
        ui_closure(point)
    recovered = points["recovery_returned_original_verification"]
    recovery = one(select(recovered.get("calls", []), "Encryption.recover"), "Original recovery positive SDK call absent/duplicated")
    need(stack(recovery, "RustEncryptionService$recover$") and recovery.get("result") == "Unit" and len(recovery.get("key", "")) == 48, "Positive control bypassed real Rust service")
    need(recovered.get("episode") == owner["episode"] and recovered.get("activityId") == owner["activityId"], "Detached positive UI episode")
    positive_tree = {node["id"]:node for node in points["recovery_positive_ui"].get("nodeTree", [])}
    need(any(node.get("class") == "io.element.android.features.securebackup.impl.enter.SecureBackupEnterRecoveryKeyNode" and
         positive_tree.get(node.get("parentId"), {}).get("class") == "io.element.android.features.securebackup.impl.SecureBackupFlowNode" for node in positive_tree.values()), "Recovery positive never mounted original Node")
    recovered_tree = {node["id"]:node for node in recovered.get("nodeTree", [])}
    need(any(node.get("class") == "io.element.android.features.verifysession.impl.VerifySelfSessionNode" and
         recovered_tree.get(node.get("parentId"), {}).get("class") == "io.element.android.features.ftue.impl.sessionverification.FtueSessionVerificationFlowNode" for node in recovered_tree.values()), "Recovery did not return through original FTUE/verification UI")
    cleanup = one([item["state"] for item in row.get("checkpoints", []) if item.get("name") == "cleanup"], "Independent case cleanup missing")
    need(cleanup.get("episode") == owner["episode"] and cleanup.get("activityDestroyed") is True and cleanup.get("scopeCancelled") is True, "Case not independently cleaned")
    complete_calls = cleanup.get("calls", [])
    need(complete_calls[:len(history)] == history and all(call.get("sequence") == index and call.get("episode") == owner["episode"] for index, call in enumerate(complete_calls)), "Cleanup truncated original calls")
    need(not any(call.get("kind") == "unbound_external_port" for call in complete_calls), "Unknown external call: unavailable")
    return points, owner, history


def acquisition(point, calls, *, expected_count=1, missing=False):
    starts, returns = select(calls, "Encryption.resetIdentity.enter"), select(calls, "Encryption.resetIdentity.return")
    need(len(starts) == expected_count and all(stack(call, "RustEncryptionService.startIdentityReset") and call.get("receiverId") == point["sdkEncryptionId"] for call in starts), "Reset acquisition bypassed original Rust bridge")
    entries, results = select(calls, kind="manager_enter"), select(calls, kind="manager_return")
    callbacks, callback_returns = select(calls, kind="root_callback_enter"), select(calls, kind="root_callback_return")
    need(callbacks and len(callbacks) == len(callback_returns), "Actual root callback entry/return absent")
    trace = point.get("dispatcherTrace", [])
    need(trace and all(item.get("sequence") == index for index, item in enumerate(trace)), "Actual dispatcher trace missing")
    for entry, returned in zip(callbacks, callback_returns):
        need(entry.get("callbackId") == returned.get("callbackId") == point["callbackId"] and
             entry.get("callbackOwnerId") == entry.get("flowId") == returned.get("flowId") == point["flowId"] and
             entry.get("sameMountedRootCallback") is True, "Different callback owner")
        if entry.get("phase") != "domain_invariant_loading":
            need(stack(entry, "ResetIdentityRootViewKt"), "Acquisition primary prefix bypassed actual root UI")
        jobs = [job for job in returned.get("childJobsAfter", []) if job not in entry.get("childJobsBefore", [])]
        need(len(jobs) == 1 and jobs == returned.get("createdChildJobIds"), "No callback-created Job")
        manager_entry = one([call for call in entries if call.get("executingJobId") == jobs[0]], "Manager not executing actual callback Job")
        need(entry.get("scopeJobId") == returned.get("scopeJobId") == manager_entry.get("scopeJobId") == point["scopeJobId"], "Callback/manager scope detached")
        need(entry["sequence"] < returned["sequence"] < manager_entry["sequence"] and stack(manager_entry, "ResetIdentityFlowNode$startReset$"), "Original asynchronous Flow callback not observed")
        need(manager_entry.get("managerId") == point["managerId"] and manager_entry.get("sameConstructedReceiver") is True, "Replaced constructed manager")
        need(any(item.get("jobId") == jobs[0] and item.get("event") == "enter" for item in trace), "Callback Job not dispatched")
    for call in starts:
        sdk = one([item for item in select(calls, kind="sdk_start") if item.get("requestId") == call.get("requestId")], "SDK request not linked to same manager")
        need(sdk.get("managerId") == point["managerId"] and sdk.get("encryptionId") == point["encryptionId"], "Detached SDK acquisition")
        need(sdk.get("scopeJobId") == point["scopeJobId"] and sdk.get("executingJobId") == call.get("executingJobId"), "SDK leaf escaped original manager Job/scope")
        need(any(call.get("executingJobId") in item.get("createdChildJobIds", []) for item in results), "SDK Job not created by actual manager")
    if missing:
        need(len(returns) == 1 and returns[0].get("sdkHandleId") is None, "Missing-handle event not observed")
    return starts, returns


def handle_binding(point, calls, kind):
    auth = one(select(calls, "IdentityResetHandle.authType"), "Original SDK factory authType absent")
    returned = one(select(calls, "Encryption.resetIdentity.return"), "Original SDK handle return absent")
    need(stack(auth, "RustIdentityResetHandleFactory.create") and auth.get("receiverId") == returned.get("sdkHandleId") == point.get("wrappedSdkHandleId"), "Original factory/wrapped SDK handle mismatch")
    need(point.get("handleClass") == RUST + "encryption.Rust" + ("Password" if kind == "password" else "Oidc") + "IdentityResetHandle", "Application handle fake/unbound wrapper")
    need(auth.get("result") == ("Uiaa" if kind == "password" else "Oidc"), "Actual SDK auth type differs")
    if kind == "password":
        tree = {node["id"]: node for node in point["nodeTree"]}
        node = tree.get(point.get("passwordNodeId"), {})
        need(node.get("class") == RESET + "password.ResetIdentityPasswordNode" and node.get("parentId") == point["flowId"], "Password page detached")
        need(point.get("passwordInputHandleId") == point.get("passwordPresenterHandleId") == point.get("handleId") and point.get("handleId") is not None, "Password original Node/presenter handle mismatch")
        frames = [frame for frame in point.get("passwordFrames", []) if frame.get("nodeId") == point["passwordNodeId"]]
        need(frames and all(frame.get("presenterId") == point.get("passwordPresenterId") and
             frame.get("inputHandleId") == point["handleId"] and stack(frame, "ResetIdentityPasswordNode.View") for frame in frames), "No same-owner original composable returns")
    return auth["receiverId"]


def derive_case(key, points, owner, calls, companion=None):
    after = points.get("after")
    need(isinstance(after, dict), "Primary AFTER absent")
    invariants = []
    if key in {"continue_requests_confirmation", "dismiss_confirmation", "confirm_starts_handle"}:
        inspected = load_current("evidence_v2").inspect_episode(key, [{"name": name, "state": {"pageOwner": point}} for name, point in points.items()])
        actual = {"confirmationVisible": after["confirmationVisible"]}
        if key == "confirm_starts_handle":
            acquisition(points["domain_cached_success"], points["domain_cached_success"]["calls"])
            handle_binding(points["domain_cached_success"], points["domain_cached_success"]["calls"], "password")
            actual.update(handleState=after["handleState"], effect="start_identity_reset" if select(calls, "Encryption.resetIdentity.enter") else None)
        else:
            actual["startResetCount"] = len(select(calls, "Encryption.resetIdentity.enter"))
        return actual, [inspected["invariantSatisfied"]]
    acquisition(after, calls, expected_count=2 if key == "handle_failure_recovers" else 1, missing=key == "handle_failure_recovers")
    if key == "password_handle_routes":
        handle_binding(after, calls, "password")
        need(points["before"]["handleState"] == "loading" and points["before"].get("controlledSdkAuthType") == "password", "Canonical loading/password given missing")
        return {"handleState": after["handleState"], "screen": "reset_password", "password": after["password"]}, [after["passwordInputHandleId"] == after["handleId"]]
    if key == "oidc_handle_routes_and_resets":
        sdk_id = handle_binding(after, calls, "oidc")
        poll = one(select(calls, "IdentityResetHandle.reset.enter"), "OIDC SDK poll absent")
        need(poll.get("receiverId") == sdk_id and poll.get("authenticationType") == "oidc" and stack(poll, "RustOidcIdentityResetHandle.resetOidc"), "OIDC poll bypassed actual wrapper")
        tree = {node["id"]: node for node in after["nodeTree"]}
        need(tree.get(after.get("oidcNodeId"), {}).get("class") == "io.element.android.libraries.oidc.impl.webview.OidcNode" and tree[after["oidcNodeId"]]["parentId"] == after["flowId"], "Actual original OIDC page missing")
        need(points["before"].get("handleState") == "loading" and points["before"].get("controlledSdkAuthType") == "oidc", "Canonical OIDC given absent")
        url = one(after.get("nativeWebViewUrls", []), "Actual WebView URL missing/ambiguous")
        return {"handleState": after["handleState"], "effect": "open_oidc_approval", "url": url, "pollEffect": "reset_oidc"}, [after.get("customTabAvailable") is False and url == after.get("oidcInputUrl")]
    if key == "handle_failure_recovers":
        stable = points["stable_after_cleanup"]
        observed = [call["state"] for call in calls if call.get("kind") == "actual_manager_state"]
        need(observed == after.get("handleStates"), "Manager state sequence projected/filtered")
        need(points["before"].get("handleState") == "loading", "Canonical loading given absent")
        enabled = any(node.get("displayed") and node.get("enabled") and stable["selectorBindings"]["continue"] in node.get("text", []) and "OnClick" in node.get("actions", []) for node in stable["semanticsInventory"])
        actual = {"failureObserved": "failure" in observed, "stateSequence": observed, "stableHandleState": stable["handleState"],
                  "screen": "reset_root", "progressVisible": stable["progressVisible"], "retryEnabled": enabled, "retryHandleState": after["handleState"]}
        return actual, ["failure" in observed and "success" not in observed,
                        stable["handleState"] == "uninitialized" and stable["progressVisible"] is False and enabled,
                        after["handleState"] == "loading" and len(select(calls, "Encryption.resetIdentity.enter")) == 2]
    if key in {"password_submit_calls_handle", "password_failure_clears_on_edit", "success_waits_for_verification"}:
        sdk_id = handle_binding(after, calls, "password")
        submitted = one(select(calls, "IdentityResetHandle.reset.enter"), "Password SDK submit absent/duplicated")
        need(submitted.get("receiverId") == sdk_id and submitted.get("authenticationType") == "password" and
             stack(submitted, "RustPasswordIdentityResetHandle.resetPassword", "ResetIdentityPasswordPresenter"), "Password submit bypassed original presenter/Rust bridge")
        session = one(select(calls, "Client.session"), "Original Rust bridge SDK session missing")
        need(submitted.get("identifier") == session.get("userId") and session.get("userId"), "Password SDK user identifier mapping broken")
        empty = points["positive_empty_password_disabled"]
        need(empty.get("password") == "" and empty.get("resetAction") == "uninitialized", "No original empty-password positive control")
        disabled = empty.get("passwordSubmitEnabled") is False and empty.get("sdkResetCount") == 0
        if key == "password_submit_calls_handle":
            before = points["before_submit"]
            need(before.get("password") == "secret" and before.get("resetAction") == "uninitialized", "Canonical password given absent")
            return {"resetAction": after["resetAction"], "effect": "reset_password", "password": submitted.get("password"), "progressVisible": after["progressVisible"]}, [disabled]
        if key == "password_failure_clears_on_edit":
            need(points["given_loading"].get("resetAction") == "loading" and points["given_loading"].get("password") == "wrong", "Canonical wrong/loading given absent")
            need(points["failure_visible"].get("resetAction") == "failure" and points["failure_visible"].get("passwordErrorVisible") is True, "SDK failure/error never observed")
            failed = one([item for item in select(calls, "IdentityResetHandle.reset.throw") if item.get("requestId") == submitted.get("requestId")], "Actual SDK reset failure missing")
            edit = one([item for item in select(calls, kind="ui_text_edit") if item.get("operation") == "replacement"], "Physical post-failure edit missing")
            need(failed["sequence"] < edit["sequence"] and edit.get("nodeId") == after["passwordNodeId"] and edit.get("presenterId") == after["passwordPresenterId"], "Edit detached from failed original owner")
            return {"resetAction": after["resetAction"], "password": after["password"], "errorVisible": after["passwordErrorVisible"], "retryEnabled": after["passwordSubmitEnabled"]}, [not select(calls, "IdentityResetHandle.cancel") and not select(calls, "IdentityResetHandle.destroy")]
        waiting = points["sdk_success_waiting_original_verification"]
        given = points["given_loading_not_verified"]
        need(given.get("resetAction") == "loading" and given.get("sessionVerificationStatus") == "NotVerified", "Canonical unverified/loading given absent")
        returned = one([item for item in select(calls, "IdentityResetHandle.reset.return") if item.get("requestId") == submitted.get("requestId")], "Actual SDK password success missing")
        event = one(select(calls, kind="external_sdk_delegate_event"), "Actual SDK verification callback missing")
        need(event.get("method") == "didFinish" and event.get("delegateId") == event.get("serviceId") == after["sessionVerificationServiceId"], "Detached/forged application verification callback")
        delegates = [item for item in select(calls, "SessionVerificationController.setDelegate") if item.get("delegateId") == event["delegateId"]]
        need(delegates and delegates[-1]["sequence"] < event["sequence"] and stack(delegates[-1], "RustSessionVerificationService"), "Callback not bound by original SDK controller delegate registration")
        state = one([item for item in select(calls, "Encryption.verificationState") if item.get("verified") is True], "Actual original service did not read verified SDK result")
        completions = select(calls, kind="actual_ftue_completion")
        need(returned["sequence"] < event["sequence"] < state["sequence"] and stack(state, "RustSessionVerificationService"), "SDK success/verification order invalid")
        need(all(item.get("managerId") == after["managerId"] and item.get("flowId") == after["flowId"] and stack(item, "ResetIdentityFlowManager", "FtueSessionVerificationFlowNode") for item in completions), "Completion bypassed actual parent owner chain")
        return {"resetAction": waiting["resetAction"], "progressVisibleUntilVerified": waiting["progressVisible"], "completionCount": len(completions)}, [given.get("completionCount") == waiting.get("completionCount") == 0 and all(item.get("status") == "Verified" and item["sequence"] > state["sequence"] for item in completions)]
    need(key == "cancel_cleans_up" and companion is not None, "Case010 independent lifecycle companion required")
    before = points["before"]
    need(before.get("handleState") == "success" and before.get("resetJobActive") is True and before.get("completionWatcherActive") is True, "Canonical active-job given absent")
    sdk_id = handle_binding(before, before["calls"], "oidc")
    verify_active_oidc_job(before)
    verify_cleanup_phase(owner, calls, sdk_id, "destroy")
    companion_points, companion_owner, companion_calls = points_for(companion)
    need(companion_owner["episode"] != owner["episode"], "Case010 reused a single episode")
    cb, cr = companion_points["before"], companion_points["after_return"]
    need(cb.get("resetJobActive") is True and cb.get("completionWatcherActive") is True, "Companion active given not reached")
    acquisition(cr, companion_calls)
    csdk = handle_binding(cb, cb["calls"], "oidc")
    verify_active_oidc_job(cb)
    verify_cleanup_phase(companion_owner, companion_calls, csdk, "stop_start")
    need(cr.get("completionWatcherActive") is True and cr.get("completionWatcherId") is not None and cr["completionWatcherId"] != cb.get("completionWatcherId"), "Original onStart watcher restart was projected away")
    verify_cleanup_phase(companion_owner, companion_calls, None, "destroy")
    invariant = cr.get("handleState") == "uninitialized" and cr.get("resetJobActive") is False and after.get("handleState") == "uninitialized" and after.get("resetJobActive") is False and after.get("completionWatcherActive") is False
    return {"effect": "cancel_reset_handle", "handleState": after["handleState"], "resetJobActive": after["resetJobActive"], "completionWatcherActive": after["completionWatcherActive"]}, [invariant]


def verify_active_oidc_job(point):
    poll = one(select(point["calls"], "IdentityResetHandle.reset.enter"), "Active OIDC job has no actual SDK poll")
    need(poll.get("authenticationType") == "oidc" and poll.get("receiverId") == point.get("wrappedSdkHandleId") and
         poll.get("executingJobId") == point.get("resetJobId") and point.get("resetJobId") is not None and
         stack(poll, "RustOidcIdentityResetHandle.resetOidc"), "Given resetJob not executing original OIDC wrapper/SDK leaf")


def verify_cleanup_phase(owner, calls, sdk_id, event):
    enter = one([item for item in select(calls, kind="actual_activity_lifecycle_enter") if item.get("event") == event], "Real Activity lifecycle event missing")
    leave = one([item for item in select(calls, kind="actual_activity_lifecycle_return") if item.get("event") == event], "Real Activity lifecycle return missing")
    need(enter.get("activityId") == owner["activityId"] and enter.get("flowId") == owner["flowId"], "Lifecycle acted on another owner")
    cancel = one([item for item in select(calls, kind="actual_manager_cancel_enter") if enter["sequence"] < item["sequence"] < leave["sequence"]], "Actual manager cleanup not inside original lifecycle")
    need(cancel.get("managerId") == owner["managerId"] and stack(cancel, "ResetIdentityFlowNode", "onDestroy" if event == "destroy" else "onStart"), "Lifecycle cleanup bypassed original FlowNode")
    result = one([item for item in select(calls, kind="actual_manager_cancel_return") if cancel["sequence"] < item["sequence"] < leave["sequence"]], "Actual original manager cleanup did not return")
    need(result.get("managerId") == owner["managerId"] and result.get("handleState") == "uninitialized" and result.get("completionWatcherActive") is False, "Original cleanup return fields not observed")
    if sdk_id is None:
        need(not any(enter["sequence"] < item["sequence"] < leave["sequence"] for item in select(calls, "IdentityResetHandle.cancel")), "Companion empty handle unexpectedly cancelled twice")
        return
    sdk_cancel = one([item for item in select(calls, "IdentityResetHandle.cancel") if enter["sequence"] < item["sequence"] < leave["sequence"]], "SDK cancel missing from lifecycle")
    destroy = one([item for item in select(calls, "IdentityResetHandle.destroy") if enter["sequence"] < item["sequence"] < leave["sequence"]], "SDK destroy missing from lifecycle")
    need(sdk_cancel.get("receiverId") == destroy.get("receiverId") == sdk_id and sdk_cancel["sequence"] < destroy["sequence"] and
         stack(sdk_cancel, "RustOidcIdentityResetHandle.cancel") and stack(destroy, "RustOidcIdentityResetHandle.cancel"), "Actual original wrapper cancel/destroy mismatch")


def inspect_rows(rows, contract):
    keys = [case["key"] for case in contract["cases"]]
    need([row.get("key") for row in rows] == keys + [COMPANION] and len(keys) == 10, "Full10 + independent companion not actually executed")
    episodes, result = [], {}
    for spec, row in zip(contract["cases"], rows[:10]):
        need(row.get("status") in {"pass", "fail"}, "Incomplete/unavailable actual method")
        points, owner, calls = points_for(row)
        episodes.append(owner["episode"])
        actual, checks = derive_case(spec["key"], points, owner, calls, rows[-1] if spec["key"] == "cancel_cleans_up" else None)
        need(set(actual) == set(spec["expected"]) and len(checks) == len(spec["invariants"]), "Original full assertion/invariant coverage missing")
        need(all(type(value) is bool for value in checks), "Invariant result not independently evaluated Boolean")
        need(actual == row.get("observed"), "Reported observed state differs from independently derived native/SDK facts")
        result[spec["key"]] = {"actual": actual, "invariants": dict(zip(spec["invariants"], checks)),
                              "expectedMatches": actual == spec["expected"], "diagnosticOnly": True,
                              "semanticStatus": "not_scored", "episode": owner["episode"]}
    companion_points, companion_owner, _ = points_for(rows[-1])
    need(rows[-1].get("status") == "pass" and companion_points.get("after_companion_destruction", {}).get("completionWatcherActive") is False, "Companion did not finish actual destruction")
    episodes.append(companion_owner["episode"])
    need(len(set(episodes)) == 11, "Cases/companion reused runtime episode")
    return result


def bounded(root, path):
    root, path = Path(root).resolve(), Path(path).resolve(strict=True)
    need(root in path.parents and path.is_file(), "Report/artifact path escapes retained audit root")
    return path


def artifact(root, item):
    path = bounded(root, item["path"])
    need(record(path) == item, "Retained artifact bytes/hash differ")
    return path


def json_at(root, name):
    return json.loads(bounded(root, root / name).read_text())


def verify_class_retention(root, retention, scope):
    need(retention and retention.get("scope") == scope and retention.get("classFiles"), "Actual compiler class ledger absent")
    rows = retention["classFiles"]
    class_root = Path(retention["classRoot"])
    mapping = {}
    for row in rows:
        relative = Path(row["path"]).relative_to(class_root).as_posix()
        need(relative not in mapping and relative.endswith(".class") and row["bytes"] > 0, "Duplicate/invalid class ledger")
        mapping[relative] = row
    if scope == "binary_free_predeclared":
        need(retention.get("archive") is None and retention.get("mainClassBytesReverified") is False, "Binary-free tier changed/overclaimed")
        return {"classFiles": len(rows), "classBytesIndependentlyChecked": False, "scope": scope}
    need(scope == "retained_tiny_classes", "Unknown binary proof tier")
    archive = artifact(root, retention["archive"])
    seen = set()
    with tarfile.open(archive) as stream:
        for entry in stream:
            need(entry.isfile() and entry.name in mapping and entry.name not in seen, "Unexpected/duplicate class archive member")
            data = stream.extractfile(entry).read()
            row = mapping[entry.name]
            need(len(data) == row["bytes"] and inputs.digest(data) == row["sha256"], "Retained class bytes differ from compiler ledger")
            seen.add(entry.name)
    need(seen == set(mapping), "Class archive incomplete")
    return {"classFiles": len(rows), "classBytesIndependentlyChecked": True, "scope": scope}


def directory_digest(files):
    digest = hashlib.sha256()
    for name, (data, _) in sorted(files.items()):
        encoded = name.encode()
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)
        digest.update(len(data).to_bytes(8, "big"))
        digest.update(data)
    return digest.hexdigest()


def candidate_resources(files, sources):
    resources = []
    for module in sorted({path.split("/src/main/", 1)[0] for path in sources}):
        names = sorted(name for name in files if name.startswith(module + "/src/main/res/"))
        if not names:
            continue
        build = files.get(module + "/build.gradle.kts")
        namespace = re.search(r'namespace\s*=\s*"([^"]+)"', build[0].decode()) if build else None
        need(namespace, "Unbound actual candidate resource namespace")
        resources.append({"package": namespace[1], "files": names})
    return resources


def candidate_reads(provenance, files, config):
    required = set(config["sources"]) | {config["dependencyCatalog"]["path"]}
    required.update(path for resource in config["resources"] for path in resource["files"])
    seen = set()
    for item in provenance.get("productionSources", []):
        path = item["path"]
        need(path in files and len(files[path][0]) == item["bytes"] and inputs.digest(files[path][0]) == item["sha256"], "Actual candidate read borrowed/mixed input bytes")
        seen.add(path)
    need(required <= seen, "Actual production/resource/catalog read closure incomplete")


def compiled_inputs(actual, files, sources, evaluators):
    expected = Counter((len(files[name][0]), inputs.digest(files[name][0])) for name in sources)
    expected.update((item["bytes"], item["sha256"]) for item in evaluators)
    need(Counter((item["bytes"], item["sha256"]) for item in actual) == expected, "Compiled project/evaluator source missing/extra/mixed")


def required_classes(retention):
    root = Path(retention["classRoot"])
    names = {Path(item["path"]).relative_to(root).as_posix() for item in retention["classFiles"]}
    classes = [RESET + name for name in ("ResetIdentityFlowNode", "ResetIdentityFlowManager", "root.ResetIdentityRootNode",
        "root.ResetIdentityRootPresenter", "root.ResetIdentityRootViewKt", "password.ResetIdentityPasswordNode",
        "password.ResetIdentityPasswordPresenter", "password.ResetIdentityPasswordViewKt")]
    classes += [RUST + "encryption." + name for name in ("RustEncryptionService", "RustIdentityResetHandleFactory", "RustPasswordIdentityResetHandle", "RustOidcIdentityResetHandle")]
    classes += [RUST + "verification.RustSessionVerificationService", "io.element.android.libraries.oidc.impl.DefaultOidcEntryPoint",
                "io.element.android.libraries.oidc.impl.webview.OidcNode", "io.element.android.libraries.oidc.impl.webview.OidcPresenter",
                "io.element.android.libraries.oidc.impl.webview.OidcViewKt"]
    need(all(name.replace(".", "/") + ".class" in names for name in classes), "Original page/presenter/View/SDK bridge classes missing from actual emitted output")


def verify_bundle(run_root, *, expected_request_sha256, reviewed_sources, expected_input_tree_sha256=None,
                  require_completed=True):
    root = Path(run_root).resolve(strict=True)
    need(root.is_dir(), "Retained audit root missing")
    # Current independently reviewed code, not an arbitrary self-signed snapshot.
    need(reviewed_sources and all(record(item["path"]) == item for item in reviewed_sources), "Current evaluator bytes do not match caller-reviewed sources")
    reviewed = {item["path"]: item for item in reviewed_sources}
    need(str(Path(__file__).resolve()) in reviewed and str(FIXTURE / "plan.py") in reviewed, "Guard/plan not independently reviewed")
    request_path = bounded(root, root / "request.json")
    need(record(request_path)["sha256"] == expected_request_sha256, "Request not caller-pinned")
    request = json.loads(request_path.read_text())
    need(request.get("implementation") == reviewed_sources and request.get("binaryProofScope") in {"retained_tiny_classes", "binary_free_predeclared"}, "Unreviewed request/proof tier")
    need(0 < request["deadlineEpochMs"] - request["startedAtEpochMs"] <= 3600000 and request["childBudget"]["deadlineEpochMs"] <= request["deadlineEpochMs"], "Overall/child deadline extended")
    need(request.get("originalRepairBudgetReused") is False, "Old repair budget reset/reused")
    plan = json_at(root, "input-plan/plan.json")
    config = json_at(root, "input-plan/configuration.json")
    need(plan.get("schemaVersion") == "android-page-owner-plan.v3" and plan.get("source") == request.get("source"), "Standalone plan/source binding missing")
    captured = plan["standaloneInput"]
    artifact(root, captured["archive"])
    files = inputs.retained_files(captured)
    if expected_input_tree_sha256 is not None:
        need(captured["treeSha256"] == expected_input_tree_sha256, "Prospectively pinned candidate differs")
    current_plan = load_current("plan")
    expected_closure = sorted(set(inputs.closure(files, current_plan.SEEDS) + [
        "anvilannotations/src/main/kotlin/io/element/android/anvilannotations/ContributesNode.kt",
        "appconfig/src/main/kotlin/io/element/android/appconfig/SecureBackupConfig.kt"]))
    need(config.get("entrypoints") == current_plan.SEEDS and config.get("sources") == expected_closure and config.get("sourceClosure") is False, "Actual candidate production closure missing/borrowed")
    need(config.get("resources") == candidate_resources(files, expected_closure), "Selected candidate resource closure omits/borrows inputs")
    need(config.get("keys") == current_plan.KEYS + [COMPANION], "Compiler/run keys omit canonical cases")
    need(plan["canonicalContract"] == request["canonicalContract"] == reviewed.get(str(ROOT / "benchmark_tasks/16_identity_reset/transitions.json")) and record(request["canonicalContract"]["path"]) == request["canonicalContract"], "Canonical contract changed/unbound")
    contract = json.loads(Path(request["canonicalContract"]["path"]).read_text())
    need(plan["configuration"] == record(root / "input-plan/configuration.json"), "Actual configuration hash differs")
    for item in plan["archives"]:
        artifact(root, item)
    snapshot_evaluators = {item["path"]: item for item in plan["evaluatorSources"]}
    need(snapshot_evaluators and all(reviewed.get(path) == item for path, item in snapshot_evaluators.items()), "Evaluator snapshot not current-reviewed code")
    with tarfile.open(root / "input-plan/evaluator-inputs.tar.gz") as stream:
        seen = set()
        for entry in stream:
            current = str(ROOT / entry.name)
            need(entry.isfile() and current in snapshot_evaluators and current not in seen and ".." not in Path(entry.name).parts, "Unknown evaluator snapshot member")
            data = stream.extractfile(entry).read()
            need(inputs.digest(data) == snapshot_evaluators[current]["sha256"], "Evaluator snapshot bytes differ")
            seen.add(current)
        need(seen == set(snapshot_evaluators), "Evaluator archive incomplete")
    raw = json_at(root, "slice.json")
    provenance = raw.get("provenance", {})
    actual_source = Path(provenance.get("source", "/missing")).resolve()
    need(root / "owned-work" in actual_source.parents and provenance.get("candidateMode") == "standalone_directory" and
         provenance.get("candidateRootSha256") == directory_digest(files) and "commit" not in provenance, "Runtime borrowed an immutable/ref/other candidate")
    candidate_reads(provenance, files, config)
    need(provenance.get("configurationSha256") == record(root / "input-plan/configuration.json")["sha256"], "Actual runtime configuration not bound")
    need(raw.get("runtimeCompile", {}).get("status") == "passed", "Actual Kotlin compilation unavailable")
    compilations = json_at(root, "actual-kotlin-compilation.json")
    compilation = one(compilations, "Ambiguous/missing actual compilation")
    need(compilation.get("exitCode") == 0 and compilation.get("command") == raw["runtimeCompile"]["command"], "Actual compiler command not bound")
    actual_kotlin = compilation.get("actualKotlinInputs", [])
    evaluator_paths = [FIXTURE / name for name in config["evaluatorSources"]] + [ROOT / "state_tests/runtime/android/common/Harness.kt"]
    need(all(str(path) in reviewed for path in evaluator_paths), "Actual compiled evaluator absent from reviewed closure")
    compiled_inputs(actual_kotlin, files, expected_closure, [reviewed[str(path)] for path in evaluator_paths])
    required_classes(compilation["classRetention"])
    class_proofs = [verify_class_retention(root, compilation["classRetention"], request["binaryProofScope"])]
    for java in json_at(root, "actual-java-compilation.json"):
        need(java.get("exitCode") == 0 and java.get("actualJavaInputs"), "Actual resource/bridge compilation unavailable")
        archive = artifact(root, java["inputArchive"])
        with tarfile.open(archive) as stream:
            members = stream.getmembers()
            need(len(members) == len(java["actualJavaInputs"]) and all(member.isfile() for member in members), "Actual Java source archive incomplete")
            for member, item in zip(members, java["actualJavaInputs"]):
                data = stream.extractfile(member).read()
                need(len(data) == item["bytes"] and inputs.digest(data) == item["sha256"], "Actual Java compiler input changed")
        class_proofs.append(verify_class_retention(root, java["classRetention"], request["binaryProofScope"]))
    class_root = compilation["classRetention"]["classRoot"]
    runtime_command = raw.get("runtimeCommand", [])
    need(runtime_command and Path(runtime_command[runtime_command.index("-cp") + 1].split(":")[0]).resolve() == Path(class_root).resolve(), "JUnit did not load actual emitted classes first")
    log = bounded(root, raw["log"]["path"])
    need(record(log)["sha256"] == raw["log"]["sha256"], "Actual stdout/log bytes changed")
    decoded = [json.loads(line[len("RUNTIME_RESULT "):]) for line in log.read_text().splitlines() if line.startswith("RUNTIME_RESULT ")]
    need(decoded == raw.get("observations"), "Rows differ from actual retained runtime stdout")
    worker_start = json_at(root, "android-worker-started.json")
    parent_launch = json_at(root, "worker-launch.json")
    need(worker_start["pid"] == worker_start["pgid"] == parent_launch["pid"] == parent_launch.get("pgid") and
         worker_start.get("request") == parent_launch.get("request") == record(request_path) and
         worker_start.get("binaryProofScope") == request["binaryProofScope"], "Owned worker/proof scope unbound")
    launches = json_at(root, "actual-process-launches.json")
    need(launches and all(item.get("pgid") == item.get("workerPgid") == parent_launch["pid"] and item.get("workerPid") == parent_launch["pid"] and request["startedAtEpochMs"] <= item["startedAtEpochMs"] <= request["childBudget"]["deadlineEpochMs"] for item in launches), "Actual process launch/group/deadline violation")
    need(any(item["command"] == runtime_command for item in launches) and any(item["command"] == compilation["command"] for item in launches), "Real compile/JUnit launches missing")
    locks = json_at(root, "android-locks-acquired.json")
    need(locks.get("pid") == parent_launch["pid"] and locks.get("lockOwner") == "child_only" and
         locks["paths"] == ["/tmp/long-term-benchmark-android-full-build.lock", str(ROOT / "state_tests/runtime/android/.build.lock")], "Both canonical locks not owned solely by child")
    diagnostic = json_at(root, "standalone-diagnostic.json")
    need(diagnostic.get("beforeRuntimeTreeSha256") == diagnostic.get("afterRuntimeTreeSha256") == diagnostic.get("retainedRuntimeInputTreeSha256") == captured["treeSha256"] and
         diagnostic.get("temporaryMaterializationRemoved") is True and diagnostic.get("endedAtEpochMs") <= request["childBudget"]["deadlineEpochMs"], "Prospective before/after input or overall completion unproved")
    facts = inspect_rows(decoded, contract)
    if require_completed:
        completed = json_at(root, "controller-admission.json")
        need(completed.get("state") == "complete" and completed.get("ownedProcesses", {}).get("groupGone") is True and
             completed["ownedProcesses"].get("leaderReaped") is True and completed.get("temporaryCleanup", {}).get("removed") is True and
             completed.get("completedAtEpochMs", float("inf")) <= request["deadlineEpochMs"], "Whole owned-supervisor episode/cleanup incomplete")
        need(not (root / "owned-work").exists(), "Owned temporary work still exists")
    return {"schemaVersion": "task16-full-native-diagnostic.v1", "formalStatus": "not_scored", "diagnosticOnly": True,
            "full10Facts": facts, "completeInputTreeSha256": captured["treeSha256"], "classProofs": class_proofs,
            "mainClassByteApprovalClaimed": False, "requiresPublicReviewBeforeAdmission": True}
