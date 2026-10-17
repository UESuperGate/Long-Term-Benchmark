#!/usr/bin/env python3
"""Remove reproducible build intermediates while preserving final evidence."""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HARMONY = ROOT / "elementx_harmony_full"
ANDROID = ROOT / "_worktrees" / "element-x-android-v26.04.0"
REPORT = HARMONY / "verification" / "cleanup-report.json"


def directory_size(path: Path) -> int:
    if not path.exists():
        return 0
    if path.is_file():
        return path.stat().st_size
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


def candidates(deep: bool) -> list[Path]:
    paths = [
        HARMONY / "entry" / ".cxx",
        HARMONY / "entry" / "build" / "default" / "intermediates",
        HARMONY / "entry" / "build" / "default" / "cache",
        HARMONY / "native" / "matrix-sdk-bridge" / "target" / "release",
        HARMONY / "native" / "matrix-sdk-bridge" / "target" / "aarch64-unknown-linux-ohos" / "release" / "build",
        HARMONY / "native" / "matrix-sdk-bridge" / "target" / "aarch64-unknown-linux-ohos" / "release" / "deps",
        HARMONY / "native" / "matrix-sdk-bridge" / "target" / "aarch64-unknown-linux-ohos" / "release" / "incremental",
        ANDROID / ".gradle",
        ANDROID / "build",
    ]
    if ANDROID.exists():
        paths.extend(path for path in ANDROID.rglob("build") if path.is_dir())
    if deep:
        paths.append(HARMONY / "native" / "matrix-sdk-bridge" / "target")
    unique: dict[str, Path] = {}
    for path in paths:
        resolved = path.resolve()
        if resolved == ROOT or ROOT not in resolved.parents:
            raise RuntimeError(f"refusing cleanup outside workspace: {resolved}")
        unique[str(resolved)] = resolved
    return sorted(unique.values(), key=lambda item: len(item.parts), reverse=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true", help="delete listed intermediates")
    parser.add_argument("--deep", action="store_true", help="also remove the Cargo target directory")
    args = parser.parse_args()

    rows: list[dict[str, object]] = []
    total = 0
    for path in candidates(args.deep):
        if not path.exists():
            continue
        size = directory_size(path)
        total += size
        rows.append({"path": str(path.relative_to(ROOT)), "bytes": size})
        if args.execute:
            shutil.rmtree(path)

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "executed": args.execute,
        "deep": args.deep,
        "bytes_selected": total,
        "paths": rows,
        "preserved": [
            "elementx_harmony_full/entry/build/default/outputs",
            "elementx_harmony_full/verification",
            "elementx_harmony_full/native/matrix-sdk-bridge/target/aarch64-unknown-linux-ohos/release/libelementx_matrix_sdk_bridge.a",
        ],
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
