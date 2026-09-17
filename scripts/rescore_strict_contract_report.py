#!/usr/bin/env python3
"""Rescore captured strict-state runs with protocol/semantic separation."""

from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime
from html import unescape
from pathlib import Path


ROOT = Path(r"C:\Users\xiexi\qingyu")
BINDINGS = ROOT / "state_tests" / "bindings"
FACT_RE = re.compile(r"strict_state_fact:([^\"'<>\r\n]+)")


def read_text(path: str | None) -> str:
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
    selectors = case.get("selectors", {}) or {}
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


def classify_row(result: dict, probe: dict, bindings: dict[str, dict]) -> dict:
    target_id = str(result.get("targetId", ""))
    case_id = str(result.get("caseId", ""))
    expected_polarity = str(result.get("expectedPolarity", ""))
    platform = str(result.get("platform", ""))
    capture_path = probe.get("xml") if platform == "android" else probe.get("layout")
    content = read_text(capture_path)
    ready = f"state_test_ready:{case_id}" in content
    case_marker = f"strict_state_case:{case_id}" in content
    legacy = bool(
        probe.get("legacyMarkerObserved")
        or probe.get("legacySourceMarker")
        or re.search(r"state_test_result:(pass|fail)|strict_state_assertion:final_feature_available", content)
    )
    expected = expected_facts(bindings.get(case_id))
    observed = {unescape(fact) for fact in FACT_RE.findall(content)}
    missing = [fact for fact in expected if fact not in observed]

    status = "mismatch"
    verdict = "mismatch"
    observed_polarity = "fail"
    harness = "passed"
    semantic = "failed"
    reason = ""

    if legacy:
        status = "protocolFail"
        verdict = "excluded"
        harness = "contaminated_legacy_harness"
        semantic = "not_scored"
        reason = "Only legacy feature/version marker evidence is present; strict runtime state assertions are absent."
    elif not (ready and case_marker):
        status = "protocolFail" if expected_polarity == "pass" else "matched"
        verdict = "excluded" if status == "protocolFail" else "matched"
        harness = "protocol_missing_ready_or_case"
        semantic = "not_scored"
        reason = f"Harness protocol failed before semantic scoring. ready={ready} caseMarker={case_marker}."
    elif expected_polarity == "pass" and not observed:
        status = "protocolFail"
        verdict = "excluded"
        harness = "missing_strict_state_facts"
        semantic = "not_scored"
        reason = "Final target reached the case but emitted no strict_state_fact markers, so semantic scoring cannot start."
    else:
        semantic_pass = bool(expected) and not missing
        observed_polarity = "pass" if semantic_pass else "fail"
        status = "matched" if observed_polarity == expected_polarity else "mismatch"
        verdict = status
        semantic = "passed" if semantic_pass else "failed"
        reason = (
            "Strict semantic facts matched the evaluator binding manifest."
            if semantic_pass
            else f"Strict semantic facts missing. ready={ready} caseMarker={case_marker} missingFacts={len(missing)} expectedFacts={len(expected)}."
        )

    return {
        "targetId": target_id,
        "taskId": result.get("taskId"),
        "platform": platform,
        "release": result.get("release"),
        "caseId": case_id,
        "expectedPolarity": expected_polarity,
        "observedPolarity": observed_polarity,
        "strictStatus": status,
        "verdict": verdict,
        "reason": reason,
        "readyMarkerObserved": ready,
        "caseMarkerObserved": case_marker,
        "expectedFactCount": len(expected),
        "observedFactCount": len(observed),
        "missingFactCount": len(missing),
        "missingRequired": [f"strict_state_fact:{fact}" for fact in missing],
        "harnessComplianceStatus": harness,
        "semanticStatus": semantic,
        "sourceProbeStatus": probe.get("status", ""),
        "capturePath": str(capture_path or ""),
    }


def main() -> int:
    if len(sys.argv) != 3:
        print("Usage: rescore_strict_contract_report.py <source_report.json> <out_dir>")
        return 2
    source = Path(sys.argv[1])
    out_dir = Path(sys.argv[2])
    out_dir.mkdir(parents=True, exist_ok=True)
    source_report = json.loads(source.read_text(encoding="utf-8-sig"))
    bindings = load_bindings()
    probes = {
        probe_key(str(probe.get("targetId", "")), str(probe.get("caseId", ""))): probe
        for probe in source_report.get("targetProbes", [])
    }
    rows = [
        classify_row(result, probes.get(probe_key(str(result.get("targetId", "")), str(result.get("caseId", ""))), {}), bindings)
        for result in source_report.get("results", [])
    ]
    by_target: dict[str, Counter] = defaultdict(Counter)
    by_task: dict[str, Counter] = defaultdict(Counter)
    for row in rows:
        by_target[str(row["targetId"])][str(row["strictStatus"])] += 1
        by_task[f"{row['taskId']}::{row['platform']}::{row['release']}"][str(row["strictStatus"])] += 1

    summary = {
        "generatedAt": datetime.now().isoformat(timespec="seconds"),
        "sourceReport": str(source),
        "policy": "protocol first, then strict semantic facts; legacy marker evidence is protocolFail",
        "caseTargetCount": len(rows),
        "statusCounts": dict(Counter(row["strictStatus"] for row in rows)),
        "harnessComplianceCounts": dict(Counter(row["harnessComplianceStatus"] for row in rows)),
        "semanticStatusCounts": dict(Counter(row["semanticStatus"] for row in rows)),
        "byTarget": {key: dict(value) for key, value in sorted(by_target.items())},
        "byTaskRelease": {key: dict(value) for key, value in sorted(by_task.items())},
        "results": rows,
    }

    json_path = out_dir / "strict_contract_rescore_report.json"
    md_path = out_dir / "strict_contract_rescore_report.md"
    json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Strict Contract Rescore Report",
        "",
        f"- Generated: {summary['generatedAt']}",
        f"- Source report: `{source}`",
        f"- Policy: {summary['policy']}",
        f"- Case-target rows: {summary['caseTargetCount']}",
        f"- Status counts: `{json.dumps(summary['statusCounts'], ensure_ascii=False)}`",
        f"- Harness compliance counts: `{json.dumps(summary['harnessComplianceCounts'], ensure_ascii=False)}`",
        f"- Semantic status counts: `{json.dumps(summary['semanticStatusCounts'], ensure_ascii=False)}`",
        "",
        "## By Task/Platform/Release",
        "",
        "| task/platform/release | matched | mismatch | protocolFail |",
        "|---|---:|---:|---:|",
    ]
    for key, counts in summary["byTaskRelease"].items():
        lines.append(f"| `{key}` | {counts.get('matched', 0)} | {counts.get('mismatch', 0)} | {counts.get('protocolFail', 0)} |")
    lines.extend(["", "## Failure Samples", ""])
    samples = [row for row in rows if row["strictStatus"] != "matched"][:30]
    if not samples:
        lines.append("- None")
    for row in samples:
        lines.append(
            f"- `{row['targetId']}` `{row['caseId']}` status={row['strictStatus']} "
            f"harness={row['harnessComplianceStatus']} semantic={row['semanticStatus']} "
            f"missing={row['missingFactCount']}/{row['expectedFactCount']}"
        )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json_path)
    print(md_path)
    print(json.dumps(summary["statusCounts"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
