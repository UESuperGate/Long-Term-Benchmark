#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
from pathlib import Path


def load_shared_runner():
    shared_path = Path(__file__).resolve().parents[3] / "01_pages_list/arkts/evaluator/run_device_semantic.py"
    spec = importlib.util.spec_from_file_location("wordpress_arkts_device_runner", shared_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load shared device runner: {shared_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    runner = load_shared_runner()

    def support_sources(project: Path) -> list[dict[str, str]]:
        relative_paths = [
            Path("entry/src/main/ets/features/UnifiedSupportController.ets"),
            Path("entry/src/main/ets/pages/Index.ets"),
            Path("entry/src/main/ets/pages/UnifiedSupportPageOwner.ets"),
            Path("entry/src/main/ets/entryability/EntryAbility.ets"),
        ]
        return [{"path": str(path), "sha256": runner.sha256(project / path)} for path in relative_paths]

    runner.production_sources = support_sources
    return runner.main()


if __name__ == "__main__":
    raise SystemExit(main())
