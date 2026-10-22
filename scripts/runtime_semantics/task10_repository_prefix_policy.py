"""Strict audited Task10 prepared-media prefix failure, never API-name absence."""
import copy
import hashlib
import json
from pathlib import Path
import re

try:
    from . import tasks10_11_runtime_evidence as evidence
except ImportError:
    import tasks10_11_runtime_evidence as evidence

POLICY = "task10.arkts.actual-prepared-prefix.v2"
CASE = "mq_state_009_failure_cancel_retry"


def _require(value, reason):
    if not value:
        raise ValueError(reason)


def _state(point):
    frame = point["state"]
    state = frame.get("state") if isinstance(frame.get("state"), dict) else frame.get("stateAfter")
    _require(isinstance(state, dict) and state.get("available") is True, "Actual production state unavailable")
    return frame, state


def _verify_transport(native, execution):
    nonce = execution.get("executionNonce")
    _require(isinstance(nonce, str) and re.fullmatch(r"[a-f0-9]{32}", nonce) and
             native.get("nativeBridge", {}).get("capabilities", {}).get("execution", {}).get("nonce") == nonce,
             "Actual native result execution nonce missing/mismatched")
    _require(isinstance(execution.get("deviceUserId"), str) and
             re.fullmatch(r"\d+", execution["deviceUserId"]), "Actual device user identity unavailable")
    artifact = execution.get("rowArtifact", {})
    marker = artifact.get("processLogMarker", {})
    _require(all(marker.get(key) == native.get(key) == execution.get(key)
                 for key in ("taskId", "role", "caseId")) and marker.get("executionNonce") == nonce,
             "Nonce-bound process result marker identity mismatch")
    _require(isinstance(marker.get("name"), str) and
             re.fullmatch(r"ltb-native-result_\d+\.json", marker["name"]) and
             isinstance(artifact.get("remote"), str) and artifact["remote"].endswith("/" + marker["name"]),
             "Native row artifact is not the process marker's result file")
    _require(type(artifact.get("bytes")) is int and artifact["bytes"] > 0 and
             marker.get("bytes") == artifact["bytes"] and type(marker.get("characters")) is int and
             0 < marker["characters"] <= artifact["bytes"] and
             isinstance(artifact.get("sha256"), str) and re.fullmatch(r"[a-f0-9]{64}", artifact["sha256"]),
             "Native row artifact byte/hash/character receipt unavailable")


def verify_native_prefix(native, execution):
    _require(native.get("taskId") == "10_media_upload_quality" and native.get("caseId") == CASE and
             native.get("role") in {"base", "agent"}, "Wrong Task10 prepared-prefix execution identity")
    _require(execution.get("taskId") == native["taskId"] and execution.get("role") == native["role"] and
             execution.get("caseId") == CASE and execution.get("transportCompleted") is True and
             execution.get("candidateAbsentBeforeInstall") is True and execution.get("productionUnchanged") is True and
             execution.get("cleanup", {}).get("ownedAppUninstalled") is True,
             "Missing real cold execution/cleanup positive control")
    _verify_transport(native, execution)
    points = {point.get("label"): point for point in native["checkpoints"]}
    _require(len(points) == len(native["checkpoints"]) and
             "prefix:caption-and-quality" in points and "after:event" in points, "Actual UI operation-prefix snapshots missing/duplicated")
    before_frame, before = _state(points["prefix:caption-and-quality"])
    after_frame, after = _state(points["after:event"])
    window = before_frame.get("windowId")
    _require(type(window) is int and window > 0 and type(after_frame.get("windowId")) is int and
             window == after_frame["windowId"] and
             before_frame.get("routeName") == after_frame.get("routeName") == "pages/Index", "Original page/window changed")
    view = before["view"]
    _require(view.get("caption") == "demo" and view.get("plan", {}).get("selectedPreset") == "standard" and
             view.get("previewVisible") is True, "Reachable caption/quality/preview given not established")
    for key in ("caption", "send"):
        control = before_frame["controls"][key]
        _require(control.get("present") is True and control.get("visible") is True and control.get("enabled") is True,
                 "Actual common input/send control not available")
    calls = after["calls"]
    inputs = [call for call in calls if call.get("owner") == "native_fs" and call.get("method") == "original_input_established"]
    _require(len(inputs) == 1 and inputs[0].get("exists") is True and inputs[0].get("bytes") == 50000000,
             "Real external source file positive control missing")
    source_path = inputs[0]["path"]
    sends = [call for call in calls if call.get("owner") == "gateway" and call.get("method") == "sendAsync"]
    _require(len(sends) == 1, "Exactly one original send is required")
    request = sends[0]["request"]
    attachments = request.get("attachments")
    _require(isinstance(attachments, list) and len(attachments) == 1, "Original picked input unavailable")
    _require(request.get("caption") == "demo" and request.get("quality", {}).get("videoQuality") == "standard" and
             attachments[0].get("uri") == source_path, "Original send input differs from actual prefix")
    stages = [call for call in calls if call.get("owner") == "gateway" and call.get("method") == "actual_stage_before_async_completion"]
    _require(len(stages) == 1 and stages[0].get("files"), "Actual production staging boundary not observed")
    for item in stages[0]["files"]:
        _require(item.get("available") is True and item.get("exists") is False and
                 item.get("path", "").startswith(source_path + "."),
                 "Absence at the gateway-listed prepared upload path is unproven or filesystem/environment unavailable")
    completed = [call for call in calls if call.get("owner") == "gateway" and call.get("method") == "sendAsync_completed"]
    _require(len(completed) == 1 and completed[0].get("result", {}).get("succeeded") is False and
             after["view"].get("sendState") == "failure", "Controlled external send failure did not complete")
    ui = [call.get("observation", {}) for call in native.get("calls", []) if call.get("module") == "ArkUI"]
    _require(any(call.get("method") == "Task11.uiAction" and call.get("kind") == "input" and call.get("value") == "demo" and
                 call.get("target", {}).get("id") == before_frame["controls"]["caption"]["id"] for call in ui) and
             any(call.get("method") == "Task11.uiAction" and call.get("kind") == "click" and
                 call.get("target", {}).get("id") == before_frame["controls"]["send"]["id"] and
                 call.get("target", {}).get("visible") is True and call.get("target", {}).get("enabled") is True for call in ui),
             "Real Driver input/click receipts missing")
    _require(after["view"].get("previewVisible") is True and after["view"].get("caption") == "demo" and
             after["view"].get("plan", {}).get("selectedPreset") == "standard", "Actual post-prefix lifecycle evidence changed")
    return {"source": inputs[0], "request": request, "staging": stages[0], "completion": completed[0],
            "canonicalPreparedGivenReached": False, "originalAssertionsEvaluated": False,
            "absenceScope": "only_prepared_upload_paths_actually_listed_by_original_gateway"}


def _object_sha(contract):
    return hashlib.sha256(json.dumps(contract, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def bind(row, report, contract, native_path, execution_path, retained):
    native = json.loads(Path(native_path).read_text())
    execution = json.loads(Path(execution_path).read_text())
    verify_native_prefix(native, execution)
    retained = Path(retained)
    retained.mkdir(parents=True, exist_ok=True)
    target = retained / "actual-prepared-prefix.native.json"
    target.write_bytes(Path(native_path).read_bytes())
    # The complete native payload remains once; the transport summary drops its duplicate rows.
    summary = {key: value for key, value in execution.items() if key not in {"rows", "commands"}}
    summary["originalExecution"] = evidence.record(Path(execution_path))
    build_path = Path(execution["buildReport"]["path"])
    build_copy = retained / "actual-prepared-prefix.build.json"
    build_copy.write_bytes(build_path.read_bytes())
    execution_copy = retained / "actual-prepared-prefix.execution-summary.json"
    execution_copy.write_text(json.dumps(summary, indent=2) + "\n")
    inventory = report["provenance"]["sourceInventory"]["sha256"]
    source = report["provenance"]["productionSourceRoot"]
    native_record = evidence.record(target)
    identity = hashlib.sha256((source + inventory + native_record["sha256"] + row["role"] + CASE).encode()).hexdigest()
    return {**copy.deepcopy(row), "status": "fail", "observed": None, "invariantChecks": [],
            "transitionExecuted": False, "failureKind": "semantic_missing_gateway_listed_prepared_paths_after_real_operation_prefix",
            "reason": "Actual reachable preview and one original send executed; the prepared upload paths actually listed by the original gateway had no files, so the canonical prepared given could not be established. This does not prove all possible prepared media absent; original final-only assertions remain unevaluated.",
            "entryFailureEvidence": {"policyId": POLICY, "positiveControlCompleted": True, "evidenceId": identity,
                "role": row["role"], "sourceRoot": source, "sourceInventorySha256": inventory,
                "canonicalObjectSha256": _object_sha(contract), "policy": evidence.record(Path(__file__)),
                "nativeRow": native_record, "executionSummary": evidence.record(execution_copy),
                "build": evidence.record(build_copy)}}


def validate_entry_failure(row, report, usedids, *, contract):
    proof = row.get("entryFailureEvidence", {})
    _require(proof.get("policyId") == POLICY and report.get("taskId") == "10_media_upload_quality" and
             report.get("platform") == "arkts" and row.get("caseId") == CASE,
             "Unsupported Task10 prepared-prefix policy/task/platform/case")
    _require(report.get("role") == row.get("role") == proof.get("role") and row["role"] in {"base", "agent"}, "Prefix role mismatch")
    spec = next((spec for spec in contract["cases"] if spec["caseId"] == CASE), None)
    _require(spec and spec["traceDigest"] == row["traceDigest"] and
             spec.get("setup", {}).get("requiredBeforeEvent", {}).get("preparedMedia") is True and
             proof.get("canonicalObjectSha256") == _object_sha(contract), "Prepared-prefix canonical binding changed")
    _require(row.get("status") == "fail" and row.get("transitionExecuted") is False and
             row.get("observed") is None and row.get("invariantChecks") == [] and proof.get("positiveControlCompleted") is True,
             "Unreached canonical states or assertions must not be fabricated")
    evidence.read_record(proof["policy"])
    _require(proof["policy"] == evidence.record(Path(__file__)), "Audited policy version changed")
    _require(proof.get("sourceRoot") == report["provenance"]["productionSourceRoot"] and
             proof.get("sourceInventorySha256") == report["provenance"]["sourceInventory"]["sha256"], "Immutable source binding changed")
    native_bytes = evidence.read_record(proof["nativeRow"])
    native = json.loads(native_bytes)
    execution = json.loads(evidence.read_record(proof["executionSummary"]))
    build = json.loads(evidence.read_record(proof["build"]))
    _verify_transport(native, execution)
    _require(execution["buildReport"]["sha256"] == proof["build"]["sha256"] and
             build.get("source") == proof["sourceRoot"] and build.get("role") == row["role"] and
             build.get("task10SourceInventory", {}).get("sha256") == proof["sourceInventorySha256"] and
             build.get("productionUnchanged") is True and build.get("copiedProductionUnchanged") is True and
             build.get("runtimeCompile", {}).get("passed") is True,
             "Compiled/executed immutable source inventory differs from report")
    compiled = {(item["path"], item["sha256"]) for item in build["production"]}
    reported = {(item["path"], item["sha256"]) for item in report["provenance"]["productionSources"]}
    _require(compiled and compiled.issubset(reported) and all(
        (item["path"], item["sha256"]) in compiled for item in native["productionSources"]),
        "Actual executed production sources differ from compiled/reported source hashes")
    _require(native.get("role") == row["role"] and native.get("traceDigest") == spec["traceDigest"], "Actual native role/digest differs")
    artifact = execution.get("rowArtifact", {})
    _require(artifact.get("sha256") == proof["nativeRow"]["sha256"] and artifact.get("bytes") == proof["nativeRow"]["bytes"],
             "Native row does not match the actual device artifact")
    _require(build.get("supportsExecutionNonce") is True and
             artifact["processLogMarker"]["characters"] == len(native_bytes.decode().encode("utf-16-le")) // 2 and
             artifact["remote"] == f'/data/app/el2/{execution["deviceUserId"]}/base/{build["bundleName"]}/cache/{artifact["processLogMarker"]["name"]}',
             "Actual row artifact character count or compiled bundle/device path differs")
    verify_native_prefix(native, execution)
    expected_id = hashlib.sha256((proof["sourceRoot"] + proof["sourceInventorySha256"] + proof["nativeRow"]["sha256"] + row["role"] + CASE).encode()).hexdigest()
    _require(proof.get("evidenceId") == expected_id and expected_id not in usedids, "Prepared-prefix evidence missing/reused")
    usedids.add(expected_id)
