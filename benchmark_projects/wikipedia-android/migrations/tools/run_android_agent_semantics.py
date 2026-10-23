#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--migration", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    harness = args.project / ".benchmark-evaluator/android-harness"
    runner = args.migration / "evaluator/run_android_semantics.py"
    return subprocess.run([
        "python3", str(runner), "--project", str(harness), "--role", "agent", "--output", str(args.output)
    ]).returncode


if __name__ == "__main__":
    raise SystemExit(main())
