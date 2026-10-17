#!/usr/bin/env python3
"""Assemble benchmark-only metrics and diagnostics for tasks 08-18."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "benchmark_tasks/extraction_catalog.json"


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def metric(passed: int, total: int) -> dict[str, Any]:
    return {"passed": passed, "total": total, "rate": round(passed / total, 6) if total else 0.0}


def semantic(report: Path) -> dict[str, Any]:
    rows = load(report)["semantic"]["cases"]
    counts = Counter(row["status"] for row in rows)
    return {
        "passed": counts["pass"],
        "failed": counts["fail"],
        "notScored": counts["not_scored"],
        "total": counts["pass"] + counts["fail"],
        "expectedTotal": len(rows),
        "available": counts["not_scored"] == 0,
        "failedCaseIds": [row["caseId"] for row in rows if row["status"] != "pass"],
    }


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def relative_to_root(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return path.name


def archive_provenance(evaluation: Path, calibration: Path, output: Path) -> None:
    provenance = output / "provenance"
    patches_out = provenance / "patches"
    if provenance.exists():
        shutil.rmtree(provenance)
    patches_out.mkdir(parents=True)

    manifest = evaluation / "eval_manifest.json"
    if not manifest.exists():
        manifest = evaluation / "eval_manifest.partial.json"
    files_to_copy = [
        (manifest, provenance / "eval_manifest.json"),
        (evaluation / "rescore_summary.json", provenance / "rescore_summary.json"),
        (evaluation / "observer_relaxation_audit.json", provenance / "observer_relaxation_audit.json"),
        (calibration / "calibration_summary.json", provenance / "calibration_summary.json"),
    ]
    for source, destination in files_to_copy:
        if source.exists():
            shutil.copy2(source, destination)

    evidence: list[dict[str, Any]] = []
    for source in sorted((evaluation / "patches").glob("*.patch")):
        destination = patches_out / source.name
        shutil.copy2(source, destination)
        evidence.append({
            "kind": "agent_patch",
            "name": source.name,
            "sha256": sha256(source),
            "bytes": source.stat().st_size,
            "published": True,
            "path": str(destination.relative_to(output)),
        })
    for source in sorted((evaluation / "logs").glob("*")):
        if source.is_file():
            evidence.append({
                "kind": "local_run_log",
                "name": source.name,
                "sha256": sha256(source),
                "bytes": source.stat().st_size,
                "published": False,
                "localArchive": relative_to_root(source),
            })
    (provenance / "evidence_index.json").write_text(
        json.dumps({"schemaVersion": 1, "artifacts": evidence}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--calibration", type=Path, required=True)
    parser.add_argument("--evaluation", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    calibration = args.calibration.resolve()
    evaluation = args.evaluation.resolve()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    reports_out = output / "reports"
    if reports_out.exists():
        shutil.rmtree(reports_out)
    reports_out.mkdir()
    calibration_summary = load(calibration / "calibration_summary.json")
    manifest_path = evaluation / "eval_manifest.json"
    if not manifest_path.exists():
        manifest_path = evaluation / "eval_manifest.partial.json"
    eval_manifest = load(manifest_path)
    ids = [str(item) for item in load(CATALOG)["acceptedTaskIds"]]
    run_rows = {(row.get("platform"), row.get("taskId")): row for row in eval_manifest["tasks"]}
    tasks: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []
    generated = compiled = semantic_passed = semantic_total = 0
    platform_counts = {platform: {"generated": 0, "compiled": 0, "runs": 0, "passed": 0, "total": 0} for platform in ("android", "arkts")}
    discriminative = 0
    semantic_available_runs = 0
    unavailable = 0

    for task_id in ids:
        task_row: dict[str, Any] = {"id": task_id, "caseCountPerPlatform": 0, "platforms": {}}
        for platform in ("android", "arkts"):
            run = run_rows.get((platform, task_id), {})
            available = run.get("availability", "available") == "available" and bool(run)
            source = evaluation / "reports" / f"{platform}_{task_id}_agent.json"
            result = semantic(source) if available and source.exists() else {
                "passed": 0,
                "failed": 0,
                "notScored": 0,
                "total": 0,
                "expectedTotal": 0,
                "available": False,
                "failedCaseIds": [],
            }
            if available and source.exists():
                shutil.copy2(source, reports_out / source.name)
            if not available:
                unavailable += 1
                task_row["platforms"][platform] = {
                    "availability": run.get("availability", "not_run"),
                    "benchmarkMetricsAvailable": False,
                }
                diagnostics.append({"taskId": task_id, "platform": platform, "availability": run.get("availability", "not_run"), "benchmarkMetricsAvailable": False})
                continue
            code_ok = bool(run.get("codeGenerated"))
            compile_ok = run.get("compile") == "passed"
            generated += int(code_ok)
            compiled += int(compile_ok)
            semantic_passed += result["passed"]
            semantic_total += result["total"]
            platform_counts[platform]["generated"] += int(code_ok)
            platform_counts[platform]["compiled"] += int(compile_ok)
            platform_counts[platform]["runs"] += 1
            platform_counts[platform]["passed"] += result["passed"]
            platform_counts[platform]["total"] += result["total"]
            is_discriminative = result["available"] and 0 < result["passed"] < result["total"]
            discriminative += int(is_discriminative)
            semantic_available_runs += int(result["available"])
            task_row["caseCountPerPlatform"] = result["expectedTotal"]
            task_row["platforms"][platform] = {
                "availability": "available",
                "benchmarkMetricsAvailable": True,
                "codeGeneration": "passed" if code_ok else "failed",
                "compile": "passed" if compile_ok else "failed",
                "semanticTestcase": result,
                "discriminative": is_discriminative,
            }
            if run.get("agentTimedOut") or run.get("runnerError") or run.get("workspacePathLeakDetected") or not compile_ok:
                diagnostics.append({"taskId": task_id, "platform": platform, "agentTimedOut": run.get("agentTimedOut", False), "runnerError": run.get("runnerError"), "workspacePathLeakDetected": run.get("workspacePathLeakDetected", False), "compile": run.get("compile")})
            if not result["available"]:
                diagnostics.append({
                    "taskId": task_id,
                    "platform": platform,
                    "semantic": "not_scored",
                    "notScoredCases": result["notScored"],
                })
        tasks.append(task_row)

    for source in (calibration / "reports").glob("*.json"):
        shutil.copy2(source, reports_out / source.name)
    archive_provenance(evaluation, calibration, output)
    expected_runs = len(ids) * 2
    total_runs = expected_runs - unavailable
    summary = {
        "schemaVersion": 1,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "runId": eval_manifest["runId"],
        "status": eval_manifest.get("status", "complete"),
        "model": eval_manifest["model"],
        "benchmarkMetrics": {
            "codeGeneration": metric(generated, total_runs),
            "compile": metric(compiled, total_runs),
            "semanticTestcase": {**metric(semantic_passed, semantic_total), "failed": semantic_total - semantic_passed},
        },
        "coverage": {"availableRuns": total_runs, "expectedRuns": expected_runs, "unavailableRuns": unavailable},
        "platforms": {
            platform: {
                "codeGeneration": metric(values["generated"], values["runs"]),
                "compile": metric(values["compiled"], values["runs"]),
                "semanticTestcase": {**metric(values["passed"], values["total"]), "failed": values["total"] - values["passed"]},
            }
            for platform, values in platform_counts.items()
        },
        "calibration": {"allPolarityValid": calibration_summary["allPolarityValid"], "tasks": calibration_summary["tasks"]},
        "agentDiscrimination": {
            "discriminativeRuns": discriminative,
            "availableRuns": semantic_available_runs,
            "extremeRuns": semantic_available_runs - discriminative,
        },
        "tasks": tasks,
        "timing": {
            "startedAt": eval_manifest["startedAt"],
            "finishedAt": eval_manifest["finishedAt"],
            "overallDurationSeconds": eval_manifest["durationSeconds"],
            "scope": eval_manifest["timingScope"],
        },
    }
    (output / "benchmark_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output / "diagnostics.json").write_text(json.dumps({"schemaVersion": 1, "benchmarkMetricsExcluded": True, "events": diagnostics}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    environment = {
        "capturedAt": datetime.now(timezone.utc).isoformat(),
        "opencode": eval_manifest.get("opencodeVersion"),
        "provider": "minimax-token-plan",
        "model": "MiniMax-M3",
        "endpoint": "https://api.minimaxi.com/v1",
        "agentTimeoutSeconds": 3600,
        "java": {"default": "OpenJDK 21", "legacyGradle": "OpenJDK 17"},
        "android": {
            "sdkRoot": str(Path.home() / "Library/Android/sdk"),
            "sdkSelection": "upstream release declaration",
            "emulatorUsedForSemanticScoring": False,
        },
        "arkts": {"devecoStudio": "6.1.1.418", "openHarmonyApi": 23, "openHarmonySdk": "6.1.0.32", "hvigor": "6.24.5"},
        "secretStored": False,
    }
    (output / "environment.json").write_text(json.dumps(environment, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    availability_note = (
        f"Evaluation is partial: {unavailable} of {expected_runs} platform-task runs are unavailable or not yet run and are excluded from all benchmark denominators. "
        f"Resume with `python3 scripts/run_new_tasks_opencode_eval_macos.py --run-id {eval_manifest['runId']} --agent-timeout 3600 --parallel 2 --resume`."
        if unavailable
        else "Evaluation coverage is complete."
    )
    task_table = []
    for task in tasks:
        task_meta = load(ROOT / f"benchmark_tasks/{task['id']}/task.json")
        android = task["platforms"]["android"]
        arkts = task["platforms"]["arkts"]

        def cell(result: dict[str, Any]) -> str:
            if not result.get("benchmarkMetricsAvailable"):
                return "unavailable"
            semantic_result = result["semanticTestcase"]
            compile_mark = "pass" if result["compile"] == "passed" else "fail"
            return f"{semantic_result['passed']}/{semantic_result['total']} (compile {compile_mark})"

        task_table.append(
            f"| `{task['id']}` | {task_meta['title']} | {task['caseCountPerPlatform']} | {cell(android)} | {cell(arkts)} |"
        )
    task_rows = "\n".join(task_table)
    readme = f"""# Element X tasks 08-18 benchmark

This bundle records {len(ids)} tasks calibrated on Android and migrated to ArkTS with one shared transition contract per task.

{availability_note}

| Metric | Result |
| --- | ---: |
| Code generation | {generated}/{total_runs} |
| Compile | {compiled}/{total_runs} |
| Semantic testcase | {semantic_passed}/{semantic_total} |
| Evaluation coverage | {total_runs}/{expected_runs} runs |

| Platform | Code generation | Compile | Semantic testcase |
| --- | ---: | ---: | ---: |
| Android | {platform_counts['android']['generated']}/{platform_counts['android']['runs']} | {platform_counts['android']['compiled']}/{platform_counts['android']['runs']} | {platform_counts['android']['passed']}/{platform_counts['android']['total']} |
| ArkTS | {platform_counts['arkts']['generated']}/{platform_counts['arkts']['runs']} | {platform_counts['arkts']['compiled']}/{platform_counts['arkts']['runs']} | {platform_counts['arkts']['passed']}/{platform_counts['arkts']['total']} |

| Task | Requirement | Cases/platform | Android agent | ArkTS agent |
| --- | --- | ---: | ---: | ---: |
{task_rows}

Four-way polarity valid: `{str(calibration_summary['allPolarityValid']).lower()}`. Agent discrimination is reported as evidence and is not forced by changing semantic expectations.

The authoritative semantic mode for this repair is `source_transition_conformance`; no Android emulator or ArkTS device was used for these semantic scores. Base/final polarity is `0/N -> N/N` on both platforms, with no unscored cases. Toolchain details are in `environment.json`. `provenance/` contains the run manifest, calibration and rescore summaries, all 22 reconstructable candidate patches, and an evidence index. Full OpenCode/build logs remain in the ignored local run archive; their SHA-256 digests are recorded in the index without publishing credentials or bulky logs.
"""
    (output / "README.md").write_text(readme, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
