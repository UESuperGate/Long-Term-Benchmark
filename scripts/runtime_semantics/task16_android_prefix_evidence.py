"""Task16-only runtime prefix verifier; no role, ref, or candidate-name inference."""
from __future__ import annotations

import copy
import hashlib
import json
import re
from pathlib import Path
from typing import List, Optional

ROOT = Path(__file__).resolve().parents[2]
TASK = "16_identity_reset"
ASSETS = ROOT / "state_tests/runtime/android/16_identity_reset"
CONTRACT = ROOT / "benchmark_tasks/16_identity_reset/transitions.json"
AUDIT_ROOT = ROOT / "experiment_results"


def binding_bytes(view_source: str) -> bytes:
    match = re.search(r"fun VerifySelfSessionView\((.*?)\)\s*\{", view_source, re.S)
    if not match:
        raise ValueError("Candidate verification View API cannot be bound")
    reset = "onResetKey = onReset," if re.search(r"\bonResetKey\s*:", match.group(1)) else ""
    return (
        "package runtime\nimport androidx.compose.runtime.Composable\n"
        "import io.element.android.features.verifysession.impl.*\n"
        "@Composable fun RenderVerificationEntry(state: VerifySelfSessionState, onRecovery: () -> Unit, "
        "onReset: () -> Unit, onFinish: () -> Unit) {\n"
        "VerifySelfSessionView(state = state, onEnterRecoveryKey = onRecovery, " + reset + " onFinish = onFinish)\n}\n"
    ).encode()


def validate_evaluator_sources(runtime: dict, report_path: Path) -> None:
    configuration = json.loads((ASSETS / "common_prefix/adapter.json").read_text())
    expected = {}
    for relative in configuration["evaluatorSources"]:
        if relative == "VerifyEntryBinding.kt":
            path = report_path.parent / "evaluator-sources/VerifyEntryBinding.kt"
            view = report_path.parent / "production-sources" / configuration["entrypoints"][0]
            expected[str(path.resolve())] = binding_bytes(view.read_text())
        else:
            path = (ASSETS / "common_prefix" / relative).resolve()
            expected[str(path)] = path.read_bytes()
    for path in (ROOT / "state_tests/runtime/android/common/Harness.kt",
                 ROOT / "state_tests/runtime/android/08_threads/robolectric/EvidenceRobolectricRunner.java",
                 ROOT / "state_tests/runtime/android/08_threads/robolectric/RobolectricMain.java"):
        expected[str(path.resolve())] = path.read_bytes()
    actual = runtime.get("provenance", {}).get("evaluatorSources", [])
    if not actual or len(actual) != len(expected) or len({item["path"] for item in actual}) != len(actual):
        raise ValueError("Task16 prefix requires the complete nonempty reviewed evaluator manifest")
    for item in actual:
        path = str(Path(item["path"]).resolve())
        reviewed = expected.get(path)
        if reviewed is None or hashlib.sha256(reviewed).hexdigest() != item["sha256"]:
            raise ValueError("Task16 prefix evaluator is not the current reviewed implementation")
        snapshot = report_path.parent / "evaluator-sources" / Path(path).name
        if not snapshot.resolve().is_relative_to(report_path.parent.resolve()):
            raise ValueError("Task16 evaluator snapshot escaped its audit directory")
        if snapshot.read_bytes() != reviewed:
            raise ValueError("Task16 prefix evaluator snapshot differs from reviewed bytes")


def record(path: Path) -> dict:
    data = path.read_bytes()
    return {"path": str(path.resolve()), "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}


def rows(report: dict) -> List[dict]:
    return report.get("observations") or report.get("semantic", {}).get("cases", [])


def row_for(report: dict, key: str) -> Optional[dict]:
    return next((row for row in rows(report) if row.get("key") == key), None)


def slice_healthy(report: dict) -> bool:
    return report.get("runtimeCompile", {}).get("status") == "passed" and not report.get("error")


def base_rows(contract: dict, entry: dict, evidence_path: Optional[Path] = None) -> List[dict]:
    result = []
    for spec in contract["cases"]:
        raw = row_for(entry, spec["key"])
        observed = (raw or {}).get("observed", {})
        absent = valid_prefix(raw, entry) and observed.get("entryAvailable") is False and raw.get("status") == "fail"
        row = {"caseId": spec["caseId"], "key": spec["key"], "traceDigest": spec["traceDigest"],
                       "status": "fail" if absent else "not_scored",
                       "observed": observed,
                       "checkpoints": raw.get("checkpoints", []) if raw else [],
                       "productionSources": copy.deepcopy(entry.get("provenance", {}).get("productionSources", [])),
                       "invariantChecks": [], "unevaluatedInvariants": copy.deepcopy(spec["invariants"]),
                       "canonicalEventExecuted": False, "prefixTransitionExecuted": bool(valid_prefix(raw, entry)),
                       "unobservedExpectedFields": list(spec["expected"]),
                       "reason": "Common verification UI and production FTUE recovery roundtrip executed independently; reset entry unavailable." if absent else "Real common prefix incomplete."}
        if absent and evidence_path:
            row["task16PrefixFailure"] = {"report": record(evidence_path), "key": spec["key"],
                "contract": record(CONTRACT), "policy": record(ASSETS / "common_prefix/policy.json")}
        elif absent:
            row["status"] = "not_scored"
        result.append(row)
    return result


def valid_prefix(raw: Optional[dict], report: dict) -> bool:
    if not raw or not slice_healthy(report):
        return False
    state = raw.get("observed", {})
    points = {point.get("name"): point.get("state", {}) for point in raw.get("checkpoints", [])}
    return (state.get("commonGivenEstablished") is True and state.get("positiveControlPassed") is True
            and state.get("recoveryUiClickExecuted") is True and state.get("recoveryRoute") == "EnterRecoveryKey"
            and state.get("returnedRoute") == "Root"
            and points.get("recovery_positive_control", {}).get("uiClickExecuted") is True
            and points.get("recovery_positive_control", {}).get("target") == "EnterRecoveryKey"
            and points.get("recovery_positive_control", {}).get("route") == "EnterRecoveryKey"
            and points.get("recovery_positive_control", {}).get("backupBuilds") == 1
            and points.get("recovery_returns_root", {}).get("route") == "Root"
            and points.get("recovery_returns_root", {}).get("done") == 0
            and points.get("common_initial", {}).get("route") == "Root"
            and points.get("common_initial", {}).get("backupBuilds") == 0
            and isinstance(state.get("executionId"), str) and len(state["executionId"]) == 36
            and points.get("common_initial", {}).get("executionId") == state["executionId"]
            and len(points) >= 5 and bool(report.get("provenance", {}).get("productionSources")))


def validate_prefix_failure(row: dict, report: dict, used_ids: set, contract: Optional[dict] = None) -> None:
    """Verify only Task16's real UI/FTUE early failure, leaving later observations unknown."""
    if report.get("taskId") != TASK or report.get("platform") != "android" or row.get("status") != "fail":
        raise ValueError("Wrong Task16 runtime prefix identity")
    canonical = json.loads(CONTRACT.read_text())
    if contract is not None and contract != canonical:
        raise ValueError("Task16 canonical contract differs")
    contract = canonical
    evidence = row["task16PrefixFailure"]
    report_path = Path(evidence["report"]["path"]).resolve()
    if not report_path.is_relative_to(AUDIT_ROOT.resolve()):
        raise ValueError("Task16 prefix report must belong to the repository audit root")
    for item in (evidence["report"], evidence["contract"], evidence["policy"]):
        if record(Path(item["path"])) != item:
            raise ValueError("Task16 prefix artifact hash mismatch")
    if evidence["contract"] != record(CONTRACT) or evidence["policy"] != record(ASSETS / "common_prefix/policy.json"):
        raise ValueError("Unreviewed Task16 prefix policy")
    runtime = json.loads(report_path.read_text())
    if runtime.get("taskId") != TASK or runtime.get("scope") != "task16_common_verification_ui_and_production_ftue_prefix":
        raise ValueError("Wrong Task16 prefix runtime identity")
    validate_evaluator_sources(runtime, report_path)
    raw = row_for(runtime, row["key"])
    state = (raw or {}).get("observed", {})
    entry_assertion = (state.get("firstDeviceEntryCount") == 1 and state.get("lastDeviceEntryCount") == 1
                       and state.get("actualRoute") == "ResetIdentity" and state.get("actualTarget") == "ResetIdentity"
                       and state.get("backupBuilds") == 2)
    checks = (raw or {}).get("invariantChecks", [])
    if (not valid_prefix(raw, runtime) or raw.get("status") != "fail" or entry_assertion or
            state.get("entryAvailable") is not False or
            (state.get("lastDeviceEntryCount") == 1 and state.get("resetUiClickExecuted") is not True) or
            len(checks) != 1 or checks[0].get("status") != "fail" or checks[0].get("invariant") !=
            "identity reset is reachable from the common verification UI through the production FTUE flow"):
        raise ValueError("Task16 prefix did not establish a real missing UI entry")
    expected = next(item for item in base_rows(contract, runtime, Path(evidence["report"]["path"])) if item["key"] == row["key"])
    if row != expected:
        raise ValueError("Task16 prefix row differs from runtime bytes")
    executions = [item.get("observed", {}).get("executionId") for item in rows(runtime)]
    if (len(executions) != len(set(executions)) or
            sorted(item["key"] for item in rows(runtime)) != sorted(item["key"] for item in contract["cases"])):
        raise ValueError("Task16 cases reused a prefix execution")
    root = Path(report["provenance"]["candidateSource"])
    if runtime["provenance"].get("source") != str(root):
        raise ValueError("Task16 prefix candidate differs")
    required = {
        "features/verifysession/impl/src/main/kotlin/io/element/android/features/verifysession/impl/VerifySelfSessionView.kt",
        "features/ftue/impl/src/main/kotlin/io/element/android/features/ftue/impl/sessionverification/FtueSessionVerificationFlowNode.kt",
        "features/securebackup/api/src/main/kotlin/io/element/android/features/securebackup/api/SecureBackupEntryPoint.kt",
        "features/verifysession/api/src/main/kotlin/io/element/android/features/verifysession/api/VerifySessionEntryPoint.kt",
    }
    if not required.issubset({item["path"] for item in row["productionSources"]}):
        raise ValueError("Task16 prefix omitted executed production entry sources")
    for item in row["productionSources"]:
        snapshot = Path(evidence["report"]["path"]).parent / "production-sources" / item["path"]
        if not snapshot.resolve().is_relative_to((report_path.parent / "production-sources").resolve()):
            raise ValueError("Task16 production snapshot escaped its audit directory")
        data = snapshot.read_bytes()
        if hashlib.sha256(data).hexdigest() != item["sha256"] or len(data) != item["bytes"]:
            raise ValueError("Task16 prefix production bytes differ")
    log = runtime["log"]
    if Path(log["path"]).resolve() != report_path.with_suffix(".log"):
        raise ValueError("Task16 prefix log must accompany its audit report")
    log_data = Path(log["path"]).read_bytes()
    if hashlib.sha256(log_data).hexdigest() != log["sha256"]:
        raise ValueError("Task16 prefix log changed")
    logged = [json.loads(line.removeprefix("RUNTIME_RESULT ")) for line in log_data.decode().splitlines() if line.startswith("RUNTIME_RESULT ")]
    if logged != rows(runtime):
        raise ValueError("Task16 prefix observations differ from executed JUnit log")
    observation_id = evidence["report"]["sha256"] + ":" + row["key"]
    if observation_id in used_ids:
        raise ValueError("Task16 prefix execution reused")
    used_ids.add(observation_id)
