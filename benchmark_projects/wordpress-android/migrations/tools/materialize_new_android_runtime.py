#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path


TASKS = {
    "03_site_picker": {
        "base": {
            "commit": "38d40e2acee2f487dd2e43da908233e847ee4cc4",
            "compiled_files": {
                "WordPress/src/main/java/org/wordpress/android/viewmodel/main/SitePickerViewModel.kt":
                    "org/wordpress/android/viewmodel/main/SitePickerViewModel.kt",
            },
            "files": [
                "WordPress/src/main/java/org/wordpress/android/ui/main/SitePickerContract.kt",
                "WordPress/src/main/java/org/wordpress/android/viewmodel/main/SitePickerViewModel.kt",
            ],
        },
        "final": {
            "commit": "d70ced8dc334e6d930af5570b9d1498407835262",
            "compiled_files": {
                "WordPress/src/main/java/org/wordpress/android/ui/main/ChooseSiteAdapter.kt":
                    "org/wordpress/android/ui/main/ChooseSiteAdapter.kt",
                "WordPress/src/main/java/org/wordpress/android/ui/main/ChooseSiteViewHolder.kt":
                    "org/wordpress/android/ui/main/ChooseSiteViewHolder.kt",
                "WordPress/src/main/java/org/wordpress/android/ui/main/SiteRecord.kt":
                    "org/wordpress/android/ui/main/SiteRecord.kt",
                "WordPress/src/main/java/org/wordpress/android/ui/main/SiteViewModel.kt":
                    "org/wordpress/android/ui/main/SiteViewModel.kt",
                "WordPress/src/main/java/org/wordpress/android/ui/main/utils/SiteRecordUtil.kt":
                    "org/wordpress/android/ui/main/utils/SiteRecordUtil.kt",
            },
            "files": [
                "WordPress/src/main/java/org/wordpress/android/ui/main/ChooseSiteActivity.kt",
                "WordPress/src/main/java/org/wordpress/android/ui/main/ChooseSiteAdapter.kt",
                "WordPress/src/main/java/org/wordpress/android/ui/main/ChooseSiteViewHolder.kt",
                "WordPress/src/main/java/org/wordpress/android/ui/main/SiteRecord.kt",
                "WordPress/src/main/java/org/wordpress/android/ui/main/SiteViewModel.kt",
                "WordPress/src/main/java/org/wordpress/android/ui/main/utils/SiteRecordUtil.kt",
                "WordPress/src/main/java/org/wordpress/android/ui/prefs/AppPrefsWrapper.kt",
            ],
        },
    },
    "04_new_stats": {
        "base": {
            "commit": "52d78ca3a60d3ae77fce80a304416eae65f68523",
            "compiled_files": {
                "WordPress/src/main/java/org/wordpress/android/ui/newstats/StatsPeriod.kt":
                    "org/wordpress/android/ui/newstats/StatsPeriod.kt",
                "WordPress/src/main/java/org/wordpress/android/ui/newstats/viewsstats/ViewsStatsCardUiState.kt":
                    "org/wordpress/android/ui/newstats/viewsstats/ViewsStatsCardUiState.kt",
                "WordPress/src/main/java/org/wordpress/android/ui/newstats/viewsstats/ViewsStatsViewModel.kt":
                    "org/wordpress/android/ui/newstats/viewsstats/ViewsStatsViewModel.kt",
            },
            "files": [
                "WordPress/src/main/java/org/wordpress/android/ui/newstats/StatsPeriod.kt",
                "WordPress/src/main/java/org/wordpress/android/ui/newstats/viewsstats/ViewsStatsCardUiState.kt",
                "WordPress/src/main/java/org/wordpress/android/ui/newstats/viewsstats/ViewsStatsViewModel.kt",
            ],
        },
        "final": {
            "commit": "e6dbc793f2256380cd7ab3c9210aae0cdd07710b",
            "compiled_files": {
                "WordPress/src/main/java/org/wordpress/android/ui/newstats/StatsPeriod.kt":
                    "org/wordpress/android/ui/newstats/StatsPeriod.kt",
                "WordPress/src/main/java/org/wordpress/android/ui/newstats/viewsstats/ViewsStatsCardUiState.kt":
                    "org/wordpress/android/ui/newstats/viewsstats/ViewsStatsCardUiState.kt",
                "WordPress/src/main/java/org/wordpress/android/ui/newstats/viewsstats/ViewsStatsViewModel.kt":
                    "org/wordpress/android/ui/newstats/viewsstats/ViewsStatsViewModel.kt",
                "WordPress/src/main/java/org/wordpress/android/ui/newstats/repository/StatsRepository.kt":
                    "org/wordpress/android/ui/newstats/repository/StatsRepository.kt",
                "WordPress/src/main/java/org/wordpress/android/ui/newstats/repository/StatsResultCache.kt":
                    "org/wordpress/android/ui/newstats/repository/StatsResultCache.kt",
                "WordPress/src/main/java/org/wordpress/android/ui/newstats/locations/LocationsCardUiState.kt":
                    "org/wordpress/android/ui/newstats/locations/LocationsCardUiState.kt",
                "WordPress/src/main/java/org/wordpress/android/ui/newstats/locations/LocationsViewModel.kt":
                    "org/wordpress/android/ui/newstats/locations/LocationsViewModel.kt",
                "WordPress/src/main/java/org/wordpress/android/ui/newstats/datasource/StatsDataSource.kt":
                    "org/wordpress/android/ui/newstats/datasource/StatsDataSource.kt",
                "WordPress/src/main/java/org/wordpress/android/ui/newstats/datasource/StatsErrorType.kt":
                    "org/wordpress/android/ui/newstats/datasource/StatsErrorType.kt",
                "WordPress/src/main/java/org/wordpress/android/ui/newstats/datasource/StatsApiError.kt":
                    "org/wordpress/android/ui/newstats/datasource/StatsApiError.kt",
            },
            "files": [
                "WordPress/src/main/java/org/wordpress/android/ui/newstats/StatsPeriod.kt",
                "WordPress/src/main/java/org/wordpress/android/ui/newstats/viewsstats/ViewsStatsCardUiState.kt",
                "WordPress/src/main/java/org/wordpress/android/ui/newstats/viewsstats/ViewsStatsViewModel.kt",
                "WordPress/src/main/java/org/wordpress/android/ui/newstats/repository/StatsRepository.kt",
                "WordPress/src/main/java/org/wordpress/android/ui/newstats/repository/StatsResultCache.kt",
                "WordPress/src/main/java/org/wordpress/android/ui/newstats/locations/LocationsCardUiState.kt",
                "WordPress/src/main/java/org/wordpress/android/ui/newstats/locations/LocationsViewModel.kt",
                "WordPress/src/main/java/org/wordpress/android/ui/newstats/datasource/StatsDataSource.kt",
                "WordPress/src/main/java/org/wordpress/android/ui/newstats/datasource/StatsErrorType.kt",
                "WordPress/src/main/java/org/wordpress/android/ui/newstats/datasource/StatsApiError.kt",
            ],
        },
    },
}


def git(repo: Path, *args: str) -> bytes:
    return subprocess.check_output(["git", "-C", str(repo), *args])


def materialize(repo_root: Path, task_id: str) -> None:
    source_repo = repo_root / "_sources/wordpress-android"
    migration = repo_root / "benchmark_projects/wordpress-android/migrations" / task_id
    task = repo_root / "benchmark_projects/wordpress-android/tasks" / task_id
    canonical = migration / "canonical"
    canonical.mkdir(parents=True, exist_ok=True)
    contract_bytes = (task / "transitions.json").read_bytes()
    (canonical / "transitions.json").write_bytes(contract_bytes)

    for role, spec in TASKS[task_id].items():
        root = migration / "android/focused-runtime" / role
        upstream = root / "upstream-immutable"
        compiled = migration / "android/focused-runtime/evaluator" / f"{role}-production"
        rows = []
        for relative in spec["files"]:
            data = git(source_repo, "show", f"{spec['commit']}:{relative}")
            destination = upstream / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(data)
            compiled_relative = spec.get("compiled_files", {}).get(relative)
            if compiled_relative:
                compiled_destination = compiled / compiled_relative
                compiled_destination.parent.mkdir(parents=True, exist_ok=True)
                compiled_destination.write_bytes(data)
            rows.append(
                {
                    "path": relative,
                    "gitBlob": git(source_repo, "rev-parse", f"{spec['commit']}:{relative}").decode().strip(),
                    "sha256": hashlib.sha256(data).hexdigest(),
                    "bytes": len(data),
                }
            )
        manifest = {
            "schemaVersion": 1,
            "taskId": task_id,
            "role": role,
            "repository": "https://github.com/wordpress-mobile/WordPress-Android.git",
            "commit": spec["commit"],
            "copyPolicy": "byte_exact_upstream_immutable",
            "compiledFiles": spec.get("compiled_files", {}),
            "files": rows,
        }
        (root / "upstream-source-manifest.json").write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("task_id", choices=sorted(TASKS))
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[4])
    args = parser.parse_args()
    materialize(args.repo_root.resolve(), args.task_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
