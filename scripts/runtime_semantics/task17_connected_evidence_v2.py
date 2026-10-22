"""Independent connected-owner checks. Synthetic inputs are never runtime scores."""

from __future__ import annotations

import json
from pathlib import Path

PROTOCOL = "task17.android.connected-roomflow.v2"
MESSAGES = "io.element.android.features.messages.impl.MessagesNode"
LIST = "io.element.android.features.messages.impl.pinned.list.PinnedMessagesListNode"
FLOW = "io.element.android.features.messages.impl.MessagesFlowNode"
PARENT = "io.element.android.appnav.LoggedInFlowNode"
ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "benchmark_tasks/17_pinned_messages/transitions.json"


class EvidenceGap(ValueError):
    pass


def require(value, reason):
    if not value:
        raise EvidenceGap(reason)


def _identity(value):
    return type(value) is int and value > 0


def _frame(frame, episode, activity):
    require(frame.get("episode") == episode and frame.get("activityId") == activity,
            "Cross-episode/activity frame")
    require(isinstance(frame.get("semanticsTree"), str) and frame["semanticsTree"].strip(),
            "Original rendered semantics absent")
    nodes = frame.get("nodes", [])
    require(nodes and len({n.get("nodeId") for n in nodes}) == len(nodes), "Ambiguous node tree")
    by_id = {n["nodeId"]: n for n in nodes}
    for node in nodes:
        require(_identity(node.get("nodeId")) and isinstance(node.get("class"), str), "Invalid node identity")
        if node.get("parentId") is not None:
            require(node["parentId"] in by_id, "Detached node parent")
        seen, cursor = set(), node
        while cursor.get("parentId") is not None:
            require(cursor["nodeId"] not in seen, "Node parent cycle")
            seen.add(cursor["nodeId"])
            cursor = by_id[cursor["parentId"]]
    owner = frame.get("owner", {})
    require(owner.get("nodeId") in by_id and owner.get("nodeClass") == by_id[owner["nodeId"]]["class"],
            "Rendered owner not in actual node tree")
    require(owner.get("nodeClass") in {MESSAGES, LIST}, "Unknown rendered surface owner")
    require(_identity(owner.get("presenterId")) and owner.get("pagePresenterId") == owner["presenterId"],
            "Detached presenter instead of actual node-owned presenter")
    require(owner.get("readback") == "actual_composition_parameter" and
            owner.get("renderFunction") == ("MessagesView" if owner["nodeClass"] == MESSAGES else "PinnedMessagesListView"),
            "State not read from original rendered production view")
    require(_identity(owner.get("providerId")) and _identity(owner.get("roomId")), "Missing SDK/provider identity")
    constructors = [c for c in frame.get("construction", []) if c.get("instanceId") == owner["presenterId"]]
    require(len(constructors) == 1, "Page presenter constructor not bound")
    dependencies = {c.get("name"): c.get("instanceId") for c in constructors[0].get("dependencies", [])}
    require(dependencies.get("navigator") == owner["nodeId"] and dependencies.get("room") == owner["roomId"],
            "Presenter navigator/room not the actual mounted node/SDK room")
    if owner["nodeClass"] == LIST:
        require(dependencies.get("timelineProvider") == owner["providerId"], "Detached list timeline provider")
    else:
        banners = [c for c in frame.get("construction", [])
                   if c.get("instanceId") == dependencies.get("pinnedMessagesBannerPresenter")]
        require(len(banners) == 1 and any(d.get("name") == "pinnedEventsTimelineProvider" and
                d.get("instanceId") == owner["providerId"] for d in banners[0].get("dependencies", [])),
                "Actual messages->banner->provider constructor chain absent")
    require(by_id[owner["nodeId"]].get("lifecycle") in {"STARTED", "RESUMED"}, "Owner is not active")
    ancestors, cursor = [], by_id[owner["nodeId"]]
    while cursor.get("parentId") is not None:
        cursor = by_id[cursor["parentId"]]
        ancestors.append(cursor["class"])
    require(FLOW in ancestors and PARENT in ancestors, "Original MessagesFlow/LoggedInFlow ancestry absent")
    require(isinstance(frame.get("state"), dict), "Actual state snapshot missing")
    return owner


def inspect_episode(raw, *, contract=None):
    """Return observations and obligations only; raw hashes/public admission are separate."""
    contract = contract or json.loads(CONTRACT.read_text())
    require(raw.get("protocol") == PROTOCOL, "Wrong connected evidence protocol")
    require(raw.get("taskId") == contract["taskId"] and raw.get("role") in {"base", "final", "agent"},
            "Wrong task/role identity")
    matches = [c for c in contract["cases"] if c["caseId"] == raw.get("caseId")]
    require(len(matches) == 1 and matches[0]["traceDigest"] == raw.get("traceDigest"), "Canonical case/digest mismatch")
    case = matches[0]
    require(raw.get("canonicalAssertions") == {"expected": case["expected"], "invariants": case["invariants"]},
            "Original canonical assertion set changed")
    episode, activity = raw.get("episode"), raw.get("activityId")
    require(isinstance(episode, str) and episode and _identity(activity), "Missing episode/activity identity")
    frames = raw.get("frames", [])
    names = [f.get("name") for f in frames]
    require(names.count("before") == names.count("after") == 1, "Missing/duplicate primary checkpoints")
    require(names.index("before") < names.index("after"), "Primary checkpoint order reversed")
    require(all(type(f.get("sequence")) is int for f in frames) and
            [f["sequence"] for f in frames] == sorted({f["sequence"] for f in frames}), "Frame ordering is ambiguous")
    before, after = (frames[names.index(name)] for name in ("before", "after"))
    owners = [_frame(f, episode, activity) for f in frames]
    first_owner, last_owner = owners[names.index("before")], owners[names.index("after")]
    calls = raw.get("sdkCalls", [])
    require(not raw.get("bindingErrors") and not raw.get("asyncErrors"), "Unbound SDK/production errors")
    require(all(c.get("episode") == episode and c.get("boundary") == "Matrix SDK" for c in calls),
            "Non-SDK or cross-episode double")
    actions = raw.get("actions", [])
    primary = [a for a in actions if a.get("phase") == "event"]
    sdk_events = case["key"] in {"load_failure", "empty_success", "filled_list"}
    require(primary and all(a.get("episode") == episode for a in primary), "Primary event is cross-episode/absent")
    if sdk_events:
        require(all(a.get("dispatch") == "external_sdk_completion" and a.get("boundary") == "Matrix SDK"
                    for a in primary), "Canonical incoming SDK event was replaced")
        require(any(a.get("phase") == "prefix" and a.get("dispatch") == "compose_original_control"
                    and a.get("eligible") is True and a.get("semanticsBefore") for a in actions),
                "SDK case missing actual UI entry prefix")
    else:
        require(all(a.get("dispatch") == "compose_original_control" and a.get("eligible") is True and
                    a.get("activityId") == activity and a.get("semanticsBefore") for a in primary),
                "No eligible original UI event")
    require(before["sequence"] < primary[0].get("sequence", -1) < after["sequence"], "UI event outside primary window")
    key = case["key"]
    if key in {"open_loading", "view_in_timeline"}:
        require(first_owner["nodeClass"] == (MESSAGES if key == "open_loading" else LIST) and
                last_owner["nodeClass"] == (LIST if key == "open_loading" else MESSAGES),
                "Original route did not change to the canonical target")
        before_parent, after_parent = before.get("parentRoute", {}), after.get("parentRoute", {})
        require(before_parent.get("nodeId") == after_parent.get("nodeId") and
                _identity(before_parent.get("nodeId")), "Parent navigation owner replaced")
        if key == "open_loading":
            require(after.get("timelineParentNodeId") == first_owner["nodeId"] and
                    any(n["nodeId"] == first_owner["nodeId"] for n in after["nodes"]),
                    "Actual timeline parent not retained")
        else:
            focus = after["state"].get("focus", {})
            require(focus.get("eventId") == case["given"]["eventId"] and focus.get("rendered") is True and
                    focus.get("targetControlDisplayed") is True, "Actual timeline focus/render target absent")
            require(after_parent.get("focusedEventId") == focus["eventId"], "Parent target and rendered focus disagree")
    else:
        require(first_owner["nodeId"] == last_owner["nodeId"] and
                first_owner["presenterId"] == last_owner["presenterId"], "Primary transition changed page owner")
    require(first_owner["roomId"] == last_owner["roomId"], "Disconnected SDK room")
    if key != "view_in_timeline":
        require(first_owner["providerId"] == last_owner["providerId"], "Disconnected provider")
    # The producer supplies actual state readbacks, never an 'observed' oracle map.
    return {"caseId": case["caseId"], "before": before, "after": after,
            "canonicalExpected": case["expected"], "canonicalInvariants": case["invariants"],
            "connectedOwnerEstablished": True, "diagnosticOnly": True}
