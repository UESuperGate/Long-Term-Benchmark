#!/usr/bin/env python3
"""Run clean-room OpenCode + MiniMax-M3 evaluation for extended tasks."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import shutil
import signal
import subprocess
import tarfile
import time
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ANDROID_REPO = ROOT / "_sources/element-x-android"
MODEL = "minimax-token-plan/MiniMax-M3"
ENDPOINT = "https://api.minimaxi.com/v1"
HVIGOR = Path("/Applications/DevEco-Studio.app/Contents/tools/hvigor/bin/hvigorw")
JAVA_HOME = Path("/opt/homebrew/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home")
ANDROID_SDK = Path.home() / "Library/Android/sdk"
OH_SDK = Path.home() / "Library/OpenHarmony/Sdk"
MIRROR_INIT = ROOT / "scripts/android_maven_mirror.init.gradle"

TASKS = {
    "06_multi_select_polls": {
        "spec": ROOT / "specs/elementx-spec6-multi-select-polls.md",
        "transitions": ROOT / "benchmark_tasks/06_multi_select_polls/transitions.json",
        "androidBase": "v26.08.4",
        "arktsBase": ROOT / "06_multi_select_polls_base_26_08_4",
    },
    "07_recent_search_history": {
        "spec": ROOT / "specs/elementx-spec7-recent-search-history.md",
        "transitions": ROOT / "benchmark_tasks/07_recent_search_history/transitions.json",
        "androidBase": "v26.09.2",
        "arktsBase": ROOT / "07_recent_search_history_base_26_09_2",
    },
}


def opencode_config(platform: str) -> dict[str, object]:
    shell = {
        "*": "deny",
        "pwd": "allow",
        "ls": "allow",
        "git status *": "allow",
        "git diff *": "allow",
    }
    if platform == "android":
        shell["./gradlew :app:assembleGplayDebug --no-daemon"] = "allow"
    else:
        shell["hvigorw assembleHap --mode module -p product=default -p buildMode=debug --no-daemon"] = "allow"
    return {
        "$schema": "https://opencode.ai/config.json",
        "agent": {
            "explore": {
                "steps": 8,
                "prompt": "Explore only the current candidate directory and return concise implementation evidence. Never access parent, sibling, home, or network paths.",
            }
        },
        "permission": {
            "*": "deny",
            "read": "allow",
            "edit": "allow",
            "glob": "allow",
            "grep": "allow",
            "list": "allow",
            "task": "allow",
            "webfetch": "deny",
            "websearch": "deny",
            "external_directory": "deny",
            "shell": shell,
            "bash": shell,
        },
    }


def public_transitions(source: Path) -> dict[str, object]:
    contract = json.loads(source.read_text(encoding="utf-8"))
    return {
        "schemaVersion": 1,
        "taskId": contract["taskId"],
        "description": "Public scenarios. Exact expected observations and evaluator bindings are private.",
        "cases": [
            {
                "caseId": case["caseId"],
                "functionalArea": case["functionalArea"],
                "given": case["given"],
                "event": case["event"],
                "invariants": case.get("invariants", []),
            }
            for case in contract["cases"]
        ],
    }


def prompt_text(task_id: str, platform: str) -> str:
    build = "./gradlew :app:assembleGplayDebug --no-daemon" if platform == "android" else "hvigorw assembleHap --mode module -p product=default -p buildMode=debug --no-daemon"
    language = "Kotlin/Compose production modules" if platform == "android" else "ArkTS/ArkUI production modules"
    return f"""Implement task {task_id} completely in this {platform} candidate now.

Read `_benchmark_inputs/requirement.md` and `_benchmark_inputs/public_transitions.json`, then inspect the existing production architecture. Implement real behavior in {language}; documentation-only work, testcase switches, marker facts, and evaluator-specific code are forbidden.

Rules:
- Work only in the current candidate directory. Never inspect parent, sibling, home, benchmark, final, or evaluator paths.
- Do not use network, browser, curl, wget, git fetch, or external tools.
- Subagents are allowed and inherit the same directory boundary.
- Preserve existing architecture and unrelated behavior. Implement state, events, effects/persistence, rendered interaction, failure recovery, and cleanup required by the task.
- Do not infer outcomes from case IDs and do not create production APIs whose only purpose is reporting test facts.
- Run `{build}` after a coherent implementation and repair compile errors within the time budget.

Finish with a concise summary of changed production files and any remaining blocker.
"""


def ignore_copy(directory: str, names: list[str]) -> set[str]:
    del directory
    return {name for name in names if name in {".git", ".hvigor", "build", "oh_modules", "node_modules"}}


def prepare(task_id: str, platform: str, candidate_root: Path) -> Path:
    task = TASKS[task_id]
    candidate = candidate_root / platform / task_id
    if candidate.exists():
        shutil.rmtree(candidate)
    candidate.parent.mkdir(parents=True, exist_ok=True)
    if platform == "android":
        candidate.mkdir()
        archive = candidate_root / f".{task_id}.tar"
        env = os.environ.copy()
        env["GIT_LFS_SKIP_SMUDGE"] = "1"
        subprocess.run(["git", "-C", str(ANDROID_REPO), "archive", "--format=tar", f"--output={archive}", task["androidBase"]], env=env, check=True)
        with tarfile.open(archive) as stream:
            stream.extractall(candidate)
        archive.unlink()
    else:
        shutil.copytree(task["arktsBase"], candidate, ignore=ignore_copy)

    inputs = candidate / "_benchmark_inputs"
    inputs.mkdir()
    shutil.copy2(task["spec"], inputs / "requirement.md")
    (inputs / "public_transitions.json").write_text(json.dumps(public_transitions(task["transitions"]), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (inputs / "prompt.md").write_text(prompt_text(task_id, platform), encoding="utf-8")
    (candidate / "opencode.json").write_text(json.dumps(opencode_config(platform), indent=2) + "\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=candidate, check=True)
    subprocess.run(["git", "add", "-A"], cwd=candidate, check=True)
    subprocess.run(["git", "-c", "user.name=Benchmark Runner", "-c", "user.email=benchmark@localhost", "commit", "-q", "-m", "clean-room base"], cwd=candidate, check=True)
    return candidate


def run_logged(command: list[str], cwd: Path, env: dict[str, str], output: Path, timeout: int) -> int:
    with output.open("w", encoding="utf-8") as stream:
        process = subprocess.Popen(command, cwd=cwd, env=env, stdout=stream, stderr=subprocess.STDOUT, text=True, start_new_session=True)
        try:
            return process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
            stream.write(json.dumps({"type": "runner_timeout", "timeoutSeconds": timeout}) + "\n")
            return 124


def environment(platform: str) -> dict[str, str]:
    env = os.environ.copy()
    if platform == "android":
        env.update({"JAVA_HOME": str(JAVA_HOME), "ANDROID_HOME": str(ANDROID_SDK), "ANDROID_SDK_ROOT": str(ANDROID_SDK)})
        env["PATH"] = os.pathsep.join([str(JAVA_HOME / "bin"), str(ANDROID_SDK / "platform-tools"), env.get("PATH", "")])
    else:
        env["DEVECO_SDK_HOME"] = str(OH_SDK)
        env["PATH"] = os.pathsep.join([str(HVIGOR.parent), "/Applications/DevEco-Studio.app/Contents/tools/ohpm/bin", env.get("PATH", "")])
    return env


def changed_files(candidate: Path) -> list[str]:
    return subprocess.check_output(["git", "status", "--porcelain=v1", "--untracked-files=all"], cwd=candidate, text=True).splitlines()


def is_production_change(path: str, platform: str) -> bool:
    parts = Path(path).parts
    generated_parts = {".gradle", ".hvigor", ".kotlin", "build", "node_modules", "oh_modules"}
    if generated_parts.intersection(parts):
        return False
    suffixes = (".kt", ".kts", ".java", ".xml") if platform == "android" else (".ets", ".ts", ".json5")
    return path.endswith(suffixes) and not path.startswith(("_benchmark_inputs/", "opencode.json"))


def build(platform: str, candidate: Path, env: dict[str, str], log: Path) -> int:
    if platform == "android":
        command = ["./gradlew", ":app:assembleGplayDebug", "--no-daemon", "--max-workers=8", "--no-configuration-cache", "--init-script", str(MIRROR_INIT)]
    else:
        command = [str(HVIGOR), "assembleHap", "--mode", "module", "-p", "product=default", "-p", "buildMode=debug", "--no-daemon"]
    return run_logged(command, candidate, env, log, 3600)


def run_one(task_id: str, platform: str, candidate: Path, logs: Path, timeout: int) -> dict[str, object]:
    started_at = datetime.now().astimezone()
    started = time.monotonic()
    env = environment(platform)
    # OpenCode resolves its project from PWD; subprocess cwd alone is not enough
    # when the parent shell exported a stale value.
    env["PWD"] = str(candidate)
    env["OLDPWD"] = str(candidate)
    prompt = (candidate / "_benchmark_inputs/prompt.md").read_text(encoding="utf-8")
    agent_log = logs / f"{platform}_{task_id}_opencode.jsonl"
    print(f"[agent] {platform}/{task_id}", flush=True)
    agent_exit = run_logged(["opencode", "run", "--standalone", "--model", MODEL, "--format", "json", "--title", f"extended {platform} {task_id}", prompt], candidate, env, agent_log, timeout)
    build_log = logs / f"{platform}_{task_id}_build.log"
    print(f"[build] {platform}/{task_id} agent_exit={agent_exit}", flush=True)
    build_exit = build(platform, candidate, env, build_log)
    changes = changed_files(candidate)
    generated = [line[3:] for line in changes if is_production_change(line[3:], platform)]
    return {
        "taskId": task_id,
        "platform": platform,
        "model": MODEL,
        "endpoint": ENDPOINT,
        "startedAt": started_at.isoformat(timespec="seconds"),
        "finishedAt": datetime.now().astimezone().isoformat(timespec="seconds"),
        "durationSeconds": round(time.monotonic() - started, 3),
        "agentTimeoutSeconds": timeout,
        "agentExit": agent_exit,
        "agentTimedOut": agent_exit == 124,
        "codeGenerated": bool(generated),
        "generatedCodeFiles": generated,
        "compile": "passed" if build_exit == 0 else "failed",
        "buildExit": build_exit,
        "candidate": str(candidate),
        "agentLog": str(agent_log),
        "buildLog": str(build_log),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", default=f"extended_opencode_minimax_m3_{datetime.now():%Y%m%d_%H%M%S}")
    parser.add_argument("--task", action="append", choices=TASKS)
    parser.add_argument("--platform", action="append", choices=("android", "arkts"))
    parser.add_argument("--agent-timeout", type=int, default=3600)
    parser.add_argument("--parallel", type=int, default=2)
    parser.add_argument("--candidate-root", type=Path)
    args = parser.parse_args()

    tasks = args.task or list(TASKS)
    platforms = args.platform or ["android", "arkts"]
    run_root = ROOT / "eval_runs" / args.run_id
    logs = run_root / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    candidate_root = (args.candidate_root or ROOT.parent / f"{ROOT.name}-extended-eval" / args.run_id).resolve()
    started_at = datetime.now().astimezone()
    started = time.monotonic()
    prepared = {(platform, task): prepare(task, platform, candidate_root) for platform in platforms for task in tasks}
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.parallel)) as pool:
        futures = [pool.submit(run_one, task, platform, prepared[(platform, task)], logs, args.agent_timeout) for platform in platforms for task in tasks]
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            results.append(result)
            print(f"[result] {result['platform']}/{result['taskId']} generated={result['codeGenerated']} compile={result['compile']}", flush=True)
    results.sort(key=lambda row: (row["platform"], row["taskId"]))
    manifest = {
        "schemaVersion": 1,
        "runId": args.run_id,
        "startedAt": started_at.isoformat(timespec="seconds"),
        "finishedAt": datetime.now().astimezone().isoformat(timespec="seconds"),
        "durationSeconds": round(time.monotonic() - started, 3),
        "model": MODEL,
        "endpoint": ENDPOINT,
        "opencodeVersion": subprocess.check_output(["opencode", "--version"], text=True).strip(),
        "candidateRoot": str(candidate_root),
        "tasks": results,
    }
    path = run_root / "eval_manifest.json"
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[manifest] {path}", flush=True)
    return 0 if all(row["agentExit"] == 0 and row["buildExit"] == 0 for row in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
