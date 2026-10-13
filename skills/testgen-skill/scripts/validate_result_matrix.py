#!/usr/bin/env python3
"""Validate base/final polarity and an agent's semantic discrimination."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


STATUS = {"pass": "pass", "passed": "pass", "fail": "fail", "failed": "fail", "not_scored": "not_scored"}


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def cases(report: dict[str, Any], label: str, errors: list[str]) -> dict[str, dict[str, str]]:
    rows = report.get("semantic", {}).get("cases", [])
    result: dict[str, dict[str, str]] = {}
    for row in rows:
        case_id = str(row.get("caseId", ""))
        status = STATUS.get(str(row.get("status", "")))
        if not case_id or not status:
            errors.append(f"{label}: invalid semantic row {row!r}")
            continue
        if case_id in result:
            errors.append(f"{label}: duplicate caseId {case_id}")
        result[case_id] = {"status": status, "traceDigest": str(row.get("traceDigest", ""))}
    if not result:
        errors.append(f"{label}: no semantic cases")
    return result


def counts(rows: dict[str, dict[str, str]]) -> dict[str, int]:
    found = Counter(row["status"] for row in rows.values())
    return {"passed": found["pass"], "failed": found["fail"], "notScored": found["not_scored"], "total": len(rows)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--final", type=Path, required=True)
    parser.add_argument("--agent", type=Path, required=True)
    parser.add_argument("--allow-agent-extreme", action="store_true", help="Do not require 0 < agent passes < total")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    reports = {name: load(path) for name, path in (("base", args.base), ("final", args.final), ("agent", args.agent))}
    errors: list[str] = []
    task_ids = {str(report.get("taskId", "")) for report in reports.values()}
    platforms = {str(report.get("platform", "")) for report in reports.values()}
    if "" in task_ids or len(task_ids) != 1:
        errors.append("base, final, and agent must have one matching non-empty taskId")
    if "" in platforms or len(platforms) != 1:
        errors.append("base, final, and agent must have one matching non-empty platform")
    for name, report in reports.items():
        if report.get("role") != name:
            errors.append(f"{name}: role must be {name!r}")
    for metric in ("codeGeneration", "compile"):
        if not isinstance(reports["agent"].get(metric, {}).get("passed"), bool):
            errors.append(f"agent: {metric}.passed must be boolean")
    indexed = {name: cases(report, name, errors) for name, report in reports.items()}
    expected_ids = set(indexed["final"])
    for name, rows in indexed.items():
        if set(rows) != expected_ids:
            errors.append(f"{name}: case IDs differ from final")
    for case_id in sorted(expected_ids):
        digests = {indexed[name].get(case_id, {}).get("traceDigest", "") for name in indexed}
        if "" in digests or len(digests) != 1:
            errors.append(f"{case_id}: missing or mismatched traceDigest")

    summary = {name: counts(rows) for name, rows in indexed.items()}
    total = summary["final"]["total"]
    if summary["base"] != {"passed": 0, "failed": total, "notScored": 0, "total": total}:
        errors.append("base polarity must be 0/N pass and N/N fail")
    if summary["final"] != {"passed": total, "failed": 0, "notScored": 0, "total": total}:
        errors.append("final polarity must be N/N pass")
    agent = summary["agent"]
    if agent["notScored"]:
        errors.append("agent contains not_scored cases")
    if not args.allow_agent_extreme and not (0 < agent["passed"] < total):
        errors.append("agent result is not discriminative; expected 0 < passed < total")

    metrics = {
        "codeGeneration": reports["agent"].get("codeGeneration", {}),
        "compile": reports["agent"].get("compile", {}),
        "semanticTestcase": agent,
    }
    payload = {"valid": not errors, "counts": summary, "benchmarkMetrics": metrics, "errors": errors}
    rendered = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
