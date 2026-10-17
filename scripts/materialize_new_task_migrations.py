#!/usr/bin/env python3
"""Materialize portable migration manifests, bindings, contracts, and results."""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "benchmark_tasks/extraction_catalog.json"


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def task_ids() -> list[str]:
    return [str(item) for item in load(CATALOG)["acceptedTaskIds"]]


def bindings(task_id: str, contract: dict[str, Any], rules: dict[str, Any]) -> dict[str, Any]:
    rows = []
    for case in contract["cases"]:
        clauses = rules["arkts"]["cases"][case["caseId"]]
        observations = [option["path"] for clause in clauses for option in clause.get("options", [])]
        rows.append({
            "caseId": case["caseId"],
            "traceDigest": case["traceDigest"],
            "fixture": case["given"],
            "eventEntrypoint": case["event"],
            "observations": sorted(set(observations)),
        })
    return {"schemaVersion": 1, "taskId": task_id, "canonicalContract": "../canonical/transitions.json", "cases": rows}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--calibration", type=Path, required=True)
    parser.add_argument("--evaluation", type=Path, required=True)
    parser.add_argument("--task", action="append", choices=task_ids())
    args = parser.parse_args()
    calibration = args.calibration.resolve()
    evaluation = args.evaluation.resolve()
    manifest_path = evaluation / "eval_manifest.json"
    if not manifest_path.exists():
        manifest_path = evaluation / "eval_manifest.partial.json"
    eval_manifest = load(manifest_path)
    evaluation_rows = {
        (row.get("platform"), row.get("taskId")): row
        for row in eval_manifest.get("tasks", [])
    }
    available = {
        key for key, row in evaluation_rows.items()
        if row.get("availability", "available") == "available"
    }
    tasks = args.task or task_ids()
    for task_id in tasks:
        task_dir = ROOT / "benchmark_tasks" / task_id
        task = load(task_dir / "task.json")
        contract = load(task_dir / "transitions.json")
        rules = load(task_dir / "observer_rules.json")
        target = ROOT / "migrations" / task_id
        (target / "android").mkdir(parents=True, exist_ok=True)
        (target / "canonical").mkdir(parents=True, exist_ok=True)
        (target / "arkts").mkdir(parents=True, exist_ok=True)
        (target / "results").mkdir(parents=True, exist_ok=True)
        shutil.copy2(task_dir / "task.json", target / "android/task.json")
        shutil.copy2(task_dir / "transitions.json", target / "canonical/transitions.json")
        write(target / "arkts/bindings.json", bindings(task_id, contract, rules))
        result_sources = {
            "android-base.json": calibration / "reports" / f"android_{task_id}_base.json",
            "android-final.json": calibration / "reports" / f"android_{task_id}_final.json",
            "arkts-base.json": calibration / "reports" / f"arkts_{task_id}_base.json",
            "arkts-final.json": calibration / "reports" / f"arkts_{task_id}_final.json",
            "android-agent.json": evaluation / "reports" / f"android_{task_id}_agent.json",
            "arkts-agent.json": evaluation / "reports" / f"arkts_{task_id}_agent.json",
        }
        for name, source in result_sources.items():
            if name.endswith("-agent.json"):
                platform = name.split("-", 1)[0]
                if (platform, task_id) not in available:
                    (target / "results" / name).unlink(missing_ok=True)
                    continue
            if source.exists():
                shutil.copy2(source, target / "results" / name)
            else:
                (target / "results" / name).unlink(missing_ok=True)
        manifest = {
            "schemaVersion": 1,
            "taskId": task_id,
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            "android": task["android"],
            "arkts": task["arkts"],
            "canonicalContract": "canonical/transitions.json",
            "bindings": "arkts/bindings.json",
            "sourceProjects": {"base": task["arkts"]["basePath"], "final": task["arkts"]["finalPath"]},
            "toolchain": {"openHarmonyApi": 23, "openHarmonySdk": "6.1.0.32", "hvigor": "6.24.5", "opencode": "2.0.20", "model": "minimax-token-plan/MiniMax-M3"},
            "evaluation": {
                "runId": eval_manifest.get("runId"),
                "status": eval_manifest.get("status"),
                "availability": {
                    platform: evaluation_rows.get((platform, task_id), {}).get("availability", "not_run")
                    for platform in ("android", "arkts")
                },
            },
            "results": {name: f"results/{name}" for name in result_sources if (target / "results" / name).exists()},
        }
        write(target / "manifest.json", manifest)
        print(json.dumps({"taskId": task_id, "output": str(target)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
