#!/usr/bin/env python3
"""Run the five OpenCode + MiniMax-M3 Element X Android benchmark tasks."""

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
import threading
import time
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ANDROID_SOURCE = ROOT / "_sources" / "element-x-android"
MODEL = "minimax-token-plan/MiniMax-M3"
ENDPOINT = "https://api.minimaxi.com/v1"
SDK_ROOT = Path.home() / "Library" / "Android" / "sdk"
JAVA_HOME = Path("/opt/homebrew/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home")
MIRROR_INIT = ROOT / "scripts" / "android_maven_mirror.init.gradle"
ANDROID_SCAFFOLD = ROOT / "state_tests" / "android_scaffold"
BUILD_SEMAPHORE = threading.Semaphore(1)

ANDROID_SPEC_REPLACEMENTS = {
    "01_user_status": {
        "本任务不是在设置页添加一个静态入口，而是把 Matrix 用户状态能力作为一个端到端产品功能迁移到 ArkTS 客户端。":
            "本任务不是在设置页添加一个静态入口，而是要在 Android 客户端中把 Matrix 用户状态能力实现为端到端产品功能。",
        "- base: Android `v26.07.0`，用户状态不作为完整可用功能暴露；对应 ArkTS base 必须缺少 final 语义。":
            "- base: Android `v26.07.0`，用户状态不作为完整可用功能暴露。",
        "- ArkTS 目标必须使用 SDK 23，并保持与 Android final 的功能边界一致；不得额外加入 Android final 没有的状态类型、设置项或社交功能。":
            "- Android 候选实现必须保持与 final 功能边界一致；不得额外加入 final 没有的状态类型、设置项或社交功能。",
        "- 不改动 Android production source；Android 只允许使用 debug/test harness 注入状态。":
            "- 必须修改 Android production source 实现真实功能；debug/test harness 只能用于注入确定性测试状态。",
        "base/final 极性要求为 Android base fail、ArkTS base fail、Android final pass、ArkTS final pass；":
            "base/final 极性要求为 Android base fail、Android final pass；",
    },
    "02_gallery_messages": {
        "- ArkTS 目标必须保留 Android final 的附件顺序、附件粒度错误处理和现有单媒体行为。":
            "- Android 候选实现必须保留 final 的附件顺序、附件粒度错误处理和现有单媒体行为。",
    },
    "03_timeline_protection_rich_events": {
        "- ArkTS 目标应把扫描状态、viewer 状态和 call 状态作为独立但可组合的 declarative state。":
            "- Android 候选实现应把扫描状态、viewer 状态和 call 状态作为独立但可组合的 declarative state。",
    },
    "04_live_location": {
        "- ArkTS 目标必须使用 Android final 的状态边界，不新增后台定位策略或地图供应商特性。":
            "- Android 候选实现必须使用 final 的状态边界，不新增后台定位策略或地图供应商特性。",
    },
    "05_link_new_device": {
        "- ArkTS 目标必须与 Android final 的安全顺序一致：capability -> owner verification -> handler/QR/digits -> done/error/cleanup。":
            "- Android 候选实现必须与 final 的安全顺序一致：capability -> owner verification -> handler/QR/digits -> done/error/cleanup。",
    },
}

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


def render_android_spec(task: dict[str, str]) -> str:
    source = ROOT / "specs" / task["spec"]
    text = source.read_text(encoding="utf-8-sig")
    for old, new in ANDROID_SPEC_REPLACEMENTS[task["id"]].items():
        if old not in text:
            raise ValueError(f"Android spec replacement source is missing for {task['id']}: {old}")
        text = text.replace(old, new)
    if "ArkTS" in text:
        raise ValueError(f"Android requirement spec still contains ArkTS instructions: {task['id']}")
    return text


def install_android_scaffold(candidate: Path) -> None:
    if not ANDROID_SCAFFOLD.is_dir():
        raise FileNotFoundError(f"Android state-test scaffold is missing: {ANDROID_SCAFFOLD}")
    shutil.copytree(ANDROID_SCAFFOLD, candidate, dirs_exist_ok=True)


def is_generated_product_code(path: str) -> bool:
    normalized = path.replace("\\", "/")
    if normalized.startswith(("_benchmark_inputs/", "app/src/debug/")):
        return False
    if normalized in {"opencode.json"}:
        return False
    return "/src/" in f"/{normalized}" and Path(normalized).suffix in {".java", ".kt", ".kts", ".xml"}


def changed_paths(candidate: Path) -> list[str]:
    baseline = subprocess.check_output(
        ["git", "rev-list", "--max-parents=0", "HEAD"],
        cwd=candidate,
        text=True,
    ).strip()
    committed = subprocess.check_output(
        ["git", "diff", "--name-only", baseline, "HEAD"],
        cwd=candidate,
        text=True,
    ).splitlines()
    status = subprocess.check_output(
        ["git", "status", "--porcelain=v1", "--untracked-files=all"],
        cwd=candidate,
        text=True,
    )
    paths = list(committed)
    for line in status.splitlines():
        value = line[3:]
        if " -> " in value:
            value = value.split(" -> ", 1)[1]
        paths.append(value)
    return sorted(set(paths))


def state_test_binding_changed(candidate: Path) -> bool:
    return "app/src/debug/kotlin/io/element/android/x/StateTestScenario.kt" in changed_paths(candidate)


def prompt_for(task: dict[str, str], project: Path, inputs: Path) -> str:
    return f"""IMPORTANT: Implement the task now. Do not stop after orientation and do not ask what to do next. Finish by editing the Android source and state-test binding.

You are working in a clean archive of the official Element X Android repository at {task['base_tag']}.

Task id: {task['id']}
Project directory: {project}
Requirement spec: {inputs / task['spec']}
State-test YAML: {inputs / task['state']}

Implement the requested long-horizon task in this Android project only.

Rules:
- Treat the requirement spec and state-test YAML as the public task contract.
- The project directory is the complete readable workspace. Do not inspect any path outside it, including the home directory, Gradle caches, Android SDK, JDK, temporary directories, sibling repositories, or system files.
- Start by reading the requirement and state-test YAML. Follow their `android_evidence` and `platform_bindings` anchors and inspect no more than 5 production source files before editing.
- Your next step after those focused reads must be a minimal production Kotlin edit. It may introduce only the smallest model or state shape needed by the task. Do not perform a repository survey first; continue exploring and refining after this concrete checkpoint.
- Subagents are allowed but optional after the first production edit. Delegate to at most one subagent at a time, require a concise report under 2,000 tokens, and continue implementation without requesting exhaustive exploration. The subagent inherits the same project-only read boundary and its time counts within this task's single wall-clock budget.
- Make incremental edits and keep each write/edit tool payload under 4,000 tokens.
- Keep every later write/edit tool payload under 4,000 tokens so an interrupted transport response cannot discard a whole feature file. Do not restart orientation or re-read the same files after context compaction.
- Do not use browser, MCP, or desktop tools. All permitted evidence is already inside the project directory.
- Evaluator binding manifests, final tags, and golden implementations are hidden. Do not search outside this project for them.
- Network retrieval is forbidden during implementation. Do not use webfetch, websearch, curl, wget, git fetch, or GitHub URLs. Any access to an upstream final tag invalidates the run.
- Do not read or copy any HarmonyOS/ArkTS implementation or another task result.
- Update the real Kotlin/Compose feature implementation, models, presenters, and tests needed by the requirement. Documentation-only changes are insufficient.
- Preserve the upstream architecture, Java 21 compatibility, and existing product flavors.
- A debug-only state-test ContentProvider is already installed. Do not replace its transport or manifest registration.
- `StateTestContract.kt` owns the stable `StateTestObservation` transport type and an answer-free `DeterministicStateTestStore`; do not replace or duplicate those declarations. Use the helper for case reset, event acknowledgement, and fact projection.
- Implement the task-specific binding in `app/src/debug/kotlin/io/element/android/x/StateTestScenario.kt`. A new `caseId` must reset and apply that case's deterministic initial fixture. A capture with `stateEvent` must apply exactly that public transition and set `appliedEvent` only after the event is applied.
- Do not invent imports or production helpers for the state-test binding. Add the binding only after its referenced production state types exist, and keep the supplied compile-safe placeholder until then.
- Return `semanticFacts` using `visible:<token>`, `hidden:<token>`, `enabled:<token>`, `disabled:<token>`, and `property:<key>=<value>` from the public YAML.
- Derive semantic facts from actual feature/presenter/fixture state. Do not pre-emit future transition facts, copy expected results, or implement a case-id-to-answer lookup detached from feature behavior.
- The debug binding is evaluation glue only. Production feature behavior belongs in normal source modules and is required for code-generation credit.
- The evaluator owns transition ordinals. Emit current unprefixed facts and acknowledge only the requested event.
- Project-local shell access is limited to inspection, Git diff/status, and Gradle. Do not use absolute paths or `..` in shell commands.
- Run `./gradlew :app:assembleGplayDebug --no-daemon` after the first coherent implementation. Use compiler errors to repair the implementation and repeat until it builds or the task time budget is exhausted.
- Run that exact Gradle command without pipes or redirection after no more than 25 write/edit calls. A compiling vertical slice takes priority over adding secondary surfaces. Implement the state-test binding before broadening beyond the required surfaces.

When done, summarize changed production files, state-test binding files, implemented behavior, and remaining blockers.
"""


def opencode_config() -> dict[str, object]:
    project_shell_permissions = {
        "*": "deny",
        "pwd": "allow",
        "ls": "allow",
        "ls -la": "allow",
        "git status --short": "allow",
        "git status --short *": "allow",
        "git diff": "allow",
        "git diff *": "allow",
        "./gradlew :app:assembleGplayDebug --no-daemon": "allow",
    }
    return {
        "$schema": "https://opencode.ai/config.json",
        "agent": {
            "explore": {
                "steps": 4,
                "prompt": (
                    "Explore only the current project directory. Return a concise report under 2,000 tokens "
                    "with exact paths and signatures needed for the delegated question. Do not perform exhaustive "
                    "repository surveys, use network or external tools, or inspect paths outside the project."
                ),
            },
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
            # OpenCode 2.x reports the tool as `shell`; retain `bash` for older
            # releases so the same candidate config remains reproducible.
            "shell": project_shell_permissions,
            "bash": project_shell_permissions,
        },
    }


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


def session_id_from_log(path: Path) -> str:
    if not path.exists():
        return ""
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            value = json.loads(line).get("sessionID")
        except json.JSONDecodeError:
            continue
        if value:
            return str(value)
    return ""


def provider_failure_from_log(path: Path) -> dict[str, object] | None:
    if not path.exists():
        return None
    for line in reversed(path.read_text(encoding="utf-8", errors="replace").splitlines()):
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if row.get("type") != "error":
            continue
        error = row.get("error") or {}
        error_type = str(error.get("type", ""))
        status = error.get("status")
        if error_type.startswith("provider.") or status in {401, 402, 403, 429}:
            return {
                "type": error_type or "provider.error",
                "status": status,
                "message": str(error.get("message", "")),
            }
    return None


def build_error_excerpt(path: Path, limit: int = 12_000) -> str:
    if not path.exists():
        return "Build failed without a readable log."
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    selected = [
        line
        for line in lines
        if line.startswith("e: ")
        or " error:" in line
        or line.startswith("FAILURE:")
        or line.startswith("* What went wrong:")
        or line.startswith("> Task ") and "FAILED" in line
    ]
    excerpt = "\n".join(selected[-120:])
    if not excerpt:
        excerpt = "\n".join(lines[-120:])
    return excerpt[-limit:]


def compile_candidate(candidate: Path, env: dict[str, str], log: Path, timeout: int) -> int:
    with BUILD_SEMAPHORE:
        return run_logged(
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
            env,
            log,
            timeout,
        )


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
    install_android_scaffold(candidate)
    inputs = candidate / "_benchmark_inputs"
    inputs.mkdir()
    android_spec = inputs / f"android-{task['spec']}"
    android_spec.write_text(render_android_spec(task), encoding="utf-8")
    shutil.copy2(ROOT / "state_tests" / task["state"], inputs / task["state"])
    shutil.copy2(ROOT / "state_tests" / "README.md", inputs / "state_tests_README.md")
    shutil.copy2(ROOT / "state_tests" / "state-test-schema.json", inputs / "state-test-schema.json")
    prompt = inputs / "opencode_prompt.md"
    prompt_task = task | {"spec": android_spec.name}
    prompt.write_text(prompt_for(prompt_task, candidate, inputs), encoding="utf-8")
    (candidate / "opencode.json").write_text(
        json.dumps(opencode_config(), indent=2)
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
    repair_reserve: int,
    resume: bool = False,
    force_repair: bool = False,
) -> dict[str, object]:
    prompt = prompt_path.read_text(encoding="utf-8")
    task_env = env.copy()
    task_env["PWD"] = str(candidate)
    task_env["OLDPWD"] = str(candidate)
    agent_log = log_root / f"{task['id']}_opencode.jsonl"
    task_started_at = datetime.now().astimezone()
    task_started = time.monotonic()
    agent_started_at = task_started_at
    agent_started = task_started
    agent_phases: list[dict[str, object]] = []
    if resume:
        print(f"[resume] {task['id']} compiling existing candidate", flush=True)
        implementation_exit = 0
    else:
        print(f"[opencode] {task['id']} started", flush=True)
        implementation_timeout = max(1, agent_timeout - repair_reserve)
        implementation_exit = run_logged(
            [
                "opencode",
                "run",
                "--standalone",
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
            implementation_timeout,
        )
        implementation_duration = round(time.monotonic() - agent_started, 3)
        agent_phases.append(
            {
                "kind": "implementation",
                "exit": implementation_exit,
                "durationSeconds": implementation_duration,
                "timeoutSeconds": implementation_timeout,
                "log": str(agent_log),
            }
        )
    build_log = log_root / f"{task['id']}_build.log"
    print(f"[build] {task['id']} implementation_exit={implementation_exit}", flush=True)
    build_exit = compile_candidate(candidate, task_env, build_log, build_timeout)
    source_session_id = session_id_from_log(agent_log)
    repair_budget = agent_timeout if resume else repair_reserve
    repair_deadline = time.monotonic() + repair_budget
    repair_attempt = 0
    binding_changed = state_test_binding_changed(candidate)
    pending_forced_repair = force_repair
    while (build_exit != 0 or not binding_changed or pending_forced_repair) and repair_attempt < 5:
        remaining = int(repair_deadline - time.monotonic())
        if remaining <= 0:
            break
        repair_attempt += 1
        suffix = "" if repair_attempt == 1 else f"_{repair_attempt}"
        repair_log = log_root / f"{task['id']}_repair{suffix}.jsonl"
        repair_started = time.monotonic()
        if build_exit != 0:
            compile_context = (
                f"The current candidate failed to compile.\n\nCompiler diagnostics:\n{build_error_excerpt(build_log)}"
            )
        elif not binding_changed:
            compile_context = (
                "The current candidate compiles, but its required StateTestScenario.kt binding is still the supplied placeholder."
            )
        else:
            compile_context = (
                "The current candidate compiles, but strict device-side semantic verification failed. "
                "Read _benchmark_inputs/semantic_failures.json, reproduce each mismatch against the public state-test YAML, "
                "and repair the production-state reducer and fact projection. Treat protocol/ready failures separately from "
                "semantic mismatches. Do not copy expected arrays into case-id answer tables. The build is already green: "
                "before any shell or Gradle call, make at least one reducer or binding edit justified by a failed phase. "
                "Use the read/grep tools for diagnosis and do not inspect build logs or unrelated tests before that edit."
            )
        binding_context = (
            "Implement the task-specific binding in app/src/debug/kotlin/io/element/android/x/StateTestScenario.kt "
            f"from _benchmark_inputs/{task['state']}. Read that public YAML and the existing production state you need. "
            "The binding must reset each case fixture, apply only the requested stateEvent, acknowledge it after applying, "
            "and project current semantic facts from real feature state. Do not hard-code expected snapshots or future facts."
            if not binding_changed
            else "Preserve and compile the existing task-specific StateTestScenario.kt binding."
        )
        repair_prompt = f"""Continue the benchmark task in this current candidate; do not restart repository exploration.

{compile_context}

{binding_context}

Fix only this candidate. Read at most two directly related files before your first edit. Keep the production implementation intact, do not inspect external paths, and run the exact project-local `./gradlew :app:assembleGplayDebug --no-daemon` command without pipes before finishing. Continue through all compiler errors visible within this repair attempt rather than stopping after the first edit.
"""
        print(
            f"[repair] {task['id']} attempt={repair_attempt} remaining={remaining}s "
            f"source_session={source_session_id} binding_changed={binding_changed}",
            flush=True,
        )
        repair_exit = run_logged(
            [
                "opencode",
                "run",
                "--standalone",
                "--model",
                MODEL,
                "--format",
                "json",
                "--title",
                f"android benchmark repair {task['id']} attempt {repair_attempt}",
                repair_prompt,
            ],
            candidate,
            task_env,
            repair_log,
            remaining,
        )
        repair_duration = round(time.monotonic() - repair_started, 3)
        agent_phases.append(
            {
                "kind": "compile_and_binding_repair",
                "attempt": repair_attempt,
                "exit": repair_exit,
                "durationSeconds": repair_duration,
                "timeoutSeconds": remaining,
                "log": str(repair_log),
                "sourceSessionId": source_session_id,
            }
        )
        build_suffix = "" if repair_attempt == 1 else f"_{repair_attempt}"
        build_log = log_root / f"{task['id']}_build_after_repair{build_suffix}.log"
        print(f"[rebuild] {task['id']} attempt={repair_attempt} repair_exit={repair_exit}", flush=True)
        build_exit = compile_candidate(candidate, task_env, build_log, build_timeout)
        binding_changed = state_test_binding_changed(candidate)
        pending_forced_repair = False
    agent_exit = int(agent_phases[-1]["exit"]) if agent_phases else 0
    agent_duration = round(sum(float(phase["durationSeconds"]) for phase in agent_phases), 3)
    agent_finished_at = datetime.now().astimezone()
    provider_failures = [
        failure
        for phase in agent_phases
        if (failure := provider_failure_from_log(Path(str(phase["log"])))) is not None
    ]
    benchmark_valid = not provider_failures
    changed = changed_paths(candidate)
    generated_code_files = [path for path in changed if is_generated_product_code(path)]
    apk = find_apk(candidate)
    if apk:
        archived_apk = candidate / "_benchmark_artifacts" / "app-gplay-arm64-v8a-debug.apk"
        archived_apk.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(apk, archived_apk)
        clean_build_outputs(candidate)
        apk = candidate / "app" / "build" / "outputs" / "apk" / "gplay" / "debug" / archived_apk.name
        apk.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(archived_apk, apk)
    task_finished_at = datetime.now().astimezone()
    task_duration = round(time.monotonic() - task_started, 3)
    print(f"[result] {task['id']} agent={agent_exit} build={build_exit} apk={bool(apk)}", flush=True)
    return {
        "id": task["id"],
        "baseTag": task["base_tag"],
        "agentResultDir": str(candidate),
        "model": MODEL,
        "agentExit": agent_exit,
        "agentTimedOut": any(phase["exit"] == 124 for phase in agent_phases),
        "agentTimeoutSeconds": agent_timeout,
        "taskStartedAt": task_started_at.isoformat(timespec="seconds"),
        "taskFinishedAt": task_finished_at.isoformat(timespec="seconds"),
        "taskDurationSeconds": task_duration,
        "agentStartedAt": agent_started_at.isoformat(timespec="seconds"),
        "agentFinishedAt": agent_finished_at.isoformat(timespec="seconds"),
        "agentDurationSeconds": agent_duration,
        "agentPhases": agent_phases,
        "benchmarkValid": benchmark_valid,
        "infrastructureFailures": provider_failures,
        "codeGenerated": bool(generated_code_files),
        "stateBindingGenerated": binding_changed,
        "generatedCodeFiles": generated_code_files,
        "changedFiles": changed,
        "buildExit": build_exit,
        "buildTimeoutSeconds": build_timeout,
        "apk": str(apk or ""),
        "agentLog": str(agent_log),
        "buildLog": str(build_log),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", default=f"android_opencode_minimax_m3_{datetime.now():%Y%m%d_%H%M%S}")
    parser.add_argument(
        "--candidate-root",
        help="Candidate workspace root. Put this outside the benchmark checkout for clean-room isolation.",
    )
    parser.add_argument("--task", action="append", default=[])
    parser.add_argument("--agent-timeout", type=int, default=3600)
    parser.add_argument("--build-timeout", type=int, default=3600)
    parser.add_argument("--repair-reserve", type=int, default=900)
    parser.add_argument("--parallel", type=int, default=1)
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Repair existing candidates under --candidate-root without recreating them.",
    )
    parser.add_argument(
        "--force-repair",
        action="store_true",
        help="Run one repair attempt even when the existing candidate compiles and has a state binding.",
    )
    args = parser.parse_args()
    run_started_at = datetime.now().astimezone()
    run_started = time.monotonic()

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
        if args.resume:
            candidate = candidate_root / task["result"]
            prompt = candidate / "_benchmark_inputs" / "opencode_prompt.md"
            if not candidate.is_dir() or not prompt.is_file():
                raise FileNotFoundError(f"Resume candidate is incomplete: {candidate}")
            print(f"[resume {index}/{len(selected)}] {task['id']}", flush=True)
            prepared[task["id"]] = candidate, prompt
        else:
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
                min(max(0, args.repair_reserve), max(0, args.agent_timeout - 1)),
                args.resume,
                args.force_repair,
            ): task["id"]
            for task in selected
        }
        for future in concurrent.futures.as_completed(futures):
            results.append(future.result())
    results.sort(key=lambda item: str(item["id"]))

    valid_results = [item for item in results if item["benchmarkValid"]]
    manifest = {
        "runId": args.run_id,
        "createdAt": datetime.now().astimezone().isoformat(timespec="seconds"),
        "runStartedAt": run_started_at.isoformat(timespec="seconds"),
        "runFinishedAt": datetime.now().astimezone().isoformat(timespec="seconds"),
        "runDurationSeconds": round(time.monotonic() - run_started, 3),
        "platform": "android",
        "runner": "opencode",
        "runnerVersion": subprocess.check_output(["opencode", "--version"], text=True).strip(),
        "model": MODEL,
        "endpoint": ENDPOINT,
        "agentTimeoutSeconds": args.agent_timeout,
        "repairReserveSeconds": args.repair_reserve,
        "resumedCandidates": args.resume,
        "forcedRepair": args.force_repair,
        "buildTimeoutSeconds": args.build_timeout,
        "javaHome": str(JAVA_HOME),
        "androidSdkRoot": str(SDK_ROOT),
        "agentResultRoot": str(candidate_root),
        "tasks": results,
        "invalidTasks": [item["id"] for item in results if not item["benchmarkValid"]],
        "benchmarkMetrics": {
            "codeGeneration": {
                "passed": sum(bool(item["codeGenerated"]) for item in valid_results),
                "total": len(valid_results),
            },
            "compile": {
                "passed": sum(item["buildExit"] == 0 for item in valid_results),
                "total": len(valid_results),
            },
            "semanticTestcase": None,
        },
    }
    manifest_path = run_root / "eval_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[manifest] {manifest_path}", flush=True)
    return 0 if all(item["agentExit"] == 0 and item["buildExit"] == 0 for item in results) else 1


if __name__ == "__main__":
    sys.exit(main())
