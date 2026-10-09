#!/usr/bin/env python3
"""Run the five OpenCode + GLM-5.3 ArkTS benchmark tasks on macOS."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODEL = "bigmodel-glm/glm-5.3"
DEVECO = Path("/Applications/DevEco-Studio.app/Contents")
SDK_ROOT = Path.home() / "Library" / "OpenHarmony" / "Sdk"

TASKS = [
    {
        "id": "01_user_status",
        "spec": "elementx-spec1-user-status.md",
        "state": "elementx-state-test1-user-status.yaml",
        "base": "01_user_status_base_26_07_0",
        "result": "01_user_status_final_26_08_4",
    },
    {
        "id": "02_gallery_messages",
        "spec": "elementx-spec2-gallery-messages.md",
        "state": "elementx-state-test2-gallery-messages.yaml",
        "base": "02_gallery_messages_base_26_06_1",
        "result": "02_gallery_messages_final_26_08_1",
    },
    {
        "id": "03_timeline_protection_rich_events",
        "spec": "elementx-spec3-active-call-timeline.md",
        "state": "elementx-state-test3-timeline-protection-rich-events.yaml",
        "base": "03_active_call_timeline_base_26_07_1",
        "result": "03_active_call_timeline_final_26_08_0",
    },
    {
        "id": "04_live_location",
        "spec": "elementx-spec4-live-location.md",
        "state": "elementx-state-test4-live-location.yaml",
        "base": "04_live_location_base_26_04_0",
        "result": "04_live_location_final_26_05_1",
    },
    {
        "id": "05_link_new_device",
        "spec": "elementx-spec5-link-new-device.md",
        "state": "elementx-state-test5-link-new-device.yaml",
        "base": "05_link_new_device_base_26_05_0",
        "result": "05_link_new_device_final_26_08_2",
    },
]

IGNORE = shutil.ignore_patterns(
    ".git", ".hvigor", "build", "oh_modules", "node_modules", "*.hap", "*.app"
)


def build_env() -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "DEVECO_HOME": str(DEVECO),
            "DEVECO_SDK_HOME": str(SDK_ROOT),
            "HOS_SDK_HOME": str(SDK_ROOT),
            "OHOS_SDK_HOME": str(SDK_ROOT),
            "OHOS_BASE_SDK_HOME": str(SDK_ROOT),
            "JAVA_HOME": str(DEVECO / "jbr" / "Contents" / "Home"),
            "NODE_HOME": str(DEVECO / "tools" / "node"),
        }
    )
    prefixes = [
        DEVECO / "tools" / "ohpm" / "bin",
        DEVECO / "tools" / "hvigor" / "bin",
        DEVECO / "tools" / "node" / "bin",
        SDK_ROOT / "23" / "toolchains",
    ]
    env["PATH"] = os.pathsep.join([*(str(path) for path in prefixes), env.get("PATH", "")])
    return env


def prompt_for(task: dict[str, str], project: Path, inputs: Path) -> str:
    return f"""IMPORTANT: Implement the task now. Do not stop after project orientation, and do not ask what to do next. Your answer is only acceptable after you have edited the ArkTS source and attempted a build.

You are running inside a copied ArkTS/HarmonyOS SDK 23 Element X benchmark base project.

Task id: {task['id']}
Project directory: {project}
Requirement spec: {inputs / task['spec']}
State-test YAML: {inputs / task['state']}

Implement the requested long-horizon task in this ArkTS project only.

Rules:
- Treat the requirement spec and state-test YAML as the public task contract.
- Evaluator binding manifests and oracle facts are hidden evaluator inputs. Do not search for, read, copy, or recreate state_tests/bindings/*.json.
- Do not read or copy from any ArkTS final answer directory outside this project.
- Do not modify Android source.
- Preserve SDK 23 compatibility and the existing project structure.
- Keep the implementation constrained to behavior described by the spec/state tests.
- First read entry/src/main/ets/pages/Index.ets and any local project files you need.
- Update the real ArkTS implementation, not only README or benchmark notes.
- Preserve the state-test transport contract: `caseId` initializes a fixture and
  `stateEvent` drives one public transition through the same event sink used by
  the real UI or mocked SDK callback. Re-delivered Wants must be supported.
- Expose `state_probe_snapshot` only from actual runtime state. Include the
  current case id, the last applied event (when any), and semantic facts derived
  from the rendered state. Do not pre-emit facts for transitions that have not
  executed.
- Give rendered semantic nodes stable ArkUI ids matching the public `expect_ui`
  tokens. Runtime facts use `visible:<token>`, `hidden:<token>`,
  `enabled:<token>`, `disabled:<token>`, and `property:<key>=<value>`.
  After a stateEvent, emit the current unprefixed facts plus `lastEvent`; the
  evaluator owns transition ordinals and prefixes.
- Do not hardcode state_test_result, final_feature_available, feature_available=true, or a case-id switch that renders expected tokens without implementing the underlying feature state.
- Do not emit strict_state_fact unless each fact is computed from actual app state after the testcase state and transitions are applied.
- The app must expose real UI/state semantics for each case; target-level smoke markers are insufficient.
- After editing, run ohpm install if needed and hvigorw assembleHap --no-daemon.
- Fix build errors before finishing. If build still fails, leave the source in your best attempted state and summarize the blocker.

When done, summarize changed files, build result, implemented functional areas, and remaining blockers.
"""


def run_logged(command: list[str], cwd: Path, env: dict[str, str], log: Path, timeout: int) -> int:
    with log.open("w", encoding="utf-8") as stream:
        process = subprocess.Popen(
            command,
            cwd=cwd,
            env=env,
            stdout=stream,
            stderr=subprocess.STDOUT,
            text=True,
            start_new_session=True,
        )
        try:
            return process.wait(timeout=timeout)
        except (subprocess.TimeoutExpired, KeyboardInterrupt) as exc:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
            if isinstance(exc, KeyboardInterrupt):
                raise
            stream.write(json.dumps({"type": "runner_timeout", "timeoutSeconds": timeout}) + "\n")
            return 124


def prepare_task(task: dict[str, str], candidate_root: Path) -> tuple[Path, Path]:
    source = ROOT / task["base"]
    candidate = candidate_root / task["result"]
    if candidate.exists():
        shutil.rmtree(candidate)
    shutil.copytree(source, candidate, ignore=IGNORE)
    inputs = candidate / "_benchmark_inputs"
    inputs.mkdir()
    shutil.copy2(ROOT / "specs" / task["spec"], inputs / task["spec"])
    shutil.copy2(ROOT / "state_tests" / task["state"], inputs / task["state"])
    shutil.copy2(ROOT / "state_tests" / "README.md", inputs / "state_tests_README.md")
    shutil.copy2(ROOT / "state_tests" / "state-test-schema.json", inputs / "state-test-schema.json")
    prompt = inputs / "opencode_prompt.md"
    prompt.write_text(prompt_for(task, candidate, inputs), encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=candidate, check=True)
    return candidate, prompt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", default=f"opencode_glm53_{datetime.now():%Y%m%d_%H%M%S}")
    parser.add_argument("--task", action="append", default=[])
    parser.add_argument("--agent-timeout", type=int, default=3600)
    args = parser.parse_args()

    selected = [task for task in TASKS if not args.task or task["id"] in set(args.task)]
    run_root = ROOT / "eval_runs" / args.run_id
    candidate_root = run_root / "arkts_agent_results"
    log_root = run_root / "logs"
    candidate_root.mkdir(parents=True, exist_ok=True)
    log_root.mkdir(parents=True, exist_ok=True)
    env = build_env()
    manifest_tasks: list[dict[str, object]] = []

    for index, task in enumerate(selected, start=1):
        print(f"[prepare {index}/{len(selected)}] {task['id']}", flush=True)
        candidate, prompt_path = prepare_task(task, candidate_root)
        prompt = prompt_path.read_text(encoding="utf-8")
        agent_log = log_root / f"{task['id']}_opencode.jsonl"
        print(f"[opencode {index}/{len(selected)}] {task['id']}", flush=True)
        agent_started_at = datetime.now().astimezone()
        agent_started = time.monotonic()
        agent_exit = run_logged(
            [
                "opencode",
                "run",
                "--standalone",
                "--auto",
                "--model",
                MODEL,
                "--format",
                "json",
                "--title",
                f"{args.run_id} {task['id']}",
                prompt,
            ],
            candidate,
            env,
            agent_log,
            args.agent_timeout,
        )
        agent_duration_seconds = round(time.monotonic() - agent_started, 3)
        agent_finished_at = datetime.now().astimezone()

        build_log = log_root / f"{task['id']}_build.log"
        print(f"[build {index}/{len(selected)}] {task['id']}", flush=True)
        ohpm_exit = run_logged(["ohpm", "install"], candidate, env, build_log, 300)
        if ohpm_exit == 0:
            with build_log.open("a", encoding="utf-8") as stream:
                build = subprocess.run(
                    ["hvigorw", "assembleHap", "--no-daemon"],
                    cwd=candidate,
                    env=env,
                    stdout=stream,
                    stderr=subprocess.STDOUT,
                    timeout=600,
                    check=False,
                )
            build_exit = build.returncode
        else:
            build_exit = -1
        haps = sorted(candidate.rglob("*.hap"), key=lambda path: path.stat().st_mtime, reverse=True)
        manifest_tasks.append(
            {
                "id": task["id"],
                "baseDir": task["base"],
                "agentResultDir": str(candidate),
                "model": MODEL,
                "agentExit": agent_exit,
                "agentTimedOut": agent_exit == 124,
                "agentTimeoutSeconds": args.agent_timeout,
                "agentStartedAt": agent_started_at.isoformat(timespec="seconds"),
                "agentFinishedAt": agent_finished_at.isoformat(timespec="seconds"),
                "agentDurationSeconds": agent_duration_seconds,
                "ohpmExit": ohpm_exit,
                "buildExit": build_exit,
                "hap": str(haps[0]) if haps else "",
                "agentLog": str(agent_log),
                "buildLog": str(build_log),
            }
        )
        print(
            f"[result {index}/{len(selected)}] {task['id']} agent={agent_exit} build={build_exit} hap={bool(haps)}",
            flush=True,
        )

    manifest = {
        "runId": args.run_id,
        "createdAt": datetime.now().astimezone().isoformat(timespec="seconds"),
        "runner": "opencode",
        "runnerVersion": subprocess.check_output(["opencode", "--version"], text=True).strip(),
        "model": MODEL,
        "sdk": 23,
        "agentTimeoutSeconds": args.agent_timeout,
        "root": str(run_root),
        "agentResultRoot": str(candidate_root),
        "tasks": manifest_tasks,
    }
    manifest_path = run_root / "eval_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[manifest] {manifest_path}", flush=True)
    return 0 if all(task["buildExit"] == 0 for task in manifest_tasks) else 1


if __name__ == "__main__":
    sys.exit(main())
