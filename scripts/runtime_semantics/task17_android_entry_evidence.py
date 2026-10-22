"""Validate Task17's source-bound, actually clicked production entry prefixes.

Public router API: validate_entry_failure(row, report, usedids, contract).
An unreachable prefix has actual checkpoints, never a canonical post-state.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
TASK = "17_pinned_messages"
POLICY_ID = "task17.android.banner-appyx-runtime-prefix.v1"
HERE = ROOT / "state_tests/runtime/android/17_pinned_messages/calibrated_v1"
PREFIX = "features/messages/impl/src/main/kotlin/io/element/android/features/messages/impl/"
REQUIRED = {PREFIX + name for name in (
    "MessagesFlowNode.kt", "MessagesNode.kt", "pinned/banner/PinnedMessagesBannerView.kt",
    "pinned/banner/PinnedMessagesBannerState.kt", "pinned/banner/PinnedMessagesBannerItem.kt")}
REQUIRED.add("libraries/architecture/src/main/kotlin/io/element/android/libraries/architecture/NodeFactories.kt")


def require(value, message):
    if not value:
        raise ValueError(message)


def artifact(path):
    path = Path(path).resolve()
    data = path.read_bytes()
    return {"path": str(path), "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}


def bound(item):
    path = Path(item["path"]).resolve()
    require(path.is_relative_to(ROOT / "experiment_results"), "Task17 evidence outside experiment results")
    data = path.read_bytes()
    require(hashlib.sha256(data).hexdigest() == item.get("sha256") and
            ("bytes" not in item or len(data) == item["bytes"]), "Task17 evidence bytes changed")
    return data


def check_actual(raw, kind, key):
    require(raw.get("key") == key and raw.get("status") == "fail", "Task17 entry did not actually fail")
    points = raw.get("checkpoints", [])
    require(len(points) == 2 and [point.get("name") for point in points] == ["common_start", "post_event"],
            "Task17 prefix checkpoints missing")
    before, after = (point["state"] for point in points)
    require(before.get("flowClass") == "io.element.android.features.messages.impl.MessagesFlowNode" and
            before.get("pinnedBannerVisible") is True and bool(before.get("viewAllLabel")),
            "Task17 real production banner/flow start missing")
    require(after.get("event") == "open_pinned_messages" and after.get("uiDispatches") == 1,
            "Task17 single actual Banner click missing")
    if kind == "base_prefix":
        require(before.get("screen") == "room_timeline" and before.get("backstackTarget") == "Messages" and
                after.get("backstackTarget") == "Messages" and after.get("screen") == "room_timeline" and
                after.get("pinnedListReachable") is False,
                "Task17 unchanged production backstack not proven")
        require(raw.get("observed") == {"screen": "room_timeline", "pinnedListReachable": False},
                "Task17 base actual observation changed")
    else:
        require(kind == "navigation_prefix" and key == "open_loading", "Unknown Task17 entry probe")
        require(before.get("backstackTarget") == "Messages(focusedEventId=null)",
                "Task17 navigation did not start from canonical timeline")
        before_keys, after_keys = before.get("backstackKeys"), after.get("backstackKeys")
        require(isinstance(before_keys, list) and len(before_keys) == 1 and isinstance(after_keys, list) and
                all(isinstance(key, str) and key for key in before_keys + after_keys),
                "Task17 actual navigation key snapshots missing")
        retained = len(after_keys) == 2 and after_keys[0] == before_keys[0] and after_keys[1] != before_keys[0]
        require(after.get("timelineParentRetained") is retained,
                "Task17 navigation parent invariant contradicts actual keys")
        require(after.get("backstackTarget") != "PinnedMessagesList" or after.get("pinnedNodeBuilds") != 1 or not retained,
                "Task17 navigation FAIL has no failed runtime assertion")
        nav = raw.get("navigation", {})
        require(nav.get("after") == after.get("backstackTarget") and nav.get("beforeKeys") == before_keys and
                nav.get("afterKeys") == after_keys and nav.get("timelineParentRetained") is retained,
                "Task17 navigation observations disagree")


def entry_row(spec, probe, path, *, kind):
    raw = json.loads(Path(path).read_text())
    check_actual(raw, kind, spec["key"])
    method = spec["key"] if kind == "base_prefix" else "open_loading_navigation"
    item = artifact(path)
    ids = [f"{POLICY_ID}:{item['sha256']}:{spec['key']}"]
    return {"caseId": spec["caseId"], "key": spec["key"], "traceDigest": spec["traceDigest"],
            "status": "fail", "reason": raw.get("reason", "The actual production Banner click failed to reach the pinned list."),
            "observed": None, "invariantChecks": [], "transitionExecuted": False,
            "checkpoints": raw["checkpoints"], "actualCheckpoints": raw["checkpoints"],
            "productionSources": probe["productionSources"],
            "entryFailureEvidence": {"policyId": POLICY_ID, "kind": kind, "runtimeEvidence": item,
                                     "execution": probe["execution"],
                                     "junit": probe["junit"], "method": method,
                                     "evaluatorSource": probe["evaluatorSource"], "log": probe["log"],
                                     "observationIds": ids}}


def validate_entry_failure(row, report, usedids, contract):
    require((report.get("taskId"), report.get("platform"), report.get("observationMode")) ==
            (TASK, "android", "runtime_state_transition"), "Task17 entry report identity changed")
    specs = [spec for spec in contract["cases"] if spec["caseId"] == row.get("caseId")]
    require(len(specs) == 1, "Task17 canonical case missing")
    spec = specs[0]
    require(row.get("key") == spec["key"] and row.get("traceDigest") == spec["traceDigest"],
            "Task17 entry canonical identity changed")
    require(row.get("status") == "fail" and row.get("observed") is None and
            row.get("invariantChecks") == [] and row.get("transitionExecuted") is False,
            "Task17 entry invented a canonical post-state or invariant")
    evidence = row.get("entryFailureEvidence", {})
    require(evidence.get("policyId") == POLICY_ID, "Unreviewed Task17 entry policy")
    kind = evidence.get("kind")
    execution = json.loads(bound(evidence["execution"]))
    require(execution.get("candidateSource") == report.get("provenance", {}).get("candidateSource"),
            "Task17 probe executed a different candidate directory")
    require(execution.get("kind") == ("base" if kind == "base_prefix" else "navigation"),
            "Task17 execution probe kind changed")
    require(execution.get("command", [None])[0] == str(Path(execution["candidateSource"]) / "gradlew"),
            "Task17 probe command is not the candidate Gradle wrapper")
    require({item["path"]: item for item in execution.get("productionSources", [])} ==
            {item["path"]: item for item in row.get("productionSources", [])},
            "Task17 row differs from executed production source manifest")
    for name in ("junit", "evaluatorSource", "log"):
        require(execution.get(name) == evidence.get(name), "Task17 execution artifact binding changed")
    raw = json.loads(bound(evidence["runtimeEvidence"]))
    check_actual(raw, kind, spec["key"])
    require(row.get("checkpoints") == raw["checkpoints"] == row.get("actualCheckpoints"),
            "Task17 actual checkpoints changed")
    evaluator = "BasePrefixRuntimeTest.kt" if kind == "base_prefix" else "FinalNavigationRuntimeTest.kt"
    require(bound(evidence["evaluatorSource"]) == (HERE / evaluator).read_bytes(),
            "Task17 executed evaluator differs from reviewed evaluator")
    bound(evidence["log"])
    junit = ET.fromstring(bound(evidence["junit"]))
    name = spec["key"] if kind == "base_prefix" else "open_loading_navigation"
    classname = "runtime.task17." + ("BasePrefixRuntimeTest" if kind == "base_prefix" else "FinalNavigationRuntimeTest")
    methods = [node for node in junit.iter("testcase") if node.get("name") == name]
    require(evidence.get("method") == name and len(methods) == 1, "Task17 independent JUnit invocation missing")
    method = methods[0]
    require(method.get("classname") == classname and method.find("error") is None and method.find("skipped") is None,
            "Task17 entry runtime had an execution error")
    if kind == "base_prefix":
        require(method.find("failure") is None, "Task17 base probe did not finish cleanly")
    else:
        failure = method.find("failure")
        require(failure is not None and failure.get("type") in {"java.lang.AssertionError", "org.junit.ComparisonFailure"},
                "Task17 navigation did not fail its preserved assertion")
    provenance = report.get("provenance", {})
    sources = row.get("productionSources", [])
    paths = [source.get("path") for source in sources]
    require(len(paths) == len(set(paths)) and REQUIRED.issubset(paths), "Task17 production source manifest incomplete")
    if kind == "navigation_prefix":
        require(PREFIX + "pinned/list/PinnedMessagesListNode.kt" in paths, "Task17 navigation node source absent")
    top = {source["path"]: source for source in provenance.get("productionSources", [])}
    for source in sources:
        require(top.get(source["path"]) == source, "Task17 row source differs from report")
        snapshot = provenance.get("productionSourceSnapshots", {}).get(source["path"])
        require(snapshot is not None, "Task17 production snapshot absent")
        data = bound(snapshot)
        require(len(data) == source["bytes"] and hashlib.sha256(data).hexdigest() == source["sha256"],
                "Task17 production snapshot differs from executed source")
    item = evidence["runtimeEvidence"]
    ids = [f"{POLICY_ID}:{item['sha256']}:{spec['key']}"]
    require(evidence.get("observationIds") == ids and not usedids.intersection(ids),
            "Task17 entry observations missing or reused")
    usedids.update(ids)
    return {"status": "fail", "caseId": spec["caseId"], "observationIds": ids}
