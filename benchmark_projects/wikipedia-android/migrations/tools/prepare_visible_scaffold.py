#!/usr/bin/env python3
"""Expose an empty candidate source root without injecting production logic."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task-id", choices=("01_reading_challenge", "02_hybrid_search"), required=True)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--migration", type=Path, required=True)
    args = parser.parse_args()

    project = args.project.resolve()
    build_path = project / "app/build.gradle.kts"
    build = build_path.read_text(encoding="utf-8")
    source_dir = project / "app/src/main/java"
    source_dir.mkdir(parents=True, exist_ok=True)
    if '"src/main/java"' not in build:
        updated = re.sub(
            r'(kotlin\.srcDirs\(\s*"src/main/upstream/kotlin")',
            r'\1,\n                "src/main/java"',
            build,
            count=1,
        )
        if updated == build:
            updated = build.replace(
                "kotlin.srcDirs(\n",
                "kotlin.srcDirs(\n                \"src/main/java\",\n",
                1,
            )
        build = updated
    build = re.sub(
        r'\s*getByName\("androidTest"\)\s*\{\s*kotlin\.srcDirs\("\.\./\.\./\.\./shared/native_test/kotlin"\)\s*\}',
        "",
        build,
        flags=re.MULTILINE,
    )
    build_path.write_text(build, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
