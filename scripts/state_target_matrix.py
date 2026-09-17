#!/usr/bin/env python3
"""
Generate the dynamic-test target matrix.

Benchmark polarity is fixed for golden targets:
- base: expected fail, because the final-oriented behavior is not present yet
- groundtruth_final: expected pass, because this is the real final implementation

Agent results are separate targets. They are scored against the final-positive
expectation, but they do not participate in validating base/final polarity.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime
from pathlib import Path

from state_dynamic_runner import ROOT, REPORT_DIR, iter_cases


MANIFEST = ROOT / "manifest.json"
ANDROID_SOURCE = ROOT / "_sources" / "element-x-android"
ANDROID_WORKTREES = ROOT / "android_worktrees"
ANDROID_BASE_ROOT = os.environ.get("QINGYU_ANDROID_BASE_ROOT")
ANDROID_FINAL_ROOT = os.environ.get("QINGYU_ANDROID_FINAL_ROOT")
ANDROID_AGENT_ROOT = os.environ.get("QINGYU_ANDROID_AGENT_ROOT")
ARKTS_BASE_ROOT = Path(os.environ.get("QINGYU_ARKTS_BASE_ROOT", str(ROOT)))
ARKTS_FINAL_ROOT = Path(os.environ.get("QINGYU_ARKTS_FINAL_ROOT", str(ROOT / "final_dev_nodes")))
ARKTS_AGENT_ROOT = os.environ.get("QINGYU_ARKTS_AGENT_ROOT")
TASK_FILTER = {item for item in os.environ.get("QINGYU_TASK_FILTER", "").split(",") if item}


TASK_IDS = [
    "01_user_status",
    "02_gallery_messages",
    "03_timeline_protection_rich_events",
    "04_live_location",
    "05_link_new_device",
]


def read_bundle(project_dir: Path) -> str:
    app_json = project_dir / "AppScope" / "app.json5"
    text = app_json.read_text(encoding="utf-8-sig")
    match = re.search(r'"bundleName"\s*:\s*"([^"]+)"', text)
    if not match:
        raise ValueError(f"bundleName not found in {app_json}")
    return match.group(1)


def read_bundle_optional(project_dir: Path, fallback: str) -> str:
    try:
        return read_bundle(project_dir)
    except Exception:
        return fallback


def final_dir_for(base_dir: str, final_tag: str) -> str:
    prefix = base_dir.split("_base_", 1)[0]
    version = final_tag.removeprefix("v").replace(".", "_")
    return f"{prefix}_final_{version}"


def android_worktree_dir(task_id: str, tag: str) -> Path:
    return ANDROID_WORKTREES / task_id / tag


def candidate_dir(root_value: str | None, task_id: str, manifest_dir: str, final_tag: str | None = None) -> Path | None:
    """Resolve evaluator-supplied generated-candidate roots without changing golden defaults."""
    if not root_value:
        return None
    root = Path(root_value)
    names = []
    if final_tag:
        names.append(final_dir_for(manifest_dir, final_tag))
    names.extend([task_id, manifest_dir])
    prefix = manifest_dir.split("_base_", 1)[0]
    names.append(prefix)
    for name in names:
        path = root / name
        if path.exists():
            return path
    return root / names[0]


def android_apk_path(worktree: Path) -> Path:
    apk_name = os.environ.get("QINGYU_ANDROID_APK_NAME", "app-gplay-universal-debug.apk")
    return worktree / "app" / "build" / "outputs" / "apk" / "gplay" / "debug" / apk_name


def arkts_hap_path(project_dir: Path) -> Path:
    return project_dir / "entry" / "build" / "default" / "outputs" / "default" / "entry-default-unsigned.hap"


def load_manifest() -> list[dict]:
    raw = json.loads(MANIFEST.read_text(encoding="utf-8-sig"))
    return raw["bases"]


def android_target(task_id: str, role: str, expected: str, tag: str, worktree: Path, is_groundtruth: bool) -> dict:
    return {
        "targetId": f"{task_id}:android:{role}",
        "taskId": task_id,
        "platform": "android",
        "targetRole": role,
        "release": "base" if role == "base" else "final",
        "expected": expected,
        "isGroundTruth": is_groundtruth,
        "tag": tag,
        "worktree": str(worktree),
        "apk": str(android_apk_path(worktree)),
        "package": "io.element.android.x.debug",
        "launchAdapter": "android instrumentation/debug state adapter",
    }


def arkts_target(
    task_id: str,
    role: str,
    expected: str,
    tag: str,
    project_dir: Path,
    bundle_fallback: str,
    is_groundtruth: bool,
) -> dict:
    return {
        "targetId": f"{task_id}:arkts:{role}",
        "taskId": task_id,
        "platform": "arkts",
        "targetRole": role,
        "release": "base" if role == "base" else "final",
        "expected": expected,
        "isGroundTruth": is_groundtruth,
        "tag": tag,
        "projectDir": str(project_dir),
        "hap": str(arkts_hap_path(project_dir)),
        "bundle": read_bundle_optional(project_dir, bundle_fallback),
        "launchAdapter": "ArkTS Want/deeplink state adapter",
    }


def build_targets() -> list[dict]:
    targets: list[dict] = []
    for index, item in enumerate(load_manifest()):
        task_id = TASK_IDS[index]
        if TASK_FILTER and task_id not in TASK_FILTER:
            continue

        manifest_dir = item["directory"]
        android_base_tag = item["android_base_tag"]
        android_final_tag = item["android_final_tag"]
        base_dir = ARKTS_BASE_ROOT / manifest_dir
        final_dir = ARKTS_FINAL_ROOT / final_dir_for(manifest_dir, android_final_tag)
        base_bundle = read_bundle(base_dir)

        android_base_worktree = candidate_dir(ANDROID_BASE_ROOT, task_id, manifest_dir) or android_worktree_dir(task_id, android_base_tag)
        android_final_worktree = candidate_dir(ANDROID_FINAL_ROOT, task_id, manifest_dir, android_final_tag) or android_worktree_dir(task_id, android_final_tag)

        targets.extend(
            [
                android_target(task_id, "base", "fail", android_base_tag, android_base_worktree, True),
                android_target(task_id, "groundtruth_final", "pass", android_final_tag, android_final_worktree, True),
                arkts_target(task_id, "base", "fail", android_base_tag, base_dir, base_bundle, True),
                arkts_target(task_id, "groundtruth_final", "pass", android_final_tag, final_dir, base_bundle, True),
            ]
        )

        android_agent_worktree = candidate_dir(ANDROID_AGENT_ROOT, task_id, manifest_dir, android_final_tag)
        if android_agent_worktree is not None:
            target = android_target(task_id, "agent_result", "pass", android_final_tag, android_agent_worktree, False)
            target["candidateOf"] = f"{task_id}:android:groundtruth_final"
            target["sourceRootEnv"] = "QINGYU_ANDROID_AGENT_ROOT"
            targets.append(target)

        arkts_agent_dir = candidate_dir(ARKTS_AGENT_ROOT, task_id, manifest_dir, android_final_tag)
        if arkts_agent_dir is not None:
            target = arkts_target(task_id, "agent_result", "pass", android_final_tag, arkts_agent_dir, base_bundle, False)
            target["candidateOf"] = f"{task_id}:arkts:groundtruth_final"
            target["sourceRootEnv"] = "QINGYU_ARKTS_AGENT_ROOT"
            targets.append(target)

    return targets


def case_matrix(cases: list, targets: list[dict]) -> list[dict]:
    rows: list[dict] = []
    targets_by_task: dict[str, list[dict]] = {}
    for target in targets:
        targets_by_task.setdefault(target["taskId"], []).append(target)

    for case in cases:
        for target in targets_by_task.get(case.task_id, []):
            rows.append(
                {
                    "caseId": case.case_id,
                    "caseTitle": case.case_title,
                    "functionalArea": case.functional_area,
                    "fixtureKind": case.fixture_kind,
                    "taskId": case.task_id,
                    "targetId": target["targetId"],
                    "platform": target["platform"],
                    "targetRole": target["targetRole"],
                    "release": target["release"],
                    "expected": target["expected"],
                    "isGroundTruth": target["isGroundTruth"],
                }
            )
    return rows


def write_markdown(report: dict, path: Path) -> None:
    lines: list[str] = []
    lines.append("# State Dynamic Target Matrix")
    lines.append("")
    lines.append(f"- Generated: {report['generatedAt']}")
    lines.append(f"- Targets: {len(report['targets'])}")
    lines.append(f"- Case-target rows: {len(report['caseTargets'])}")
    lines.append("- Golden polarity: base fail; groundtruth_final pass")
    lines.append("- Agent result scoring: agent_result is expected pass against final-oriented cases, but is not used to validate testcase polarity")
    lines.append("")
    lines.append("## Targets")
    for target in report["targets"]:
        artifact = target.get("apk") or target.get("hap")
        exists = Path(artifact).exists() if artifact else False
        lines.append(
            f"- `{target['targetId']}` role `{target['targetRole']}` expected `{target['expected']}` "
            f"groundtruth `{target['isGroundTruth']}` tag `{target['tag']}` artifactExists `{exists}`"
        )
    lines.append("")
    lines.append("## Execution Meaning")
    lines.append("")
    lines.append("A testcase validates the benchmark only when the task's golden base rows fail and golden final rows pass.")
    lines.append("Agent result rows are scored against the same final-oriented semantic assertions and reported separately for discriminativity.")
    lines.append("A blocked row is not a pass or fail; it means the required state adapter, device, or build artifact is missing.")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    cases = list(iter_cases())
    targets = build_targets()
    report = {
        "generatedAt": datetime.now().isoformat(timespec="seconds"),
        "root": str(ROOT),
        "androidSource": str(ANDROID_SOURCE),
        "targets": targets,
        "caseTargets": case_matrix(cases, targets),
    }
    json_path = REPORT_DIR / "state_dynamic_target_matrix.json"
    md_path = REPORT_DIR / "state_dynamic_target_matrix.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_markdown(report, md_path)
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    print(f"Targets: {len(targets)}")
    print(f"Case-target rows: {len(report['caseTargets'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
