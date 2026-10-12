#!/usr/bin/env python3
"""Audit whether archived semantic results came from evaluator-owned evidence."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from semantic_candidate_integrity import audit_candidate


def build_report(manifest: dict[str, Any]) -> dict[str, Any]:
    tasks = []
    for task in manifest.get("tasks") or []:
        candidate = Path(str(task.get("agentResultDir") or ""))
        integrity = audit_candidate(candidate, "android")
        tasks.append({
            "id": task.get("id"),
            "candidate": str(candidate),
            "semanticMetricValid": bool(integrity["valid"]),
            "correctedSemanticStatus": "requires_external_observer" if integrity["valid"] else "not_scored",
            "integrity": integrity,
        })
    return {
        "schemaVersion": 1,
        "generatedAt": datetime.now().astimezone().isoformat(timespec="seconds"),
        "runId": manifest.get("runId"),
        "semanticMetricValid": bool(tasks) and all(task["semanticMetricValid"] for task in tasks),
        "reason": "candidate semantic adapters are not independent evaluator evidence",
        "tasks": tasks,
    }


def write_markdown(report: dict[str, Any], path: Path) -> None:
    lines = [
        "# Semantic Result Validity Correction",
        "",
        f"- Run: `{report.get('runId')}`",
        f"- Semantic metric valid: `{str(report['semanticMetricValid']).lower()}`",
        "- Previous semantic pass counts must not be used when candidate-owned oracle code is detected.",
        "",
        "| Task | Valid | Corrected status | Integrity status |",
        "| --- | --- | --- | --- |",
    ]
    for task in report["tasks"]:
        lines.append(
            f"| {task['id']} | {str(task['semanticMetricValid']).lower()} | "
            f"{task['correctedSemanticStatus']} | {task['integrity']['status']} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--eval-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--markdown", type=Path)
    args = parser.parse_args()
    manifest = json.loads(args.eval_manifest.read_text(encoding="utf-8-sig"))
    report = build_report(manifest)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.markdown:
        write_markdown(report, args.markdown)
    print(args.output)
    return 0 if report["semanticMetricValid"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
