#!/usr/bin/env python3
"""Run isolated OpenCode + MiniMax-M3 evaluations for extracted tasks 08-18."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import shutil
import signal
import shlex
import subprocess
import tarfile
import threading
import time
import re
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ANDROID_REPO = ROOT / "_sources/element-x-android"
CATALOG = ROOT / "benchmark_tasks/extraction_catalog.json"
MODEL = "minimax-token-plan/MiniMax-M3"
ENDPOINT = "https://api.minimaxi.com/v1"
HVIGOR = Path("/Applications/DevEco-Studio.app/Contents/tools/hvigor/bin/hvigorw")
JAVA_HOME_17 = Path("/opt/homebrew/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home")
JAVA_HOME_21 = Path("/opt/homebrew/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home")
ANDROID_SDK = Path.home() / "Library/Android/sdk"
OH_SDK = Path.home() / "Library/OpenHarmony/Sdk"
MIRROR_INIT = ROOT / "scripts/android_maven_mirror.init.gradle"
OBSERVER = ROOT / "scripts/run_task_semantic_observer.py"


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def task_ids() -> list[str]:
    return [str(task_id) for task_id in load(CATALOG)["acceptedTaskIds"]]


def task_data(task_id: str) -> dict[str, Any]:
    return load(ROOT / "benchmark_tasks" / task_id / "task.json")


def agent_build_command(platform: str) -> str:
    if platform == "android":
        return "./gradlew :app:assembleGplayDebug --no-daemon --init-script _benchmark_inputs/android_maven_mirror.init.gradle"
    return "hvigorw assembleHap --mode module -p product=default -p buildMode=debug --no-daemon"


def candidate_path_permissions(candidate: Path) -> dict[str, str]:
    # OpenCode permission rules are last-match-wins. Relative paths remain
    # available, absolute paths are denied, and the candidate prefix is the
    # sole absolute-path exception.
    return {
        "*": "allow",
        "/*": "deny",
        f"{candidate.resolve()}/*": "allow",
    }


def opencode_config(platform: str, candidate: Path) -> dict[str, object]:
    shell = {
        "*": "deny",
        "true": "allow",
        "pwd": "allow",
        "ls": "allow",
        "git status --short": "allow",
        "git diff --stat": "allow",
        "git diff --name-only": "allow",
        agent_build_command(platform): "allow",
    }
    return {
        "$schema": "https://opencode.ai/config.json",
        "agent": {
            "explore": {
                "steps": 12,
                "prompt": "Explore only the current candidate directory. Never access parent, sibling, home, network, final, benchmark, or evaluator paths.",
            }
        },
        "permission": {
            "*": "deny",
            "read": candidate_path_permissions(candidate),
            "edit": candidate_path_permissions(candidate),
            "glob": candidate_path_permissions(candidate),
            "grep": "allow",
            "list": candidate_path_permissions(candidate),
            "task": "allow",
            "webfetch": "deny",
            "websearch": "deny",
            "external_directory": "deny",
            "shell": shell,
            "bash": shell,
        },
    }


def public_transitions(source: Path) -> dict[str, object]:
    contract = load(source)
    return {
        "schemaVersion": 1,
        "taskId": contract["taskId"],
        "description": "Public scenarios; evaluator observations and expected values are private.",
        "cases": [
            {
                "caseId": case["caseId"],
                "functionalArea": case.get("functionalArea"),
                "given": case["given"],
                "event": case["event"],
                "invariants": case.get("invariants", []),
            }
            for case in contract["cases"]
        ],
    }


def prompt_text(task_id: str, platform: str) -> str:
    build = agent_build_command(platform)
    language = "Kotlin/Compose" if platform == "android" else "ArkTS/ArkUI"
    return f"""Implement task {task_id} completely in this {platform} candidate.

Read `_benchmark_inputs/requirement.md` and `_benchmark_inputs/public_transitions.json`, inspect the existing production architecture, and implement the behavior in real {language} production code.

Rules:
- Work only in this candidate directory. Never inspect parent, sibling, home, benchmark, final, evaluator, or network paths.
- Subagents are allowed but inherit the same boundary.
- Do not create testcase switches, marker facts, semantic projections, or evaluator-specific APIs.
- Preserve unrelated behavior. Implement state, events, effects or persistence, real page wiring, and failure recovery.
- Run `{build}` exactly as written, without shell pipes or redirection, and repair compilation within the task time limit.

Finish with a concise summary of changed production files and remaining blockers.
"""


def ignore_copy(directory: str, names: list[str]) -> set[str]:
    del directory
    return {name for name in names if name in {".git", ".hvigor", "build", "oh_modules", "node_modules"}}


def prepare(task_id: str, platform: str, candidate_root: Path) -> Path:
    task = task_data(task_id)
    candidate = candidate_root / platform / task_id
    if candidate.exists():
        shutil.rmtree(candidate, ignore_errors=True)
    candidate.parent.mkdir(parents=True, exist_ok=True)
    if platform == "android":
        candidate.mkdir()
        archive = candidate_root / f".{task_id}-{os.getpid()}.tar"
        env = os.environ.copy()
        env["GIT_LFS_SKIP_SMUDGE"] = "1"
        subprocess.run(
            ["git", "-C", str(ANDROID_REPO), "archive", "--format=tar", f"--output={archive}", task["android"]["baseRef"]],
            env=env,
            check=True,
        )
        # The archive is produced locally by Git from a trusted immutable tag.
        # Avoid tarfile's Python 3.12-only extraction filter on the macOS 3.9 runtime.
        with tarfile.open(archive) as stream:
            stream.extractall(candidate)
        archive.unlink()
    else:
        shutil.copytree(ROOT / task["arkts"]["basePath"], candidate, ignore=ignore_copy)

    inputs = candidate / "_benchmark_inputs"
    inputs.mkdir()
    shutil.copy2(ROOT / "benchmark_tasks" / task_id / "requirement.md", inputs / "requirement.md")
    if platform == "android":
        shutil.copy2(MIRROR_INIT, inputs / "android_maven_mirror.init.gradle")
    transitions = ROOT / "benchmark_tasks" / task_id / "transitions.json"
    (inputs / "public_transitions.json").write_text(json.dumps(public_transitions(transitions), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (inputs / "prompt.md").write_text(prompt_text(task_id, platform), encoding="utf-8")
    (candidate / "opencode.json").write_text(json.dumps(opencode_config(platform, candidate), indent=2) + "\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=candidate, check=True)
    subprocess.run(["git", "add", "-A"], cwd=candidate, check=True)
    subprocess.run(
        ["git", "-c", "user.name=Benchmark Runner", "-c", "user.email=benchmark@localhost", "commit", "-q", "-m", "clean-room base"],
        cwd=candidate,
        check=True,
    )
    return candidate


def run_logged(command: list[str], cwd: Path, env: dict[str, str], output: Path, timeout: int) -> int:
    output.parent.mkdir(parents=True, exist_ok=True)
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


def android_java_home(candidate: Path) -> Path:
    wrapper = candidate / "gradle/wrapper/gradle-wrapper.properties"
    content = wrapper.read_text(encoding="utf-8", errors="replace") if wrapper.exists() else ""
    match = re.search(r"gradle-(\d+)\.(\d+)(?:\.\d+)?-", content)
    if match and (int(match.group(1)), int(match.group(2))) < (8, 11):
        return JAVA_HOME_17
    return JAVA_HOME_21


def environment(platform: str, candidate: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["PWD"] = str(candidate)
    env["OLDPWD"] = str(candidate)
    if platform == "android":
        java_home = android_java_home(candidate)
        env.update({"JAVA_HOME": str(java_home), "ANDROID_HOME": str(ANDROID_SDK), "ANDROID_SDK_ROOT": str(ANDROID_SDK)})
        env["PATH"] = os.pathsep.join([str(java_home / "bin"), str(ANDROID_SDK / "platform-tools"), env.get("PATH", "")])
    else:
        env["DEVECO_SDK_HOME"] = str(OH_SDK)
        env["PATH"] = os.pathsep.join([str(HVIGOR.parent), "/Applications/DevEco-Studio.app/Contents/tools/ohpm/bin", env.get("PATH", "")])
    return env


def status_paths(candidate: Path) -> list[str]:
    rows = subprocess.check_output(["git", "status", "--porcelain=v1", "--untracked-files=all"], cwd=candidate, text=True).splitlines()
    return [row[3:] for row in rows if len(row) > 3]


def is_production(path: str, platform: str) -> bool:
    if path.startswith(("_benchmark_inputs/", "opencode.json")):
        return False
    if {"build", ".gradle", ".hvigor", "oh_modules", "node_modules"}.intersection(Path(path).parts):
        return False
    suffixes = {".kt", ".kts", ".java", ".xml"} if platform == "android" else {".ets", ".ts", ".json5"}
    return Path(path).suffix in suffixes


def build(platform: str, candidate: Path, env: dict[str, str], log: Path) -> tuple[int, str]:
    if platform == "android":
        command = ["./gradlew", ":app:assembleGplayDebug", "--no-daemon", "--max-workers=8", "--no-configuration-cache", "--init-script", str(MIRROR_INIT)]
    else:
        command = [str(HVIGOR), "assembleHap", "--mode", "module", "-p", "product=default", "-p", "buildMode=debug", "--no-daemon"]
    return run_logged(command, candidate, env, log, 3600), " ".join(command)


def score(task_id: str, platform: str, candidate: Path, generated: list[str], build_exit: int, build_command: str, output: Path) -> None:
    command = [
        "python3", str(OBSERVER), "--task", task_id, "--platform", platform, "--role", "agent", "--source", str(candidate),
        "--code-generated", str(bool(generated)).lower(), "--compile-passed", str(build_exit == 0).lower(),
        "--compile-command", build_command, "--output", str(output),
    ]
    for path in generated:
        command.extend(["--changed-production-file", path])
    subprocess.run(command, cwd=ROOT, check=True)


def clean_candidate(candidate: Path) -> None:
    if candidate.exists():
        shutil.rmtree(candidate, ignore_errors=True)


def provider_quota_exhausted(log: Path) -> bool:
    content = log.read_text(encoding="utf-8", errors="replace") if log.exists() else ""
    return '"type":"provider.quota"' in content or '"status":402' in content


def _inside_candidate(path: str, candidate: Path) -> bool:
    expanded = Path(os.path.expandvars(os.path.expanduser(path)))
    resolved = expanded.resolve() if expanded.is_absolute() else (candidate / expanded).resolve()
    try:
        resolved.relative_to(candidate.resolve())
        return True
    except ValueError:
        return False


def _strings(value: object) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    if isinstance(value, dict):
        for key, child in value.items():
            if isinstance(child, str):
                rows.append((str(key), child))
            else:
                rows.extend(_strings(child))
    elif isinstance(value, list):
        for child in value:
            rows.extend(_strings(child))
    return rows


def audit_agent_log(log: Path, candidate: Path) -> list[dict[str, str]]:
    """Return tool inputs that attempted to leave the isolated candidate."""
    violations: list[dict[str, str]] = []
    if not log.exists():
        return violations
    path_keys = {"path", "file", "filePath", "directory", "dir", "cwd", "root"}
    for line_number, line in enumerate(log.read_text(encoding="utf-8", errors="replace").splitlines(), start=1):
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") != "tool_use":
            continue
        part = event.get("part", {})
        tool = str(part.get("tool", ""))
        state = part.get("state", {})
        if not isinstance(state, dict) or state.get("status") != "completed":
            continue
        tool_input = state.get("input", {}) if isinstance(state, dict) else {}
        for key, value in _strings(tool_input):
            reason = ""
            if key in path_keys or (tool in {"glob", "grep", "list", "read", "write", "edit"} and key == "pattern"):
                if value.startswith(("/", "~")) or ".." in Path(value).parts:
                    if not _inside_candidate(value, candidate):
                        reason = "external_path"
            if key == "command" or tool in {"shell", "bash"} and key in {"cmd", "input"}:
                try:
                    tokens = shlex.split(value)
                except ValueError:
                    tokens = value.split()
                if any(token == ".." or token.startswith(("../", "~/")) for token in tokens):
                    reason = "parent_or_home_shell_path"
                if "$HOME" in value or "${HOME}" in value:
                    reason = "home_shell_path"
                for match in re.finditer(r"(?<![A-Za-z0-9._-])(/[^\s'\"|;&<>]+)", value):
                    absolute = match.group(1).rstrip(")]},")
                    if absolute == "/dev/null":
                        continue
                    if not _inside_candidate(absolute, candidate):
                        reason = "external_shell_path"
                        break
            if reason:
                violations.append({
                    "line": str(line_number),
                    "tool": tool,
                    "reason": reason,
                    "input": value[:500],
                })
                if len(violations) >= 20:
                    return violations
    return violations


def run_one(task_id: str, platform: str, candidate_root: Path, run_root: Path, timeout: int, keep: bool) -> dict[str, Any]:
    started_at = datetime.now().astimezone()
    started = time.monotonic()
    candidate = prepare(task_id, platform, candidate_root)
    env = environment(platform, candidate)
    logs = run_root / "logs"
    reports = run_root / "reports"
    patches = run_root / "patches"
    logs.mkdir(parents=True, exist_ok=True)
    reports.mkdir(parents=True, exist_ok=True)
    patches.mkdir(parents=True, exist_ok=True)
    agent_log = logs / f"{platform}_{task_id}_opencode.jsonl"
    prompt = (candidate / "_benchmark_inputs/prompt.md").read_text(encoding="utf-8")
    agent_exit = run_logged(
        ["opencode", "run", "--standalone", "--model", MODEL, "--format", "json", "--title", f"new benchmark {platform} {task_id}", prompt],
        candidate,
        env,
        agent_log,
        timeout,
    )
    if provider_quota_exhausted(agent_log):
        result = {
            "taskId": task_id,
            "platform": platform,
            "model": MODEL,
            "endpoint": ENDPOINT,
            "startedAt": started_at.isoformat(timespec="seconds"),
            "finishedAt": datetime.now().astimezone().isoformat(timespec="seconds"),
            "durationSeconds": round(time.monotonic() - started, 3),
            "agentTimeoutSeconds": timeout,
            "agentExit": agent_exit,
            "agentTimedOut": False,
            "availability": "provider_quota",
            "benchmarkMetricsAvailable": False,
        }
        clean_candidate(candidate)
        return result
    isolation_violations = audit_agent_log(agent_log, candidate)
    if isolation_violations:
        result = {
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
            "workspacePathLeakDetected": True,
            "isolationViolations": isolation_violations,
            "availability": "isolation_violation",
            "benchmarkMetricsAvailable": False,
        }
        clean_candidate(candidate)
        return result
    build_log = logs / f"{platform}_{task_id}_build.log"
    build_exit, build_command = build(platform, candidate, env, build_log)
    changed = status_paths(candidate)
    generated = [path for path in changed if is_production(path, platform)]
    if generated:
        # Intent-to-add makes newly created production files visible to git diff
        # without staging their contents or changing the clean-room baseline.
        subprocess.run(["git", "add", "-N", "--", *generated], cwd=candidate, check=True)
    patch = subprocess.run(["git", "diff", "--binary"], cwd=candidate, text=True, stdout=subprocess.PIPE, check=True).stdout
    (patches / f"{platform}_{task_id}.patch").write_text(patch, encoding="utf-8")
    report = reports / f"{platform}_{task_id}_agent.json"
    score(task_id, platform, candidate, generated, build_exit, build_command, report)
    result = {
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
        "semanticReport": str(report),
        "workspacePathLeakDetected": False,
        "availability": "available",
        "benchmarkMetricsAvailable": True,
    }
    if not keep:
        clean_candidate(candidate)
    return result


def run_with_platform_lock(
    lock: threading.Lock,
    quota_event: threading.Event,
    task_id: str,
    platform: str,
    candidate_root: Path,
    run_root: Path,
    timeout: int,
    keep: bool,
) -> dict[str, Any]:
    with lock:
        if quota_event.is_set():
            return {
                "taskId": task_id,
                "platform": platform,
                "model": MODEL,
                "endpoint": ENDPOINT,
                "availability": "provider_quota",
                "benchmarkMetricsAvailable": False,
                "notAttemptedAfterQuota": True,
            }
        result = run_one(task_id, platform, candidate_root, run_root, timeout, keep)
        if result.get("availability") == "provider_quota":
            quota_event.set()
        return result


def manifest_payload(
    run_id: str,
    started_at: datetime,
    candidate_root: Path,
    keep_candidates: bool,
    results: list[dict[str, Any]],
    status: str,
) -> dict[str, Any]:
    finished_at = datetime.now().astimezone()
    return {
        "schemaVersion": 1,
        "runId": run_id,
        "status": status,
        "startedAt": started_at.isoformat(timespec="seconds"),
        "finishedAt": finished_at.isoformat(timespec="seconds"),
        "durationSeconds": round((finished_at - started_at).total_seconds(), 3),
        "timingScope": "overall run start through the last task completion; subagents are not timed separately",
        "concurrencyPolicy": "at most one candidate per platform; Android and ArkTS may run concurrently",
        "model": MODEL,
        "endpoint": ENDPOINT,
        "opencodeVersion": subprocess.check_output(["opencode", "--version"], text=True).strip(),
        "candidateRoot": str(candidate_root),
        "candidatesPreserved": keep_candidates,
        "tasks": sorted(results, key=lambda row: (str(row.get("platform")), str(row.get("taskId")))),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", default=f"new_tasks_opencode_minimax_m3_{datetime.now():%Y%m%d_%H%M%S}")
    parser.add_argument("--task", action="append", choices=task_ids())
    parser.add_argument("--platform", action="append", choices=("android", "arkts"))
    parser.add_argument("--agent-timeout", type=int, default=3600)
    parser.add_argument("--parallel", type=int, default=2)
    parser.add_argument("--candidate-root", type=Path)
    parser.add_argument("--keep-candidates", action="store_true")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    tasks = args.task or task_ids()
    platforms = args.platform or ["android", "arkts"]
    run_root = ROOT / "eval_runs" / args.run_id
    run_root.mkdir(parents=True, exist_ok=True)
    candidate_root = (args.candidate_root or ROOT.parent / ".ltb-new-tasks-eval" / args.run_id).resolve()
    partial_manifest = run_root / "eval_manifest.partial.json"
    previous: list[dict[str, Any]] = []
    started_at = datetime.now().astimezone()
    if args.resume and partial_manifest.exists():
        prior = load(partial_manifest)
        audited: list[dict[str, Any]] = []
        for row in prior.get("tasks", []):
            row = dict(row)
            task_id = str(row.get("taskId", ""))
            platform = str(row.get("platform", ""))
            log = run_root / "logs" / f"{platform}_{task_id}_opencode.jsonl"
            violations = audit_agent_log(log, candidate_root / platform / task_id)
            if violations:
                row.update({
                    "workspacePathLeakDetected": True,
                    "isolationViolations": violations,
                    "availability": "isolation_violation",
                    "benchmarkMetricsAvailable": False,
                })
            audited.append(row)
        previous = [row for row in audited if row.get("availability", "available") == "available"]
        started_at = datetime.fromisoformat(prior["startedAt"])
    results: list[dict[str, Any]] = list(previous)
    completed = {(row.get("taskId"), row.get("platform")) for row in previous}
    work_by_platform = {
        platform: [task_id for task_id in tasks if (task_id, platform) not in completed]
        for platform in platforms
    }
    platform_locks = {platform: threading.Lock() for platform in platforms}
    quota_event = threading.Event()
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.parallel)) as pool:
        futures: dict[concurrent.futures.Future[dict[str, Any]], tuple[str, str]] = {}

        def submit_next(platform: str) -> None:
            queue = work_by_platform[platform]
            if not queue:
                return
            task_id = queue.pop(0)
            future = pool.submit(
                run_with_platform_lock,
                platform_locks[platform],
                quota_event,
                task_id,
                platform,
                candidate_root,
                run_root,
                args.agent_timeout,
                args.keep_candidates,
            )
            futures[future] = (task_id, platform)

        for platform in platforms:
            submit_next(platform)
        while futures:
            done, _ = concurrent.futures.wait(futures, return_when=concurrent.futures.FIRST_COMPLETED)
            for future in done:
                task_id, platform = futures.pop(future)
                try:
                    result = future.result()
                except Exception as error:
                    result = {"taskId": task_id, "platform": platform, "runnerError": repr(error)}
                results.append(result)
                print(json.dumps(result, ensure_ascii=False), flush=True)
                partial_manifest.write_text(
                    json.dumps(manifest_payload(args.run_id, started_at, candidate_root, args.keep_candidates, results, "partial"), ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
                submit_next(platform)
    expected = len(tasks) * len(platforms)
    complete = len(results) == expected and all(row.get("availability", "available") == "available" for row in results)
    manifest = manifest_payload(args.run_id, started_at, candidate_root, args.keep_candidates, results, "complete" if complete else "partial")
    destination = run_root / ("eval_manifest.json" if complete else "eval_manifest.partial.json")
    destination.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if not args.keep_candidates and candidate_root.exists():
        shutil.rmtree(candidate_root)
    failed = [row for row in results if row.get("agentExit") != 0 or row.get("buildExit") != 0 or row.get("runnerError")]
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
