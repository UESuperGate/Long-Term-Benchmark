#!/usr/bin/env python3
"""Aggregate task-local canonical contracts without changing their semantics."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "benchmark_tasks/extraction_catalog.json"
OUTPUT = ROOT / "state_tests/canonical/new_tasks_cross_platform_contract.json"
BINDINGS = ROOT / "state_tests/canonical/new_tasks_cross_platform_bindings.json"


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    task_ids = [str(item) for item in load(CATALOG)["acceptedTaskIds"]]
    cases: list[dict[str, Any]] = []
    task_bindings: dict[str, Any] = {}
    seen: set[str] = set()
    for task_id in task_ids:
        task_dir = ROOT / "benchmark_tasks" / task_id
        contract = load(task_dir / "transitions.json")
        rules = load(task_dir / "observer_rules.json")
        if contract["taskId"] != task_id or rules["taskId"] != task_id:
            raise ValueError(f"task mismatch for {task_id}")
        for case in contract["cases"]:
            if case["caseId"] in seen:
                raise ValueError(f"duplicate cross-task caseId: {case['caseId']}")
            seen.add(case["caseId"])
            cases.append(case)
        task_bindings[task_id] = {
            "contract": f"../../benchmark_tasks/{task_id}/transitions.json",
            "observerRules": f"../../benchmark_tasks/{task_id}/observer_rules.json",
            "caseIds": [case["caseId"] for case in contract["cases"]],
            "arktsBase": load(task_dir / "task.json")["arkts"]["basePath"],
            "arktsFinal": load(task_dir / "task.json")["arkts"]["finalPath"],
        }
    payload = {
        "schemaVersion": 1,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "owner": "evaluator",
        "description": "Shared Android/ArkTS semantic contracts for extracted Element X tasks 08-18",
        "taskCount": len(task_ids),
        "caseCount": len(cases),
        "cases": cases,
    }
    bindings = {"schemaVersion": 1, "generatedAt": datetime.now(timezone.utc).isoformat(), "tasks": task_bindings}
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    BINDINGS.write_text(json.dumps(bindings, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUTPUT), "bindings": str(BINDINGS), "tasks": len(task_ids), "cases": len(cases)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
