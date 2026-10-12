#!/usr/bin/env python3
"""Generate the shared semantic contract from audited platform bindings."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BINDINGS = ROOT / "state_tests" / "canonical" / "cross_platform_bindings.json"
DEFAULT_OFFICIAL = ROOT / "state_tests" / "canonical" / "official_transition_contract.json"
DEFAULT_OUTPUT = ROOT / "state_tests" / "canonical" / "cross_platform_contract.json"
TRACES = ROOT / "state_tests" / "traces"


def canonical_digest(case: dict[str, Any]) -> str:
    semantic = {
        "taskId": case["taskId"],
        "key": case["key"],
        "given": case["given"],
        "event": case["event"],
        "expected": case["expected"],
    }
    encoded = json.dumps(semantic, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode()).hexdigest()


def load_trace_cases() -> dict[str, dict[str, Any]]:
    cases: dict[str, dict[str, Any]] = {}
    for path in sorted(TRACES.glob("*.trace.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        task_id = data["task"]["id"]
        for case in data["cases"]:
            cases[case["caseId"]] = case | {"taskId": task_id}
    return cases


def generate(bindings: dict[str, Any], official: dict[str, Any]) -> list[dict[str, Any]]:
    traces = load_trace_cases()
    official_index = {
        (case["taskId"], case["className"], case["methodName"]): case
        for case in official["cases"]
    }
    used_android_evidence: set[tuple[str, str, str]] = set()
    generated: list[dict[str, Any]] = []
    for task_id, task in bindings["tasks"].items():
        default_class = task.get("androidClass", "")
        for source in task["cases"]:
            evidence_pairs = source.get("androidEvidence") or [
                [default_class, method] for method in source.get("androidMethods", [])
            ]
            android_evidence = []
            for class_name, method_name in evidence_pairs:
                key = (task_id, class_name, method_name)
                if key not in official_index:
                    raise ValueError(f"unknown Android evidence: {key}")
                if key in used_android_evidence:
                    raise ValueError(f"Android evidence reused by multiple benchmark cases: {key}")
                used_android_evidence.add(key)
                item = official_index[key]
                android_evidence.append({
                    "className": class_name,
                    "methodName": method_name,
                    "officialCaseId": item["caseId"],
                    "officialTraceDigest": item["traceDigest"],
                })
            trace = traces.get(source["arktsCase"])
            if trace is None or trace["taskId"] != task_id:
                raise ValueError(f"invalid ArkTS trace binding for {task_id}: {source['arktsCase']}")
            ordinals = {int(phase["ordinal"]) for phase in trace["phases"]}
            requested = {int(value) for value in source["arktsPhases"]}
            if not requested or not requested.issubset(ordinals):
                raise ValueError(f"invalid phase binding for {source['arktsCase']}: {sorted(requested)}")
            case = {
                "caseId": f"cross_{task_id}_{source['key']}",
                "taskId": task_id,
                "key": source["key"],
                "given": source["given"],
                "event": source["event"],
                "expected": source["expected"],
                "androidEvidence": android_evidence,
                "arktsEvidence": {
                    "traceCaseId": source["arktsCase"],
                    "traceDigest": trace["traceDigest"],
                    "phaseOrdinals": sorted(requested),
                },
            }
            case["traceDigest"] = canonical_digest(case)
            generated.append(case)
    return generated


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bindings", type=Path, default=DEFAULT_BINDINGS)
    parser.add_argument("--official", type=Path, default=DEFAULT_OFFICIAL)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    bindings = json.loads(args.bindings.read_text(encoding="utf-8"))
    official = json.loads(args.official.read_text(encoding="utf-8"))
    cases = generate(bindings, official)
    payload = {
        "schemaVersion": 1,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "owner": "evaluator",
        "description": "Platform-neutral semantic intersection with audited Android and ArkTS evidence bindings",
        "cases": cases,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "cases": len(cases)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
