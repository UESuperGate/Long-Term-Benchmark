#!/usr/bin/env python3
"""Rescore snapshot-state run artifacts without touching devices."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RUNNER_PATH = ROOT / "scripts" / "run_snapshot_state_matrix.py"


def load_runner() -> Any:
    spec = importlib.util.spec_from_file_location("run_snapshot_state_matrix", RUNNER_PATH)
    if not spec or not spec.loader:
        raise RuntimeError(f"Cannot load {RUNNER_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True)
    parser.add_argument("--out-json", required=True)
    parser.add_argument("--out-md", required=True)
    args = parser.parse_args()

    runner = load_runner()
    report_path = Path(args.report)
    summary = json.loads(report_path.read_text(encoding="utf-8-sig"))
    out_dir = Path(summary["root"]) / "verification_reports" / "snapshot_state_dynamic"
    bindings = runner.load_binding_cases()

    for row in summary["results"]:
        artifact_dir = out_dir / "snapshot_probe" / runner.ps_safe(f"{row['targetId']}__{row['caseId']}")
        artifact = artifact_dir / ("provider_query.txt" if row["platform"] == "android" else "layout.json")
        snapshot = None
        if artifact.exists():
            snapshot = runner.extract_snapshot_from_text(artifact.read_text(encoding="utf-8", errors="ignore"))
        row["snapshot"] = snapshot
        facts = (bindings.get(row["caseId"]) or {}).get("expectedFacts", [])
        row.update(runner.score_snapshot(snapshot, row["expectedPolarity"], facts))
        (artifact_dir / "snapshot.rescored.json").write_text(
            json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n" if snapshot else "null\n",
            encoding="utf-8",
        )

    for key in ("strictStatus", "semanticStatus", "targetRole"):
        counts: dict[str, int] = {}
        for item in summary["results"]:
            value = str(item.get(key) or "unspecified")
            counts[value] = counts.get(value, 0) + 1
        out_key = {"strictStatus": "statusCounts", "semanticStatus": "semanticStatusCounts", "targetRole": "targetRoleCounts"}[key]
        summary[out_key] = counts

    out_json = Path(args.out_json)
    out_md = Path(args.out_md)
    out_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    runner.write_markdown(summary, out_md)
    print(f"Wrote {out_json}")
    print(f"Wrote {out_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
