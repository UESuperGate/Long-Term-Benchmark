"""Independently verify the retained exact Task14/15 ArkTS runtime poles."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess

try:
    from . import task14_15_formal_core as core
    from . import task14_15_arkts_artifacts as artifacts
except ImportError:
    import task14_15_formal_core as core
    import task14_15_arkts_artifacts as artifacts


def same_runtime_row(row, raw):
    for field in ("status", "observed", "checkpoints", "invariantChecks"):
        artifacts.require(row.get(field) == raw.get(field),
                          f"Formal {field} differs from its executed runtime pole")


def runtime_row(report, case_id):
    rows = [item for item in report["semantic"]["cases"] if item.get("caseId") == case_id]
    artifacts.require(len(rows) == 1, "Missing or duplicate executed canonical observation")
    return rows[0]


def bound_source(raw, candidate):
    provenance = raw.get("provenance", {})
    value = (provenance.get("candidateSource") or provenance.get("original") or raw.get("target"))
    artifacts.require(isinstance(value, str) and Path(value).resolve() == candidate,
                      "Executed runtime pole belongs to another source")


def task14_rows(root, report, candidate):
    clock = core.load(root / "host-virtual-clock.json")
    arkvm = core.load(root / "arkvm-production/reports/arkts_14_join_room_by_address_agent.json")
    bound_source(clock, candidate)
    bound_source(arkvm, candidate)
    artifacts.require(arkvm["runtimeCompile"]["passed"] is True, "ArkVM packaging did not pass")
    for row in report["semantic"]["cases"]:
        pole = row["runtime"]
        if pole == "host_transpiled_virtual_clock_production":
            raw = runtime_row(clock, row["caseId"])
        elif pole == "native_previewer_arkvm_production_module":
            raw = runtime_row(arkvm, row["caseId"])
        else:
            matches = []
            for path in root.glob(f"device-original-ui-{row['caseId']}-attempt-*.json"):
                device = core.load(path)
                if (device.get("runtimeCompile", {}).get("passed") is True and
                        device.get("diagnostics", {}).get("transport") == "transport_completed"):
                    item = runtime_row(device, row["caseId"])
                    if item["status"] in {"pass", "fail"}:
                        bound_source(device, candidate)
                        matches.append(item)
            artifacts.require(len(matches) == 1, "Device row has no unique completed runtime attempt")
            raw = matches[0]
        same_runtime_row(row, raw)


def native_observations(evidence, provider):
    login, first, pending, failure, retry = (
        evidence[name] for name in ("login", "firstSubmit", "pending", "failure", "retry"))
    requests = [item for item in provider["requests"] if item.get("kind") == "deactivation"]
    color = login.get("entryInspector", {}).get("$attrs", {}).get("foregroundColor")
    return {
        "ad_state_001_capability_gates_entry": {
            "deactivateEntryVisible": login.get("entryVisible"),
            "entryStyle": "destructive" if color == "#FFB42318" else color},
        "ad_state_005_first_submit_confirms": {
            "action": first.get("action"), "requestCount": first.get("logicalServiceCalls"),
            "confirmationVisible": first.get("confirmationVisible")},
        "ad_state_006_confirm_sends_payload": {
            "action": pending.get("action"), "effect": "deactivate_account" if requests else None,
            "payload": {"password": pending.get("passwordAfterInputAttempt"),
                        "eraseData": requests[0].get("body", {}).get("erase") if requests else None}},
        "ad_state_008_failure_preserves_form": {
            "action": failure.get("action"), "password": failure.get("password"),
            "eraseData": failure.get("eraseData"), "retryEnabled": failure.get("retryVisible")},
        "ad_state_009_retry_bypasses_confirmation": {
            "action": retry.get("action"), "requestCount": retry.get("logicalServiceCalls"),
            "confirmationVisible": retry.get("confirmationVisible")},
    }


def task15_rows(root, report, candidate):
    host = core.load(root / "host-production-presenter.json")
    bound_source(host, candidate)
    execution = root / "native-e2e/execution"
    evidence = core.load(execution / "native-e2e-evidence.json")
    provider = core.load(execution / "provider-transcript.json")
    run = core.load(root / "native-e2e/run.json")
    artifacts.require(run.get("status") == "passed", "Native HTTPS runtime did not complete")
    production = {item["path"]: item for item in report["provenance"]["productionSources"]}
    for item in run["sourceHashes"]:
        artifacts.require(production.get(item["path"], {}).get("sha256") == item["sha256"],
                          "HTTPS production input differs from the candidate manifest")
    verifier = core.ROOT / "state_tests/runtime/arkts/native/Task15NativeE2E.verifier.cjs"
    javascript = """const fs=require('node:fs');
const {verifyTask15NativeE2E}=require(process.argv[1]);
const [evidence,provider,run]=process.argv.slice(2).map(p=>JSON.parse(fs.readFileSync(p,'utf8')));
process.stdout.write(JSON.stringify(verifyTask15NativeE2E({evidence,provider,run})));"""
    process = subprocess.run([
        "/Applications/DevEco-Studio.app/Contents/tools/node/bin/node", "-e", javascript,
        str(verifier), str(execution / "native-e2e-evidence.json"),
        str(execution / "provider-transcript.json"), str(root / "native-e2e/run.json")],
        capture_output=True, text=True, timeout=30, check=True)
    verified = json.loads(process.stdout)
    artifacts.require((verified["passed"], verified["total"]) == (15, 15),
                      "Independent HTTPS verifier rejected the retained runtime")
    observed = native_observations(evidence, provider)
    for row in report["semantic"]["cases"]:
        if row["runtime"] == "host_transpiled_current_production_presenter":
            same_runtime_row(row, runtime_row(host, row["caseId"]))
        else:
            artifacts.require(row["observed"] == observed[row["caseId"]],
                              "Formal HTTPS state differs from the device/provider observations")


def verify_report(path: Path, contract: dict) -> dict:
    report = core.load(path)
    candidate = Path(report["provenance"]["candidateSource"]).resolve()
    core.validate_report(report, task_id=contract["taskId"], platform="arkts", source=candidate,
                         contract=contract, expected=None)
    retained = report["provenance"]["retainedEvidence"]
    root = Path(retained["path"])
    for item in retained["files"]:
        artifacts.bound({**item, "path": str(root / item["path"])})
    production = report["provenance"]["productionSources"]
    for item in production:
        snapshot = report["provenance"]["productionSourceSnapshots"][item["path"]]
        data = artifacts.bound(snapshot)
        artifacts.require(len(data) == item["bytes"] and snapshot["sha256"] == item["sha256"],
                          "Retained source differs from the executed production input")
    entries = [row.get("entryFailureEvidence") is not None for row in report["semantic"]["cases"]]
    if not all(entries):
        artifacts.require(not any(entries), "Unexpected mixed missing-entry/multipole composition")
        if contract["taskId"] == "14_join_room_by_address":
            task14_rows(root, report, candidate)
        else:
            task15_rows(root, report, candidate)
    core.validate_public_report(report, contract)
    return {"passed": True, "publicValidatorPassed": True,
            "cases": len(report["semantic"]["cases"]), "productionSources": len(production),
            "reportSha256": core.sha256(path)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("--contract", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(verify_report(args.report, core.load(args.contract)), indent=2))


if __name__ == "__main__":
    main()
