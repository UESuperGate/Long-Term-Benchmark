#!/usr/bin/env python3
"""Independent verifier for Task17 Android base/final runtime calibration."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
SOURCE = ROOT / "_sources/element-x-android"
TASK = "17_pinned_messages"
CONTRACT = ROOT / "benchmark_tasks" / TASK / "transitions.json"
BASE_COMMIT = "4ecc9f46b6627f89184d66b758094a7c4a24c258"
BASE_TREE = "6c90042e69580acd06c8d669447c90a4a90ec9e8"
FINAL_COMMIT = "eff868ddf9e1caef8182e55ac59054e81526a68f"
FINAL_TREE = "0cd8a58632515f8e0f6fb669b02c8b35614d9181"
BASE_SCOPE = ":features:messages:impl:testDebugUnitTest"
BASE_CLASS = "runtime.task17.BasePrefixRuntimeTest"
TARGET_BASE = {"pass": 0, "fail": 9, "not_scored": 0}
TARGET_FINAL = {"pass": 9, "fail": 0, "not_scored": 0}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_record(path: Path) -> dict:
    data = path.read_bytes()
    return {"path": str(path.resolve()), "sha256": digest(data), "bytes": len(data)}


def record_matches(record: dict | None) -> bool:
    if not isinstance(record, dict):
        return False
    path = Path(record.get("path", ""))
    return path.is_file() and record.get("sha256") == digest(path.read_bytes()) and record.get("bytes") == path.stat().st_size


def canonical_specs(contract: dict) -> tuple[list[str], dict[str, dict]]:
    rows = contract.get("cases", [])
    return [row.get("key") for row in rows], {row.get("key"): row for row in rows}


def counts(rows: list[dict]) -> dict:
    return {status: sum(row.get("status") == status for row in rows) for status in ("pass", "fail", "not_scored")}


def validate_identity(name: str, document: dict, role: str, commit: str, tree: str, errors: list[str]) -> list[dict]:
    if (document.get("taskId"), document.get("platform"), document.get("role")) != (TASK, "android", role):
        errors.append(f"{name}: identity mismatch")
    if document.get("schemaVersion") != 2 or document.get("status") != "candidate":
        errors.append(f"{name}: schema/status mismatch")
    candidate = document.get("candidate", {})
    if (candidate.get("commit"), candidate.get("tree")) != (commit, tree):
        errors.append(f"{name}: immutable commit/tree mismatch")
    if document.get("applicationCompile") != {"status": "not_run", "passed": None}:
        errors.append(f"{name}: application compile scope must remain explicitly not_run")
    rows = document.get("semantic", {}).get("cases", [])
    if not isinstance(rows, list):
        errors.append(f"{name}: semantic cases missing")
        return []
    if document.get("semantic", {}).get("counts") != counts(rows):
        errors.append(f"{name}: semantic counts do not match case rows")
    return rows


def validate_documents(base: dict, final: dict, contract: dict) -> list[str]:
    errors: list[str] = []
    expected_keys, specs = canonical_specs(contract)
    if len(expected_keys) != 9 or len(set(expected_keys)) != 9:
        errors.append("contract: expected nine unique canonical cases")

    base_rows = validate_identity("base", base, "base", BASE_COMMIT, BASE_TREE, errors)
    final_rows = validate_identity("final", final, "final", FINAL_COMMIT, FINAL_TREE, errors)
    contract_sha = digest(CONTRACT.read_bytes())
    for name, document in (("base", base), ("final", final)):
        record = document.get("contract", {})
        if record.get("sha256") != contract_sha or record.get("bytes") != CONTRACT.stat().st_size:
            errors.append(f"{name}: canonical contract hash/size mismatch")

    base_compile = base.get("runtimeCompile", {})
    if base_compile != {
        "status": "passed", "passed": True, "scope": BASE_SCOPE, "exitCode": 0,
        "isolatedTestJvms": 9, "forkEvery": 1,
    }:
        errors.append("base: module runtime compile or JVM isolation mismatch")
    if base.get("runtimeDomain") != "robolectric_real_banner_to_appyx_production_flow_prefix":
        errors.append("base: runtime domain is not the production Appyx flow prefix")
    if counts(base_rows) != TARGET_BASE:
        errors.append("base: expected 0 PASS / 9 FAIL / 0 NOT_SCORED")
    if [row.get("key") for row in base_rows] != expected_keys:
        errors.append("base: canonical case order/set mismatch")

    base_evidence_paths = []
    for row in base_rows:
        key = row.get("key")
        spec = specs.get(key)
        if not spec or any(row.get(field) != spec.get(field) for field in ("caseId", "traceDigest", "given", "event", "expected")):
            errors.append(f"base: canonical identity/contract mismatch for {key}")
        if row.get("status") != "fail":
            errors.append(f"base: non-fail semantic result for {key}")
        if row.get("observed") != {"screen": "room_timeline", "pinnedListReachable": False}:
            errors.append(f"base: unexpected runtime observation for {key}")
        checkpoints = {item.get("name"): item.get("state", {}) for item in row.get("checkpoints", [])}
        start = checkpoints.get("common_start", {})
        post = checkpoints.get("post_event", {})
        if start.get("pinnedBannerVisible") is not True or start.get("flowClass") != "io.element.android.features.messages.impl.MessagesFlowNode":
            errors.append(f"base: missing real banner/flow start evidence for {key}")
        if post.get("event") != "open_pinned_messages" or post.get("uiDispatches") != 1:
            errors.append(f"base: missing single real UI dispatch for {key}")
        if post.get("backstackTarget") != "Messages" or post.get("pinnedListReachable") is not False:
            errors.append(f"base: production backstack prefix is not proven for {key}")
        checks = row.get("invariantChecks", [])
        if len(checks) != 1 or checks[0].get("status") != "pass" or checks[0].get("evidence") != {"before": "Messages", "after": "Messages"}:
            errors.append(f"base: navigation-parent invariant evidence mismatch for {key}")
        junit = row.get("junit", {})
        if junit.get("classname") != BASE_CLASS or any(junit.get(field) for field in ("failure", "error", "skipped")):
            errors.append(f"base: test execution was not clean for {key}")
        evidence = row.get("runtimeEvidence")
        if not isinstance(evidence, dict):
            errors.append(f"base: runtime evidence missing for {key}")
        else:
            base_evidence_paths.append(evidence.get("path"))
    if len(set(base_evidence_paths)) != 9:
        errors.append("base: runtime evidence was reused across cases")

    final_compile = final.get("runtimeCompile", {})
    if final_compile != {"status": "passed", "isolatedSlices": 9}:
        errors.append("final: runtime slices did not all compile")
    if final.get("runtimeDomain") != "host_jvm_robolectric_real_production_transition":
        errors.append("final: runtime domain is not a real production transition")
    if final.get("isolation") != {
        "oneRunSlicePerCase": True,
        "separateCompilerTemporaryDirectoryPerCase": True,
        "separateJvmPerCase": True,
        "externalDeviceUsed": False,
    }:
        errors.append("final: per-case compiler/JVM isolation mismatch")
    if counts(final_rows) != TARGET_FINAL:
        errors.append("final: expected 9 PASS / 0 FAIL / 0 NOT_SCORED")
    if [row.get("key") for row in final_rows] != expected_keys:
        errors.append("final: canonical case order/set mismatch")

    final_raw_paths = []
    for row in final_rows:
        key = row.get("key")
        spec = specs.get(key)
        if not spec or any(row.get(field) != spec.get(field) for field in ("caseId", "traceDigest", "given", "event", "expected")):
            errors.append(f"final: canonical identity/contract mismatch for {key}")
            continue
        if row.get("status") != "pass" or row.get("observed") != spec.get("expected"):
            errors.append(f"final: observed state is not exactly canonical expected for {key}")
        checks = row.get("invariantChecks", [])
        check_names = [item.get("invariant") for item in checks]
        if check_names != spec.get("invariants") or any(item.get("status") != "pass" for item in checks):
            errors.append(f"final: canonical invariant evidence mismatch for {key}")
        if not row.get("checkpoints") or row["checkpoints"][-1].get("name") != "post_event":
            errors.append(f"final: post-event runtime checkpoint missing for {key}")
        runtime_report = row.get("runtimeReport")
        if not isinstance(runtime_report, dict):
            errors.append(f"final: raw runtime report missing for {key}")
        else:
            final_raw_paths.append(runtime_report.get("path"))
    if len(set(final_raw_paths)) != 9:
        errors.append("final: raw runtime report was reused across cases")

    rows_by_key = {row.get("key"): row for row in final_rows}
    open_post = rows_by_key.get("open_loading", {}).get("checkpoints", [{}, {}])[-1].get("state", {})
    if open_post.get("openPinnedTimelineCalls") != 1:
        errors.append("final: opening transition did not cross the production timeline boundary exactly once")
    success_post = rows_by_key.get("unpin_success", {}).get("checkpoints", [{}, {}])[-1].get("state", {})
    calls = success_post.get("unpinCalls", [])
    if calls != [{"port": "io.element.android.libraries.matrix.api.timeline.Timeline", "method": "unpinEvent", "args": ["$a"]}]:
        errors.append("final: successful unpin lacks the exact SDK boundary call")
    failure_post = rows_by_key.get("unpin_failure_recovery", {}).get("checkpoints", [{}, {}])[-1].get("state", {})
    if failure_post.get("retryUnpinCalls") != 2 or not failure_post.get("snackbarMessage"):
        errors.append("final: failure recovery lacks snackbar and a second production unpin call")
    return errors


def validate_navigation(navigation: dict, contract: dict) -> list[str]:
    errors: list[str] = []
    spec = next((row for row in contract.get("cases", []) if row.get("key") == "open_loading"), None)
    if (navigation.get("taskId"), navigation.get("platform"), navigation.get("role"), navigation.get("probe")) != (
        TASK, "android", "final", "open_loading_navigation_conjunct",
    ):
        errors.append("final-navigation: identity mismatch")
    if navigation.get("status") != "candidate":
        errors.append("final-navigation: probe is not a successful candidate")
    candidate = navigation.get("candidate", {})
    if (candidate.get("commit"), candidate.get("tree")) != (FINAL_COMMIT, FINAL_TREE):
        errors.append("final-navigation: immutable commit/tree mismatch")
    expected_compile = {
        "status": "passed", "passed": True, "scope": BASE_SCOPE, "exitCode": 0,
        "isolatedTestJvms": 1, "forkEvery": 1,
    }
    if navigation.get("runtimeCompile") != expected_compile:
        errors.append("final-navigation: module runtime compile/isolation mismatch")
    semantic = navigation.get("semantic", {})
    if spec is None or semantic.get("key") != "open_loading" or semantic.get("status") != "pass":
        errors.append("final-navigation: canonical open_loading result missing")
    elif semantic.get("evidenceSchemaVersion") not in {2, 3} and semantic.get("observed") != spec.get("expected"):
        errors.append("final-navigation: observed state differs from canonical expected")
    nav = semantic.get("navigation", {})
    expected_nav = {
        "before": "Messages(focusedEventId=null)",
        "after": "PinnedMessagesList",
        "uiDispatches": 1,
        "pinnedNodeBuilds": 1,
        "bannerLabel": "View All",
        "flowClass": "io.element.android.features.messages.impl.MessagesFlowNode",
        "callbackClass": "io.element.android.features.messages.impl.MessagesFlowNode$resolve$callback$1",
    }
    if semantic.get("evidenceSchemaVersion") == 3:
        before_keys, after_keys = nav.get("beforeKeys"), nav.get("afterKeys")
        if not (isinstance(before_keys, list) and len(before_keys) == 1 and isinstance(after_keys, list) and
                len(after_keys) == 2 and after_keys[0] == before_keys[0] and after_keys[1] != before_keys[0] and
                all(isinstance(key, str) and key for key in before_keys + after_keys) and
                nav.get("timelineParentRetained") is True):
            errors.append("final-navigation: timeline parent key not retained in actual backstack")
        expected_nav.update(beforeKeys=before_keys, afterKeys=after_keys, timelineParentRetained=True)
    if nav != expected_nav:
        errors.append("final-navigation: real banner/callback/backstack/node transition mismatch")
    if semantic.get("evidenceSchemaVersion") in {2, 3}:
        if semantic.get("observed") != {"backstackTarget": "PinnedMessagesList", "pinnedNodeBuilds": 1}:
            errors.append("final-navigation: actual navigation observation mismatch")
        points = {point.get("name"): point.get("state", {}) for point in semantic.get("checkpoints", [])}
        before, after = points.get("common_start", {}), points.get("post_event", {})
        if (before.get("backstackTarget"), after.get("backstackTarget"), after.get("uiDispatches"),
                after.get("pinnedNodeBuilds")) != ("Messages(focusedEventId=null)", "PinnedMessagesList", 1, 1):
            errors.append("final-navigation: actual before/after checkpoints mismatch")
        if semantic.get("evidenceSchemaVersion") == 3 and (
                before.get("backstackKeys") != nav.get("beforeKeys") or
                after.get("backstackKeys") != nav.get("afterKeys") or after.get("timelineParentRetained") is not True):
            errors.append("final-navigation: actual parent checkpoints disagree")
    checks = semantic.get("invariantChecks", [])
    if len(checks) != 1 or checks[0].get("invariant") != spec.get("invariants", [None])[0] or checks[0].get("status") != "pass":
        errors.append("final-navigation: canonical parent invariant missing")
    elif semantic.get("evidenceSchemaVersion") == 3 and checks[0].get("evidence") != {
            "beforeKeys": nav.get("beforeKeys"), "afterKeys": nav.get("afterKeys")}:
        errors.append("final-navigation: invariant evidence does not contain actual parent keys")
    junit = navigation.get("junit", {})
    if junit != {
        "name": "open_loading_navigation", "classname": "runtime.task17.FinalNavigationRuntimeTest",
        "failure": False, "error": False, "skipped": False,
    }:
        errors.append("final-navigation: JUnit execution was not clean")
    return errors


def verify_upstream(records: list[dict], tree: str, label: str, errors: list[str]) -> None:
    seen: set[str] = set()
    for item in records:
        path = item.get("path")
        if not isinstance(path, str) or path in seen:
            errors.append(f"{label}: duplicate/invalid production source path {path}")
            continue
        seen.add(path)
        try:
            data = subprocess.check_output(["git", "-C", str(SOURCE), "show", f"{tree}:{path}"], stderr=subprocess.PIPE)
        except (OSError, subprocess.SubprocessError):
            errors.append(f"{label}: production source unavailable {path}")
            continue
        if item.get("sha256") != digest(data) or item.get("bytes") != len(data):
            errors.append(f"{label}: production source hash/size mismatch {path}")


def verify_files(base: dict, final: dict) -> list[str]:
    errors: list[str] = []
    if not record_matches(base.get("contract")) or not record_matches(final.get("contract")):
        errors.append("contract: recorded artifact does not match disk")

    for label in ("runner", "initScript", "evaluatorSource", "injectedEvaluatorSource", "gradleLog", "junit"):
        if not record_matches(base.get("provenance", {}).get(label)):
            errors.append(f"base: artifact hash mismatch for {label}")
    base_sources = base.get("provenance", {}).get("productionSources", [])
    verify_upstream(base_sources, BASE_TREE, "base", errors)
    junit_path = Path(base.get("provenance", {}).get("junit", {}).get("path", ""))
    if junit_path.is_file():
        root = ET.parse(junit_path).getroot()
        methods = root.findall(".//testcase")
        if (root.attrib.get("tests"), root.attrib.get("failures"), root.attrib.get("errors"), root.attrib.get("skipped")) != ("9", "0", "0", "0"):
            errors.append("base: JUnit suite totals are not 9 clean executions")
        if {node.attrib.get("name") for node in methods} != {row.get("key") for row in base.get("semantic", {}).get("cases", [])}:
            errors.append("base: JUnit method set does not match canonical cases")
    for row in base.get("semantic", {}).get("cases", []):
        record = row.get("runtimeEvidence")
        if not record_matches(record):
            errors.append(f"base: evidence artifact hash mismatch for {row.get('key')}")
            continue
        evidence = json.loads(Path(record["path"]).read_text())
        for field in ("key", "status", "reason", "observed", "checkpoints", "invariantChecks"):
            if evidence.get(field) != row.get(field):
                errors.append(f"base: evidence/report mismatch for {row.get('key')} field {field}")

    for label, record in (("runner", final.get("provenance", {}).get("runner")),):
        if not record_matches(record):
            errors.append(f"final: artifact hash mismatch for {label}")
    for record in final.get("provenance", {}).get("evaluatorSources", []):
        if not record_matches(record):
            errors.append(f"final: evaluator source hash mismatch {record.get('path')}")

    reference_sources = None
    required_sources = {
        "features/messages/impl/src/main/kotlin/io/element/android/features/messages/impl/pinned/PinnedEventsTimelineProvider.kt",
        "features/messages/impl/src/main/kotlin/io/element/android/features/messages/impl/pinned/list/PinnedMessagesListPresenter.kt",
        "features/messages/impl/src/main/kotlin/io/element/android/features/messages/impl/actionlist/ActionListPresenter.kt",
        "libraries/matrix/api/src/main/kotlin/io/element/android/libraries/matrix/api/timeline/Timeline.kt",
        "libraries/designsystem/src/main/kotlin/io/element/android/libraries/designsystem/utils/snackbar/SnackbarDispatcher.kt",
    }
    for row in final.get("semantic", {}).get("cases", []):
        key = row.get("key")
        record = row.get("runtimeReport")
        if not record_matches(record):
            errors.append(f"final: raw report hash mismatch for {key}")
            continue
        raw_path = Path(record["path"])
        raw = json.loads(raw_path.read_text())
        provenance = raw.get("provenance", {})
        if (raw.get("taskId"), raw.get("role"), raw.get("status")) != (TASK, "final", "passed"):
            errors.append(f"final: raw identity/status mismatch for {key}")
        if (provenance.get("commit"), provenance.get("tree")) != (FINAL_COMMIT, FINAL_TREE):
            errors.append(f"final: raw immutable identity mismatch for {key}")
        if raw.get("runtimeCompile", {}).get("status") != "passed" or raw.get("error") is not None:
            errors.append(f"final: raw compile/runtime error for {key}")
        observations = raw.get("observations", [])
        projected = {field: row.get(field) for field in ("key", "status", "reason", "checkpoints", "observed", "invariantChecks")}
        if len(observations) != 1 or any(observations[0].get(field) != value for field, value in projected.items()):
            errors.append(f"final: raw observation/report projection mismatch for {key}")
        config_path = raw_path.with_suffix(".config.json")
        if not config_path.is_file() or provenance.get("configurationSha256") != digest(config_path.read_bytes()):
            errors.append(f"final: config hash mismatch for {key}")
        for evaluator in provenance.get("evaluatorSources", []):
            path = Path(evaluator.get("path", ""))
            if not path.is_file() or evaluator.get("sha256") != digest(path.read_bytes()):
                errors.append(f"final: raw evaluator source mismatch for {key}: {path}")
        production_sources = provenance.get("productionSources", [])
        compact = [(item.get("path"), item.get("sha256"), item.get("bytes")) for item in production_sources]
        if reference_sources is None:
            reference_sources = compact
            verify_upstream(production_sources, FINAL_TREE, "final", errors)
            if not required_sources.issubset({item.get("path") for item in production_sources}):
                errors.append("final: production closure misses required transition classes")
        elif compact != reference_sources:
            errors.append(f"final: production source closure differs for {key}")

    raw_records = final.get("provenance", {}).get("rawReports", [])
    if len(raw_records) != 9 or any(not record_matches(record) for record in raw_records):
        errors.append("final: top-level raw report provenance mismatch")
    return errors


def verify_navigation_files(navigation: dict) -> list[str]:
    errors: list[str] = []
    if not record_matches(navigation.get("contract")):
        errors.append("final-navigation: contract artifact mismatch")
    provenance = navigation.get("provenance", {})
    for label in ("runner", "initScript", "evaluatorSource", "injectedEvaluatorSource", "gradleLog", "junit", "runtimeEvidence"):
        if not record_matches(provenance.get(label)):
            errors.append(f"final-navigation: artifact hash mismatch for {label}")
    evidence_record = provenance.get("runtimeEvidence", {})
    if record_matches(evidence_record):
        evidence = json.loads(Path(evidence_record["path"]).read_text())
        if evidence != navigation.get("semantic"):
            errors.append("final-navigation: evidence/report projection mismatch")
    verify_upstream(provenance.get("productionSources", []), FINAL_TREE, "final-navigation", errors)
    required = {
        "features/messages/impl/src/main/kotlin/io/element/android/features/messages/impl/MessagesFlowNode.kt",
        "features/messages/impl/src/main/kotlin/io/element/android/features/messages/impl/MessagesNode.kt",
        "features/messages/impl/src/main/kotlin/io/element/android/features/messages/impl/pinned/banner/PinnedMessagesBannerView.kt",
        "features/messages/impl/src/main/kotlin/io/element/android/features/messages/impl/pinned/list/PinnedMessagesListNode.kt",
    }
    if not required.issubset({item.get("path") for item in provenance.get("productionSources", [])}):
        errors.append("final-navigation: production transition source set incomplete")
    return errors


def main() -> int:
    default_results = ROOT / "experiment_results/runtime_transition_20261020/task17_android"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, default=default_results / "base-candidate-v6/android_17_pinned_messages_base_calibrated_v1.json")
    parser.add_argument("--final", type=Path, default=default_results / "final-candidate-v2/android_17_pinned_messages_final_calibrated_v1.json")
    parser.add_argument("--final-navigation", type=Path, default=default_results / "final-navigation-v1/android_17_pinned_messages_final_navigation_v1.json")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    base = json.loads(args.base.read_text())
    final = json.loads(args.final.read_text())
    navigation = json.loads(args.final_navigation.read_text())
    contract = json.loads(CONTRACT.read_text())
    errors = (
        validate_documents(base, final, contract)
        + validate_navigation(navigation, contract)
        + verify_files(base, final)
        + verify_navigation_files(navigation)
    )
    result = {
        "schemaVersion": 1,
        "taskId": TASK,
        "platform": "android",
        "validated": not errors,
        "promotable": not errors,
        "errors": errors,
        "base": base.get("semantic", {}).get("counts"),
        "final": final.get("semantic", {}).get("counts"),
        "compileScope": {
            "application": "not_run",
            "base": BASE_SCOPE,
            "final": "nine isolated host Robolectric production slices plus one isolated module navigation conjunct",
        },
        "canonicalContract": file_record(CONTRACT),
        "immutableUpstream": {
            "base": {"commit": BASE_COMMIT, "tree": BASE_TREE},
            "final": {"commit": FINAL_COMMIT, "tree": FINAL_TREE},
        },
        "finalNavigationConjunct": file_record(args.final_navigation),
        "verifier": file_record(Path(__file__)),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))
    return 0 if result["validated"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
