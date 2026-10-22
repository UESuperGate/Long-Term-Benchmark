"""Task15 exact-pole verifier, independent of frozen Task14 Android verification."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import task14_15_formal_core as core
import task14_15_android_entry_evidence as artifacts
import task14_15_formal_verify as old_android
import task14_15_arkts_formal_verify as old_arkts
import task15_capability_probe


def verify_android(path, contract):
    report = core.load(path)
    if all(row.get("entryFailureEvidence") for row in report["semantic"]["cases"]):
        return old_android.verify_report(path, contract)
    provenance = report["provenance"]
    candidate = Path(provenance["candidateSource"])
    core.validate_report(report, task_id=contract["taskId"], platform="android", source=candidate,
                         contract=contract, expected=None)
    root = Path(provenance["retainedEvidence"]["path"])
    for item in provenance["retainedEvidence"]["files"]:
        artifacts.bound({**item, "path": str(root / item["path"])})
    manifest = {item["path"]: item for item in provenance["productionSources"]}
    for name, item in manifest.items():
        data = artifacts.bound(provenance["productionSourceSnapshots"][name])
        artifacts.require(len(data) == item["bytes"] and
            provenance["productionSourceSnapshots"][name]["sha256"] == item["sha256"], "Production snapshot mismatch")
    poles = {}
    emitted = {}
    inputs = {}
    for pole in ("preferences", "modal", "domain"):
        raw = core.load(root / (pole + ".json"))
        artifacts.require(raw["provenance"]["source"] == str(candidate) and
            raw["provenance"]["candidateRootSha256"] == provenance["candidateRootSha256"], "Wrong runtime candidate")
        artifacts.require(raw["runtimeCompile"]["status"] == "passed", "Runtime pole did not compile")
        for item in raw["provenance"]["productionSources"]:
            artifacts.require(manifest.get(item["path"]) == item, "Executed production source omitted/replaced")
            inputs[item["path"]] = item
        log = artifacts.bound(raw.get("log") or raw["diagnostics"]["log"]).decode()
        emitted_rows = [json.loads(line[len("RUNTIME_RESULT "):]) for line in log.splitlines()
                        if line.startswith("RUNTIME_RESULT ")]
        emitted[pole] = {item["key"]: item for item in emitted_rows}
        artifacts.require(len(emitted[pole]) == len(emitted_rows), "Duplicate JUnit runtime observation")
        rows = raw.get("observations") or raw["semantic"]["cases"]
        poles[pole] = {row["key"]: row for row in rows}
    artifacts.require(inputs == manifest, "Manifest includes unexecuted production sources")
    for row in report["semantic"]["cases"]:
        key = row["key"]
        pole = "preferences" if key == "capability_gates_entry" else "modal" if key in {
            "password_enables_submit", "failure_preserves_form", "confirm_sends_payload"} else "domain"
        raw = poles[pole]["loading_modal_blocks_input" if key == "confirm_sends_payload" else key]
        actual = emitted[pole][raw["key"]]
        artifacts.require(all(raw[field] == actual[field] for field in (
            "status", "observed", "checkpoints", "invariantChecks")), "Retained row differs from actual JUnit output")
        artifacts.require(row["status"] == raw["status"] and row["checkpoints"] == raw["checkpoints"],
                          "Formal verdict/checkpoints differ from executed UI/domain observation")
        if key != "confirm_sends_payload":
            artifacts.require(row["observed"] == raw["observed"] and row["invariantChecks"] == raw["invariantChecks"],
                              "Runtime state/invariants were rewritten")
        else:
            points = {point["name"]: point["state"] for point in raw["checkpoints"]}
            artifacts.require(row["observed"] == {"action": "loading", "effect": "deactivate_account",
                "payload": points["confirmation_control_activated"]["requests"][0]}, "Modal payload mismatch")
            before = points["loading_modal_before_global_input"]
            after = points["loading_modal_after_global_input"]
            artifacts.require(raw["observed"]["formInputBlocked"] is True and raw["observed"]["requestCount"] == 1 and
                all(before[key] == after[key] for key in ("password", "eraseData", "action", "requests")),
                "Original loading modal did not block actual global input")
    core.validate_public_report(report, contract)
    return {"passed": True, "cases": len(report["semantic"]["cases"]), "publicValidatorPassed": True,
            "runtimePoles": sorted(poles), "reportSha256": core.sha256(path)}


def verify_arkts(path, contract):
    import task14_15_arkts_artifacts as artifacts
    report = core.load(path)
    result = old_arkts.verify_report(path, contract)
    if all(row.get("entryFailureEvidence") for row in report["semantic"]["cases"]):
        return result
    row = next(row for row in report["semantic"]["cases"] if row["key"] == "capability_gates_entry")
    record = row["invariantChecks"][0]["evidence"]["unsupportedCapability"]
    control = json.loads(artifacts.bound(record, inventory=report["provenance"]["retainedEvidence"]))
    raw = json.loads(artifacts.bound(control["observation"]))
    entry_binding = control.get("entryBinding")
    if entry_binding is not None:
        source = entry_binding["presenterSource"]
        snapshot = report["provenance"]["productionSourceSnapshots"][source]
        artifacts.bound(snapshot)
        source_root = Path(snapshot["path"])
        for _ in Path(source).parts:
            source_root = source_root.parent
        import time
        actual_binding = task15_capability_probe.describe_entry(source_root, time.monotonic() + 30)
        artifacts.require(actual_binding == entry_binding, "Unsupported capability entry API differs from executed production source")
    actual_passed = task15_capability_probe.validate_observation(raw,
        entry_binding["entryId"] if entry_binding is not None else "deactivate_account_entry")
    artifacts.require(row["invariantChecks"][0]["status"] == ("pass" if actual_passed else "fail"),
                      "Unsupported capability invariant contradicts the authenticated production UI")
    artifacts.require(control["source"] == report["provenance"]["candidateSource"] and
        control["candidateRootSha256"] == report["provenance"]["candidateRootSha256"] and
        control["ownedAppUninstalled"] is True and control["productionUnchanged"] is True,
        "Unsupported capability source/cleanup identity mismatch")
    for command in control["commands"]:
        artifacts.require(command["exitCode"] == 0, "Capability environment error was scored")
        artifacts.bound(command["log"])
    production = {item["path"]: item for item in report["provenance"]["productionSources"]}
    for item in control["build"]["production"]:
        artifacts.require(production[item["path"]]["sha256"] == item["sha256"], "Capability executed another source")
    for fixture in control["build"]["fixtures"]:
        artifacts.bound(fixture, inventory=report["provenance"]["retainedEvidence"])
    result["authenticatedUnsupportedCapabilityVerified"] = True
    return result


def verify_report(path, contract):
    if contract["taskId"] != "15_account_deactivation":
        raise ValueError("Task15 verifier received another task")
    return (verify_android if core.load(path)["platform"] == "android" else verify_arkts)(path, contract)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("--contract", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(verify_report(args.report, core.load(args.contract)), indent=2))
