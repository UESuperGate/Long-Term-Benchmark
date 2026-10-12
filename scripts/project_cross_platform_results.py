#!/usr/bin/env python3
"""Project platform-specific evidence onto the shared semantic contract."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTRACT = ROOT / "state_tests" / "canonical" / "cross_platform_contract.json"


def combine(statuses: list[str]) -> str:
    if not statuses or "not_scored" in statuses:
        return "not_scored"
    return "passed" if all(status == "passed" for status in statuses) else "failed"


def project_android(report: dict[str, Any], contract: dict[str, Any]) -> list[dict[str, Any]]:
    index = {
        (row["taskId"], row["className"], row["methodName"]): row["semanticStatus"]
        for row in report.get("cases", [])
    }
    rows = []
    for case in contract["cases"]:
        statuses = [
            index.get((case["taskId"], item["className"], item["methodName"]), "not_scored")
            for item in case["androidEvidence"]
        ]
        rows.append({
            "caseId": case["caseId"],
            "taskId": case["taskId"],
            "traceDigest": case["traceDigest"],
            "semanticStatus": combine(statuses),
            "platform": "android",
            "sourceStatuses": statuses,
        })
    return rows


def project_arkts(report: dict[str, Any], contract: dict[str, Any]) -> list[dict[str, Any]]:
    source_rows = report.get("results", report.get("cases", []))
    target_keys = sorted({
        (
            str(row.get("targetId", "arkts")),
            str(row.get("targetRole", "unknown")),
            str(row["taskId"]),
        )
        for row in source_rows if row.get("platform", "arkts") == "arkts"
    })
    rows = []
    for target_id, target_role, task_id in target_keys:
        index = {
            (row["taskId"], row["caseId"]): row.get("semanticStatus", "not_scored")
            for row in source_rows
            if str(row.get("targetId", "arkts")) == target_id
            and str(row.get("targetRole", "unknown")) == target_role
        }
        for case in contract["cases"]:
            if case["taskId"] != task_id:
                continue
            source_case = case["arktsEvidence"]["traceCaseId"]
            rows.append({
                "caseId": case["caseId"],
                "taskId": case["taskId"],
                "traceDigest": case["traceDigest"],
                "semanticStatus": index.get((case["taskId"], source_case), "not_scored"),
                "platform": "arkts",
                "targetId": target_id,
                "targetRole": target_role,
                "sourceTraceCaseId": source_case,
                "sourceTraceDigest": case["arktsEvidence"]["traceDigest"],
                "phaseOrdinals": case["arktsEvidence"]["phaseOrdinals"],
            })
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--platform", choices=("android", "arkts"), required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = json.loads(args.input.read_text(encoding="utf-8"))
    contract = json.loads(args.contract.read_text(encoding="utf-8"))
    rows = project_android(report, contract) if args.platform == "android" else project_arkts(report, contract)
    counts = Counter(row["semanticStatus"] for row in rows)
    payload = {
        "schemaVersion": 1,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "platform": args.platform,
        "contract": str(args.contract.resolve()),
        "counts": {status: counts[status] for status in ("passed", "failed", "not_scored")} | {"total": len(rows)},
        "cases": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "counts": payload["counts"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
