#!/usr/bin/env python3
"""Bind retained Task10/11 runtime evidence without executing builds or devices."""
from __future__ import annotations

import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import tarfile

from scripts.runtime_semantics.tasks10_11_runtime_evidence import (
    ROOT, attach_child, bind_report, diagnostic_sources, record, require, validate_report,
)

EVIDENCE = ROOT / "experiment_results/runtime_transition_20261020/formal_tasks10_11_source_param_v1"
OUTPUT = EVIDENCE / "handler-accepted-v5"
REPO = ROOT / "_sources/element-x-android"


def immutable_inventory(commit):
    archive = subprocess.check_output([
        "git", "-C", str(REPO), "-c", "filter.lfs.process=", "-c", "filter.lfs.smudge=cat",
        "-c", "filter.lfs.required=false", "archive", commit], env={**os.environ, "GIT_LFS_SKIP_SMUDGE": "1"})
    digest, count = hashlib.sha256(), 0
    ignored = {".git", "build", ".gradle", ".idea", "node_modules", "oh_modules"}
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        for member in sorted(tar.getmembers(), key=lambda member: Path(member.name)):
            if not member.isfile() or any(part in ignored for part in Path(member.name).parts):
                continue
            name, data = member.name.encode(), tar.extractfile(member).read()
            digest.update(len(name).to_bytes(8, "big")); digest.update(name)
            digest.update(len(data).to_bytes(8, "big")); digest.update(data)
            count += 1
    return {"files": count, "sha256": digest.hexdigest()}


def main():
    require(not OUTPUT.exists(), "Refusing to overwrite accepted metadata reports")
    OUTPUT.mkdir(parents=True)
    summary = json.loads((EVIDENCE / "summary.json").read_text())
    accepted = []
    cache = {}
    for item in summary["results"]:
        task, platform, role = item["task"], item["platform"], item["role"]
        task_id = "10_media_upload_quality" if task == 10 else "11_room_upgrade_navigation"
        contract = json.loads((ROOT / "benchmark_tasks" / task_id / "transitions.json").read_text())
        if task == 10 and platform == "arkts":
            name = "final-copy-sanity" if role == "agent" else role
            source_report = EVIDENCE / "task10/arkts/api23-recovered-v2" / (name + ".runtime.json")
            report = json.loads(source_report.read_text())
            report = attach_child(report, contract, source_report.parent / (name + "-artifacts"),
                                  OUTPUT / "task10/arkts" / (role + ".audit"))
        else:
            source_report = EVIDENCE / item["report"]
            require(record(source_report)["sha256"] == item["reportSha256"], "Accepted original report changed")
            report = json.loads(source_report.read_text())
            if platform == "android":
                manifest = json.loads((ROOT / "migrations" / task_id / "manifest.json").read_text())
                ref = manifest["android"]["baseCommit" if role == "base" else "finalCommit"]
                inventory = cache.setdefault(ref, immutable_inventory(ref))
                recorded = report["provenance"]["sourceSnapshot"]["sourceInventory"]
                require(all(recorded[key] == inventory[key] for key in inventory), "Immutable source export mismatch")
                tree = subprocess.check_output(["git", "-C", str(REPO), "rev-parse", ref+"^{tree}"], text=True).strip()
                artifacts = source_report.with_name(source_report.name.replace(".runtime.json", "-artifacts"))
                logs = sorted(artifacts.rglob("*.log"))
                sources = diagnostic_sources(logs, REPO, ref)
                report = bind_report(report, contract, sources=sources, logs=logs, commit=ref, tree=tree)
                report["provenance"]["immutableInputBinding"] = {
                    "repository": str(REPO), "commit": ref, "tree": tree, "sourceInventory": recorded,
                    "verifiedBy": "full git archive inventory; exact executed compiler warning source lines"}
                report["provenance"]["productionSourceCoverage"] = "confirmed_executed_compiler_warning_subset"
            else:
                compact = report
                report = {"schemaVersion": 2, "taskId": task_id, "platform": platform,
                          "role": compact["role"], "target": compact["target"], "source": compact["source"],
                          "observationMode": compact["observationMode"],
                          "compile": compact["acceptedVerdict"]["compile"],
                          "runtimeCompile": compact["acceptedVerdict"]["runtimeCompile"],
                          "semantic": {**compact["acceptedVerdict"]["semantic"], "cases": compact["cases"]},
                          "provenance": compact["provenance"], "elapsedSeconds": compact["elapsedSeconds"],
                          "diagnostics": {"strictRuntime": compact["strictRuntime"]}}
                report["provenance"]["productionSources"] = [s for c in compact["cases"] for s in c["productionSources"]]
        report["provenance"]["acceptedOriginalReport"] = record(source_report)
        report["inputKind"] = "standalone_final_copy_sanity" if role == "agent" else "immutable_calibration"
        report["modelAgentResult"] = False
        validate_report(report, contract)
        target = OUTPUT / f"task{task}" / platform / (role + ".runtime.json")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report, indent=2) + "\n")
        accepted.append({"taskId": task_id, "platform": platform, "role": role,
                         "inputKind": report["inputKind"], "modelAgentResult": False,
                         "report": record(target),
                         "counts": {key: report["semantic"][key] for key in ("total", "passed", "failed", "notScored")},
                         "validatedBy": "scripts.runtime_semantics.tasks10_11_runtime_evidence.validate_report"})
        print(task, platform, role, accepted[-1]["counts"], flush=True)
    (OUTPUT / "accepted_reports.json").write_text(json.dumps({"schemaVersion": 1, "results": accepted}, indent=2)+"\n")


if __name__ == "__main__":
    main()
