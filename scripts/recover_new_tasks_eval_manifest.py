#!/usr/bin/env python3
"""Recover a resumable evaluation manifest from durable logs and reports."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MODEL = "minimax-token-plan/MiniMax-M3"
ENDPOINT = "https://api.minimaxi.com/v1"


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def log_events(path: Path) -> list[dict[str, Any]]:
    events = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events


def stamp(milliseconds: int) -> datetime:
    return datetime.fromtimestamp(milliseconds / 1000).astimezone()


def available_row(report: Path, log: Path) -> dict[str, Any]:
    payload = load(report)
    events = log_events(log)
    timestamps = [int(event["timestamp"]) for event in events if event.get("timestamp")]
    started = stamp(min(timestamps)) if timestamps else datetime.fromtimestamp(log.stat().st_mtime).astimezone()
    finished = datetime.fromisoformat(payload["generatedAt"]).astimezone()
    text = log.read_text(encoding="utf-8", errors="replace")
    timed_out = "runner_timeout" in text
    errored = any(event.get("type") == "error" for event in events)
    return {
        "taskId": payload["taskId"],
        "platform": payload["platform"],
        "model": MODEL,
        "endpoint": ENDPOINT,
        "startedAt": started.isoformat(timespec="seconds"),
        "finishedAt": finished.isoformat(timespec="seconds"),
        "durationSeconds": round((finished - started).total_seconds(), 3),
        "agentTimeoutSeconds": 3600,
        "agentExit": 124 if timed_out else (1 if errored else 0),
        "agentTimedOut": timed_out,
        "codeGenerated": bool(payload["codeGeneration"]["passed"]),
        "generatedCodeFiles": payload["codeGeneration"].get("changedProductionFiles", []),
        "compile": "passed" if payload["compile"]["passed"] else "failed",
        "buildExit": 0 if payload["compile"]["passed"] else 1,
        "semanticReport": str(report),
        "workspacePathLeakDetected": False,
        "availability": "available",
        "benchmarkMetricsAvailable": True,
        "recoveredFromDurableArtifacts": True,
    }


def quota_row(platform: str, task_id: str, log: Path) -> dict[str, Any]:
    events = log_events(log)
    timestamps = [int(event["timestamp"]) for event in events if event.get("timestamp")]
    started = stamp(min(timestamps)) if timestamps else datetime.fromtimestamp(log.stat().st_mtime).astimezone()
    finished = stamp(max(timestamps)) if timestamps else started
    return {
        "taskId": task_id,
        "platform": platform,
        "model": MODEL,
        "endpoint": ENDPOINT,
        "startedAt": started.isoformat(timespec="seconds"),
        "finishedAt": finished.isoformat(timespec="seconds"),
        "durationSeconds": round((finished - started).total_seconds(), 3),
        "agentExit": 1,
        "agentTimedOut": False,
        "availability": "provider_quota",
        "benchmarkMetricsAvailable": False,
        "recoveredFromDurableArtifacts": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    run_root = ROOT / "eval_runs" / args.run_id
    reports = run_root / "reports"
    logs = run_root / "logs"
    rows: list[dict[str, Any]] = []
    for report in sorted(reports.glob("*_agent.json")):
        payload = load(report)
        platform = str(payload["platform"])
        task_id = str(payload["taskId"])
        log = logs / f"{platform}_{task_id}_opencode.jsonl"
        if not log.exists():
            continue
        if '"type":"provider.quota"' in log.read_text(encoding="utf-8", errors="replace"):
            rows.append(quota_row(platform, task_id, log))
        else:
            rows.append(available_row(report, log))
    indexed = {(row["platform"], row["taskId"]) for row in rows}
    for log in sorted(logs.glob("*_opencode.jsonl")):
        content = log.read_text(encoding="utf-8", errors="replace")
        if '"type":"provider.quota"' not in content:
            continue
        stem = log.name.removesuffix("_opencode.jsonl")
        platform, task_id = stem.split("_", 1)
        if (platform, task_id) not in indexed:
            rows.append(quota_row(platform, task_id, log))
    starts = [datetime.fromisoformat(row["startedAt"]) for row in rows]
    finishes = [datetime.fromisoformat(row["finishedAt"]) for row in rows]
    started = min(starts)
    finished = max(finishes)
    payload = {
        "schemaVersion": 1,
        "runId": args.run_id,
        "status": "partial",
        "startedAt": started.isoformat(timespec="seconds"),
        "finishedAt": finished.isoformat(timespec="seconds"),
        "durationSeconds": round((finished - started).total_seconds(), 3),
        "timingScope": "overall run start through the last task completion; subagents are not timed separately",
        "concurrencyPolicy": "at most one candidate per platform; Android and ArkTS may run concurrently",
        "model": MODEL,
        "endpoint": ENDPOINT,
        "opencodeVersion": "2.0.20",
        "candidateRoot": str((ROOT.parent / ".ltb-new-tasks-eval" / args.run_id).resolve()),
        "candidatesPreserved": False,
        "tasks": sorted(rows, key=lambda row: (row["platform"], row["taskId"])),
    }
    output = run_root / "eval_manifest.partial.json"
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), "available": sum(row["availability"] == "available" for row in rows), "unavailable": sum(row["availability"] != "available" for row in rows)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
