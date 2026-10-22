#!/usr/bin/env python3
"""Independent verifier for the staged Task16 ArkTS revision-5 device run."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


CONTRACT_SHA = "1efc94614a2fb8c0e6687dd1ae2da32549b5972d0ace5bd5a15ee7d1428e1735"
BINDING_SHA = "c24fc74e41b78e038e4b2109a2c3f75468d95c5bbb642c78f356b3952030b02d"
ACTIVE_CONTRACT_SHA = "c24cb42af839dd9d4d0b48862c5b53be853f5519b536199351e531dc72668746"
ACTIVE_BINDING_SHA = "40e979457b339cc530f10b5c073120cc6d94f387500141a331e5147f1d536894"
CASE006 = "ir_state_006_handle_failure_recovers"
CASE006_DIGEST = "7ecb1377a8e794fda7550e4a962942b6ffb14208118e07a45d10dcc043445909"
CASE006_SEQUENCE = ["uninitialized", "loading", "failure", "uninitialized", "loading"]
OBSERVATION_LEVEL = "openharmony_api23_native_candidate_ui_and_production_runtime"


class VerificationError(AssertionError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise VerificationError(message)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def iso_seconds(start: str, finish: str) -> float:
    return (datetime.fromisoformat(finish.replace("Z", "+00:00")) -
            datetime.fromisoformat(start.replace("Z", "+00:00"))).total_seconds()


def transition(row: dict[str, Any]) -> dict[str, Any]:
    evidence = row.get("evidence", [])
    require(len(evidence) == 1 and isinstance(evidence[0].get("nativePageTransition"), dict),
            f"{row.get('caseId')}: one native page transition is required")
    return evidence[0]["nativePageTransition"]


def control(frame: dict[str, Any], name: str) -> dict[str, Any]:
    matches = [item for item in frame.get("controls", []) if item.get("name") == name]
    require(len(matches) == 1, f"{name}: exactly one control observation is required")
    return matches[0]


def checkpoint(row: dict[str, Any], label: str) -> dict[str, Any]:
    matches = [item["state"] for item in row.get("checkpoints", []) if item.get("label") == label]
    require(len(matches) == 1, f"{row.get('caseId')}: checkpoint {label} is required exactly once")
    return matches[0]


def load_inputs(root: Path, base_build: Path, final_build: Path,
                base_device: Path, final_device: Path) -> dict[str, Any]:
    contract_path = root / "experiment_results/runtime_transition_20261020/contract_audit/revision_5_task16/after/transitions.json"
    binding_path = root / "experiment_results/runtime_transition_20261020/contract_audit/revision_5_task16/after/arkts-bindings.json"
    audit_path = root / "experiment_results/runtime_transition_20261020/contract_audit/revision_5_task16/manifest.json"
    paths = {
        "contract": contract_path,
        "binding": binding_path,
        "audit": audit_path,
        "base_build": base_build,
        "final_build": final_build,
        "base_device": base_device,
        "final_device": final_device,
    }
    documents = {name: read_json(path) for name, path in paths.items()}
    raw_rows: dict[str, dict[str, dict[str, Any]]] = {}
    for role in ("base", "final"):
        device_path = paths[f"{role}_device"]
        execution = documents[f"{role}_device"]
        raw_rows[role] = {}
        for item in execution.get("rows", []):
            row_path = device_path.parent / item["file"]
            require(row_path.is_file(), f"{role}/{item.get('caseId')}: raw row is missing")
            require(digest(row_path) == item.get("sha256"), f"{role}/{item.get('caseId')}: raw row digest changed")
            require(row_path.stat().st_size == item.get("bytes"), f"{role}/{item.get('caseId')}: raw row size changed")
            raw_rows[role][item["caseId"]] = read_json(row_path)
    return {"root": root, "paths": paths, "documents": documents, "raw_rows": raw_rows}


def verify_documents(inputs: dict[str, Any], check_workspace: bool = True) -> dict[str, Any]:
    root: Path = inputs["root"]
    paths: dict[str, Path] = inputs["paths"]
    docs = inputs["documents"]
    raw_rows = inputs["raw_rows"]
    contract, binding, audit = docs["contract"], docs["binding"], docs["audit"]

    if check_workspace:
        require(digest(paths["contract"]) == CONTRACT_SHA, "staged contract digest changed")
        require(digest(paths["binding"]) == BINDING_SHA, "staged binding digest changed")
        require(digest(root / "benchmark_tasks/16_identity_reset/transitions.json") == ACTIVE_CONTRACT_SHA,
                "active canonical contract changed")
        require(digest(root / "migrations/16_identity_reset/arkts/bindings.json") == ACTIVE_BINDING_SHA,
                "active ArkTS binding changed")

    require(contract.get("taskId") == "16_identity_reset" and contract.get("revision") == 5,
            "staged Task16 revision 5 contract required")
    cases = contract.get("cases", [])
    require(len(cases) == 10, "contract must contain ten cases")
    expected = {item["caseId"]: item["traceDigest"] for item in cases}
    require(len(expected) == 10 and all(re.fullmatch(r"[a-f0-9]{64}", value) for value in expected.values()),
            "contract case identities/digests are invalid")
    require(expected.get(CASE006) == CASE006_DIGEST, "case006 staged digest changed")
    contract_case006 = next(item for item in cases if item["caseId"] == CASE006)
    require(contract_case006.get("expected", {}).get("stateSequence") == CASE006_SEQUENCE,
            "case006 contract sequence changed")
    require({item["caseId"]: item["traceDigest"] for item in binding.get("cases", [])} == expected,
            "binding does not match all staged contract digests")
    require(audit.get("revision") == 5 and audit.get("activeCanonicalModified") is False,
            "contract audit does not preserve active canonical")
    require(audit.get("activeCanonicalBefore", {}).get("sha256") == ACTIVE_CONTRACT_SHA ==
            audit.get("activeCanonicalAfter", {}).get("sha256"), "active canonical audit hash mismatch")
    require(audit.get("bindingsSource", {}).get("sha256") == ACTIVE_BINDING_SHA,
            "active binding audit hash mismatch")

    fixtures: dict[str, dict[str, str]] = {}
    production_hashes: dict[str, dict[str, str]] = {}
    for role in ("base", "final"):
        build = docs[f"{role}_build"]
        require(build.get("taskId") == "16_identity_reset" and build.get("role") == role and
                build.get("revision") == 5 and build.get("status") == "built", f"{role}: invalid build identity/status")
        require(build.get("compile", {}).get("passed") is True and
                build.get("runtimeCompile", {}).get("passed") is True, f"{role}: app or ohosTest compile did not pass")
        require(build.get("bundleCaseCount") == 10 and build.get("productionCopiedUnchanged") is True and
                build.get("productionSourceUnchanged") is True and build.get("temporaryProjectRemoved") is True,
                f"{role}: build isolation/provenance incomplete")
        require(build.get("contract", {}).get("sha256") == CONTRACT_SHA and
                build.get("binding", {}).get("sha256") == BINDING_SHA and
                build.get("activeCanonical", {}).get("sha256") == ACTIVE_CONTRACT_SHA,
                f"{role}: staged or active input hash mismatch")
        require(len(build.get("commands", [])) == 2 and
                all(item.get("exitCode") == 0 and not item.get("error") for item in build["commands"]),
                f"{role}: build command failed")
        require(build.get("evaluatorInstall", {}).get("productionUnchanged") is True,
                f"{role}: evaluator installer changed production")
        fixtures[role] = {item["installedPath"]: item["sha256"]
                          for item in build["evaluatorInstall"].get("fixtures", [])}
        require(len(fixtures[role]) >= 9, f"{role}: Task16 evaluator fixtures incomplete")
        production_hashes[role] = {item["path"]: item["sha256"] for item in build.get("production", [])}
        if check_workspace:
            source = Path(build["source"])
            for relative, value in production_hashes[role].items():
                require(digest(source / relative) == value, f"{role}: production source changed after run: {relative}")
            require(all(not Path(item["path"]).exists() for item in build.get("haps", [])),
                    f"{role}: generated HAP was not cleaned")
    require(fixtures["base"] == fixtures["final"], "base/final Task16 evaluator fixtures differ")

    metrics: dict[str, dict[str, int]] = {}
    verified_rows: dict[str, dict[str, dict[str, Any]]] = {}
    for role in ("base", "final"):
        report = docs[f"{role}_device"]
        build_path = paths[f"{role}_build"]
        require(report.get("taskId") == "16_identity_reset" and report.get("role") == role and
                report.get("revision") == 5 and report.get("status") == "completed" and
                report.get("transportCompleted") is True, f"{role}: device execution incomplete")
        require(report.get("serial") == "127.0.0.1:5555", f"{role}: unexpected device serial")
        require(iso_seconds(report["startedAt"], report["finishedAt"]) <= 3600, f"{role}: timeout exceeded")
        require(report.get("buildReport", {}).get("sha256") == digest(build_path),
                f"{role}: device/build report provenance mismatch")
        cleanup = report.get("cleanup", {})
        require(all(cleanup.get(key) is True for key in
                    ("appUninstalled", "hapsRemoved", "lockReleased", "hilogBufferRestored")),
                f"{role}: device cleanup incomplete")
        expected_metrics = ({"passed": 0, "failed": 10, "notScored": 0, "total": 10} if role == "base" else
                            {"passed": 10, "failed": 0, "notScored": 0, "total": 10})
        semantic = report.get("semantic", {})
        metrics[role] = {key: semantic.get(key) for key in expected_metrics}
        require(metrics[role] == expected_metrics, f"{role}: semantic polarity/counts changed")
        rows = semantic.get("cases", [])
        require(len(rows) == 10 and {item.get("caseId") for item in rows} == set(expected),
                f"{role}: semantic rows are incomplete")
        require(set(raw_rows[role]) == set(expected), f"{role}: raw row set is incomplete")
        summary_rows = {item["caseId"]: item for item in report.get("rows", [])}
        require(set(summary_rows) == set(expected), f"{role}: result index is incomplete")
        verified_rows[role] = {}
        for row in rows:
            case_id = row["caseId"]
            raw = raw_rows[role][case_id]
            require(raw == row, f"{role}/{case_id}: semantic row differs from raw device artifact")
            require(row.get("taskId") == "16_identity_reset" and row.get("role") == role and
                    row.get("traceDigest") == expected[case_id], f"{role}/{case_id}: identity/digest mismatch")
            require(row.get("status") == ("fail" if role == "base" else "pass"),
                    f"{role}/{case_id}: unexpected status")
            require(row.get("observationLevel") == OBSERVATION_LEVEL and
                    row.get("unsupportedObservations") == [] and row.get("missingObservations") == [] and
                    row.get("missingInvariants") == [], f"{role}/{case_id}: runtime observation is incomplete")
            bridge = row.get("nativeBridge", {})
            require(bridge.get("candidateUIVerified") is True and bridge.get("applicationContextAvailable") is True,
                    f"{role}/{case_id}: native UI/context not verified")
            capabilities = bridge.get("capabilities", {})
            require(capabilities.get("runtime", {}).get("backend") == "device_ohosTest" and
                    capabilities.get("execution", {}).get("nonce") == report.get("executionNonce") and
                    re.fullmatch(r"[a-f0-9]{32}", report.get("executionNonce", "")),
                    f"{role}/{case_id}: backend/nonce mismatch")
            native = transition(row)
            require(native.get("entryExecuted") is True and native.get("eventExecuted") is True and
                    native.get("observationMode") == "runtime_state_transition" and not native.get("failure"),
                    f"{role}/{case_id}: native transition did not execute")
            require(native.get("frames") and all(frame.get("windowIdentity", {}).get("hostVerified") is True
                    for frame in native["frames"]), f"{role}/{case_id}: ArkUI window identity missing")
            source_map = {item["path"]: item["sha256"] for item in native.get("productionSources", [])}
            require(source_map and all(production_hashes[role].get(path) == value for path, value in source_map.items()),
                    f"{role}/{case_id}: production source provenance mismatch")
            invariants = row.get("invariantChecks", [])
            require(invariants and all(item.get("passed") is (role == "final") for item in invariants),
                    f"{role}/{case_id}: invariant polarity mismatch")
            if role == "base":
                require(native.get("baseFeatureAbsent") is True and
                        native.get("basePositiveControl") == {"rendered": True, "enabledBackupThroughActualUi": True},
                        f"base/{case_id}: positive control or feature absence missing")
                require(any(item.get("target") == "baseEnable" and item.get("executed") is True
                            for item in native.get("actions", [])), f"base/{case_id}: physical positive-control action missing")
            verified_rows[role][case_id] = row

    case006 = verified_rows["final"][CASE006]
    require(case006.get("traceDigest") == CASE006_DIGEST and case006.get("observed") == {
        "failureObserved": True,
        "stateSequence": CASE006_SEQUENCE,
        "stableHandleState": "uninitialized",
        "screen": "reset_root",
        "progressVisible": False,
        "retryEnabled": True,
        "retryHandleState": "loading",
    }, "final/case006: exact failure-cleanup-retry observation changed")
    stable = checkpoint(case006, "task16_ui_stable_after_cleanup")
    require(stable.get("presenter", {}).get("handleState") == "uninitialized" and
            stable.get("presenter", {}).get("screen") == "reset_root" and
            stable.get("presenter", {}).get("progressVisible") is False and
            "failure" in stable.get("presenter", {}).get("cleanupHistory", []),
            "final/case006: stable cleanup checkpoint is invalid")
    actions006 = [item.get("target") for item in transition(case006).get("actions", []) if item.get("executed")]
    require(actions006 == ["continue", "confirm", "retry", "confirm"],
            "final/case006: physical failure/retry action sequence changed")

    case005 = verified_rows["final"]["ir_state_005_oidc_handle_routes_and_resets"]
    require(case005.get("observed") == {"handleState": "success", "effect": "open_oidc_approval",
            "url": "https://id.example/reset", "pollEffect": "reset_oidc"},
            "final/case005: OIDC observation changed")
    oidc_after = checkpoint(case005, "task16_ui_after_event")
    require(control(oidc_after, "oidcWebview").get("id") == "identity_reset_oidc_webview" and
            control(oidc_after, "oidcWebview").get("visible") is True and
            control(oidc_after, "approvalUrl").get("id") == "identity_reset_oidc_url",
            "final/case005: real WebView/URL controls not observed")

    case010 = verified_rows["final"]["ir_state_010_cancel_cleans_up"]
    require(case010.get("observed") == {"effect": "cancel_reset_handle", "handleState": "uninitialized",
            "resetJobActive": False, "completionWatcherActive": False},
            "final/case010: cleanup observation changed")
    cleanup_after = checkpoint(case010, "task16_ui_after_event").get("presenter", {})
    require(all(reason in cleanup_after.get("cleanupHistory", []) for reason in
                ("cancel", "oidc_return", "node_destroy")), "final/case010: cleanup reasons missing")
    require(sum(1 for item in cleanup_after.get("calls", []) if item.get("owner") == "manager" and
                item.get("method") == "cancel") >= 3, "final/case010: shared manager.cancel path missing")

    return {
        "schemaVersion": 1,
        "status": "verified",
        "taskId": "16_identity_reset",
        "revision": 5,
        "platform": "arkts",
        "runtime": "OpenHarmony API23 ArkVM / ArkUI / ohosTest",
        "contractSha256": CONTRACT_SHA,
        "bindingSha256": BINDING_SHA,
        "activeCanonicalPreserved": True,
        "activeBindingPreserved": True,
        "compile": {"base": True, "final": True},
        "semantic": metrics,
        "case006": {"traceDigest": CASE006_DIGEST, "stateSequence": CASE006_SEQUENCE,
                    "physicalActions": actions006, "verified": True},
        "cleanupVerified": True,
        "agentResultReused": False,
    }


def verify(root: Path, base_build: Path, final_build: Path,
           base_device: Path, final_device: Path) -> dict[str, Any]:
    inputs = load_inputs(root, base_build, final_build, base_device, final_device)
    return verify_documents(inputs, check_workspace=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--base-build", type=Path, required=True)
    parser.add_argument("--final-build", type=Path, required=True)
    parser.add_argument("--base-device", type=Path, required=True)
    parser.add_argument("--final-device", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    paths = [item.resolve() for item in
             (args.base_build, args.final_build, args.base_device, args.final_device)]
    result = verify(root, *paths)
    if args.output_dir:
        args.output_dir.mkdir(parents=True, exist_ok=True)
        (args.output_dir / "verified.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        for role, build_path, device_path in (("base", paths[0], paths[2]), ("final", paths[1], paths[3])):
            report = read_json(device_path)
            summary = {"schemaVersion": 1, "taskId": "16_identity_reset", "platform": "arkts",
                       "role": role, "revision": 5, "compilePassed": True,
                       "semantic": {key: report["semantic"][key] for key in ("passed", "failed", "notScored", "total")},
                       "buildReport": str(build_path), "deviceReport": str(device_path),
                       "executionNonce": report["executionNonce"], "verified": True}
            (args.output_dir / f"{role}.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
