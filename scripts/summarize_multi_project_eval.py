#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def semantic_counts(report: dict[str, Any]) -> dict[str, int]:
    semantic = report.get("semantic", {})
    counts = semantic.get("summary", semantic)
    result = {
        key: counts.get(key)
        for key in ("passed", "failed", "notScored", "total")
    }
    if not all(isinstance(value, int) and value >= 0 for value in result.values()):
        raise ValueError("semantic counts must be non-negative integers")
    if result["passed"] + result["failed"] + result["notScored"] != result["total"]:
        raise ValueError("semantic counts do not add up to total")
    return result  # type: ignore[return-value]


def metric(passed: int, total: int) -> dict[str, Any]:
    return {
        "passed": passed,
        "total": total,
        "rate": round(passed / total, 6) if total else None,
    }


def empty_bucket() -> dict[str, int]:
    return {
        "runs": 0,
        "codeGeneration": 0,
        "compile": 0,
        "semanticPassed": 0,
        "semanticTotal": 0,
    }


def add_report(bucket: dict[str, int], report: dict[str, Any]) -> None:
    code_generation = report.get("codeGeneration", {}).get("passed")
    compile_passed = report.get("compile", {}).get("passed")
    if not isinstance(code_generation, bool) or not isinstance(compile_passed, bool):
        raise ValueError("codeGeneration.passed and compile.passed must be boolean")
    semantic = semantic_counts(report)
    if semantic["notScored"]:
        raise ValueError("formal agent report contains unscored semantic cases")
    bucket["runs"] += 1
    bucket["codeGeneration"] += int(code_generation)
    bucket["compile"] += int(compile_passed)
    bucket["semanticPassed"] += semantic["passed"]
    bucket["semanticTotal"] += semantic["total"]


def render(bucket: dict[str, int]) -> dict[str, Any]:
    return {
        "taskRuns": bucket["runs"],
        "codeGeneration": metric(bucket["codeGeneration"], bucket["runs"]),
        "compile": metric(bucket["compile"], bucket["runs"]),
        "semanticTestcase": metric(bucket["semanticPassed"], bucket["semanticTotal"]),
    }


def summarize(run_root: Path, catalog_path: Path) -> dict[str, Any]:
    catalog = load(catalog_path)
    aggregate = empty_bucket()
    platforms = {"android": empty_bucket(), "arkts": empty_bucket()}
    projects: dict[str, Any] = {}
    rows: list[dict[str, Any]] = []

    for project_entry in catalog["projects"]:
        project_id = project_entry["projectId"]
        project_catalog = load(catalog_path.parent / project_entry["catalog"])
        project_buckets = {"android": empty_bucket(), "arkts": empty_bucket()}
        for task_id in project_catalog["acceptedTaskIds"]:
            for platform in ("android", "arkts"):
                report_path = run_root / project_id / task_id / f"{platform}-agent.json"
                if not report_path.is_file():
                    raise FileNotFoundError(f"missing formal report: {report_path}")
                report = load(report_path)
                if report.get("taskId") != task_id or report.get("platform") != platform:
                    raise ValueError(f"report identity mismatch: {report_path}")
                semantic = semantic_counts(report)
                add_report(project_buckets[platform], report)
                add_report(platforms[platform], report)
                add_report(aggregate, report)
                rows.append({
                    "projectId": project_id,
                    "taskId": task_id,
                    "platform": platform,
                    "codeGeneration": report["codeGeneration"]["passed"],
                    "compile": report["compile"]["passed"],
                    "semanticTestcase": semantic,
                    "report": str(report_path.relative_to(run_root.parent)),
                })
        projects[project_id] = {
            platform: render(project_buckets[platform])
            for platform in ("android", "arkts")
        }

    return {
        "schemaVersion": 1,
        "runId": run_root.name,
        "metrics": render(aggregate),
        "platforms": {platform: render(bucket) for platform, bucket in platforms.items()},
        "projects": projects,
        "rows": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, default=ROOT / "benchmark_projects/catalog.json")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    result = summarize(args.run_root.resolve(), args.catalog.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
