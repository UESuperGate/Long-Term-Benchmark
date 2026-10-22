#!/usr/bin/env python3
"""Review fixture generator; not a runtime scorer and never infers candidate roles."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.runtime_semantics.task10_native_artifacts import read_native_artifact
from scripts.runtime_semantics.tasks10_11_runtime_evidence import record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("Never overwrite a reviewed closure fixture")
    report = json.loads(args.report.read_text())
    first = report["semantic"]["cases"][0]
    build = json.loads(read_native_artifact(first["nativeArtifacts"]["build"]))
    inventory = json.loads(subprocess.check_output(["node", "-e",
        "const runtime=require('./scripts/runtime_semantics/task10_arkts_strict_runtime.cjs');"
        "console.log(JSON.stringify(runtime.sourceInventory(process.argv[1])))", str(args.source.resolve())], cwd=ROOT))
    if any(inventory[key] != report["provenance"]["sourceInventory"][key] for key in ("files", "sha256")):
        raise ValueError("Reviewed input source differs from actual retained calibration")
    files = []
    for path in sorted(args.source.rglob("*")):
        if path.is_file() and not any(part in {".git", ".hvigor", "build", "oh_modules", "node_modules"}
                                      for part in path.relative_to(args.source).parts):
            files.append({**record(path), "path": path.relative_to(args.source).as_posix()})
    for item in build["production"]:
        if hashlib.sha256((args.source / item["path"]).read_bytes()).hexdigest() != item["sha256"]:
            raise ValueError("Reviewed compiled production closure differs from source")
    native_pair = first["nativeArtifacts"]["layouts"][0]
    tree = read_native_artifact(native_pair)
    projection = json.loads(subprocess.check_output(["node", "-e",
        "const fs=require('node:fs');const guard=require('./scripts/runtime_semantics/task10_arkts_closure_guard.cjs');"
        "console.log(JSON.stringify(guard.projectTree(JSON.parse(fs.readFileSync(0,'utf8')))))"], input=tree, cwd=ROOT))
    fixture = {"schemaVersion": 1, "taskId": "10_media_upload_quality",
        "guardId": "task10.arkts.reviewed-common-closure.v1",
        "scope": "eligibility only; real common preview/caption/send prefix remains mandatory",
        "fullInputInventory": {key: inventory[key] for key in ("files", "sha256")},
        "sourceFiles": files, "compiledProduction": build["production"], "bundleName": build["bundleName"],
        "initialUiProjection": projection, "reviewEvidence": {"report": record(args.report),
            "build": first["nativeArtifacts"]["build"], "initialLayout": native_pair,
            "manifest": record(ROOT / "migrations/10_media_upload_quality/manifest.json")},
        "sourceMatchingDoesNotProduceSemanticVerdicts": True, "roleOrFilenameInference": False}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(fixture, indent=2) + "\n")
    print(json.dumps(record(args.output)))


if __name__ == "__main__":
    main()
