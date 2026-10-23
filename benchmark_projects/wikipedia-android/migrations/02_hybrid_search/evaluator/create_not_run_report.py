#!/usr/bin/env python3
"""Create an explicit not-run placeholder without executing or scoring a runtime."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--platform", required=True, choices=("android", "arkts"))
    parser.add_argument("--role", required=True, choices=("base", "final", "agent"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    migration = Path(__file__).resolve().parents[1]
    contract = json.loads((migration / "canonical" / "transitions.json").read_text())
    report = {
        "schemaVersion": 1,
        "taskId": contract["taskId"],
        "platform": args.platform,
        "role": args.role,
        "observationMode": "runtime_state_transition",
        "runtime": "not_run",
        "codeGeneration": {"passed": None, "changedProductionFiles": []},
        "compile": {"passed": None, "command": []},
        "semantic": {"cases": [{
            "caseId": case["caseId"],
            "key": case["key"],
            "traceDigest": case["traceDigest"],
            "status": "not_scored",
            "observed": {},
            "checkpoints": [],
            "invariantChecks": [],
            "reason": "Runtime, build, and device execution were intentionally not run during bundle construction."
        } for case in contract["cases"]]},
        "diagnostics": {
            "adapter": "not_executed",
            "transport": "not_attempted",
            "runtimeCompile": {"passed": None},
            "sourceObserver": False
        }
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
