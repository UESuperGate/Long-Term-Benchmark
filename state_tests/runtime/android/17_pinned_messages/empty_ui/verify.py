"""Verify only the archived task17 final empty-success rendered execution."""
import argparse
import copy
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
sys.path.insert(0, str(ROOT / "scripts/runtime_semantics"))
from android_supplemental import _validate_artifacts, file_record, normalize_slice

REPORT = ROOT / "experiment_results/runtime_transition_20261019/android17_followup/empty-ui/final-v6.json"
REPORT_SHA = "6e439b59370978f7dcbbcac2771931ab2b2578fd13948b6f5ebbf91e0f575867"
CONTRACT = ROOT / "benchmark_tasks/17_pinned_messages/transitions.json"
CONTRACT_SHA = "351bacebd24bd1c95707bfea9e5caa8d4813a087f88606a3571d8c73d168fd93"
COMMIT = "eff868ddf9e1caef8182e55ac59054e81526a68f"
TREE = "0cd8a58632515f8e0f6fb669b02c8b35614d9181"
CASE = "pm_state_003_empty_success"
DIGEST = "0848f056c3d15e7e25ad5d4038e3118286bc6e232124202d066b12027429fd96"
HEADLINE = "Pin important messages so that they can be easily discovered"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def same(left, right):
    return json.dumps(left, sort_keys=True) == json.dumps(right, sort_keys=True)


def validate_data(report, contract):
    """Strict case-specific shape checks, separately exercised by negative tests."""
    require(report["taskId"] == contract["taskId"] == "17_pinned_messages" and report["role"] == "final", "task/role")
    require(report["platform"] == "android" and report["executionEnvironment"] == "host_jvm_robolectric_rendered_compose", "runtime scope")
    require(report["compile"]["passed"] is None and report["compile"]["scope"] == "android_application", "no app compilation claim")
    require(report["runtimeCompile"]["status"] == "passed" and report["status"] == "passed", "slice execution")
    provenance = report["provenance"]
    require(provenance["tree"] == TREE and provenance["commit"] == COMMIT and provenance["role"] == "final", "candidate")
    require(report["contractSha256"] == CONTRACT_SHA, "contract")
    specs = contract["cases"]
    spec = next(case for case in specs if case["caseId"] == CASE)
    require(spec["traceDigest"] == DIGEST and spec["key"] == "empty_success", "reviewed case")
    rows = report["semantic"]["cases"]
    require(len(rows) == len(specs) == 9, "case count")
    require([(r["caseId"], r["traceDigest"]) for r in rows] == [(s["caseId"], s["traceDigest"]) for s in specs], "case identity")
    require(len(report["observations"]) == 1, "one runtime observation")
    raw = report["observations"][0]
    row = next(r for r in rows if r["caseId"] == CASE)
    require(same({k: v for k, v in row.items() if k not in ("caseId", "traceDigest")}, raw), "raw/row mismatch")
    require(row["status"] == "pass" and row["reason"] is None, "successful real execution")
    require(same(row["observed"], spec["expected"]), "complete actual expected fields")
    for other in rows:
        if other["caseId"] != CASE:
            require(other["status"] == "not_scored" and other["observed"] is None and not other["checkpoints"] and not other["invariantChecks"], "no reused evidence")
    checks = row["invariantChecks"]
    require(len(checks) == 1 and checks[0]["invariant"] == spec["invariants"][0] and checks[0]["status"] == "pass" and checks[0]["evidence"], "complete invariant")
    points = row["checkpoints"]
    require([p["name"] for p in points] == ["canonical_given", "pending_original_ui", "empty_original_ui"], "ordered checkpoints")
    given, before, after = [p["state"] for p in points]
    require(same(given["given"], spec["given"]) and same(given["event"], spec["event"]), "canonical given/event")
    require(given["sdkCompletionHeld"] is True and given["fullAppNavigationClaimed"] is False, "held request/scope")
    require(same(given["identities"], before["identities"]) and same(before["identities"], after["identities"]), "same receiver chain")
    require(set(given["identities"]) == {"presenter", "factory", "provider", "timeline"} and all(type(v) is int for v in given["identities"].values()), "receiver identities")
    require((before["state"], before["providerState"], before["factoryEmissions"]) == ("Loading", "Loading", []), "actual loading given")
    require((after["state"], after["providerState"], after["factoryEmissions"]) == ("Empty", "Success", [0]), "actual production success chain")
    for point in (before, after):
        require(point["sdkItemsCount"] == 0 and point["openCalls"] == 1 and point["unexpected"] == [], "controlled SDK calls only")
        require(point["pixels"]["width"] == 411 and point["pixels"]["height"] == 891, "full viewport")
        require("Text = '[Pinned messages]'" in point["semantics"] and "Failed loading messages" not in point["semantics"], "original title/error UI")
    require("ProgressBarRangeInfo =" in before["semantics"] and HEADLINE not in before["semantics"], "rendered loading")
    require("ProgressBarRangeInfo =" not in after["semantics"] and HEADLINE in after["semantics"], "rendered empty")
    require(before["pixels"]["sha256"] != after["pixels"]["sha256"], "different real frames")
    require(before["constructors"] == after["constructors"] and len(after["constructors"]) == 17, "real constructor graph")
    sources = {record["path"] for record in provenance["productionSources"]}
    for cls in after["constructors"]:
        require(any(p.endswith("/" + cls.replace(".", "/") + ".kt") for p in sources), "constructor must have immutable production source: " + cls)
    for name in ("PinnedEventsTimelineProvider", "PinnedMessagesListPresenter", "PinnedMessagesListView", "PinnedMessagesListState", "ActionListPresenter"):
        require(any(p.endswith("/" + name + ".kt") for p in sources), "missing real production " + name)
    expected_evaluators = {str(p) for p in (HERE / "PinnedEmptyUiTest.kt", HERE / "Annotations.kt", HERE.parents[1] / "common/Anvil.kt", HERE.parents[1] / "common/Harness.kt",
        HERE.parents[1] / "08_threads/robolectric/EvidenceRobolectricRunner.java", HERE.parents[1] / "08_threads/robolectric/RobolectricMain.java")}
    require({r["path"] for r in provenance["evaluatorSources"]} == expected_evaluators, "no legacy factory/model/UI stubs")
    calls = after["sdkCalls"]
    require(calls[:len(before["sdkCalls"])] == before["sdkCalls"], "same cumulative boundary trace")
    require(sum(c["method"].startswith("pinnedEventsTimeline") for c in calls) == 1 and any(c["method"] == "getTimelineItems" for c in calls), "actual provider request and collection")
    allowed = {"io.element.android.libraries.featureflag.api.FeatureFlagService", "io.element.android.libraries.matrix.api.room.MatrixRoom", "io.element.android.libraries.matrix.api.timeline.Timeline"}
    require(all(c["port"] in allowed for c in calls), "no executed factory/navigation/preferences shim")
    return row


def verify(report_path=REPORT):
    require(file_record(report_path)["sha256"] == REPORT_SHA, "archived report hash")
    require(file_record(CONTRACT)["sha256"] == CONTRACT_SHA, "canonical contract hash")
    report = json.loads(Path(report_path).read_text())
    contract = json.loads(CONTRACT.read_text())
    row = validate_data(report, contract)
    errors = _validate_artifacts(report)
    require(not errors, "artifact verification: " + "; ".join(errors))
    for point in row["checkpoints"][1:]:
        record = point["state"]["pixels"]
        require(file_record(record["path"])["sha256"] == record["sha256"], "rendered PNG hash")
    for record in report["provenance"]["supplementalMetadataArtifacts"]:
        require(file_record(record["path"])["sha256"] == record["sha256"], "Compose metadata hash")
    generator = ROOT / "scripts/runtime_semantics/android_robolectric_sources.py"
    require(file_record(generator)["sha256"] == report["provenance"]["sourceClosureGeneratorSha256"], "closure generator hash")
    log = Path(report["log"]["path"]).read_text()
    records = [json.loads(line[len("RUNTIME_RESULT "):]) for line in log.splitlines() if line.startswith("RUNTIME_RESULT ")]
    require(same(records, report["observations"]), "actual JVM log observation")
    require('Exception in thread' not in log and 'Caused by:' not in log, "unhandled runtime error")
    verified = copy.deepcopy(report)
    verified["reportArtifact"] = file_record(report_path)
    normalized = normalize_slice(verified, contract, contract_sha256=CONTRACT_SHA)
    require(not normalized["validationErrors"], "normalization errors")
    require([r["caseId"] for r in normalized["semantic"]["cases"] if r["status"] == "pass"] == [CASE], "exactly reviewed case passes normalization")
    normalized["independentVerification"] = {"verifier": file_record(__file__), "rawReport": file_record(report_path),
        "scope": "One original production loading-to-empty Compose slice, not app/Node/navigation/device execution", "primaryModified": False}
    return normalized


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = verify()
    with args.output.open("x") as output:
        output.write(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"pass": 1, "fail": 0, "not_scored": 8, "output": str(args.output)}))
