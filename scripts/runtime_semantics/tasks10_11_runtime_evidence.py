"""Task10/11 evidence binding and independently checked Android entry prefixes.

Source hashes come from executed slice manifests. Historical reports whose raw
manifests were compacted may instead use compiler diagnostics corroborated by
the immutable input blob and its exact diagnostic source line.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys
import subprocess

ROOT = Path(__file__).resolve().parents[2]
TASKS = {"10_media_upload_quality", "11_room_upgrade_navigation"}
POLICY = "tasks10_11.android.common-prefix.v1"
TASK10_ENTRIES = {
    "async_loading": "maxUploadSize|limitState|estimationState",
    "limit_fallback": "maxUploadSize|fallback",
    "image_optimization": "optimizeImages|compressImages",
    "estimate_video_presets": "videoPreset|estimatedSize|canUpload",
    "choose_best_preset": "selectedPreset|selectionState",
    "dismiss_preserves_selection": "selectorOpen|selectedPreset",
    "reject_oversized_preset": "selectorOpen|selectedPreset|sendable",
    "block_when_all_oversized": "fileTooLarge|selectedPreset",
    "background_failure_cleanup": "selectedPreset|mediaOptimizationConfig",
}


def record(path: Path) -> dict:
    data = path.read_bytes()
    return {"path": str(path.resolve()), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def equal(left, right):
    return json.dumps(left, sort_keys=True) == json.dumps(right, sort_keys=True)


def read_record(item: dict) -> bytes:
    path = Path(item["path"])
    data = path.read_bytes()
    require(len(data) == item["bytes"] and hashlib.sha256(data).hexdigest() == item["sha256"],
            f"Runtime evidence hash changed: {path}")
    return data


def logged_rows(log: Path) -> list[dict]:
    return [json.loads(line.split("RUNTIME_RESULT ", 1)[1]) for line in log.read_text().splitlines()
            if line.startswith("RUNTIME_RESULT ")]


def collect_slice_sources(artifact_root: Path) -> list[dict]:
    """Read hashes already emitted by Candidate.read in real executed slices."""
    found = {}
    def visit(value, evidence):
        if isinstance(value, dict):
            for item in value.get("productionSources", value.get("buildProduction", value.get("production", []))):
                if isinstance(item, dict) and item.get("path") and item.get("sha256"):
                    found[(item["path"], item["sha256"])] = {**item, "runtimeSlice": evidence}
            for key, child in value.items():
                if key != "productionSources":
                    visit(child, evidence)
        elif isinstance(value, list):
            for child in value:
                visit(child, evidence)
    for path in sorted(artifact_root.rglob("*.json")):
        try:
            value = json.loads(path.read_text())
        except (ValueError, UnicodeError):
            continue
        if isinstance(value, dict) and (value.get("runtimeCompile", {}).get("passed") is True or
                                       value.get("runtimeCompile", {}).get("status") == "passed" or
                                       value.get("status") == "passed"):
            visit(value, record(path))
    return list(found.values())


def attach_child(report: dict, contract: dict, artifact_root: Path, retained: Path) -> dict:
    """Finish metadata while real slice reports still exist, before cleanup."""
    sources = collect_slice_sources(artifact_root)
    if not sources:
        sources = report.get("provenance", {}).get("productionSources", []) or [
            source for row in report["semantic"]["cases"] for source in row.get("productionSources", [])]
    require(sources, "Executed runtime slices did not provide productionSources")
    result = copy.deepcopy(report)
    retained.mkdir(parents=True, exist_ok=True)
    manifests = {}
    for source in sources:
        manifest = source.get("runtimeSlice")
        if manifest:
            identity = manifest["path"], manifest["sha256"]
            if identity not in manifests:
                target = retained / f"slice-{len(manifests)}.manifest.json"
                target.write_bytes(read_record(manifest))
                manifests[identity] = record(target)
            source["runtimeSlice"] = manifests[identity]
    result.setdefault("provenance", {})["productionSources"] = sources
    for row in result["semantic"]["cases"]:
        for check in row.get("invariantChecks", []):
            if not check.get("description"):
                check["description"] = check.get("invariant", check.get("text"))
    if result["platform"] == "arkts" and result["taskId"] == "10_media_upload_quality":
        device_file = artifact_root / "device/report.json"
        require(device_file.is_file(), "Actual Task10 device report missing")
        device = json.loads(device_file.read_text())
        device_rows = {row["caseId"]: row for row in device["semantic"]["cases"]}
        for case_index, row in enumerate(result["semantic"]["cases"]):
            raw = device_rows[row["caseId"]]
            for point_index, point in enumerate(row.get("checkpoints", [])):
                label = point.get("sourceName", point.get("name"))
                actual = next((p for p in raw["checkpoints"] if p["name"] == label), None)
                require(actual and actual.get("layout"), "Actual Task10 checkpoint layout missing")
                data = read_record(actual["layout"])
                target = retained / f"ui-{case_index}-{point_index}.snapshot.json"
                target.write_bytes(data)
                point["actualSnapshot"] = record(target)
                point["state"] = {"controls": _layout_nodes(json.loads(data))}
    for case_index, row in enumerate(result["semantic"]["cases"]):
        for point_index, point in enumerate(row.get("checkpoints", [])):
            snapshot = point.get("actualSnapshot")
            if snapshot:
                target = retained / f"actual-{case_index}-{point_index}.snapshot.json"
                target.write_bytes(read_record(snapshot))
                point["actualSnapshot"] = record(target)
                if result["taskId"] == "11_room_upgrade_navigation" and result["platform"] == "arkts":
                    frame = json.loads(target.read_text())["state"]
                    production = frame.get("state")
                    if not isinstance(production, dict):
                        production = frame.get("stateAfter")
                    require(isinstance(production, dict) and production, "Actual Task11 snapshot lost production state")
                    point["state"] = {"production": production, "controls": frame["controls"],
                                      "routeName": frame.get("routeName"), "windowId": frame.get("windowId"),
                                      "viewport": frame.get("viewport")}
    if result["platform"] == "android":
        snapshot = result["provenance"].get("sourceSnapshot", {})
        if any(row.get("transitionExecuted") is False or row.get("entryFailureEvidence")
                                             for row in result["semantic"]["cases"]):
            logs = []
            for index, source in enumerate(sorted(artifact_root.rglob("*.log"))):
                if not logged_rows(source):
                    continue
                target = retained / f"runtime-{index}.log"
                shutil.copyfile(source, target)
                logs.append(target)
            result = bind_report(result, contract, sources=sources, logs=logs,
                                 commit=snapshot.get("snapshotCommit", ""), tree=snapshot.get("snapshotTree", ""))
        else:
            result["provenance"].update(commit=snapshot.get("snapshotCommit"), tree=snapshot.get("snapshotTree"))
    elif result["taskId"] == "10_media_upload_quality" and any(
            row.get("transitionExecuted") is False or row.get("entryFailureEvidence")
            for row in result["semantic"]["cases"]):
        device = artifact_root / "device/report.json"
        require(device.is_file(), "Task10 ArkTS actual base device report missing")
        raw = json.loads(device.read_text())
        copied = retained / "base.device.json"
        for index, row in enumerate(raw["semantic"]["cases"]):
            for point_index, point in enumerate(row["checkpoints"]):
                layout = point["layout"]
                contents = read_record(layout)
                target = retained / f"layout-{index}-{point_index}.json"
                target.write_bytes(contents)
                point["layout"] = record(target)
        copied.write_text(json.dumps(raw, indent=2) + "\n")
        result = bind_arkts_base(result, contract, record(copied))
    return result


def _layout_nodes(value):
    if not isinstance(value, dict):
        return []
    return [value.get("attributes", {})] + [node for child in value.get("children", []) for node in _layout_nodes(child)]


def bind_arkts_base(report: dict, contract: dict, device_record: dict) -> dict:
    result = copy.deepcopy(report)
    device = json.loads(read_record(device_record))
    require(device.get("status") == "passed" and device.get("role") == report["role"], "Task10 common-prefix device execution incomplete")
    for row, spec in zip(result["semantic"]["cases"], contract["cases"]):
        raw = next(r for r in device["semantic"]["cases"] if r["caseId"] == spec["caseId"])
        row.update(observed=None, invariantChecks=[], unevaluatedInvariants=spec.get("invariants", []))
        row["entryFailureEvidence"] = {
            "policyId": POLICY, "implementationSha256": record(Path(__file__))["sha256"],
            "device": device_record, "sourceInventory": result["provenance"]["sourceInventory"],
            "role": report["role"], "contractSha256": result["provenance"]["contract"]["sha256"],
            "positiveControlCompleted": True,
        }
    return result


def diagnostic_sources(logs: list[Path], repository: Path, commit: str) -> list[dict]:
    """Recover only compiled production paths corroborated by warning source lines."""
    paths = subprocess.check_output(["git", "-C", str(repository), "ls-tree", "-r", "--name-only", commit], text=True).splitlines()
    candidates = [p for p in paths if "/src/main/" in p and p.endswith(".kt")]
    found = {}
    pattern = re.compile(r"^(.*\.kt):(\d+):\d+: warning:")
    for log in logs:
        lines = log.read_text().splitlines()
        for index, line in enumerate(lines):
            match = pattern.match(line)
            if not match:
                continue
            filename = re.sub(r"^\d+_", "", Path(match[1]).name)
            line_number = int(match[2])
            matched = []
            for path in (p for p in candidates if Path(p).name == filename):
                data = subprocess.check_output(["git", "-C", str(repository), "show", f"{commit}:{path}"])
                source_lines = data.decode().splitlines()
                if not 0 < line_number <= len(source_lines):
                    continue
                source_line = source_lines[line_number - 1].strip()
                if not source_line or not any(source_line == value.strip() for value in lines[index+1:index+14]):
                    continue
                item = {"path": path, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
                        "origin": "executed_compiler_diagnostic_corroborated_by_immutable_blob",
                        "compilerLog": record(log), "diagnostic": line, "sourceLine": line_number,
                        "repository": str(repository.resolve()), "commit": commit}
                matched.append(item)
            if len(matched) == 1:
                item = matched[0]
                found[(item["path"], item["sha256"])] = item
    require(found, "No actual production source could be recovered from executed slice diagnostics")
    return list(found.values())


def _prefix(raw: dict, spec: dict, task: str) -> None:
    states = {p["name"]: p.get("state", {}) for p in raw.get("checkpoints", [])}
    if task == "10_media_upload_quality":
        require(raw.get("status") == "pass", "Task10 common positive-control JUnit did not pass")
        observed = raw.get("observed", {})
        require(equal(observed.get("positiveControl"), {
            "previewRendered": True, "caption": "demo", "codecCalls": 1, "uploadCalls": 1,
            "uploadCaption": "demo", "doneCalls": 1, "cleanupCalls": 1, "preparedMediaExists": False}),
            "Task10 real preview/send/cleanup positive control missing")
        require(observed.get("requiredEntryPresent") is False and
                observed.get("requiredEntry") == TASK10_ENTRIES[spec["key"]],
                "Task10 required version-bounded entry was not observed absent")
        require({"production_preprocess_boundary", "common_preview_positive_control", "production_timeline_send",
                 "base_runtime_feature_surface"} <= states.keys(), "Task10 runtime prefix incomplete")
        require(states["base_runtime_feature_surface"].get("requiredEntryPresent") is False,
                "Task10 runtime entry inventory disagrees")
        return
    require(raw.get("status") == "fail", "Task11 actual prefix assertion did not fail")
    require({"common_start", "post_event"} <= states.keys(), "Task11 common-state runtime prefix incomplete")
    before, after = states["common_start"], states["post_event"]
    require(equal(after.get("event"), spec["event"]), "Task11 real event differs from canonical event")
    require(equal(before.get("given", before.get("canonicalGiven")), spec["given"]),
            "Task11 canonical inputs were not established")
    key = spec["key"]
    if key in {"tombstone_is_read_only", "open_successor"}:
        require(before.get("actualRoomInfo", {}).get("successorRoomId") == "!new:example.org",
                "Actual base successor input absent")
        positive = before.get("positiveControls", {})
        require(positive.get("historyVisible") == ["Earlier message"] and
                any(p.get("enabled") is True for p in positive.get("composerEditors", [])),
                "Actual MessagesView history/composer positive control missing")
        if key == "tombstone_is_read_only":
            require(after.get("successorProjectionPresent") is False, "Base successor projection not absent")
        else:
            require(after.get("successorEntryPresent") is False and
                    after.get("positiveControl", {}).get("roomDetailsClicks") == ["!old:example.org"],
                    "Same-view room-details click positive control missing")
    elif key == "room_list_tombstone_preview":
        require(before.get("clickedRoomId") == "!old:example.org" and
                before.get("ordinaryPreview") == "Earlier message" and after.get("isTombstoned") is False,
                "Actual room-list click/preview positive control missing")
    elif key == "map_predecessor_metadata":
        require(equal(before.get("externalPredecessorBoundary"), spec["given"]["predecessor"]) and
                before.get("positiveControls", {}).get("name") == "Replacement room" and
                after.get("projectionEntryPresent") is False, "Actual timeline mapping positive control missing")
    else:
        require(before.get("positiveControls", {}).get("ordinaryBeginningVisible") is True,
                "Actual room-beginning positive control missing")
        field = "predecessorBannerVisible" if key == "predecessor_banner" else "predecessorActionPresent"
        require(after.get(field) is False, "Expected missing room-beginning entry not observed")


def bind_report(report: dict, contract: dict, *, sources: list[dict], logs: list[Path],
                commit: str, tree: str) -> dict:
    """Create a versioned metadata envelope, retaining original runtime verdicts."""
    result = copy.deepcopy(report)
    require(result["taskId"] in TASKS and sources, "Task10/11 executed source closure required")
    provenance = result.setdefault("provenance", {})
    provenance.update(productionSources=sources, commit=commit, tree=tree,
                      entryPolicyImplementation=record(Path(__file__)))
    contract_file = ROOT / "benchmark_tasks" / result["taskId"] / "transitions.json"
    require(equal(json.loads(contract_file.read_text()), contract), "Canonical contract binding mismatch")
    provenance["contract"] = record(contract_file)
    for row, spec in zip(result["semantic"]["cases"], contract["cases"]):
        if result["role"] not in {"base", "agent"} or result["platform"] != "android" or not row.get("entryFailureEvidence"):
            continue
        matches = [(log, raw) for log in logs for raw in logged_rows(log) if raw.get("key") == spec["key"]]
        require(len(matches) == 1, "Missing or ambiguous independently logged base observation")
        log, raw = matches[0]
        _prefix(raw, spec, result["taskId"])
        row.update(observed=None, invariantChecks=[], unevaluatedInvariants=spec.get("invariants", []),
                   transitionExecuted=False, checkpoints=raw["checkpoints"], status="fail")
        row["entryFailureEvidence"] = {
            "policyId": POLICY, "implementationSha256": provenance["entryPolicyImplementation"]["sha256"],
            "positiveControlCompleted": True, "log": record(log), "raw": raw,
            "role": result["role"], "contractSha256": provenance["contract"]["sha256"],
            "commit": commit, "tree": tree,
            "sourceInventory": provenance.get("sourceSnapshot", {}).get("sourceInventory"),
        }
    return result


def validate_entry_failure(row: dict, report: dict, used_observation_ids: set,
                           *, contract: dict) -> dict:
    _validate_sources(report)
    if report.get("taskId") == "10_media_upload_quality" and report.get("platform") == "arkts":
        return _validate_arkts_entry(row, report, used_observation_ids, contract)
    require(report.get("taskId") in TASKS and report.get("platform") == "android" and
            report.get("role") in {"base", "agent"}, "Task10/11 Android entry policy role/task/platform mismatch")
    spec = next((c for c in contract["cases"] if c["caseId"] == row["caseId"]), None)
    require(spec is not None and row.get("traceDigest") == spec["traceDigest"], "Entry contract identity mismatch")
    evidence, provenance = row.get("entryFailureEvidence", {}), report["provenance"]
    require(evidence.get("policyId") == POLICY and evidence.get("implementationSha256") == record(Path(__file__))["sha256"],
            "Entry policy implementation changed")
    require(evidence.get("role") == report["role"] and evidence.get("contractSha256") == provenance["contract"]["sha256"],
            "Entry role/contract binding mismatch")
    require(equal(json.loads(read_record(provenance["contract"])), contract), "Entry canonical contract changed")
    for name in ("commit", "tree"):
        require(evidence.get(name) == provenance.get(name) and bool(provenance.get(name)),
                "Entry immutable candidate tree/commit mismatch")
    require(equal(evidence.get("sourceInventory"), provenance.get("sourceSnapshot", {}).get("sourceInventory")),
            "Entry source inventory changed")
    logged = [json.loads(line.split("RUNTIME_RESULT ", 1)[1])
              for line in read_record(evidence["log"]).decode().splitlines() if line.startswith("RUNTIME_RESULT ")]
    raw = evidence["raw"]
    require(sum(equal(raw, item) for item in logged) == 1 and raw.get("key") == spec["key"],
            "Entry raw observation differs from execution log")
    _prefix(raw, spec, report["taskId"])
    require(row.get("status") == "fail" and row.get("observed") is None and row.get("invariantChecks") == [] and
            row.get("transitionExecuted") is False and equal(row.get("checkpoints"), raw["checkpoints"]) and
            equal(row.get("unevaluatedInvariants"), spec.get("invariants", [])),
            "Entry failure invented post-state or evaluated invariants")
    observation_id = evidence["log"]["sha256"] + ":" + spec["caseId"]
    require(observation_id not in used_observation_ids, "Base entry observation reused")
    used_observation_ids.add(observation_id)
    return {"status": "fail", "caseId": spec["caseId"], "observationIds": [observation_id]}


def _validate_arkts_entry(row, report, used, contract):
    evidence, provenance = row["entryFailureEvidence"], report["provenance"]
    require(report.get("role") in {"base", "agent"} and evidence.get("role") == report["role"], "ArkTS entry role mismatch")
    require(evidence.get("policyId") == POLICY and evidence.get("implementationSha256") == record(Path(__file__))["sha256"],
            "ArkTS entry policy changed")
    require(equal(json.loads(read_record(provenance["contract"])), contract) and
            evidence.get("contractSha256") == provenance["contract"]["sha256"], "ArkTS entry contract mismatch")
    require(equal(evidence.get("sourceInventory"), provenance.get("sourceInventory")), "ArkTS candidate inventory mismatch")
    device = json.loads(read_record(evidence["device"]))
    require(device.get("status") == "passed" and device.get("role") == report["role"] and
            device.get("taskId") == report["taskId"], "Actual device entry execution mismatch")
    raw = next(r for r in device["semantic"]["cases"] if r["caseId"] == row["caseId"])
    observed = raw["observed"]
    require(raw["traceDigest"] == row["traceDigest"] and raw["status"] == "fail" and
            observed.get("commonPreviewVisible") is True and observed.get("originalMediaSendCompleted") is True,
            "Actual device common preview/send positive control missing")
    missing = observed.get("missingEntrypointsBeforePositiveControl")
    require(missing and missing == observed.get("missingEntrypointsAfterPositiveControl"), "Missing required entry changed")
    points = raw["checkpoints"]
    require([p["name"] for p in points] == ["reachable_common_base", "caption_entered", "original_media_positive_control_done"],
            "Actual device prefix checkpoint sequence mismatch")
    layouts = [_layout_nodes(json.loads(read_record(p["layout"]))) for p in points]
    for nodes in layouts:
        require(not any(n.get("visible") == "true" and n.get("id") in missing for n in nodes), "Required entry was visible")
    require(any(n.get("id") == "attachment_caption" and n.get("text") == observed["caption"] for n in layouts[1]),
            "Caption was not entered through real UI")
    require(any(n.get("text") == "Send state: done" and n.get("visible") == "true" for n in layouts[2]),
            "Actual original-media send did not finish")
    spec = next(c for c in contract["cases"] if c["caseId"] == row["caseId"])
    require(row.get("observed") is None and row.get("invariantChecks") == [] and row.get("transitionExecuted") is False and
            equal(row.get("unevaluatedInvariants"), spec["invariants"]), "ArkTS entry invented post-state/invariants")
    observation_id = evidence["device"]["sha256"] + ":" + row["caseId"]
    require(observation_id not in used, "ArkTS entry observation reused")
    used.add(observation_id)
    return {"status": "fail", "observationIds": [observation_id]}


def validate_report(report: dict, contract: dict) -> None:
    """Parent can route Tasks10/11 here, or route only validate_entry_failure."""
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from scripts.run_runtime_transition_matrix import validate_report as shared_validate
    require(report.get("taskId") in TASKS, "Unsupported Task10/11 validator task")
    rows = report["semantic"]["cases"]
    require([(r["caseId"], r["traceDigest"]) for r in rows] ==
            [(s["caseId"], s["traceDigest"]) for s in contract["cases"]], "Canonical row identity/order mismatch")
    require(report.get("observationMode") == "runtime_state_transition", "Runtime mode required")
    require(report.get("taskId") == contract["taskId"], "Task identity mismatch")
    if report["taskId"] == "11_room_upgrade_navigation" and report.get("platform") == "arkts":
        for row in rows:
            for point in row.get("checkpoints", []):
                require(isinstance(point.get("state", {}).get("production"), dict) and point.get("actualSnapshot"),
                        "Task11 historical hash-only checkpoint is partial; actual snapshots are required")
                frame = json.loads(read_record(point["actualSnapshot"]))["state"]
                production = frame.get("state") if isinstance(frame.get("state"), dict) else frame.get("stateAfter")
                require(equal(point["state"]["production"], production) and
                        equal(point["state"]["controls"], frame.get("controls")), "Task11 actual snapshot differs from inline state")
    _validate_sources(report)
    shared_validate(report, contract)


def _validate_sources(report):
    sources = report.get("provenance", {}).get("productionSources", [])
    require(sources or all(row.get("productionSources") for row in report["semantic"]["cases"]),
            "Actual executed production sources required")
    for source in sources:
        if source.get("runtimeSlice"):
            manifest = json.loads(read_record(source["runtimeSlice"]))
            def contains(value):
                if isinstance(value, dict):
                    if value.get("path") == source["path"] and value.get("sha256") == source["sha256"]:
                        return True
                    return any(contains(child) for child in value.values())
                return isinstance(value, list) and any(contains(child) for child in value)
            require(contains(manifest), "Production source is not in its executed slice manifest")
        if source.get("origin") != "executed_compiler_diagnostic_corroborated_by_immutable_blob":
            continue
        binding = report.get("provenance", {}).get("immutableInputBinding")
        require(binding and source["commit"] == binding["commit"] and
                source["repository"] == binding["repository"], "Compiled source belongs to a different immutable candidate")
        log = read_record(source["compilerLog"]).decode()
        require(source["diagnostic"] in log.splitlines(), "Executed compiler diagnostic changed")
        data = subprocess.check_output(["git", "-C", source["repository"], "show",
                                        source["commit"] + ":" + source["path"]])
        require(len(data) == source["bytes"] and hashlib.sha256(data).hexdigest() == source["sha256"],
                "Executed production blob hash mismatch")
        require(data.decode().splitlines()[source["sourceLine"] - 1].strip() in
                [line.strip() for line in log.splitlines()], "Compiler diagnostic source line changed")
    binding = report.get("provenance", {}).get("immutableInputBinding")
    if binding:
        prov = report["provenance"]
        require(prov.get("commit") == binding["commit"] and prov.get("tree") == binding["tree"],
                "Immutable input tree/commit mismatch")
        require(equal(binding["sourceInventory"], prov["sourceSnapshot"]["sourceInventory"]),
                "Immutable input inventory mismatch")
        actual = subprocess.check_output(["git", "-C", binding["repository"], "rev-parse",
                                          binding["commit"] + "^{tree}"], text=True).strip()
        require(actual == binding["tree"], "Immutable Git tree differs")
