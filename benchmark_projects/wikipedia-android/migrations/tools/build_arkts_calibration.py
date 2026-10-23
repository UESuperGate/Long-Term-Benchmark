#!/usr/bin/env python3
"""Build a calibration HAP with hidden observer wiring, leaving production source clean."""

from __future__ import annotations

import argparse
import importlib.util
import os
import shutil
import subprocess
from pathlib import Path


MIN_FREE_BYTES = 8 * 1024 * 1024 * 1024


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--migration", type=Path, required=True)
    parser.add_argument("--task-id", required=True)
    args = parser.parse_args()
    project = args.project.resolve()
    migration = args.migration.resolve()
    free = shutil.disk_usage(project).free
    if free < MIN_FREE_BYTES:
        raise RuntimeError(
            f"refusing disk-heavy ArkTS build with {free} free bytes; "
            f"at least {MIN_FREE_BYTES} are required"
        )
    temporary = project / ".benchmark-calibration-build"
    if temporary.exists():
        shutil.rmtree(temporary)
    shutil.copytree(project, temporary, ignore=shutil.ignore_patterns("build", ".hvigor", ".benchmark-calibration-build"))
    module_path = migration.parent / "tools/prepare_agent_harness.py"
    spec = importlib.util.spec_from_file_location("prepare_agent_harness", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load harness preparation module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    hidden = temporary / ".benchmark-evaluator"
    hidden.mkdir()
    module.prepare_arkts(args.task_id, temporary, migration, hidden)
    hvigor = os.environ.get("HVIGORW", "/Applications/DevEco-Studio.app/Contents/tools/hvigor/bin/hvigorw")
    try:
        run = subprocess.run([hvigor, "--mode", "module", "-p", "product=default", "-p", "module=entry@default",
                              "assembleHap", "--no-daemon"], cwd=temporary)
        if run.returncode != 0:
            return run.returncode
        haps = sorted((temporary / "entry/build").rglob("*.hap"))
        if not haps:
            raise RuntimeError("calibration build produced no HAP")
        output = project / "entry/build/default/outputs/default" / haps[-1].name
        output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(haps[-1], output)
    finally:
        shutil.rmtree(temporary, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
