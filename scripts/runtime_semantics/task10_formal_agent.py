#!/usr/bin/env python3
"""Formal source-parameterized scorer for Task10 on Android and ArkTS."""

from __future__ import annotations

from pathlib import Path
import shutil
import sys

try:
    from .tasks10_11_formal_scorer import RuntimeRunner, TaskSpec, main as _main, score as _score
except ImportError:
    from tasks10_11_formal_scorer import RuntimeRunner, TaskSpec, main as _main, score as _score


SPEC = TaskSpec(
    task_id="10_media_upload_quality",
    case_count=9,
)


RUNNERS = {
    "android": RuntimeRunner(Path(sys.executable), Path(__file__).with_name("task10_android_strict_runtime.py")),
    "arkts": RuntimeRunner(Path(shutil.which("node") or "/usr/bin/node"),
                           Path(__file__).with_name("task10_arkts_strict_runtime.cjs")),
}


def score(*, platform: str, source: Path, base_source: Path, final_source: Path,
          output: Path, timeout: float = 3600, compile_passed: bool | None = None,
          compile_command: str = "", runtime_runner: RuntimeRunner | None = None, **testing) -> dict:
    runner = runtime_runner or RUNNERS.get(platform)
    if runner is None:
        raise ValueError("platform must be android or arkts")
    return _score(spec=SPEC, platform=platform, source=source, base_source=base_source,
                  final_source=final_source, output=output, timeout=timeout,
                  compile_passed=compile_passed, compile_command=compile_command,
                  runtime_runner=runner, **testing)


dispatch = score


def main() -> int:
    return _main(task_id=SPEC.task_id)


if __name__ == "__main__":
    raise SystemExit(main())
