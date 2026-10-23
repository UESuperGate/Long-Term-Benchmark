#!/usr/bin/env python3
"""Run one complete device transaction while holding a cross-worker file lock."""

from __future__ import annotations

import argparse
import fcntl
import os
import subprocess
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lock", required=True)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        parser.error("a command is required after --")

    lock_path = Path(args.lock)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a") as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        try:
            env = os.environ.copy()
            env["BENCHMARK_DEVICE_LOCK_PATH"] = str(lock_path)
            env["BENCHMARK_DEVICE_LOCK_IMPLEMENTATION"] = "python_fcntl.flock"
            return subprocess.run(command, env=env, check=False).returncode
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


if __name__ == "__main__":
    sys.exit(main())
