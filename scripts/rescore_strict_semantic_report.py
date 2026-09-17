#!/usr/bin/env python3
"""Rescore an existing strict-state run with semantic facts only.

This script is evaluator-side. It does not install, launch, or modify apps. It
uses captured Android XML / ArkTS layout files from a previous dynamic run and
scores each row against evaluator-owned binding manifests. Feature-availability
markers are treated as smoke evidence and never as semantic pass evidence.
"""
from __future__ import annotations

import json
import re
import sys
from html import unescape
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(r"C:\Users\xiexi\qingyu")
BINDINGS = ROOT / "state_tests" / "bindings"
FACT_RE = re.compile(r"strict_state_fact:([^\"'<>\r\n]+)")


def read_text(path: str | Path | None) -> str:
    if not path:
        return ""
    p = Path(path)
    if not p.exists():
        return ""
    return p.read_text(encoding="utf-8", errors="ignore")


def load_bindings() -> dict[str, dict]:
    cases: dict[str, dict] = {}
    for path in sorted(BINDINGS.glob("*.binding.json")):
        if path.name == "state_binding_manifest_index.json":
            continue
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        for case in data.get("cases", []):
            cases[case["caseId"]] = case
    return cases


def expected_facts(case: dict | None) -> list[str]:
    if not case:
        return []
    facts: list[str] = []
    selectors = case.get("selectors", {})
    for bucket in ("visible", "hidden", "enabled", "disabled"):
        for token in selectors.get(bucket, []) or []:
            facts.append(f"{bucket}:{token}")
    for key, value in (selectors.get("properties", {}) or {}).items():
        facts.append(f"property:{key}={value}")
    for transition in case.get("transitionSelectors", []) or []:
        ordinal = transition.get("ordinal")
        event = transition.get("event", "")
        if ordinal and event:
            facts.append(f"transition:{ordinal}:{event}")
        for bucket in ("visible", "hidden", "enabled", "disabled"):
            for token in transition.get(bucket, []) or []:
                facts.append(f"transition:{ordinal}:{bucket}:{token}")
        for key, value in (transition.get("properties", {}) or {}).items():
            facts.append(f"transition:{ordinal}:property:{key}={value}")
    return sorted(set(facts))


def probe_key(target_id: str, case_id: str) -> str:
    return f"{target_id}\u241f{case_id}"


def main() -> int:
    if len(sys.argv) < 3:
        print("Usage: rescore_strict_semantic_report.py <strict_state_matrix_run_report.json> <out_dir>")
        return 2
    source_report = Path(sys.argv[1])
    out_dir = Path(sys.argv[2])
    out_dir.mkdir(parents=True, exist_ok=True)

    report = json.loads(source_report.read_text(encoding="utf-8-sig"))
    bindings = load_bindings()
    probes = {
        probe_key(str(probe.get("targetId", "")), str(probe.get("caseId", ""))): probe
        for probe in report.get("targetProbes", [])
    }

    rows = []
    for result in report.get("results", []):
        target_id = str(result.get("targetId", ""))
        case_id = str(result.get("caseId", ""))
        probe = probes.get(probe_key(target_id, case_id), {})
        capture_path = probe.get("xml") if result.get("platform") == "android" else probe.get("layout")
        content = read_text(capture_path)
        ready = f"state_test_ready:{case_id}" in content
        case_marker = f"strict_state_case:{case_id}" in content
        expected = expected_facts(bindings.get(case_id))
        observed = {unescape(fact) for fact in FACT_RE.findall(content)}
        missing = [fact for fact in expected if fact not in observed]
        semantic_pass = bool(expected) and ready and case_marker and not missing
        observed_polarity = "pass" if semantic_pass else "fail"
        strict_status = "matched" if observed_polarity == result.get("expectedPolarity") else "mismatch"
        rows.append({
            "targetId": target_id,
            "taskId": result.get("taskId"),
            "platform": result.get("platform"),
            "release": result.get("release"),
            "caseId": case_id,
            "expectedPolarity": result.get("expectedPolarity"),
            "observedPolarity": observed_polarity,
            "strictStatus": strict_status,
            "scoringMode": "strict_semantic_facts_rescore",
            "readyMarkerObserved": ready,
            "caseMarkerObserved": case_marker,
            "expectedFactCount": len(expected),
            "observedFactCount": len(observed),
            "missingFactCount": len(missing),
            "missingRequired": [f"strict_state_fact:{fact}" for fact in missing[:100]],
            "capturePath": str(capture_path or ""),
        })

    by_target = defaultdict(Counter)
    by_task_release = defaultdict(Counter)
    for row in rows:
        by_target[row["targetId"]][row["strictStatus"]] += 1
        key = f"{row['taskId']}::{row['platform']}::{row['release']}"
        by_task_release[key][row["strictStatus"]] += 1

    summary = {
        "generatedAt": datetime.now().isoformat(timespec="seconds"),
        "sourceReport": str(source_report),
        "policy": "semantic facts only; feature availability smoke markers are ignored",
        "caseTargetCount": len(rows),
        "statusCounts": dict(Counter(row["strictStatus"] for row in rows)),
        "byTarget": {key: dict(value) for key, value in sorted(by_target.items())},
        "byTaskRelease": {key: dict(value) for key, value in sorted(by_task_release.items())},
        "results": rows,
    }

    json_path = out_dir / "strict_semantic_rescore_report.json"
    md_path = out_dir / "strict_semantic_rescore_report.md"
    json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Strict Semantic Rescore Report",
        "",
        f"- Generated: {summary['generatedAt']}",
        f"- Source report: `{source_report}`",
        f"- Policy: {summary['policy']}",
        f"- Case-target rows: {summary['caseTargetCount']}",
        f"- Status counts: `{json.dumps(summary['statusCounts'], ensure_ascii=False)}`",
        "",
        "## By Target",
        "",
        "| target | matched | mismatch |",
        "|---|---:|---:|",
    ]
    for target, counts in summary["byTarget"].items():
        lines.append(f"| `{target}` | {counts.get('matched', 0)} | {counts.get('mismatch', 0)} |")
    lines.extend(["", "## By Task/Platform/Release", "", "| task/platform/release | matched | mismatch |", "|---|---:|---:|"])
    for key, counts in summary["byTaskRelease"].items():
        lines.append(f"| `{key}` | {counts.get('matched', 0)} | {counts.get('mismatch', 0)} |")
    lines.extend(["", "## Mismatch Samples", ""])
    for row in [row for row in rows if row["strictStatus"] == "mismatch"][:30]:
        lines.append(
            f"- `{row['targetId']}` `{row['caseId']}` expected={row['expectedPolarity']} "
            f"observed={row['observedPolarity']} missing={row['missingFactCount']}/{row['expectedFactCount']}"
        )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json_path)
    print(md_path)
    print(json.dumps(summary["statusCounts"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
