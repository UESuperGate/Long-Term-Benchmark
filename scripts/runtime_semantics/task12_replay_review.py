"""Independently review current Task12 replay bytes, without a device or a model."""

import argparse
import copy
from pathlib import Path
import re
import time

from . import task12_13_formal_core as core
from . import task12_arkts_replay_v2 as replay
from scripts.run_runtime_transition_matrix import validate_report


def normalize(report):
    result = copy.deepcopy(report)
    for row in result["semantic"]["cases"]:
        for check in row.get("invariantChecks", []):
            if "description" not in check and isinstance(check.get("text"), str):
                check["description"] = check["text"]
    return result


def flatten(tree):
    result = [tree["attributes"]] if "attributes" in tree else []
    for child in tree.get("children", []):
        result.extend(flatten(child))
    return result


def verify_current(path, inventory, cleanup_path, *, deadline):
    report = core.load(path)
    evidence = report["provenance"]["runtimeEvidence"]
    raw_path = replay.checked(evidence["raw"])
    shim = core.load(replay.checked(evidence["build"]))
    build = core.load(replay.checked(shim["applicationBuild"]))
    replay.require(shim["source"] == build["source"] == inventory["source"] and
                   build["passed"] is True and all(build.get(key) is True for key in
                   ("productionUnchanged", "copiedProductionUnchanged", "temporaryProjectRemoved")),
                   "current production compile binding differs")
    files = {item["path"]: item for item in inventory["files"]}
    replay.require(all(files.get(item["path"]) == item for item in build["sources"]) and
                   report["provenance"]["sourceInventorySha256"] == inventory["sha256"],
                   "runtime source differs from frozen reconstructed input")
    hap = build["hap"]
    replay.require(Path(hap["path"]).is_relative_to(path.parent) and not Path(hap["path"]).exists(),
                   "current HAP boundary/removal differs")
    cleanup = core.load(cleanup_path)
    replay.require(cleanup.get("performed") is True and cleanup.get("binaryHashesRecordedBeforeRemoval") is True and
                   cleanup.get("binariesRetained") is False and any(all(item.get(key) == hap[key]
                   for key in ("path", "bytes", "sha256")) for item in cleanup.get("binaryHashes", [])),
                   "missing actual current-run HAP hash-before-delete receipt")
    raw = core.load(raw_path)
    commands = raw["diagnostics"]["commands"]
    for command in commands:
        replay.checked(command["log"])
        allowed = (0, 255) if command["args"][0] in {"uninstall", "fport"} or command["args"][:3] == ["shell", "bm", "dump"] else (0,)
        replay.require(command["exitCode"] in allowed, "current native transport command failed")
    replay.require(sum(command["args"][:2] == ["install", "-r"] for command in commands) == 10 and
                   sum(command["args"][:3] == ["shell", "aa", "start"] for command in commands) == 10,
                   "current ten fresh installs/ability starts missing")
    native = None
    if not report["semantic"]["cases"][0].get("entryFailureEvidence"):
        replay.require(raw.get("nativeProtocol") == "task12.actual-ui-effects.v2" and
                       Path(raw["provenance"]["facts"]["path"]).name == "Task12ActualUiFacts.cjs",
                       "legacy/v1 projections cannot be accepted by invariant metadata normalization")
        replay.require(raw["source"] == inventory["source"] and re.fullmatch("[0-9a-f]{32}", raw["nativeNonce"]),
                       "current native source/nonce binding differs")
        config = core.load(replay.checked(raw["provenance"]["config"]))
        replay.require(config["source"] == inventory["source"] and config["hap"] == hap["path"],
                       "current native configuration differs")
        for key in ("runner", "facts", "contract"):
            replay.checked(raw["provenance"][key])
        for row, original in zip(report["semantic"]["cases"], raw["semantic"]["cases"]):
            replay.require(row == original, "normalized row differs from actual native observation")
            for point in original["checkpoints"]:
                layout = core.load(replay.checked(point["layout"]))
                if point["name"] == "common_start":
                    nodes = flatten(layout)
                    replay.require(any(node.get("id") == "room_details_id" and node.get("text") == "!room:example.org" and
                        node.get("visible") == "true" for node in nodes), "actual common room identity missing")
        native = replay.verify_native(raw_path, replay.CONTRACT, bundle=config["bundle"], deadline=deadline,
                                       log=path.parent / "review-native-recomputation.log")
    checked_report = normalize(report)
    core.validate_runtime_report(checked_report, spec=replay.formal.SPEC, platform="arkts", role=report["role"],
        source=Path(inventory["source"]), inventory=inventory, contract=core.load(replay.CONTRACT),
        lineage=core.calibrator_lineage(replay.formal.SPEC, "arkts"))
    validate_report(checked_report, core.load(replay.CONTRACT))
    return {"validated": True, "currentRunOnly": True, "originalReport": core.file_record(path),
            "native": native, "cleanup": core.file_record(cleanup_path), "standaloneProductionHap": hap,
            "counts": {key: report["semantic"][key] for key in ("passed", "failed", "notScored")}}, checked_report


def review(root):
    root = root.resolve()
    completion = core.load(root / "completion.json")
    replay.require(completion.get("temporarySourcesRemoved") is True and
                   completion.get("elapsedSeconds", 3600) < 3600 and
                   completion.get("protectedOriginalsUnchanged") is True and completion.get("newModelCall") is False,
                   "runtime replay deadline/cleanup/protected-original proof incomplete")
    deadline = time.monotonic() + max(1, 3600 - completion["elapsedSeconds"])
    inventories = core.load(root / "source-inventories.json")
    reconstruction = core.load(root / "reconstruction.json")
    replay.require(inventories["agent"]["sha256"] == reconstruction["sourceInventory"]["sha256"] and
                   reconstruction.get("exactFrozenTreeVerified") is True and
                   reconstruction.get("candidateModifiedByEvaluator") is False,
                   "runtime candidate differs from exact frozen baseline+patch reconstruction")
    result = {"scope": "independent retained current-run native recomputation, not a new runtime/model call",
              "readyCandidate": False, "historicalDeletedHapValidationRelaxed": False,
              "originalReportsOverwritten": False, "roles": []}
    original_formal = root / "agent.replay.json"
    for role in ("base", "final", "agent"):
        path = root / "agent.replay.strict-evidence" / role / "runtime.json"
        proof, checked_report = verify_current(path, inventories[role], path.parent / "cleanup.json", deadline=deadline)
        target = path.parent / "runtime.reviewed.json"
        replay.require(not target.exists(), "refusing existing reviewed report")
        core.write(target, checked_report)
        proof.update(role=role, reviewedReport=core.file_record(target), publicPassed=True)
        result["roles"].append(proof)
    replay.require(result["roles"][0]["counts"] == {"passed": 0, "failed": 10, "notScored": 0} and
                   result["roles"][1]["counts"] == {"passed": 10, "failed": 0, "notScored": 0},
                   "current dynamic exact calibration differs")
    formal = normalize(core.load(original_formal))
    formal["diagnostics"]["calibrationAnchors"] = {role: {**result["roles"][index]["reviewedReport"],
        "counts": result["roles"][index]["counts"]} for index, role in enumerate(("base", "final"))}
    formal["diagnostics"]["metadataRevision"] = {"scope": "invariant description aliases and current dynamic anchor references only",
        "originalReport": core.file_record(original_formal), "newRuntimeExecuted": False}
    validate_report(formal, core.load(replay.CONTRACT))
    target = root / "agent.replay.reviewed.json"
    replay.require(not target.exists(), "refusing existing reviewed formal report")
    core.write(target, formal)
    result.update(readyCandidate=True, formalPublicPassed=True, reviewedFormalReport=core.file_record(target),
                  originalFormalReport=core.file_record(original_formal))
    core.write(root / "current-evidence-review.json", result)
    print({"readyCandidate": True, "counts": [role["counts"] for role in result["roles"]]})
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    review(**vars(parser.parse_args()))
