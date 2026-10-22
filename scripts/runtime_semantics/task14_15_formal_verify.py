"""Verify retained Task14/15 Android runtime evidence after temporary-source cleanup."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import task14_15_formal_core as core
import task14_15_android_entry_evidence as entry


def verify_report(path: Path, contract: dict, *, require_public: bool = True) -> dict:
    report = core.load(path)
    core.validate_report(report, task_id=contract["taskId"], platform="android",
                         source=Path(report["provenance"]["candidateSource"]), contract=contract,
                         expected=None)
    provenance = report["provenance"]
    retained = provenance["retainedEvidence"]
    root = Path(retained["path"])
    for item in retained["files"]:
        entry.bound({**item, "path": str(root / item["path"])})
    source_manifest = {item["path"]: item for item in provenance["productionSources"]}
    for name, item in source_manifest.items():
        data = entry.bound(provenance["productionSourceSnapshots"][name])
        entry.require(len(data) == item["bytes"] and entry.digest(
            provenance["productionSourceSnapshots"][name]["path"]) == item["sha256"],
            "Production snapshot differs from executed source")
    raw_sources = {}
    raw_reports = {}
    for name in ("entry-probe", "final-entry", "rendered", "preferences", "modal", "domain"):
        artifact_path = root / f"{name}.json"
        if not artifact_path.is_file():
            continue
        raw = core.load(artifact_path)
        raw_provenance = raw["provenance"]
        entry.require(raw_provenance.get("source") == provenance["candidateSource"] and
                      raw_provenance.get("candidateRootSha256") == provenance["candidateRootSha256"],
                      "Runtime pole belongs to a different candidate")
        entry.require(raw.get("runtimeCompile", {}).get("status") == "passed", "Runtime pole did not compile")
        for item in raw_provenance["productionSources"]:
            entry.require(source_manifest.get(item["path"]) == item, "Runtime source omitted or replaced")
            raw_sources[item["path"]] = item
        log = raw.get("log") or raw.get("diagnostics", {}).get("log")
        entry.require(log is not None, "Runtime pole log missing")
        entry.bound(log)
        raw_reports[name] = raw
    entry.require(raw_sources == source_manifest, "Production metadata includes unexecuted sources")
    cases = report["semantic"]["cases"]
    for row in cases:
        if row.get("entryFailureEvidence"):
            continue
        key = row["key"]
        if contract["taskId"].startswith("14"):
            pole = ("final-entry" if key == "entry_opens_address_flow" else
                    "rendered" if key in {"invalid_after_continue", "not_found_recovers", "timeout_recovers"}
                    else "domain")
        else:
            pole = ("preferences" if key == "capability_gates_entry" else
                    "modal" if key == "confirm_sends_payload" else "domain")
        raw_report = raw_reports[pole]
        raw_rows = raw_report.get("observations") or raw_report.get("semantic", {}).get("cases", [])
        raw_key = "loading_modal_blocks_input" if pole == "modal" else key
        matches = [raw for raw in raw_rows if raw["key"] == raw_key]
        entry.require(len(matches) == 1, "Missing or duplicate raw pole observation")
        raw = matches[0]
        entry.require(row["status"] == raw["status"] and row["checkpoints"] == raw["checkpoints"],
                      "Scored verdict or checkpoints differ from production runtime")
        if pole != "modal":
            entry.require(row["observed"] == raw["observed"] and
                          row["invariantChecks"] == raw["invariantChecks"], "Production state was rewritten")
        else:
            points = {point["name"]: point["state"] for point in raw["checkpoints"]}
            before = points["loading_modal_before_global_input"]
            after = points["loading_modal_after_global_input"]
            requests = points["confirmation_control_activated"]["requests"]
            entry.require(row["observed"] == {"action": "loading", "effect": "deactivate_account",
                                             "payload": requests[0]}, "Modal payload differs from runtime")
            entry.require(raw["observed"]["formInputBlocked"] is True and
                          raw["observed"]["requestCount"] == 1 and before == after,
                          "Modal interaction or request-count assertion failed")
    if require_public:
        core.validate_public_report(report, contract)
    return {"passed": True, "cases": len(cases), "productionSources": len(source_manifest),
            "runtimePoles": sorted(raw_reports), "publicValidator": require_public,
            "reportSha256": core.sha256(path)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("--contract", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(verify_report(args.report, core.load(args.contract)), indent=2))


if __name__ == "__main__":
    main()
