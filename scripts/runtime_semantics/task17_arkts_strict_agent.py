#!/usr/bin/env python3
"""Task17 ArkTS formal agent scorer module."""

import argparse
import json
import time
from pathlib import Path
from typing import Optional

try:
    from .arkts_strict_agent_scorer import ROOT, score as score_shared
except ImportError:
    from arkts_strict_agent_scorer import ROOT, score as score_shared


CONTRACT = ROOT / "benchmark_tasks/17_pinned_messages/transitions.json"
BUILD = ROOT / "scripts/runtime_semantics/task17_arkts_strict_build.cjs"


def score(source: Path, output: Path, deadline: float, device_serial: Optional[str] = None) -> dict:
    return score_shared(task_id="17_pinned_messages", source=source, output=output, deadline=deadline,
                        contract_path=CONTRACT, build_script=BUILD, device_serial=device_serial)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=int, default=3600)
    parser.add_argument("--device-serial")
    args = parser.parse_args()
    if args.timeout_seconds != 3600:
        parser.error("formal score timeout must be exactly 3600 seconds")
    report = score(args.source, args.output, time.monotonic() + args.timeout_seconds, args.device_serial)
    print(json.dumps({"output": str(args.output), "publishableWithoutApplicationCompile":
                      report["diagnostics"]["publishableWithoutApplicationCompile"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
