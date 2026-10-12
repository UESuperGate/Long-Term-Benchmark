#!/usr/bin/env python3
"""Summarize an Android run with the three benchmark metrics."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BINDINGS = ROOT / "state_tests" / "bindings"


def rate(passed: int, total: int) -> float:
    return round(passed / total, 6) if total else 0.0


def metric(passed: int, total: int) -> dict[str, int | float]:
    return {"passed": passed, "total": total, "rate": rate(passed, total)}


def semantic_metric(passed: int, scored: int, expected: int) -> dict[str, int | float | bool | None]:
    complete = scored == expected
    return {
        "passed": passed,
        "total": scored,
        "expected": expected,
        "rate": rate(passed, scored) if scored else None,
        "available": complete,
    }


def binding_case_counts(task_ids: set[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for task_id in sorted(task_ids):
        path = BINDINGS / f"{task_id}.binding.json"
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        counts[task_id] = len(data.get("cases") or [])
    return counts


def summarize(
    eval_manifest: dict[str, Any],
    semantic_report: dict[str, Any],
    case_counts: dict[str, int],
) -> dict[str, Any]:
    tasks = list(eval_manifest.get("tasks") or [])
    task_ids = {str(task["id"]) for task in tasks}
    rows = [
        row
        for row in semantic_report.get("results") or []
        if row.get("platform") == "android"
        and row.get("targetRole") == "agent_result"
        and row.get("taskId") in task_ids
    ]
    row_by_case = {(str(row["taskId"]), str(row["caseId"])): row for row in rows}

    per_task: list[dict[str, Any]] = []
    for task in tasks:
        task_id = str(task["id"])
        expected_cases = int(case_counts[task_id])
        task_rows = [row for (row_task, _), row in row_by_case.items() if row_task == task_id]
        scored_rows = [row for row in task_rows if row.get("semanticStatus") in {"passed", "failed"}]
        semantic_passed = sum(row.get("semanticStatus") == "passed" for row in scored_rows)
        per_task.append(
            {
                "id": task_id,
                "codeGeneration": metric(int(bool(task.get("codeGenerated"))), 1),
                "compile": metric(int(task.get("buildExit") == 0), 1),
                "semanticTestcase": semantic_metric(semantic_passed, len(scored_rows), expected_cases),
            }
        )

    expected_total = sum(case_counts[task_id] for task_id in task_ids)
    scored_rows = [row for row in row_by_case.values() if row.get("semanticStatus") in {"passed", "failed"}]
    semantic_passed = sum(row.get("semanticStatus") == "passed" for row in scored_rows)
    status_counts = Counter(str(row.get("semanticStatus") or "missing") for row in rows)
    strict_counts = Counter(str(row.get("strictStatus") or "missing") for row in rows)
    return {
        "schemaVersion": 1,
        "generatedAt": datetime.now().astimezone().isoformat(timespec="seconds"),
        "runId": eval_manifest.get("runId"),
        "platform": "android",
        "benchmarkMetrics": {
            "codeGeneration": metric(sum(bool(task.get("codeGenerated")) for task in tasks), len(tasks)),
            "compile": metric(sum(task.get("buildExit") == 0 for task in tasks), len(tasks)),
            "semanticTestcase": semantic_metric(semantic_passed, len(scored_rows), expected_total),
        },
        "tasks": per_task,
        "diagnostics": {
            "agentTimeouts": sum(bool(task.get("agentTimedOut")) for task in tasks),
            "semanticRowsObserved": len(row_by_case),
            "semanticRowsExpected": expected_total,
            "semanticStatusCounts": dict(sorted(status_counts.items())),
            "strictStatusCounts": dict(sorted(strict_counts.items())),
        },
    }


def write_markdown(summary: dict[str, Any], path: Path) -> None:
    metrics = summary["benchmarkMetrics"]
    lines = [
        "# Android Benchmark Summary",
        "",
        "| Metric | Passed | Total | Rate |",
        "| --- | ---: | ---: | ---: |",
    ]
    labels = {
        "codeGeneration": "Code generation",
        "compile": "Compile",
        "semanticTestcase": "Semantic testcase",
    }
    for key in ("codeGeneration", "compile", "semanticTestcase"):
        value = metrics[key]
        rendered_rate = f"{value['rate']:.2%}" if value["rate"] is not None else "N/A"
        rendered_total = str(value["total"])
        if key == "semanticTestcase" and not value.get("available", True):
            rendered_total = f"{value['total']} scored / {value['expected']} expected"
        lines.append(f"| {labels[key]} | {value['passed']} | {rendered_total} | {rendered_rate} |")
    lines.extend(["", "Diagnostics are retained in the JSON output and are not benchmark metrics."])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--eval-manifest", type=Path, required=True)
    parser.add_argument("--semantic-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--markdown", type=Path)
    args = parser.parse_args()

    eval_manifest = json.loads(args.eval_manifest.read_text(encoding="utf-8-sig"))
    semantic_report = json.loads(args.semantic_report.read_text(encoding="utf-8-sig"))
    task_ids = {str(task["id"]) for task in eval_manifest.get("tasks") or []}
    summary = summarize(eval_manifest, semantic_report, binding_case_counts(task_ids))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.markdown:
        args.markdown.parent.mkdir(parents=True, exist_ok=True)
        write_markdown(summary, args.markdown)
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
