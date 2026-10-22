#!/usr/bin/env python3
"""Retain exact executed slice evidence, validate publicly, then remove temporary files."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
from scripts.run_runtime_transition_matrix import validate_report as public_validate
from scripts.runtime_semantics.tasks10_11_runtime_evidence import attach_child, record, validate_report
from scripts.runtime_semantics.tasks10_11_formal_scorer import candidate_smoke, cleanup_evidence_artifacts, write


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-report", type=Path, required=True)
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--remove-owned-input", type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("Refusing to overwrite finalized evidence")
    report = json.loads(args.raw_report.read_text())
    contract = json.loads((ROOT / "benchmark_tasks" / report["taskId"] / "transitions.json").read_text())
    audit = args.output.with_suffix(".audit")
    audit.mkdir(parents=True, exist_ok=False)
    if args.remove_owned_input:
        source = args.remove_owned_input.resolve()
        if not source.name.startswith("ltb-standalone-") or source != Path(report["target"]).resolve():
            raise ValueError("Only the explicit runner-bound temporary input may be removed")
        write(audit / "input.json", candidate_smoke(source, report["platform"]))
    result = attach_child(report, contract, args.artifact_root.resolve(), audit)
    result.update(modelAgentResult=False,
                  inputKind="standalone_copy_sanity" if result["role"] == "agent" else "calibration")
    public_validate(result, contract)
    validate_report(result, contract)
    write(args.output, result)
    cleanup = cleanup_evidence_artifacts(args.artifact_root, args.artifact_root)
    if args.remove_owned_input:
        shutil.rmtree(args.remove_owned_input)
        cleanup["temporaryInputRemoved"] = not args.remove_owned_input.exists()
    write(audit / "cleanup.json", cleanup)
    counts = {key: sum(row["status"] == status for row in result["semantic"]["cases"])
              for key, status in (("passed", "pass"), ("failed", "fail"), ("notScored", "not_scored"))}
    write(audit / "public-validation.json", {"report": record(args.output), "publicAccepted": True,
                                            "counts": counts, "modelAgentResult": False})
    print(json.dumps({"report": str(args.output.resolve()), "publicAccepted": True, **counts}))


if __name__ == "__main__":
    main()
