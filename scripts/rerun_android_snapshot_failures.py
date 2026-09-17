#!/usr/bin/env python3
"""Rerun Android snapshot rows that did not match in an existing report."""

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


def refresh_counts(summary: dict[str, Any]) -> None:
    for key in ("strictStatus", "semanticStatus", "targetRole"):
        counts: dict[str, int] = {}
        for item in summary["results"]:
            value = str(item.get(key) or "unspecified")
            counts[value] = counts.get(value, 0) + 1
        out_key = {"strictStatus": "statusCounts", "semanticStatus": "semanticStatusCounts", "targetRole": "targetRoleCounts"}[key]
        summary[out_key] = counts


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--matrix", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument("--out-json", required=True)
    parser.add_argument("--out-md", required=True)
    parser.add_argument("--android-serial", default="")
    args = parser.parse_args()

    runner_mod = load_runner()
    matrix = json.loads(Path(args.matrix).read_text(encoding="utf-8-sig"))
    summary = json.loads(Path(args.report).read_text(encoding="utf-8-sig"))
    out_dir = Path(args.out_json).parent
    out_dir.mkdir(parents=True, exist_ok=True)
    runner = runner_mod.Runner(matrix, out_dir, args.android_serial)
    target_map = {t["targetId"]: t for t in matrix["targets"]}
    bindings = runner_mod.load_binding_cases()

    rows = [
        row for row in summary["results"]
        if row["platform"] == "android" and row["strictStatus"] != "matched"
    ]
    print(f"Rerunning {len(rows)} Android rows")
    for index, row in enumerate(rows, start=1):
        target = target_map[row["targetId"]]
        case_id = row["caseId"]
        artifact_dir = out_dir / "snapshot_probe" / runner_mod.ps_safe(f"{row['targetId']}__{case_id}")
        artifact_dir.mkdir(parents=True, exist_ok=True)
        print(f"[android-rerun] {index}/{len(rows)} {row['targetId']} {case_id}", flush=True)
        snapshot, detail = runner.android_snapshot(target, case_id, artifact_dir)
        facts = (bindings.get(case_id) or {}).get("expectedFacts", [])
        row["snapshot"] = snapshot
        row["probe"] = detail
        row.update(runner_mod.score_snapshot(snapshot, row["expectedPolarity"], facts))
        (artifact_dir / "snapshot.rerun.json").write_text(
            json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n" if snapshot else "null\n",
            encoding="utf-8",
        )

    refresh_counts(summary)
    out_json = Path(args.out_json)
    out_md = Path(args.out_md)
    out_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    runner_mod.write_markdown(summary, out_md)
    print(f"Wrote {out_json}")
    print(f"Wrote {out_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
