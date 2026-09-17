#!/usr/bin/env python3
"""Audit whether semantic state-test cases are executable by the current runtime harness.

This is evaluator-side only. It compares the semantic contract declared in the
state-test YAML/binding manifest with captured runtime UI trees and reports
which cases are still only feature-level smoke versus genuinely scoreable by
per-case semantic facts.
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(r"C:\Users\xiexi\qingyu")
DEFAULT_REPORT = ROOT / "verification_reports" / "state_dynamic" / "arkts_observation_oracle_all" / "strict_state_matrix_run_report.json"
BINDINGS = ROOT / "state_tests" / "bindings"

TOKEN_RE = re.compile(r"strict_state_fact:([^\"<]+)")


def read_text(path: str | Path) -> str:
    p = Path(path)
    if not p.exists():
        return ""
    return p.read_text(encoding="utf-8", errors="ignore")


def load_bindings() -> dict[str, dict]:
    out: dict[str, dict] = {}
    for path in sorted(BINDINGS.glob("*.binding.json")):
        if path.name == "state_binding_manifest_index.json":
            continue
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        out[data["task"]["id"]] = {case["caseId"]: case for case in data["cases"]}
    return out


def expected_facts(case: dict) -> list[str]:
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
        facts.append(f"transition:{ordinal}:{event}")
        for bucket in ("visible", "hidden", "enabled", "disabled"):
            for token in transition.get(bucket, []) or []:
                facts.append(f"transition:{ordinal}:{bucket}:{token}")
        for key, value in (transition.get("properties", {}) or {}).items():
            facts.append(f"transition:{ordinal}:property:{key}={value}")
    return sorted(set(facts))


def observed_facts(content: str) -> set[str]:
    facts = set(TOKEN_RE.findall(content))
    # Existing UI-token scorer compatibility: raw semantic ids appearing in UI tree
    # are treated as weak observed facts for this audit only.
    return facts


def main() -> int:
    report_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_REPORT
    out_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else report_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    report = json.loads(report_path.read_text(encoding="utf-8-sig"))
    bindings = load_bindings()

    rows = []
    for result in report.get("results", []):
        if result.get("release") != "final":
            continue
        task_id = result["taskId"]
        case_id = result["caseId"]
        case = bindings.get(task_id, {}).get(case_id)
        if not case:
            continue
        expected = expected_facts(case)
        probe = next((p for p in report.get("targetProbes", []) if p.get("targetId") == result.get("targetId") and p.get("caseId") == case_id), None)
        capture = ""
        if probe:
            capture = read_text(probe.get("layout") or probe.get("xml") or "")
        obs = observed_facts(capture)
        missing = [fact for fact in expected if fact not in obs]
        mode = "semantic_facts" if expected and not missing else "feature_smoke_only"
        if not expected:
            mode = "no_semantic_requirements"
        rows.append({
            "targetId": result.get("targetId"),
            "taskId": task_id,
            "caseId": case_id,
            "functionalArea": case.get("functionalArea", ""),
            "fixtureKind": case.get("fixtureKind", ""),
            "expectedFactCount": len(expected),
            "observedFactCount": len(obs),
            "missingFactCount": len(missing),
            "semanticExecutable": mode == "semantic_facts",
            "currentScoringMode": result.get("scoringMode", ""),
            "strictStatus": result.get("strictStatus", ""),
            "missingFacts": missing[:50],
        })

    summary = {
        "generatedAt": datetime.now().isoformat(timespec="seconds"),
        "sourceReport": str(report_path),
        "caseCount": len(rows),
        "semanticExecutableCount": sum(1 for row in rows if row["semanticExecutable"]),
        "featureSmokeOnlyCount": sum(1 for row in rows if not row["semanticExecutable"]),
        "byTask": {},
        "byFunctionalArea": {},
        "rows": rows,
    }
    by_task = defaultdict(Counter)
    by_area = defaultdict(Counter)
    for row in rows:
        by_task[row["taskId"]]["semantic" if row["semanticExecutable"] else "smoke_only"] += 1
        by_area[f"{row['taskId']}::{row['functionalArea']}"]["semantic" if row["semanticExecutable"] else "smoke_only"] += 1
    summary["byTask"] = {k: dict(v) for k, v in sorted(by_task.items())}
    summary["byFunctionalArea"] = {k: dict(v) for k, v in sorted(by_area.items())}

    json_path = out_dir / "semantic_harness_gap_audit.json"
    md_path = out_dir / "semantic_harness_gap_audit.md"
    json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Semantic Harness Gap Audit",
        "",
        f"- Generated: {summary['generatedAt']}",
        f"- Source report: `{report_path}`",
        f"- Final rows audited: {summary['caseCount']}",
        f"- Semantic executable rows: {summary['semanticExecutableCount']}",
        f"- Feature-smoke-only rows: {summary['featureSmokeOnlyCount']}",
        "",
        "## By Task",
        "",
        "| task | semantic executable | smoke only |",
        "|---|---:|---:|",
    ]
    for task, counts in summary["byTask"].items():
        lines.append(f"| `{task}` | {counts.get('semantic', 0)} | {counts.get('smoke_only', 0)} |")
    lines += ["", "## Largest Missing Fact Sets", ""]
    for row in sorted(rows, key=lambda r: r["missingFactCount"], reverse=True)[:30]:
        lines.append(f"- `{row['taskId']}` `{row['caseId']}` area=`{row['functionalArea']}` missing={row['missingFactCount']}/{row['expectedFactCount']}")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json_path)
    print(md_path)
    print(json.dumps({"semanticExecutable": summary["semanticExecutableCount"], "smokeOnly": summary["featureSmokeOnlyCount"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
