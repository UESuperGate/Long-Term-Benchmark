#!/usr/bin/env python3
"""Diagnose unsupported ArkUI bindings; never generate semantic verdicts."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def record(path: Path) -> dict:
    data = path.read_bytes()
    return {"path": str(path.resolve()), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def common_prefix_binding(nodes: list[dict]) -> dict:
    visible = [node for node in nodes if node.get("visible") == "true"]
    required = {"attachment_caption", "attachment_send"}
    common = all(sum(node.get("id") == name for node in visible) == 1 for name in required)
    extra = [node for node in visible if node.get("id") not in required and
             (node.get("clickable") == "true" or node.get("type") in
              {"Button", "Toggle", "Checkbox", "Radio", "Select", "Slider", "TextInput"})]
    return {"commonControlsVisible": common, "additionalInteractiveControls": [
        {key: node.get(key) for key in ("id", "type", "text", "enabled", "visible", "clickable")}
        for node in extra], "exactCommonOnlyBinding": common and not extra,
        "semanticFeaturePresenceInferred": False}


def audit(report: dict, report_path: Path, patch_path: Path) -> dict:
    if report.get("taskId") != "10_media_upload_quality" or report.get("platform") != "arkts":
        raise ValueError("Task10 ArkTS report required")
    findings = []
    for row in report["semantic"]["cases"]:
        if row.get("transitionExecuted") is not False:
            continue
        for point in row.get("checkpoints", []):
            nodes = point.get("state", {}).get("controls")
            if not nodes:
                continue
            binding = common_prefix_binding(nodes)
            if binding["additionalInteractiveControls"]:
                snapshot = point["actualSnapshot"]
                actual = record(Path(snapshot["path"]))
                if actual != snapshot:
                    raise ValueError("Actual runtime snapshot binding changed")
                findings.append({"caseId": row["caseId"], "checkpoint": point["name"],
                                 "actualSnapshot": snapshot, "binding": binding})
                break
    return {"taskId": report["taskId"], "platform": report["platform"],
            "originalReport": record(report_path), "fixedCandidatePatch": record(patch_path),
            "originalSemantic": {key: value for key, value in report["semantic"].items() if key != "cases"},
            "originalCompile": report.get("compile"), "runtimeCompile": report.get("runtimeCompile"),
            "findings": findings, "semanticScoreUsable": False if findings else None,
            "assessment": "unsupported_entry_binding_not_proven_feature_absence" if findings else
                          "no_additional_control_contradiction_found_not_a_semantic_validation",
            "replacementSemanticScore": None, "semanticScoringPerformed": False,
            "candidateModified": False, "acceptedEvidenceModified": False,
            "centralModified": False, "deviceExecutionStarted": False,
            "requiredFollowup": "Bind the real production entry and all canonical state/invariants; rerun unchanged base/final and fixed candidate."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--patch", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("Refusing to overwrite prior audit")
    result = audit(json.loads(args.report.read_text()), args.report, args.patch)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"affectedCases": len(result["findings"]), "semanticScoreUsable": result["semanticScoreUsable"]}))


if __name__ == "__main__":
    main()
