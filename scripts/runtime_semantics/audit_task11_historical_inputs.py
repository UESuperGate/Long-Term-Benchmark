#!/usr/bin/env python3
"""Find exact retained historical fixture bytes; never relabel current fixtures."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.runtime_semantics import android11_reviewed_navigation as reviewed
from scripts.runtime_semantics.tasks10_11_runtime_evidence import record


def audit(roots):
    raw = json.loads(reviewed.REPORT.read_text())
    inputs = raw["provenance"]["evaluatorSources"]
    index = {}
    for root in roots:
        for path in root.rglob("*"):
            if path.is_file() and path.suffix in {".kt", ".java"}:
                index.setdefault(hashlib.sha256(path.read_bytes()).hexdigest(), []).append(path)
    entries = []
    for item in inputs:
        current = Path(item["path"])
        exact = index.get(item["sha256"], [])
        entries.append({"historicalInput": item, "currentPath": record(current) if current.exists() else None,
                        "exactRetainedInputs": [record(path) for path in exact],
                        "status": "exact_bytes_retained" if exact else "historical_input_not_retained"})
    return {"report": record(reviewed.REPORT), "searchRoots": [str(path) for path in roots],
            "scope": "accessible Task11 evaluator and retained experiment Java/Kotlin files, not whole disk",
            "inputs": entries, "allHistoricalFixturesRetained": all(item["exactRetainedInputs"] for item in entries),
            "oldReportsModified": False, "oldHashLabelsModified": False, "validatorRelaxed": False,
            "recoveredFixtureWritten": False, "historicalValidationPolicy": "fail_closed_if_input_not_retained"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("Never overwrite a historical audit")
    result = audit([ROOT / "state_tests/runtime/android", ROOT / "experiment_results/runtime_transition_20261020"])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"allHistoricalFixturesRetained": result["allHistoricalFixturesRetained"],
                      "missing": [item["historicalInput"]["path"] for item in result["inputs"]
                                  if not item["exactRetainedInputs"]]}))


if __name__ == "__main__":
    main()
