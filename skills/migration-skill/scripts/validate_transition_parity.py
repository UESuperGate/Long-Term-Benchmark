#!/usr/bin/env python3
"""Verify Android and ArkTS contracts bind identical semantic transitions."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def canonical(case: dict[str, Any], task_id: str) -> dict[str, Any]:
    version = case.get('traceSchemaVersion', 1)
    if type(version) is not int or version not in (1, 2):
        raise ValueError('Unsupported traceSchemaVersion')
    if case.get('taskId', task_id) != task_id:
        raise ValueError('Case taskId differs from its contract')
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


def index(contract: dict[str, Any], label: str, errors: list[str]) -> dict[str, dict[str, Any]]:
    task_id = contract.get("taskId")
    result = {}
    if not isinstance(task_id, str) or not task_id:
        errors.append(f"{label}: nonempty taskId required")
        return result
    if not isinstance(contract.get('cases'), list) or not contract['cases']:
        errors.append(f"{label}: nonempty cases list required")
        return result
    keys = set()
    for case in contract.get("cases", []):
        if not isinstance(case, dict):
            errors.append(f"{label}: case must be an object")
            continue
        case_id = case.get("caseId")
        if not isinstance(case_id, str) or not case_id:
            errors.append(f"{label}: case without caseId")
            continue
        if case_id in result:
            errors.append(f"{label}: duplicate caseId {case_id}")
        if not isinstance(case.get('key'), str) or not case['key'] or case['key'] in keys:
            errors.append(f"{label}: invalid or duplicate key for {case_id}")
        keys.add(case.get('key') if isinstance(case.get('key'), str) else None)
        try:
            semantic = canonical(case, task_id)
        except (KeyError, TypeError, ValueError) as error:
            errors.append(f"{label}: {case_id}: {error}")
            continue
        declared = str(case.get("traceDigest", ""))
        result[case_id] = {
            "semantic": semantic,
            "invariants": case.get("invariants", []),
            "declaredDigest": declared,
            "computedDigest": digest(semantic),
        }
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--android", type=Path, required=True)
    parser.add_argument("--arkts", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    errors: list[str] = []
    android = index(load(args.android), "android", errors)
    arkts = index(load(args.arkts), "arkts", errors)
    if set(android) != set(arkts):
        errors.append("Android and ArkTS case IDs differ")
    for case_id in sorted(set(android) & set(arkts)):
        left, right = android[case_id], arkts[case_id]
        if left["semantic"] != right["semantic"] or left["invariants"] != right["invariants"]:
            errors.append(f"{case_id}: semantic clauses differ")
        if not left["declaredDigest"] or left["declaredDigest"] != right["declaredDigest"]:
            errors.append(f"{case_id}: declared traceDigest missing or different")
        if left["computedDigest"] != right["computedDigest"]:
            errors.append(f"{case_id}: computed semantic digest differs")
        if left["declaredDigest"] != left["computedDigest"]:
            errors.append(f"{case_id}: declared traceDigest does not match canonical clauses")

    payload = {"valid": not errors, "caseCount": len(set(android) & set(arkts)), "errors": errors}
    rendered = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
