#!/usr/bin/env python3
"""Run the five OpenCode + GLM-5.3 Element X Android benchmark tasks."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import shutil
import signal
import subprocess
import sys
import tarfile
import time
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ANDROID_SOURCE = ROOT / "_sources" / "element-x-android"
MODEL = "bigmodel-glm/glm-5.3"
ENDPOINT = "https://api.kjdfhl.school/v1"
SDK_ROOT = Path.home() / "Library" / "Android" / "sdk"
JAVA_HOME = Path("/opt/homebrew/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home")
MIRROR_INIT = ROOT / "scripts" / "android_maven_mirror.init.gradle"

TASKS = [
    {
        "id": "01_user_status",
        "spec": "elementx-spec1-user-status.md",
        "state": "elementx-state-test1-user-status.yaml",
        "base_tag": "v26.07.0",
        "result": "01_user_status_final_26_08_4",
    },
    {
        "id": "02_gallery_messages",
        "spec": "elementx-spec2-gallery-messages.md",
        "state": "elementx-state-test2-gallery-messages.yaml",
        "base_tag": "v26.06.1",
        "result": "02_gallery_messages_final_26_08_1",
    },
    {
        "id": "03_timeline_protection_rich_events",
        "spec": "elementx-spec3-active-call-timeline.md",
        "state": "elementx-state-test3-timeline-protection-rich-events.yaml",
        "base_tag": "v26.07.1",
        "result": "03_active_call_timeline_final_26_08_0",
    },
    {
        "id": "04_live_location",
        "spec": "elementx-spec4-live-location.md",
        "state": "elementx-state-test4-live-location.yaml",
        "base_tag": "v26.04.0",
        "result": "04_live_location_final_26_05_1",
    },
    {
        "id": "05_link_new_device",
        "spec": "elementx-spec5-link-new-device.md",
        "state": "elementx-state-test5-link-new-device.yaml",
        "base_tag": "v26.05.0",
        "result": "05_link_new_device_final_26_08_2",
    },
]


def build_env() -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "ANDROID_HOME": str(SDK_ROOT),
            "ANDROID_SDK_ROOT": str(SDK_ROOT),
            "JAVA_HOME": str(JAVA_HOME),
        }
    )
    env["PATH"] = os.pathsep.join(
        [
            str(JAVA_HOME / "bin"),
            str(SDK_ROOT / "platform-tools"),
            str(SDK_ROOT / "cmdline-tools" / "latest" / "bin"),
            env.get("PATH", ""),
        ]
    )
    env["GRADLE_OPTS"] = " ".join(
        filter(
            None,
            [
                env.get("GRADLE_OPTS", ""),
                "-Dorg.gradle.internal.http.connectionTimeout=30000",
                "-Dorg.gradle.internal.http.socketTimeout=30000",
                "-Djava.net.useSystemProxies=false",
                "-Dhttp.nonProxyHosts=maven.aliyun.com|maven-central.storage-download.googleapis.com",
                "-Dhttps.nonProxyHosts=maven.aliyun.com|maven-central.storage-download.googleapis.com",
                "-Dhttp.proxyHost=127.0.0.1",
                "-Dhttp.proxyPort=7898",
                "-Dhttps.proxyHost=127.0.0.1",
                "-Dhttps.proxyPort=7898",
            ],
        )
    )
    return env


def prompt_for(task: dict[str, str], project: Path, inputs: Path) -> str:
    return f"""IMPORTANT: Implement the task now. Do not stop after orientation and do not ask what to do next. Finish by editing the Android source and attempting a debug APK build.

You are working in a clean archive of the official Element X Android repository at {task['base_tag']}.

Task id: {task['id']}
Project directory: {project}
Requirement spec: {inputs / task['spec']}
State-test YAML: {inputs / task['state']}

Implement the requested long-horizon task in this Android project only.

Rules:
- Treat the requirement spec and state-test YAML as the public task contract.
- Evaluator binding manifests, final tags, and golden implementations are hidden. Do not search outside this project for them.
- Network retrieval is forbidden during implementation. Do not use webfetch, websearch, curl, wget, git fetch, or GitHub URLs. Any access to an upstream final tag invalidates the run.
- Do not read or copy any HarmonyOS/ArkTS implementation or another task result.
- Update the real Kotlin/Compose feature implementation, models, presenters, and tests needed by the requirement. Documentation-only changes are insufficient.
- Preserve the upstream architecture, Java 21 compatibility, and existing product flavors.
- Add a debug-only ContentProvider at authority `${{applicationId}}.state-test-probe` for deterministic evaluation. Query parameters are `caseId` and optional `stateEvent`; return a cursor column named `snapshot` containing JSON.
- The initial query must expose the current case state. A query with `stateEvent` must apply exactly that public transition and expose the resulting state plus `lastEvent`.
- JSON must include `caseId`, `ready: true`, `lastEvent` when applied, and `semanticFacts`. Facts use `visible:<token>`, `hidden:<token>`, `enabled:<token>`, `disabled:<token>`, and `property:<key>=<value>` from the public YAML.
- Derive semantic facts from actual feature/fixture state. Do not pre-emit future transition facts, copy expected results, or implement a case-id-to-answer lookup detached from the feature behavior.
- Keep the provider and deterministic fixture in `app/src/debug`; production feature behavior belongs in normal source modules.
- The evaluator owns transition ordinals. Emit current unprefixed facts and acknowledge only the requested event.
- Run `./gradlew :app:assembleGplayDebug --no-daemon`. Fix build errors before finishing when possible.

When done, summarize changed production files, debug adapter files, build result, implemented behavior, and remaining blockers.
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
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
            stream.write(json.dumps({"type": "runner_timeout", "timeoutSeconds": timeout}) + "\n")
            return 124


def prepare_task(task: dict[str, str], candidate_root: Path) -> tuple[Path, Path]:
    candidate = candidate_root / task["result"]
    if candidate.exists():
        shutil.rmtree(candidate)
    candidate.mkdir(parents=True)
    archive = candidate_root / f".{task['id']}.tar"
    if archive.exists():
        archive.unlink()
    archive_env = os.environ.copy()
    archive_env["GIT_LFS_SKIP_SMUDGE"] = "1"
    subprocess.run(
        ["git", "-C", str(ANDROID_SOURCE), "archive", "--format=tar", f"--output={archive}", task["base_tag"]],
        env=archive_env,
        check=True,
    )
    with tarfile.open(archive) as source:
        source.extractall(candidate)
    archive.unlink()
    build_file = candidate / "app" / "build.gradle.kts"
    build_text = build_file.read_text(encoding="utf-8")
    build_text = build_text.replace(
        'abiFilters += listOf("armeabi-v7a", "x86", "arm64-v8a", "x86_64")',
        'abiFilters += listOf("arm64-v8a")',
    )
    build_text = build_text.replace(
        'include("armeabi-v7a", "x86", "arm64-v8a", "x86_64")',
        'include("arm64-v8a")',
    )
    build_text = build_text.replace("isEnable = !buildingAppBundle", "isEnable = false")
    build_text = build_text.replace('include("arm64-v8a")', "// ABI splits are disabled for the arm64 benchmark build.")
    build_text = build_text.replace("isUniversalApk = true", "isUniversalApk = false")
    build_file.write_text(build_text, encoding="utf-8")
    inputs = candidate / "_benchmark_inputs"
    inputs.mkdir()
    shutil.copy2(ROOT / "specs" / task["spec"], inputs / task["spec"])
    shutil.copy2(ROOT / "state_tests" / task["state"], inputs / task["state"])
    shutil.copy2(ROOT / "state_tests" / "README.md", inputs / "state_tests_README.md")
    shutil.copy2(ROOT / "state_tests" / "state-test-schema.json", inputs / "state-test-schema.json")
    prompt = inputs / "opencode_prompt.md"
    prompt.write_text(prompt_for(task, candidate, inputs), encoding="utf-8")
    (candidate / "opencode.json").write_text(
        json.dumps(
            {
                "$schema": "https://opencode.ai/config.json",
                "permission": {
                    "webfetch": "deny",
                    "websearch": "deny",
                    "external_directory": "deny",
                    "bash": {
                        "*": "allow",
                        "curl *": "deny",
                        "wget *": "deny",
                        "git fetch*": "deny",
                        "git clone*": "deny",
                        "*github.com*": "deny",
                        "*raw.githubusercontent.com*": "deny",
                    },
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "init", "-q"], cwd=candidate, check=True)
    subprocess.run(["git", "add", "-A"], cwd=candidate, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Benchmark Runner",
            "-c",
            "user.email=benchmark@localhost",
            "commit",
            "-q",
            "-m",
            f"baseline {task['base_tag']}",
        ],
        cwd=candidate,
        check=True,
    )
    return candidate, prompt


def find_apk(candidate: Path) -> Path | None:
    apk_name = "app-gplay-arm64-v8a-debug.apk"
    preferred_paths = [
        candidate / "app" / "build" / "outputs" / "apk" / "gplay" / "debug" / apk_name,
        candidate / "app" / "build" / "intermediates" / "apk" / "gplay" / "debug" / apk_name,
    ]
    for preferred in preferred_paths:
        if preferred.exists():
            return preferred
    apks = sorted(candidate.glob("app/build/**/apk/**/*.apk"), key=lambda path: path.stat().st_mtime, reverse=True)
    return apks[0] if apks else None


def clean_build_outputs(project: Path) -> None:
    module_roots = {path.parent for pattern in ("build.gradle", "build.gradle.kts") for path in project.rglob(pattern)}
    for module_root in sorted(module_roots, key=lambda path: len(path.parts), reverse=True):
        output = module_root / "build"
        if output.exists():
            shutil.rmtree(output)


def run_task(
    task: dict[str, str],
    candidate: Path,
    prompt_path: Path,
    log_root: Path,
    env: dict[str, str],
    agent_timeout: int,
    build_timeout: int,
) -> dict[str, object]:
    prompt = prompt_path.read_text(encoding="utf-8")
    task_env = env.copy()
    task_env["PWD"] = str(candidate)
    task_env["OLDPWD"] = str(candidate)
    agent_log = log_root / f"{task['id']}_opencode.jsonl"
    started_at = datetime.now().astimezone()
    started = time.monotonic()
    print(f"[opencode] {task['id']} started", flush=True)
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
            f"android benchmark {task['id']}",
            prompt,
        ],
        candidate,
        task_env,
        agent_log,
        agent_timeout,
    )
    agent_duration = round(time.monotonic() - started, 3)
    build_log = log_root / f"{task['id']}_build.log"
    print(f"[build] {task['id']} agent_exit={agent_exit}", flush=True)
    build_exit = run_logged(
        [
            "./gradlew",
            ":app:assembleGplayDebug",
            "--no-daemon",
            "--max-workers=8",
            "--no-configuration-cache",
            "--init-script",
            str(MIRROR_INIT),
        ],
        candidate,
        task_env,
        build_log,
        build_timeout,
    )
    apk = find_apk(candidate)
    if apk:
        archived_apk = candidate / "_benchmark_artifacts" / "app-gplay-arm64-v8a-debug.apk"
        archived_apk.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(apk, archived_apk)
        clean_build_outputs(candidate)
        apk = candidate / "app" / "build" / "outputs" / "apk" / "gplay" / "debug" / archived_apk.name
        apk.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(archived_apk, apk)
    print(f"[result] {task['id']} agent={agent_exit} build={build_exit} apk={bool(apk)}", flush=True)
    return {
        "id": task["id"],
        "baseTag": task["base_tag"],
        "agentResultDir": str(candidate),
        "model": MODEL,
        "agentExit": agent_exit,
        "agentTimedOut": agent_exit == 124,
        "agentTimeoutSeconds": agent_timeout,
        "agentStartedAt": started_at.isoformat(timespec="seconds"),
        "agentFinishedAt": datetime.now().astimezone().isoformat(timespec="seconds"),
        "agentDurationSeconds": agent_duration,
        "buildExit": build_exit,
        "buildTimeoutSeconds": build_timeout,
        "apk": str(apk or ""),
        "agentLog": str(agent_log),
        "buildLog": str(build_log),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", default=f"android_opencode_glm53_{datetime.now():%Y%m%d_%H%M%S}")
    parser.add_argument(
        "--candidate-root",
        help="Candidate workspace root. Put this outside the benchmark checkout for clean-room isolation.",
    )
    parser.add_argument("--task", action="append", default=[])
    parser.add_argument("--agent-timeout", type=int, default=3600)
    parser.add_argument("--build-timeout", type=int, default=3600)
    parser.add_argument("--parallel", type=int, default=1)
    args = parser.parse_args()

    selected = [task for task in TASKS if not args.task or task["id"] in set(args.task)]
    run_root = ROOT / "eval_runs" / args.run_id
    candidate_root = (
        Path(args.candidate_root).expanduser().resolve()
        if args.candidate_root
        else ROOT.parent / f"{ROOT.name}-android-eval" / args.run_id
    )
    log_root = run_root / "logs"
    candidate_root.mkdir(parents=True, exist_ok=True)
    log_root.mkdir(parents=True, exist_ok=True)
    env = build_env()

    prepared: dict[str, tuple[Path, Path]] = {}
    for index, task in enumerate(selected, start=1):
        print(f"[prepare {index}/{len(selected)}] {task['id']}", flush=True)
        prepared[task["id"]] = prepare_task(task, candidate_root)

    results: list[dict[str, object]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.parallel)) as executor:
        futures = {
            executor.submit(
                run_task,
                task,
                prepared[task["id"]][0],
                prepared[task["id"]][1],
                log_root,
                env,
                args.agent_timeout,
                args.build_timeout,
            ): task["id"]
            for task in selected
        }
        for future in concurrent.futures.as_completed(futures):
            results.append(future.result())
    results.sort(key=lambda item: str(item["id"]))

    manifest = {
        "runId": args.run_id,
        "createdAt": datetime.now().astimezone().isoformat(timespec="seconds"),
        "platform": "android",
        "runner": "opencode",
        "runnerVersion": subprocess.check_output(["opencode", "--version"], text=True).strip(),
        "model": MODEL,
        "endpoint": ENDPOINT,
        "agentTimeoutSeconds": args.agent_timeout,
        "buildTimeoutSeconds": args.build_timeout,
        "javaHome": str(JAVA_HOME),
        "androidSdkRoot": str(SDK_ROOT),
        "agentResultRoot": str(candidate_root),
        "tasks": results,
    }
    manifest_path = run_root / "eval_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[manifest] {manifest_path}", flush=True)
    return 0 if all(item["agentExit"] == 0 and item["buildExit"] == 0 for item in results) else 1


if __name__ == "__main__":
    sys.exit(main())
