#!/usr/bin/env python3
"""Validate a transition draft and add stable canonical digests."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


REQUIRED_CASE_FIELDS = ("caseId", "key", "given", "event", "expected")


def canonical(task_id: str, case: dict[str, Any]) -> dict[str, Any]:
    version = case.get('traceSchemaVersion', 1)
    if type(version) is not int or version not in (1, 2):
        raise ValueError('Unsupported traceSchemaVersion')
    semantic = {
        "taskId": task_id,
        "key": case["key"],
        "given": case["given"],
        "event": case["event"],
        "expected": case["expected"],
    }
    if 'setup' in case:
        semantic['setup'] = case['setup']
    if 'setup' in case or version == 2:
        if not isinstance(case.get('invariants'), list):
            raise ValueError('Versioned action-prefix contracts require an invariants list')
        semantic['invariants'] = case['invariants']
    if version == 2:
        semantic['traceSchemaVersion'] = version
    return semantic


def digest(value: dict[str, Any]) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def build(draft: dict[str, Any]) -> dict[str, Any]:
    task_id = draft.get("taskId")
    if not isinstance(task_id, str) or not task_id:
        raise ValueError("taskId must be a non-empty string")
    source_cases = draft.get("cases")
    if not isinstance(source_cases, list) or not source_cases:
        raise ValueError("cases must be a non-empty list")

    case_ids: set[str] = set()
    keys: set[str] = set()
    cases = []
    for index, source in enumerate(source_cases):
        if not isinstance(source, dict):
            raise ValueError(f"case {index} must be an object")
        missing = [field for field in REQUIRED_CASE_FIELDS if field not in source]
        if missing:
            raise ValueError(f"case {index} is missing: {', '.join(missing)}")
        case_id = source["caseId"]
        key = source["key"]
        if not isinstance(case_id, str) or not case_id:
            raise ValueError(f"case {index} has invalid caseId")
        if not isinstance(key, str) or not key:
            raise ValueError(f"case {case_id} has invalid key")
        if case_id in case_ids:
            raise ValueError(f"duplicate caseId: {case_id}")
        if key in keys:
            raise ValueError(f"duplicate key: {key}")
        case_ids.add(case_id)
        keys.add(key)
        case = dict(source)
        case["taskId"] = task_id
        case["traceDigest"] = digest(canonical(task_id, case))
        cases.append(case)

    return {
        **draft,
        "schemaVersion": draft.get('schemaVersion', 1),
        "taskId": task_id,
        "owner": "evaluator",
        "description": draft.get("description", "Platform-neutral state transition contract"),
        "cases": cases,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    payload = build(json.loads(args.input.read_text(encoding="utf-8")))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "taskId": payload["taskId"], "cases": len(payload["cases"])}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
