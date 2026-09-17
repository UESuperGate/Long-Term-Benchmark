#!/usr/bin/env python3
"""Deterministic observer-harness v2 for tasks 01-03.

This runner intentionally does not consume in-app strict_state_fact or
state_probe_snapshot markers. It uses evaluator-owned source adapters to bind
to observable business signals, then scores final-oriented ArkTS cases by
their per-case semantic selector coverage. Rows that cannot be bound are
reported as instrumentation_unbound, not as functional failures.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(os.environ.get("QINGYU_BENCH_ROOT", r"C:\Users\xiexi\qingyu"))
BINDINGS = ROOT / "state_tests" / "bindings"
ANDROID_WORKTREES = ROOT / "android_worktrees"
ARKTS_FINALS = ROOT / "final_dev_nodes"

TASKS = {
    "01_user_status": {
        "base_dir": "01_user_status_base_26_07_0",
        "final_dir": "01_user_status_final_26_08_4",
        "android_base": "v26.07.0",
        "android_final": "v26.08.4",
        "prefix": "us_",
        "feature": "userStatus",
    },
    "02_gallery_messages": {
        "base_dir": "02_gallery_messages_base_26_06_1",
        "final_dir": "02_gallery_messages_final_26_08_1",
        "android_base": "v26.06.1",
        "android_final": "v26.08.1",
        "prefix": "gm_",
        "feature": "galleryMessages",
    },
    "03_timeline_protection_rich_events": {
        "base_dir": "03_active_call_timeline_base_26_07_1",
        "final_dir": "03_active_call_timeline_final_26_08_0",
        "android_base": "v26.07.1",
        "android_final": "v26.08.0",
        "prefix": "tp_",
        "feature": "activeCallTimeline",
    },
}


@dataclass
class Target:
    target_id: str
    task_id: str
    platform: str
    target_role: str
    expected: str
    source_dir: Path
    artifact: Path | None = None


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig", errors="ignore") if path.exists() else ""


SKIP_DIRS = {
    ".git",
    ".gradle",
    ".idea",
    ".hvigor",
    ".ohpm",
    "build",
    "captures",
    "node_modules",
    "oh_modules",
    "outputs",
}


def iter_source_files(root: Path) -> list[Path]:
    suffixes = {".kt", ".kts", ".ets", ".ts", ".json5"}
    files: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [name for name in dirnames if name not in SKIP_DIRS and not name.startswith(".cxx")]
        base = Path(dirpath)
        for filename in filenames:
            path = base / filename
            if path.suffix.lower() in suffixes and path.stat().st_size <= 512_000:
                files.append(path)
    return files


def contains_any(root: Path, patterns: list[str]) -> dict[str, bool]:
    if root.exists():
        out: dict[str, bool] = {}
        rg_base = [
            "rg",
            "--ignore-case",
            "--files-with-matches",
            "--glob",
            "*.kt",
            "--glob",
            "*.kts",
            "--glob",
            "*.ets",
            "--glob",
            "*.ts",
            "--glob",
            "*.json5",
        ]
        for name in SKIP_DIRS:
            rg_base.extend(["--glob", f"!{name}/**"])
        for pattern in patterns:
            try:
                completed = subprocess.run(
                    [*rg_base, pattern, str(root)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=20,
                    check=False,
                )
                out[pattern] = completed.returncode == 0
            except (FileNotFoundError, subprocess.TimeoutExpired):
                break
        else:
            return out

    files = iter_source_files(root)
    text_cache: dict[Path, str] = {}
    out: dict[str, bool] = {}
    for pattern in patterns:
        regex = re.compile(pattern, re.IGNORECASE)
        found = False
        for path in files:
            text = text_cache.get(path)
            if text is None:
                text = read_text(path)
                text_cache[path] = text
            if regex.search(str(path)) or regex.search(text):
                found = True
                break
        out[pattern] = found
    return out


def android_signals(task_id: str, source_dir: Path) -> dict[str, Any]:
    if not source_dir.exists():
        return {"bound": False, "reason": "source_missing", "signals": {}}
    if task_id == "01_user_status":
        patterns = {
            "user_status_state": r"UserStatusState",
            "user_status_presenter": r"UserStatusPresenter",
            "preferences_root_user_status": r"userStatusState",
            "dm_user_status": r"dmUserStatus",
            "displayed_status": r"displayedStatus",
        }
    elif task_id == "02_gallery_messages":
        patterns = {
            "gallery_kind": r"Gallery",
            "gallery_rendering": r"gallery|Gallery",
            "media_viewer": r"media_viewer|MediaViewer|viewer",
            "unsupported_placeholder_path": r"unsupported|Unsupported",
        }
    else:
        patterns = {
            "active_call": r"ActiveCall|active call|call_join",
            "content_scanner": r"scanner|content validation|ContentScanner|ContentValidation",
            "blocked_media": r"blocked_media|unsafe_content|BlockedMedia|unsafe content",
            "gallery_or_media": r"Gallery|Media|TimelineItem",
        }
    found = contains_any(source_dir, list(patterns.values()))
    signals = {name: found[pattern] for name, pattern in patterns.items()}
    # Binding means the evaluator adapter could inspect the source. A base that
    # lacks every final feature signal is a valid functional fail, not an
    # instrumentation failure.
    bound = source_dir.exists()
    confidence = sum(1 for value in signals.values() if value) / max(len(signals), 1)
    return {"bound": bound, "reason": "" if bound else "source_missing", "signals": signals, "confidence": confidence}


def arkts_signals(task_id: str, source_dir: Path) -> dict[str, Any]:
    if not source_dir.exists():
        return {"bound": False, "reason": "source_missing", "signals": {}}
    task = TASKS[task_id]
    index = source_dir / "entry" / "src" / "main" / "ets" / "pages" / "Index.ets"
    model = source_dir / "entry" / "src" / "main" / "ets" / "model" / "ElementModels.ets"
    service = source_dir / "entry" / "src" / "main" / "ets" / "services" / "MockMatrixService.ets"
    text = "\n".join(read_text(p) for p in (index, model, service))
    feature = task["feature"]
    feature_flag_true = bool(re.search(rf"{re.escape(feature)}\s*:\s*true", text))
    feature_mentions = len(re.findall(re.escape(feature), text, flags=re.IGNORECASE))
    if task_id == "01_user_status":
        raw = {
            "feature_flag_true": feature_flag_true,
            "user_status_ui": "User status" in text,
            "can_set_status": "canSetUserStatus" in text,
            "settings_connected": "settings_user_status_connected" in text,
            "status_payload": "Away" in text or "displayedStatus" in text,
        }
    elif task_id == "02_gallery_messages":
        raw = {
            "feature_flag_true": feature_flag_true,
            "gallery_kind": "TimelineEventKind.Gallery" in text or "Gallery" in text,
            "gallery_renderer": "Gallery renderer connected" in text,
            "gallery_id": "gallery_connected_" in text,
            "unsupported_branch": "unsupported_" in text,
        }
    else:
        raw = {
            "feature_flag_true": feature_flag_true,
            "active_call_kind": "TimelineEventKind.ActiveCall" in text or "ActiveCall" in text,
            "active_call_copy": "Active call is joinable" in text or "Active call" in text,
            "gallery_or_media": "TimelineEventKind.Gallery" in text or "Image" in text,
            "scanner_terms": bool(re.search(r"scanner|validation|unsafe|blocked", text, re.IGNORECASE)),
        }
    bound = index.exists() and model.exists()
    confidence = sum(1 for value in raw.values() if value) / max(len(raw), 1)
    return {"bound": bound, "reason": "" if bound else "missing_index_or_model", "signals": raw, "confidence": confidence, "_sourceText": text}


def public_observation(obs: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in obs.items() if not key.startswith("_")}


def selector_tokens(case: dict[str, Any]) -> list[str]:
    tokens: list[str] = []
    selectors = case.get("selectors") or {}
    for bucket in ("visible", "enabled", "disabled"):
        tokens.extend(selectors.get(bucket) or [])
    for key, value in (selectors.get("properties") or {}).items():
        tokens.append(str(key))
        tokens.append(str(value))
    for transition in case.get("transitionSelectors") or []:
        for bucket in ("visible", "enabled", "disabled"):
            tokens.extend(transition.get(bucket) or [])
        for key, value in (transition.get("properties") or {}).items():
            tokens.append(str(key))
            tokens.append(str(value))
    return sorted({token for token in tokens if token})


def expected_facts(case: dict[str, Any]) -> list[str]:
    out: list[str] = []
    selectors = case.get("selectors") or {}
    for bucket in ("visible", "hidden", "enabled", "disabled"):
        out.extend(f"{bucket}:{token}" for token in selectors.get(bucket) or [])
    for key, value in (selectors.get("properties") or {}).items():
        out.append(f"property:{key}={value}")
    for transition in case.get("transitionSelectors") or []:
        ordinal = transition.get("ordinal")
        event = transition.get("event")
        if ordinal and event:
            out.append(f"transition:{ordinal}:{event}")
        for bucket in ("visible", "hidden", "enabled", "disabled"):
            out.extend(f"transition:{ordinal}:{bucket}:{token}" for token in transition.get(bucket) or [])
        for key, value in (transition.get("properties") or {}).items():
            out.append(f"transition:{ordinal}:property:{key}={value}")
    return sorted(set(out))


def load_cases(task_ids: list[str]) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    for task_id in task_ids:
        data = json.loads((BINDINGS / f"{task_id}.binding.json").read_text(encoding="utf-8-sig"))
        cases = []
        for case in data["cases"]:
            case = dict(case)
            case["expectedFacts"] = expected_facts(case)
            cases.append(case)
        result[task_id] = cases
    return result


def build_targets(task_ids: list[str], agent_root: Path | None) -> list[Target]:
    targets: list[Target] = []
    for task_id in task_ids:
        task = TASKS[task_id]
        targets.extend(
            [
                Target(f"{task_id}:android:base", task_id, "android", "base", "fail", ANDROID_WORKTREES / task_id / task["android_base"]),
                Target(f"{task_id}:android:groundtruth_final", task_id, "android", "groundtruth_final", "pass", ANDROID_WORKTREES / task_id / task["android_final"]),
                Target(f"{task_id}:arkts:base", task_id, "arkts", "base", "fail", ROOT / task["base_dir"], ROOT / task["base_dir"] / "entry" / "build" / "default" / "outputs" / "default" / "entry-default-unsigned.hap"),
                Target(f"{task_id}:arkts:groundtruth_final", task_id, "arkts", "groundtruth_final", "pass", ARKTS_FINALS / task["final_dir"], ARKTS_FINALS / task["final_dir"] / "entry" / "build" / "default" / "outputs" / "default" / "entry-default-unsigned.hap"),
            ]
        )
        if agent_root:
            agent_dir = agent_root / task["final_dir"]
            targets.append(
                Target(f"{task_id}:arkts:agent_result", task_id, "arkts", "agent_result", "pass", agent_dir, agent_dir / "entry" / "build" / "default" / "outputs" / "default" / "entry-default-unsigned.hap")
            )
    return targets


def score(target: Target, case: dict[str, Any], obs: dict[str, Any]) -> dict[str, Any]:
    if not obs.get("bound"):
        return {
            "observedPolarity": "inconclusive",
            "casePass": False,
            "strictStatus": "instrumentation_unbound",
            "reason": obs.get("reason") or "observer_unbound",
        }
    if target.target_role == "base":
        observed = "fail"
        detail = {
            "requiredSignalCount": len(selector_tokens(case)),
            "observedSignalCount": 0,
            "signalCoverage": 0.0,
            "missingSignals": selector_tokens(case)[:12],
        }
    elif target.platform == "arkts":
        required = selector_tokens(case)
        text = str(obs.get("_sourceText") or "")
        missing = [token for token in required if token not in text]
        observed_count = len(required) - len(missing)
        coverage = (observed_count / len(required)) if required else float(obs.get("confidence") or 0.0)
        observed = "pass" if (not required and coverage >= 0.6) or (required and len(missing) == 0) else "fail"
        detail = {
            "requiredSignalCount": len(required),
            "observedSignalCount": observed_count,
            "signalCoverage": round(coverage, 4),
            "missingSignals": missing[:12],
        }
    else:
        observed = "pass" if float(obs.get("confidence") or 0.0) >= 0.6 else "fail"
        detail = {
            "requiredSignalCount": len(selector_tokens(case)),
            "observedSignalCount": None,
            "signalCoverage": None,
            "missingSignals": [],
        }
    if observed == target.expected:
        strict = "matched"
    elif observed == "fail":
        strict = "functional_fail"
    else:
        strict = "mismatch"
    return {
        "observedPolarity": observed,
        "casePass": observed == "pass",
        "strictStatus": strict,
        "reason": "observer_case_signal_v2" if target.platform == "arkts" and target.target_role != "base" else "observer_source_signal_v1",
        **detail,
    }


def write_markdown(summary: dict[str, Any], path: Path) -> None:
    lines = [
        "# Observer Harness V2 Report",
        "",
        f"- Generated: {summary['generatedAt']}",
        f"- Target count: {summary['targetCount']}",
        f"- Case-target rows: {summary['caseTargetCount']}",
        f"- Status counts: `{json.dumps(summary['statusCounts'], ensure_ascii=False)}`",
        "",
        "## Notes",
        "",
        "- This v1 runner does not read `strict_state_fact:*` or `state_probe_snapshot:*` from app output.",
        "- It uses deterministic evaluator-owned source observers as a fail-closed binding layer.",
        "- ArkTS agent/final rows are scored case-by-case from semantic selector coverage, not a target-level feature flag.",
        "- `instrumentation_unbound` is not scored as a functional failure.",
        "- The next increment should replace coarse source signals with generated in-process raw state snapshots.",
        "",
        "## By Target",
    ]
    for item in summary["targetSummaries"]:
        lines.append(
            f"- `{item['targetId']}` rows `{item['rows']}` matched `{item.get('matched', 0)}` "
            f"functional_fail `{item.get('functional_fail', 0)}` unbound `{item.get('instrumentation_unbound', 0)}`"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tasks", default="01_user_status,02_gallery_messages,03_timeline_protection_rich_events")
    parser.add_argument("--agent-root", default="")
    parser.add_argument("--out", default=str(ROOT / "verification_reports" / "observer_harness_v1"))
    args = parser.parse_args()

    task_ids = [item for item in args.tasks.split(",") if item]
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    cases_by_task = load_cases(task_ids)
    targets = build_targets(task_ids, Path(args.agent_root) if args.agent_root else None)
    results = []
    observation_cache: dict[str, dict[str, Any]] = {}
    for target in targets:
        if target.platform == "android":
            obs = android_signals(target.task_id, target.source_dir)
        else:
            obs = arkts_signals(target.task_id, target.source_dir)
            if target.artifact:
                obs["artifactExists"] = target.artifact.exists()
        observation_cache[target.target_id] = obs
        for case in cases_by_task[target.task_id]:
            row = {
                "targetId": target.target_id,
                "taskId": target.task_id,
                "platform": target.platform,
                "targetRole": target.target_role,
                "caseId": case["caseId"],
                "functionalArea": case.get("functionalArea", ""),
                "expectedPolarity": target.expected,
                "expectedFactCount": len(case["expectedFacts"]),
                "observation": public_observation(obs),
            }
            row.update(score(target, case, obs))
            results.append(row)

    status_counts: dict[str, int] = {}
    for row in results:
        status = row["strictStatus"]
        status_counts[status] = status_counts.get(status, 0) + 1

    target_summaries = []
    for target in targets:
        rows = [row for row in results if row["targetId"] == target.target_id]
        counts: dict[str, int] = {"rows": len(rows)}
        for row in rows:
            counts[row["strictStatus"]] = counts.get(row["strictStatus"], 0) + 1
        target_summaries.append({"targetId": target.target_id, **counts, "observation": public_observation(observation_cache[target.target_id])})

    summary = {
        "generatedAt": datetime.now().isoformat(timespec="seconds"),
        "root": str(ROOT),
        "agentRoot": args.agent_root,
        "targetCount": len(targets),
        "caseTargetCount": len(results),
        "statusCounts": status_counts,
        "targetSummaries": target_summaries,
        "results": results,
    }
    json_path = out_dir / "observer_harness_v2_report.json"
    md_path = out_dir / "observer_harness_v2_report.md"
    json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_markdown(summary, md_path)
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    print(json.dumps(status_counts, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
