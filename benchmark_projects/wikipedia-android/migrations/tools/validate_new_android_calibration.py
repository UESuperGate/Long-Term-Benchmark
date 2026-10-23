#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("migration", type=Path)
    args = parser.parse_args()
    root = args.migration.resolve()
    contract = json.loads((root / "canonical/transitions.json").read_text())
    expected = {case["caseId"]: case["traceDigest"] for case in contract["cases"]}
    errors: list[str] = []
    roles = {
        "base": (root / "results/android-base.json", (0, 10, 0)),
        "final": (root / "results/android-final.json", (10, 0, 0)),
        "no_change": (root / "results/android-no-change-control.json", (0, 10, 0)),
        "known_final": (root / "results/android-known-final-control.json", (10, 0, 0)),
    }
    for label, (path, counts) in roles.items():
        report = json.loads(path.read_text())
        semantic = report.get("semantic", {})
        actual_counts = (semantic.get("passed"), semantic.get("failed"), semantic.get("notScored"))
        if actual_counts != counts:
            errors.append(f"{label}: expected {counts}, found {actual_counts}")
        if report.get("observationMode") != "runtime_state_transition":
            errors.append(f"{label}: not runtime_state_transition")
        if report.get("diagnostics", {}).get("sourceObserver") is not False:
            errors.append(f"{label}: source observer enabled")
        rows = semantic.get("cases", [])
        actual = {row.get("caseId"): row.get("traceDigest") for row in rows}
        if actual != expected:
            errors.append(f"{label}: case IDs or digests differ from canonical contract")
        if any(row.get("status") in {"pass", "fail"} and
               (len(row.get("checkpoints", [])) < 4 or not row.get("productionSources") or not row.get("invariantChecks"))
               for row in rows):
            errors.append(f"{label}: scored row lacks runtime/source/invariant evidence")
    payload = {"valid": not errors, "taskId": contract["taskId"], "counts": {k: v[1] for k, v in roles.items()}, "errors": errors}
    output = root / "provenance/calibration-validation.json"
    output.write_text(json.dumps(payload, indent=2) + "\n")
    print(json.dumps(payload))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
