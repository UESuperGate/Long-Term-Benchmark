#!/usr/bin/env python3
import argparse
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "experiment_results/runtime_transition_20261020/contract_audit/revision_4_task10_v2/after/transitions.json"
ACTIVE = ROOT / "benchmark_tasks/10_media_upload_quality/transitions.json"
STAGING = ROOT / "experiment_results/runtime_transition_20261020/contract_audit/revision_4_task10_v2/manifest.json"
BUILD = ROOT / "experiment_results/runtime_transition_20261020/task10_repair/arkts-final-build-v6/device-build-report.json"
HAP = ROOT / "experiment_results/runtime_transition_20261020/task10_repair/arkts-final-build-v6/entry-default-unsigned.hap"
CASE_ID = "mq_state_009_failure_cancel_retry"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def checked_file(item, label):
    path = (ROOT / item["path"]).resolve()
    require(path == ROOT or ROOT in path.parents, f"{label} escapes repository")
    require(path.is_file(), f"{label} missing")
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


def visible(nodes, node_id):
    return [node for node in nodes if node.get("id") == node_id and node.get("visible") == "true"]


def one(nodes, node_id):
    matches = visible(nodes, node_id)
    require(len(matches) == 1, f"expected one visible {node_id}, found {len(matches)}")
    return matches[0]


def command(report, prefix, contains=None):
    matches = []
    for item in report["diagnostics"]["commands"]:
        args = item["args"]
        if args[:len(prefix)] == prefix and (contains is None or any(contains in value for value in args)):
            matches.append(item)
    require(len(matches) == 1, f"expected one command {prefix} {contains or ''}, found {len(matches)}")
    require(matches[0]["exitCode"] == 0, f"command failed: {matches[0]['args']}")
    log = checked_file(matches[0]["log"], "command log")
    return matches[0], log.read_text()


def verify(report_path, output=None):
    report_path = Path(report_path).resolve()
    report = json.loads(report_path.read_text())
    contract = json.loads(CONTRACT.read_text())
    staging = json.loads(STAGING.read_text())
    build = json.loads(BUILD.read_text())
    spec = next(item for item in contract["cases"] if item["caseId"] == CASE_ID)

    require(report["taskId"] == "10_media_upload_quality", "wrong task")
    require(report["platform"] == "arkts" and report["role"] == "final", "wrong platform or role")
    require(report["caseId"] == CASE_ID and spec["key"] == "background_failure_cleanup", "wrong case revision")
    require(report["runtime"] == "openharmony_api23_device_uitest_and_sandbox_fs", "wrong runtime")
    require(report["observationMode"] == "runtime_state_transition", "not a runtime transition")
    require(report["status"] == "passed", "report did not pass")
    require(report["compile"]["passed"] is True and report["compile"]["scope"] == "application_hap", "app HAP compile missing")
    checked_file(report["compile"]["build"], "build report")
    checked_file(report["compile"]["hap"], "HAP")
    require(report["compile"]["build"]["sha256"] == digest(BUILD), "wrong build report")
    require(report["compile"]["hap"]["sha256"] == digest(HAP), "wrong HAP")
    require(build["status"] == "built_not_executed" and build["runtimeCompile"]["passed"] is True,
            "build did not produce application and test HAPs")
    require(build["productionUnchanged"] is True and build["copiedProductionUnchanged"] is True and
            build["temporaryProjectRemoved"] is True, "build provenance/cleanup invalid")
    source = Path(build["source"]).resolve()
    require(source == ROOT / "final_dev_nodes/10_media_upload_quality_final_25_08_3", "wrong production source")
    for item in build["production"]:
        production = source / item["path"]
        require(production.is_file() and digest(production) == item["sha256"], f"production changed: {item['path']}")

    require(report["provenance"]["activeCanonicalModified"] is False, "active canonical marked modified")
    checked_file(report["provenance"]["contract"], "staged contract")
    checked_file(report["provenance"]["runner"], "device runner")
    require(report["provenance"]["contract"]["sha256"] == digest(CONTRACT), "wrong staged contract")
    require(staging["activeCanonicalModified"] is False, "staging modified active canonical")
    require(staging["activeCanonicalBefore"] == staging["activeCanonicalAfter"], "active before/after differs")
    require(staging["activeCanonicalAfter"]["sha256"] == digest(ACTIVE), "active canonical changed since staging")

    semantic = report["semantic"]
    require((semantic["total"], semantic["passed"], semantic["failed"], semantic["notScored"]) == (1, 1, 0, 0),
            "semantic totals are not 1/1")
    require(len(semantic["cases"]) == 1, "expected one case row")
    row = semantic["cases"][0]
    require(row["caseId"] == CASE_ID and row["traceDigest"] == spec["traceDigest"], "case identity/digest mismatch")
    require(row["status"] == "pass" and row["transitionExecuted"] is True, "transition not passed")
    require(row["observed"] == spec["expected"], "observed state differs from strict expected state")
    require(row["invariantChecks"] == [{"text": spec["invariants"][0], "passed": True}], "invariant proof mismatch")
    checkpoints = {item["name"]: item for item in row["checkpoints"]}
    require(set(checkpoints) == {"prepared_before_event", "post_event"}, "checkpoint set mismatch")
    require(checkpoints["prepared_before_event"]["state"] == spec["setup"]["requiredBeforeEvent"], "setup prefix mismatch")
    require(checkpoints["prepared_before_event"]["artifact"]["payload"] == {
        "preset": "standard", "compressImages": True, "videoCompressionPreset": "standard"
    }, "prepared artifact payload mismatch")
    require(checkpoints["post_event"]["state"] == spec["expected"], "post-event checkpoint mismatch")

    before_path = checked_file(checkpoints["prepared_before_event"]["layout"], "before layout")
    after_path = checked_file(checkpoints["post_event"]["layout"], "after layout")
    require(before_path != after_path, "layouts reused")
    before = flatten_layout(json.loads(before_path.read_text()))
    after = flatten_layout(json.loads(after_path.read_text()))
    require(one(before, "media_caption").get("text") == "demo", "rendered setup caption mismatch")
    require(one(before, "video_quality_selector").get("text") == "Quality: standard", "rendered setup preset mismatch")
    one(before, "media_send")
    require(not visible(after, "media_caption") and not visible(after, "media_send"), "preview controls survived")
    require(one(after, "media_background_result").get("text") == "The preview closed. Background upload failed.",
            "rendered failure result mismatch")
    require(one(after, "media_cleanup_status").get("text") == "Temporary media removed", "rendered cleanup result mismatch")
    require(one(after, "media_background_effect").get("text") == "Attempts: 1; preset: standard; caption: demo",
            "rendered effect mismatch")

    remote = checkpoints["post_event"]["artifactPath"]
    _, prepared_log = command(report, ["shell", "cat"], remote)
    require(json.loads(prepared_log) == checkpoints["prepared_before_event"]["artifact"]["payload"],
            "device prepared-file content mismatch")
    _, deleted_log = command(report, ["shell", "ls", "-l"], remote)
    require("No such file or directory" in deleted_log, "device did not prove artifact deletion")
    command(report, ["install", "-r"])
    command(report, ["shell", "aa", "start"])
    command(report, ["uninstall", "com.qingyu.elementx.mediaquality.final"])
    for item in report["diagnostics"]["commands"]:
        checked_file(item["log"], "command log")
    require(report["diagnostics"]["adapter"] == "ready" and report["diagnostics"]["transport"] == "ready",
            "runtime diagnostics not ready")
    require(report["diagnostics"]["cleanup"]["ownedAppUninstalled"] is True and
            report["diagnostics"]["cleanup"]["remoteLayoutsRemoved"] >= 2 and
            report["diagnostics"]["cleanup"]["deviceLockRemoved"] is True, "cleanup incomplete")

    result = {"schemaVersion": 1, "validated": True, "promotableScope": "task10_arkts_final_case009_only",
              "report": str(report_path.relative_to(ROOT)), "reportSha256": digest(report_path),
              "semantic": {"total": 1, "passed": 1, "failed": 0, "notScored": 0},
              "verifiedProductionFiles": len(build["production"]),
              "verifiedCommandLogs": len(report["diagnostics"]["commands"]), "activeCanonicalModified": False}
    if output:
        Path(output).write_text(json.dumps(result, indent=2) + "\n")
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("report")
    parser.add_argument("--output")
    args = parser.parse_args()
    print(json.dumps(verify(args.report, args.output), indent=2))


if __name__ == "__main__":
    main()
