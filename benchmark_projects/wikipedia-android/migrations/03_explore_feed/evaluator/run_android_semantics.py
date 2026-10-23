#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--role", choices=("base", "final", "agent"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    migration = Path(__file__).resolve().parents[1]
    tool = migration.parent / "tools/run_android_state_transition.py"
    return subprocess.run(["python3", str(tool), "--project", str(args.project), "--migration", str(migration),
                           "--role", args.role, "--output", str(args.output),
                           "--runner", "org.wikipedia.benchmark.explore.native.NativeExploreInstrumentation"]).returncode


if __name__ == "__main__":
    raise SystemExit(main())

