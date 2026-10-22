"""One reviewed evidence exception, not a general navigation score adapter.

Only the immutable final attempt7 predecessor is approved. This module reads
evidence; it never executes candidate code, constructs observations, or clears
the global callback-only quarantine for other reports.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
TASK = "11_room_upgrade_navigation"
KEY = "open_predecessor"
DIRECTORY = ROOT / "state_tests/runtime/android" / TASK / "android11_navigation_followup"
REPORT = DIRECTORY / "loaded_navigation_attempt7.json"
REPORT_SHA = "c4ea803d3894faf1a167b62617eabce264112230676832a8e920d07f5f414348"
CONTRACT = ROOT / "benchmark_tasks" / TASK / "transitions.json"
CONTRACT_SHA = "d570c2955778cbf353ccdc91bcfe3a01624af3b12b2c6000c6c5e00690e174e4"
COMMIT = "426e5de99caac15a44f3d4f27f1ff6e3d4960f84"
TREE = "804cdad7547932ed2f0dcacbf9b35b78bc9d00a0"
LOG_SHA = "190332ecaeb503406bb9bf49fe10cdcf611ba9c174ebcf05359bca170ca0d830"
CONFIG_SHA = "b8ec2f1bb64749ed23843837d3975a958e6af67cc09608f77f2f04fdc94eeacf"
PIXEL_SHA = "a7fae8dea9b23356f9cbeb5a5f4667c867588cad80282ee31f0803a88ade253c"
OWNER = "io.element.android.appnav.LoggedInFlowNode"
CHAIN = (
    "io.element.android.appnav.room.RoomFlowNode",
    "io.element.android.appnav.room.joined.JoinedRoomFlowNode",
    "io.element.android.appnav.room.joined.JoinedRoomLoadedFlowNode",
    "io.element.android.features.messages.impl.MessagesFlowNode",
    "io.element.android.features.messages.impl.MessagesNode",
)
PRESENTER = "io.element.android.features.messages.impl.timeline.TimelinePresenter"


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _bytes(path, digest):
    data = Path(path).read_bytes()
    _require(hashlib.sha256(data).hexdigest() == digest, f"Pinned artifact hash mismatch: {path}")
    return data


def _one(items, condition):
    selected = [item for item in items if condition(item)]
    _require(len(selected) == 1, "Missing/duplicate runtime chain member")
    return selected[0]


def _owner(runtime):
    root = runtime["nodeTree"]
    _require(root["class"] == "runtime.LoadedNavigationTest$TestHost", "Wrong runtime host")
    return _one(root["children"], lambda node: node["class"] == OWNER)


def _route(runtime, room, lifecycle):
    owner = _owner(runtime)
    node = _one(owner["children"], lambda child:
                child["class"] == CHAIN[0] and child["target"] == f"JoinedRoom(roomId={room})")
    targets = (f"JoinedRoom(roomId={room})", "Loaded", "Messages(focusedEventId=null)", "Messages(focusedEventId=null)", None)
    for index, (kind, target) in enumerate(zip(CHAIN, targets)):
        _require(node["class"] == kind and node["target"] == target and node["lifecycle"] == lifecycle,
                 f"Original loaded route/lifecycle missing: {kind}")
        if index + 1 < len(CHAIN):
            node = _one(node["children"], lambda child: child["class"] == CHAIN[index + 1])
    return owner["target"]


def _node_ids(runtime, kind):
    return [event["id"] for event in runtime["construction"]
            if event["kind"] == "nodeConstructed" and event["class"] == kind]


def _check_chain(row, spec):
    """Check runtime records independently of the immutable payload pin."""
    _require(row["key"] == KEY and row["status"] == "pass", "Only passed predecessor evidence is approved")
    _require(row["caseId"] == spec["caseId"] and row["traceDigest"] == spec["traceDigest"], "Canonical row identity mismatch")
    _require(not row.get("unsupportedInvariants") and not row.get("unsupported") and not row.get("scoringExclusion"),
             "Explicit unsupported evidence")
    points = row["checkpoints"]
    _require([p["name"] for p in points] == ["before_setup", "before", "before_click", "after", "back", "cleanup"],
             "Missing/duplicate/reordered click checkpoints")
    setup, before, click, after, back, cleanup = [p["state"] for p in points]
    given = spec["given"]
    current, target = given["currentRoomId"], given["predecessor"]["roomId"]
    last = given["predecessor"]["lastEventId"]
    _require(spec["event"] == {"name": "open_predecessor_room"} and current != target, "Wrong given/event")
    _require(setup["sourceRoom"] == current and setup["targetRoom"] == target, "Canonical given not established")
    metadata = f"PredecessorRoom(roomId={target}, lastEventId={last})"
    for point in (before, after):
        _require(point["predecessorMetadata"] == metadata, "Actual timeline metadata does not retain canonical given")
        _require(point["messagesClass"] == CHAIN[-1] and point["messagesLifecycle"] == "RESUMED", "Wrong Messages lifecycle")
        _require(point["timelineItems"] == [f"Virtual(id={current}/beginning, model=TimelineItemRoomBeginningModel)"],
                 "Production timeline beginning not established")
    _require(click["action"] == "See old messages" and "Role = 'Button'" in click["semanticsTree"]
             and "Actions = [OnClick, RequestFocus]" in click["semanticsTree"]
             and "[See old messages]" in click["semanticsTree"] and "Disabled" not in click["semanticsTree"],
             "Actual eligible UI click evidence missing")
    _require(click["pixels"]["sha256"] == PIXEL_SHA and click["pixels"]["width"] == 411
             and click["pixels"]["height"] == 891, "Wrong source screenshot")
    source_runtime, click_runtime, target_runtime = (point["runtime"] for point in (before, click, after))
    original_route = _route(source_runtime, current, "RESUMED")
    _require(_route(click_runtime, current, "RESUMED") == original_route, "Navigation changed before click")
    destination_route = _route(target_runtime, target, "RESUMED")
    _route(target_runtime, current, "CREATED")
    _require(destination_route.startswith(f"Room(roomIdOrAlias=Id(roomId={target}), serverNames=[], trigger=Timeline,")
             and destination_route != original_route, "Original owner did not push the target Timeline route")
    _require(original_route.startswith(f"Room(roomIdOrAlias=Id(roomId={current}),"), "Wrong original owner route")
    for kind in CHAIN:
        old, clicked, new = (_node_ids(runtime, kind) for runtime in (source_runtime, click_runtime, target_runtime))
        _require(len(old) == 1 and clicked == old and len(new) == 2 and new[:1] == old
                 and len(set(new)) == 2, f"Original distinct node instance evidence missing: {kind}")
    for runtime, room, index in ((source_runtime, current, 0), (click_runtime, current, 0), (target_runtime, target, 1)):
        owner_id = _node_ids(runtime, CHAIN[2])[index]
        _require(runtime["navigation"].startswith(f"AppNavigationState(navigationState=Room(owner={owner_id}, roomId={room}, parentSpace="),
                 "Actual navigation service is not owned by the loaded room")
        _require(runtime["activeRoom"] == room, "Actual active room mismatch")
        _require(any(e["kind"] == "constructed" and e["class"] == PRESENTER for e in runtime["construction"]),
                 "Original TimelinePresenter not constructed")
    _require(after["differentMessagesNode"] is True, "Destination reuses source MessagesNode")
    for point in (before, click, after, back, cleanup):
        runtime = point["runtime"]
        _require(runtime["sessionScopeErrors"] == [] and not any(e["kind"] in ("bindingGap", "graphCleanupError")
                 for e in runtime["construction"]), "Runtime binding/cleanup error")
    calls = target_runtime["sdkCalls"]
    for method in ("getRoomInfoFlow", "getJoinedRoom"):
        _require([c["arguments"] for c in calls if c["port"] == "MatrixClient" and c["method"] == method]
                 == [[current], [target]], "Source/target SDK loading sequence missing")
    _require(any(c["port"] == "JoinedRoom" and c["method"] == "predecessorRoom" and c["roomId"] == current for c in calls),
             "Timeline metadata never read from source SDK room")
    _require(back["restoredOriginalMessagesNode"] is True and back["targetMessagesLifecycle"] == "DESTROYED"
             and back["sourceMessagesLifecycle"] == "RESUMED" and _route(back["runtime"], current, "RESUMED") == original_route,
             "Actual backstack/lifecycle completion missing")
    _require(cleanup["hostLifecycle"] == "DESTROYED" and cleanup["scopeActive"] is False
             and cleanup["runtime"]["activeRoom"] is None
             and cleanup["runtime"]["navigation"] == "AppNavigationState(navigationState=Root, isInForeground=true)",
             "Runtime cleanup not established")
    observed = row["observed"]
    _require(all(_json(observed[k]) == _json(v) for k, v in spec["expected"].items()), "Canonical observation mismatch")
    _require(observed["actualDestination"] == CHAIN[-1] and observed["destinationLifecycle"] == "RESUMED", "Destination observation missing")
    checks = row["invariantChecks"]
    _require(len(checks) == len(spec["invariants"]) == 1 and checks[0]["invariant"] == spec["invariants"][0]
             and checks[0]["status"] == "pass" and checks[0]["evidence"] == {
                 "before": metadata, "after": metadata, "actualPresenter": PRESENTER}, "Invariant lacks actual presenter metadata")


def _check_sources(provenance):
    source = provenance["source"]
    actual_tree = subprocess.check_output(["git", "-C", source, "rev-parse", f"{COMMIT}^{{tree}}"], timeout=30, stderr=subprocess.PIPE).decode().strip()
    _require(actual_tree == TREE, "Immutable commit/tree mismatch")
    records = provenance["productionSources"]
    _require(len(records) == 775, "Incomplete source/resource/catalog manifest")
    requests = "".join(f"{TREE}:{record['path']}\n" for record in records).encode()
    data = subprocess.check_output(["git", "-C", source, "cat-file", "--batch"], input=requests, timeout=60, stderr=subprocess.PIPE)
    offset = 0
    for record in records:
        end = data.index(b"\n", offset)
        header = data[offset:end].split()
        _require(len(header) == 3 and header[1] == b"blob", "Missing immutable production blob")
        length = int(header[2])
        content = data[end + 1:end + 1 + length]
        _require(hashlib.sha256(content).hexdigest() == record["sha256"], f"Production source hash mismatch: {record['path']}")
        offset = end + length + 2
    _require(offset == len(data), "Unexpected source batch output")


def validate_reviewed_predecessor(report, row, contract, *, contract_sha256):
    """Return errors, fail closed. Only [] grants this one quarantine exception.

    Even a normalized copy is not accepted as the approved raw input. No caller
    flag can opt out of byte, source, canonical, or runtime-chain verification.
    """
    try:
        _require(report.get("taskId") == TASK and report.get("role") == "final" and row.get("key") == KEY,
                 "Not the approved final predecessor")
        _require(contract_sha256 == CONTRACT_SHA, "Not the approved canonical contract")
        artifact = report["reportArtifact"]
        _require(Path(artifact["path"]).resolve() == REPORT and artifact["sha256"] == REPORT_SHA, "Not the fixed reviewed report artifact")
        raw_bytes = _bytes(REPORT, REPORT_SHA)
        _require(artifact.get("bytes", len(raw_bytes)) == len(raw_bytes), "Report byte length mismatch")
        raw = json.loads(raw_bytes)
        supplied = {key: value for key, value in report.items() if key != "reportArtifact"}
        _require(_json(supplied) == _json(raw), "Report payload differs from pinned artifact")
        approved_row = _one(raw["semantic"]["cases"], lambda item: item["key"] == KEY)
        _require(_json(row) == _json(approved_row), "Row differs from pinned artifact")
        frozen_contract = json.loads(_bytes(CONTRACT, CONTRACT_SHA))
        _require(_json(contract) == _json(frozen_contract), "Supplied canonical contract differs from pinned bytes")
        spec = _one(contract["cases"], lambda item: item["key"] == KEY)
        _check_chain(row, spec)
        provenance = raw["provenance"]
        _require(provenance["commit"] == COMMIT and provenance["tree"] == TREE and provenance["role"] == "final"
                 and provenance.get("patchSha256") is None, "Wrong immutable role/tree/patch")
        _require(raw["runtimeCompile"]["status"] == "passed" and raw["cleanup"] == {
            "compilerOutput": "temporary directories removed", "jvmBuildLock": "released"}, "Compile/cleanup unavailable")
        _require(provenance["configurationSha256"] == CONFIG_SHA and raw["log"]["sha256"] == LOG_SHA, "Wrong config/log pin")
        _bytes(REPORT.with_suffix(".config.json"), CONFIG_SHA)
        log = _bytes(raw["log"]["path"], LOG_SHA).decode()
        logged = [json.loads(line.removeprefix("RUNTIME_RESULT ")) for line in log.splitlines() if line.startswith("RUNTIME_RESULT ")]
        logged_row = _one(logged, lambda item: item["key"] == KEY)
        for field in ("key", "status", "reason", "checkpoints", "observed", "invariantChecks"):
            _require(_json(logged_row[field]) == _json(row[field]), f"Original JUnit log mismatch: {field}")
        records = (provenance["evaluatorSources"] + provenance["packagingSources"] +
                   [provenance["canonicalContract"], provenance["renderedRunner"], provenance["dependencyPom"]])
        for record in records:
            _bytes(record["path"], record["sha256"])
        click = row["checkpoints"][2]["state"]
        _bytes(click["pixels"]["path"], PIXEL_SHA)
        _check_sources(provenance)
        return []
    except (AttributeError, KeyError, IndexError, TypeError, ValueError, OSError, subprocess.SubprocessError) as error:
        return [f"Reviewed Android11 predecessor rejected: {error}"]
