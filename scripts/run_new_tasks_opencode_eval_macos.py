#!/usr/bin/env python3
"""Run isolated OpenCode + MiniMax-M3 evaluations for retained tasks 08-17."""

from __future__ import annotations

import argparse
import concurrent.futures
from contextlib import contextmanager
import fcntl
import hashlib
import importlib.util
import json
import os
import shutil
import signal
import shlex
import subprocess
import tarfile
import tempfile
import threading
import time
import re
from datetime import datetime
from pathlib import Path
from typing import Any

_AUDIT_SPEC = importlib.util.spec_from_file_location('benchmark_opencode_subagent_audit',
    Path(__file__).with_name('opencode_subagent_audit.py'))
assert _AUDIT_SPEC and _AUDIT_SPEC.loader
subagent_audit = importlib.util.module_from_spec(_AUDIT_SPEC)
_AUDIT_SPEC.loader.exec_module(subagent_audit)

_INPUT_SPEC = importlib.util.spec_from_file_location('benchmark_android_candidate_inputs',
    Path(__file__).with_name('android_candidate_inputs.py'))
assert _INPUT_SPEC and _INPUT_SPEC.loader
android_inputs = importlib.util.module_from_spec(_INPUT_SPEC)
_INPUT_SPEC.loader.exec_module(android_inputs)


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
OBSERVER = ROOT / "scripts/run_task_runtime_tests.py"
FULL_BUILD_LOCK = Path("/tmp/long-term-benchmark-android-full-build.lock")
MIN_FREE_BYTES = 8 * 1024 ** 3
ANDROID_BUILD_RECIPE_VERSION = 'android-candidate-local-build.v1'
ANDROID_BUILD_ARGV = ('./gradlew', ':app:assembleGplayDebug', '--no-daemon', '--max-workers=1',
                      '--init-script', android_inputs.INIT_RELATIVE)


class StorageProtectionError(RuntimeError):
    pass


class TaskDeadlineExceeded(TimeoutError):
    def __init__(self, phase: str):
        super().__init__(f'Task execution budget exhausted during {phase}')
        self.phase = phase


def remaining_budget(deadline: float | None, phase: str, default: float = 3600) -> float:
    if deadline is None:
        return default
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TaskDeadlineExceeded(phase)
    return remaining


def require_disk_space(directory: Path) -> None:
    while not directory.exists():
        directory = directory.parent
    free = shutil.disk_usage(directory).free
    if free < MIN_FREE_BYTES:
        raise StorageProtectionError(f"Only {free} bytes free; at least {MIN_FREE_BYTES} required")


@contextmanager
def application_build_slot(platform: str, directory: Path, timeout: float = 3600, *, deadline: float | None = None):
    deadline = min(time.monotonic() + timeout, deadline) if deadline is not None else time.monotonic() + timeout
    remaining_budget(deadline, 'build_lock_wait')
    if platform != "android":
        require_disk_space(directory)
        yield
        return
    with FULL_BUILD_LOCK.open("a") as lock:
        while True:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                time.sleep(min(0.25, remaining_budget(deadline, 'build_lock_wait')))
        try:
            remaining_budget(deadline, 'build_lock_wait')
            require_disk_space(directory)
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def clean_application_build(candidate: Path, manifest: Path, *, deadline: float | None = None) -> None:
    artifacts = []
    disposable = []
    for parent, directories, files in os.walk(candidate):
        remaining_budget(deadline, 'build_artifact_cleanup')
        directory = Path(parent)
        if directory.name in {"build", ".gradle", ".hvigor", ".cxx"}:
            disposable.append(directory)
            directories[:] = []
            for artifact in directory.rglob("*"):
                remaining_budget(deadline, 'build_artifact_cleanup')
                if artifact.is_file() and artifact.suffix.lower() in {".apk", ".hap", ".aab", ".apks", ".har", ".app"}:
                    digest = hashlib.sha256()
                    with artifact.open("rb") as stream:
                        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                            remaining_budget(deadline, 'build_artifact_cleanup')
                            digest.update(chunk)
                    artifacts.append({"path": str(artifact.relative_to(candidate)),
                                      "bytes": artifact.stat().st_size, "sha256": digest.hexdigest()})
        else:
            directories[:] = [name for name in directories if name not in {".git", "node_modules", "oh_modules"}]
    payload = {"schemaVersion": 1, "policy": "hash_before_removing_application_build_outputs",
               "artifacts": artifacts, "removedDirectories": [str(path.relative_to(candidate)) for path in disposable],
               "cleanupCompleted": False}
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    for directory in disposable:
        remaining_budget(deadline, 'build_artifact_cleanup')
        shutil.rmtree(directory)
    payload["cleanupCompleted"] = all(not directory.exists() for directory in disposable)
    manifest.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def task_ids() -> list[str]:
    return [str(task_id) for task_id in load(CATALOG)["acceptedTaskIds"]]


def task_data(task_id: str) -> dict[str, Any]:
    return load(ROOT / "benchmark_tasks" / task_id / "task.json")


def agent_build_command(platform: str) -> str:
    if platform == "android":
        return shlex.join(ANDROID_BUILD_ARGV)
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
    edit = candidate_path_permissions(candidate)
    if platform == 'android':
        for path in ('_benchmark_inputs/*', '_benchmark_inputs/**', './_benchmark_inputs/*',
                     './_benchmark_inputs/**', f'{candidate.resolve()}/_benchmark_inputs/*',
                     f'{candidate.resolve()}/_benchmark_inputs/**'):
            edit[path] = 'deny'
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
            "edit": edit,
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


def prepare(task_id: str, platform: str, candidate_root: Path, *, deadline: float | None = None) -> Path:
    remaining_budget(deadline, 'prepare')
    task = task_data(task_id)
    candidate = candidate_root / platform / task_id
    if candidate.exists():
        clean_candidate(candidate, deadline=deadline)
    candidate.parent.mkdir(parents=True, exist_ok=True)
    if platform == "android":
        candidate.mkdir()
        archive = candidate / f".benchmark-source-{os.getpid()}.tar"
        env = os.environ.copy()
        env["GIT_LFS_SKIP_SMUDGE"] = "1"
        subprocess.run(
            ["git", "-C", str(ANDROID_REPO), "archive", "--format=tar", f"--output={archive}", task["android"]["baseRef"]],
            env=env,
            check=True,
            timeout=remaining_budget(deadline, 'prepare'),
        )
        # The archive is produced locally by Git from a trusted immutable tag.
        # Avoid tarfile's Python 3.12-only extraction filter on the macOS 3.9 runtime.
        with tarfile.open(archive) as stream:
            for member in stream:
                remaining_budget(deadline, 'prepare')
                stream.extract(member, candidate)
        archive.unlink()
    else:
        def copy_file(source, destination):
            remaining_budget(deadline, 'prepare')
            copied = shutil.copy2(source, destination)
            remaining_budget(deadline, 'prepare')
            return copied
        shutil.copytree(ROOT / task["arkts"]["basePath"], candidate, ignore=ignore_copy, copy_function=copy_file)

    inputs = candidate / "_benchmark_inputs"
    inputs.mkdir()
    shutil.copy2(ROOT / "benchmark_tasks" / task_id / "requirement.md", inputs / "requirement.md")
    if platform == "android":
        shutil.copy2(MIRROR_INIT, inputs / "android_maven_mirror.init.gradle")
    transitions = ROOT / "benchmark_tasks" / task_id / "transitions.json"
    (inputs / "public_transitions.json").write_text(json.dumps(public_transitions(transitions), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (inputs / "prompt.md").write_text(prompt_text(task_id, platform), encoding="utf-8")
    (candidate / "opencode.json").write_text(json.dumps(opencode_config(platform, candidate), indent=2) + "\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=candidate, check=True, timeout=remaining_budget(deadline, 'prepare'))
    subprocess.run(["git", "add", "-A"], cwd=candidate, check=True, timeout=remaining_budget(deadline, 'prepare'))
    subprocess.run(
        ["git", "-c", "user.name=Benchmark Runner", "-c", "user.email=benchmark@localhost", "commit", "-q", "-m", "clean-room base"],
        cwd=candidate,
        check=True,
        timeout=remaining_budget(deadline, 'prepare'),
    )
    return candidate


def signal_owned_group(process, sig):
    try:
        os.killpg(process.pid, sig)
    except ProcessLookupError:
        pass
    except PermissionError:
        # macOS can return EPERM after the group exits between wait(0) and
        # killpg. An already-reaped direct child is not a live kill failure.
        if process.poll() is None:
            raise


def run_logged(command: list[str], cwd: Path, env: dict[str, str], output: Path, timeout: int,
               *, protect_storage: bool = False, deadline: float | None = None) -> int:
    deadline = min(time.monotonic() + timeout, deadline) if deadline is not None else time.monotonic() + timeout
    remaining_budget(deadline, 'subprocess_start')
    execution_deadline = deadline - min(.1, max(0, deadline-time.monotonic()) / 3)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as stream:
        process = subprocess.Popen(command, cwd=cwd, env=env, stdout=stream, stderr=subprocess.STDOUT, text=True, start_new_session=True)
        try:
            while True:
                if protect_storage:
                    require_disk_space(cwd)
                remaining = execution_deadline - time.monotonic()
                if remaining <= 0:
                    raise subprocess.TimeoutExpired(command, timeout)
                try:
                    return process.wait(timeout=min(5, remaining))
                except subprocess.TimeoutExpired:
                    if time.monotonic() >= execution_deadline:
                        raise
        except (subprocess.TimeoutExpired, StorageProtectionError) as error:
            signal_owned_group(process, signal.SIGTERM)
            try:
                process.wait(timeout=max(0, min(15, deadline-time.monotonic())))
            except subprocess.TimeoutExpired:
                signal_owned_group(process, signal.SIGKILL)
                process.wait()
            if isinstance(error, StorageProtectionError):
                stream.write(json.dumps({"type": "storage_protection_environment", "reason": str(error)}) + "\n")
                raise
            stream.write(json.dumps({"type": "runner_timeout", "timeoutSeconds": timeout}) + "\n")
            return 124
        except BaseException:
            if process.poll() is None:
                try:
                    signal_owned_group(process, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                try:
                    process.wait(timeout=max(0, min(15, deadline-time.monotonic())))
                except subprocess.TimeoutExpired:
                    signal_owned_group(process, signal.SIGKILL)
                    process.wait()
            raise


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
        env[android_inputs.INIT_ENV] = json.dumps(android_inputs.seal_init(candidate), sort_keys=True)
    else:
        env["DEVECO_SDK_HOME"] = str(OH_SDK)
        env["PATH"] = os.pathsep.join([str(HVIGOR.parent), "/Applications/DevEco-Studio.app/Contents/tools/ohpm/bin", env.get("PATH", "")])
    return env


def status_paths(candidate: Path, *, deadline: float | None = None) -> list[str]:
    changed = subprocess.check_output(['git', 'diff', 'HEAD', '--name-only', '--no-renames', '-z'], cwd=candidate,
                                     timeout=remaining_budget(deadline, 'generation_inventory'))
    untracked = subprocess.check_output(['git', 'ls-files', '--others', '--exclude-standard', '-z'], cwd=candidate,
                                       timeout=remaining_budget(deadline, 'generation_inventory'))
    return sorted({os.fsdecode(path) for path in (changed + untracked).split(b'\0') if path})


def is_production(path: str, platform: str) -> bool:
    if path.startswith(("_benchmark_inputs/", "opencode.json")):
        return False
    if {"build", ".gradle", ".hvigor", "oh_modules", "node_modules"}.intersection(Path(path).parts):
        return False
    suffixes = {".kt", ".kts", ".java", ".xml"} if platform == "android" else {".ets", ".ts", ".json5"}
    return Path(path).suffix in suffixes


def is_patch_input(path: str) -> bool:
    """Archive reconstructable inputs independently of the legacy code metric."""
    relative = Path(path)
    if relative.is_absolute() or '..' in relative.parts or not relative.parts:
        return False
    parts = {part.lower() for part in relative.parts}
    if parts.intersection({'build', '.git', '.gradle', '.hvigor', '.cxx', 'oh_modules', 'node_modules',
                           '.cache', '__pycache__', '.idea', '.vscode', 'dist', 'out', 'coverage',
                           '_benchmark_inputs', '.opencode', '.ssh', 'signing', 'secrets', '.secrets'}):
        return False
    name = relative.name.lower()
    if (name.startswith(('.env', 'opencode.')) or
            name in {'local.properties', 'key.properties', 'keystore.properties', '.npmrc', '.netrc', '.pypirc'} or
            re.fullmatch(r'\.?secrets?(?:[._-].*)?|credentials?(?:[._-].*)?', name)):
        return False
    return relative.suffix.lower() not in {'.p12', '.pfx', '.pem', '.key', '.jks', '.keystore',
        '.apk', '.aab', '.apks', '.hap', '.hsp', '.app', '.abc', '.dex', '.class', '.pyc', '.log'}


def archive_candidate_patch(candidate: Path, destination: Path, *, baseline_commit: str | None = None,
                            deadline: float | None = None) -> dict[str, Any]:
    """Include new resources/tests, preserve the live index, and verify Git replay."""
    if destination.exists():
        raise FileExistsError(f'Refusing to overwrite candidate patch: {destination}')
    def git(*arguments, env=None, text=False):
        return subprocess.check_output(['git', *arguments], cwd=candidate, env=env, text=text,
                                       timeout=remaining_budget(deadline, 'patch_archive'))
    baseline_commit = baseline_commit or subprocess.check_output(
        ['git', 'rev-parse', 'HEAD'], cwd=candidate, text=True,
        timeout=remaining_budget(deadline, 'patch_archive')).strip()
    base_paths = git('ls-tree', '-r', '--name-only', '-z', baseline_commit)
    tracked = {os.fsdecode(path) for path in base_paths.split(b'\0') if path}
    delta = git('diff', baseline_commit, '--name-only', '--no-renames', '-z')
    changed = {os.fsdecode(path) for path in delta.split(b'\0') if path}
    paths = {path for path in changed if is_patch_input(path)}
    # Walk ignored source inputs too: .gitignore is not an archive policy. Prune
    # generated/dependency/secret directories before descending into them.
    for parent, directories, files in os.walk(candidate, followlinks=False):
        remaining_budget(deadline, 'patch_archive')
        parent = Path(parent)
        for name in list(directories):
            path = parent / name
            relative = path.relative_to(candidate).as_posix()
            if not is_patch_input(relative):
                directories.remove(name)
            elif path.is_symlink():
                directories.remove(name)
                if relative not in tracked:
                    paths.add(relative)
        for name in files:
            relative = (parent / name).relative_to(candidate).as_posix()
            if relative not in tracked and is_patch_input(relative):
                paths.add(relative)
    with tempfile.TemporaryDirectory(prefix='ltb-patch-index-') as temporary:
        env = {**os.environ, 'GIT_INDEX_FILE': str(Path(temporary) / 'archive.index'),
               'GIT_LITERAL_PATHSPECS': '1'}
        git('read-tree', baseline_commit, env=env)
        selected = sorted(paths)
        for offset in range(0, len(selected), 128):
            git('add', '--force', '--all', '--', *selected[offset:offset+128], env=env)
        files = git('diff', '--cached', baseline_commit, '--name-only', '--no-renames', '-z', env=env)
        patch_data = git('diff', '--cached', baseline_commit, '--binary', '--full-index',
                         '--no-renames', '--no-ext-diff', '--no-textconv', env=env)
        tree = git('write-tree', env=env, text=True).strip()
        env['GIT_INDEX_FILE'] = str(Path(temporary) / 'replay.index')
        git('read-tree', baseline_commit, env=env)
        if patch_data:
            subprocess.run(['git', 'apply', '--cached', '--binary', '--whitespace=nowarn', '-'],
                           input=patch_data, cwd=candidate, env=env, check=True,
                           timeout=remaining_budget(deadline, 'patch_replay'))
        reconstructed = git('write-tree', env=env, text=True).strip()
        if tree != reconstructed:
            raise ValueError('Candidate patch failed exact baseline-to-input-tree reconstruction')
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open('xb') as stream:
        stream.write(patch_data)
    return {'path': str(destination.resolve()), 'bytes': len(patch_data),
            'sha256': hashlib.sha256(patch_data).hexdigest(), 'baselineCommit': baseline_commit,
            'tree': tree, 'reconstructionVerified': True,
            'policy': 'all_candidate_inputs_except_generated_dependencies_and_secret_configuration_v1',
            'files': sorted(os.fsdecode(path) for path in files.split(b'\0') if path),
            'excludedTrackedChanges': sorted(path for path in changed if not is_patch_input(path))}


def build(platform: str, candidate: Path, env: dict[str, str], log: Path,
          *, deadline: float | None = None) -> tuple[int, str]:
    if platform == "android":
        command = list(ANDROID_BUILD_ARGV)
    else:
        command = [str(HVIGOR), "assembleHap", "--mode", "module", "-p", "product=default", "-p", "buildMode=debug", "--no-daemon"]
    options = {'deadline': deadline} if deadline is not None else {}
    with application_build_slot(platform, candidate, **options):
        if platform != 'android':
            return run_logged(command, candidate, env, log, remaining_budget(deadline, 'build'),
                              protect_storage=True, **options), ' '.join(command)
        if platform == 'android':
            android_inputs.verify_init(candidate, env, deadline)
        try:
            exit_code = run_logged(command, candidate, env, log, remaining_budget(deadline, 'build'),
                                   protect_storage=True, **options)
        finally:
            if platform == 'android':
                android_inputs.verify_init(candidate, env, deadline)
        return exit_code, shlex.join(command)


def score(task_id: str, platform: str, candidate: Path, generated: list[str], build_exit: int, build_command: str,
          output: Path, *, deadline: float | None = None) -> None:
    command = [
        "python3", str(OBSERVER), "--task", task_id, "--platform", platform, "--role", "agent", "--source", str(candidate),
        "--code-generated", str(bool(generated)).lower(), "--compile-passed", str(build_exit == 0).lower(),
        "--compile-command", build_command, "--output", str(output),
    ]
    for path in generated:
        command.extend(["--changed-production-file", path])
    if deadline is None:
        subprocess.run(command, cwd=ROOT, check=True, timeout=3600)
    else:
        deadline = float(deadline)
        host_started = time.clock_gettime(time.CLOCK_MONOTONIC)
        budget = remaining_budget(deadline, 'score')
        host_deadline = host_started + budget
        command.extend(['--timeout', '3600', '--internal-deadline-monotonic', repr(host_deadline)])
        env = {**os.environ, 'LTB_TRUSTED_INTERNAL_DEADLINE': repr(host_deadline),
               'LTB_TRUSTED_INTERNAL_DEADLINE_CLOCK': 'CLOCK_MONOTONIC'}
        exit_code = run_logged(command, ROOT, env, output.with_suffix('.scorer.log'), budget, deadline=deadline)
        remaining_budget(deadline, 'score')
        if exit_code == 124:
            raise TaskDeadlineExceeded('score')
        if exit_code:
            raise subprocess.CalledProcessError(exit_code, command)


def clean_candidate(candidate: Path, *, deadline: float | None = None) -> None:
    if candidate.exists():
        if deadline is None:
            shutil.rmtree(candidate, ignore_errors=True)
        else:
            for parent, directories, files in os.walk(candidate, topdown=False, followlinks=False):
                for name in files:
                    remaining_budget(deadline, 'candidate_cleanup')
                    (Path(parent) / name).unlink(missing_ok=True)
                for name in directories:
                    remaining_budget(deadline, 'candidate_cleanup')
                    path = Path(parent) / name
                    path.unlink() if path.is_symlink() else path.rmdir()
                remaining_budget(deadline, 'candidate_cleanup')
            candidate.rmdir()


def provider_quota_exhausted(log: Path) -> bool:
    return provider_failure_kind(log) == "provider_quota"


def provider_failure_kind(log: Path, *, deadline: float | None = None) -> str | None:
    if not log.exists():
        return None
    failure = None
    with log.open(encoding='utf-8', errors='replace') as stream:
        return _provider_failure_lines(stream, deadline=deadline)


def _provider_failure_lines(lines, *, deadline: float | None = None) -> str | None:
    failure = None
    for line in lines:
        remaining_budget(deadline, 'provider_diagnostics')
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if event.get("type") != "error":
            continue
        error = event.get("error", {})
        if not isinstance(error, dict):
            failure = "agent_runtime_error"
            continue
        detail = error.get("data", {})
        detail = detail if isinstance(detail, dict) else {}
        status = detail.get("statusCode", detail.get("status", error.get("status")))
        kind = error.get("type", error.get("name", ""))
        if kind == "provider.quota" or status in (402, 429):
            return "provider_quota"
        if kind in ("provider.auth", "provider.authentication") or status in (401, 403):
            failure = "provider_auth"
        elif str(kind).startswith("provider.") or status is not None:
            failure = "provider_transport"
        else:
            failure = "agent_runtime_error"
    return failure


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


def fixed_shell_allowlist(platform: str, candidate: Path) -> set[str]:
    policy = opencode_config(platform, candidate)['permission']['shell']
    allowed = {command for command, decision in policy.items() if decision == 'allow'}
    if any(any(char in command for char in '*?[') for command in allowed):
        raise ValueError('Recursive audit requires fixed exact shell commands, not wildcard allows')
    return allowed


def root_session_id_from_log(log: Path) -> str:
    ids = set()
    first = None
    for line in log.read_text(encoding='utf-8').splitlines():
        if not line.strip():
            continue
        event = json.loads(line)
        for value in (event.get('sessionID'), event.get('part', {}).get('sessionID')):
            if value is not None:
                if not isinstance(value, str) or not subagent_audit.SESSION_ID.fullmatch(value):
                    raise ValueError('Invalid JSONL session id')
                ids.add(value)
        if first is None and event.get('type') == 'step_start':
            first = event.get('sessionID', event.get('part', {}).get('sessionID'))
    if first is None or ids != {first}:
        raise ValueError('Missing or ambiguous root session in actual JSONL')
    return first


def isolation_availability(audit: dict[str, Any]) -> str:
    completed = {(r.get('sessionID'), r.get('callID')) for r in audit.get('records', [])
                 if r.get('status') == 'completed'}
    if any(v.get('code') in {'outside_candidate_path', 'network_tool_access'} and
           v.get('callID') is not None and (v.get('sessionID'), v.get('callID')) in completed
           for v in audit.get('violations', [])):
        return 'isolation_violation'
    if audit.get('complete') is True and audit.get('valid') is True and not audit.get('violations'):
        return 'available'
    return 'isolation_unverified'


def _artifact_binding(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    return {'path': str(path.resolve()), 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


def _crosscheck_isolation_history(log: Path, exports: dict[str, Any], inventory: dict[str, Any], root_id: str) -> None:
    if set(exports) != {s['sessionID'] for s in inventory['sessions']}:
        raise ValueError('CLI exports do not cover all DB descendants')
    for session in inventory['sessions']:
        export = exports[session['sessionID']]
        if (export['info'].get('parentID') != session['parentID'] or
                export['info'].get('projectID') != session['projectID'] or
                export['info'].get('outcome') != session['outcome'] or
                export['info'].get('time', {}).get('idle') != session['timeIdle'] or
                export['info'].get('location', {}).get('directory') != session['directory']):
            raise ValueError('CLI export differs from DB session metadata')
        messages = export['messages']
        if len(messages) != len(session['messages']):
            raise ValueError('CLI export is missing DB messages')
        for message, row in zip(messages, session['messages']):
            data = {k: v for k, v in message.items() if k not in {'id', 'type'}}
            if (message.get('id') != row['id'] or message.get('type') != row['type'] or
                    subagent_audit.value_hash(data) != row['dataSha256']):
                raise ValueError('CLI export message content differs from DB')
    tools = {p['id']: p for message in exports[root_id]['messages'] for p in message.get('content', [])
             if p.get('type') == 'tool'}
    rows = [e['part'] for e in (json.loads(line) for line in log.read_text().splitlines() if line.strip())
            if e.get('type') == 'tool_use']
    if len(rows) != len(tools) or {p['id'] for p in rows} != set(tools):
        raise ValueError('CLI root tool coverage differs from actual JSONL')
    for row in rows:
        part, state = tools[row['id']], row['state']
        content = part['state'].get('content', [])
        if (row['tool'] != part['name'] or state['status'] != part['state']['status'] or
                state['input'] != part['state']['input'] or
                content != state.get('metadata', {}).get('content', []) or
                state.get('output', '') != (content[0]['text'] if content else '') or
                state.get('time', {}).get('start') != part['time']['created'] or
                state.get('time', {}).get('end') != part['time']['completed']):
            raise ValueError('CLI root tool record differs from actual JSONL')


def audit_recursive_agent_log(log: Path, candidate: Path, platform: str, run_root: Path,
                              *, deadline: float | None = None) -> dict[str, Any]:
    """Read/export existing history only; never trust commands observed in logs."""
    audit: dict[str, Any] = {'complete': False, 'valid': False, 'records': [], 'violations': []}
    bindings = []
    options = {'deadline': deadline} if deadline is not None else {}
    try:
        remaining_budget(deadline, 'audit')
        allowed = fixed_shell_allowlist(platform, candidate)
        root_id = root_session_id_from_log(log)
        inventory = subagent_audit.read_db_session_inventory(
            Path.home() / '.local/share/opencode/opencode.db', root_id, **options)
        by_parent: dict[str, list[str]] = {}
        for session in inventory['sessions']:
            by_parent.setdefault(session['parentID'], []).append(session['sessionID'])
        prefix = log.stem.removesuffix('_opencode')
        loader = subagent_audit.CliExportLoader(log.parent, prefix, **options)
        audit = subagent_audit.audit_sessions(root_id, candidate, loader,
                    allowed_shell_commands=allowed, discover_children=lambda sid: by_parent.get(sid, []), **options)
        exports = {sid: json.loads(loader(sid)) for sid in loader.paths}
        _crosscheck_isolation_history(log, exports, inventory, root_id)
        remaining_budget(deadline, 'audit')
        inventory_path = log.parent / f'{prefix}_session-inventory.json'
        inventory_path.write_text(json.dumps(inventory, indent=2) + '\n', encoding='utf-8')
        bindings = [_artifact_binding(p) for p in [log, inventory_path, *loader.paths.values()]]
        audit.update({'rootSessionID': root_id, 'inputBindings': bindings,
                      'inventoryPath': str(inventory_path.resolve()),
                      'exportPaths': {sid: str(path.resolve()) for sid, path in loader.paths.items()},
                      'allowedShellCommands': sorted(allowed), 'jsonlAndDBCrosschecksPassed': True})
    except Exception as error:
        audit.update({'complete': False, 'valid': False, 'crosscheckErrorType': type(error).__name__})
    if deadline is not None and time.monotonic() >= deadline:
        audit.update({'complete': False, 'valid': False, 'deadlineExhausted': True})
    audit.update({'schema': 'opencode_recursive_isolation_v1', 'candidate': str(candidate.resolve()),
                  'availability': isolation_availability(audit),
                  'reviewedHelperSha256': hashlib.sha256(Path(subagent_audit.__file__).read_bytes()).hexdigest(),
                  'timingScope': 'Task overall interval only; tool timestamps are forensic ordering, not summed duration.'})
    destination = run_root / 'reports' / f'{log.stem.removesuffix("_opencode")}_isolation-audit.json'
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(audit, indent=2) + '\n', encoding='utf-8')
    return {'availability': audit['availability'], 'complete': audit['complete'],
            'violations': audit['violations'], 'schema': audit['schema'], **_artifact_binding(destination)}


def _validate_retained_isolation(row: dict[str, Any], candidate: Path, platform: str, run_root: Path) -> str:
    receipt = row['isolationAudit']
    path = Path(receipt['path']).resolve()
    if run_root.resolve() not in path.parents or _artifact_binding(path) != {
            k: receipt[k] for k in ('path', 'bytes', 'sha256')}:
        raise ValueError('Isolation audit receipt changed or escaped run root')
    audit = load(path)
    if (audit.get('schema') != 'opencode_recursive_isolation_v1' or
            audit.get('reviewedHelperSha256') != hashlib.sha256(Path(subagent_audit.__file__).read_bytes()).hexdigest() or
            audit.get('candidate') != str(candidate.resolve()) or
            audit.get('allowedShellCommands') != sorted(fixed_shell_allowlist(platform, candidate)) or
            not audit.get('jsonlAndDBCrosschecksPassed') or not audit.get('inputBindings')):
        raise ValueError('Isolation audit is legacy, incomplete, or bound to another policy/evaluator')
    for binding in audit['inputBindings']:
        source = Path(binding['path']).resolve()
        if run_root.resolve() not in source.parents or _artifact_binding(source) != binding:
            raise ValueError('Archived session input changed or missing')
    bound_paths = {binding['path'] for binding in audit['inputBindings']}
    referenced_paths = [audit['inventoryPath'], *audit['exportPaths'].values()]
    if any(str(Path(source).resolve()) not in bound_paths for source in referenced_paths):
        raise ValueError('Isolation audit references unbound session archives')
    root_id = audit['rootSessionID']
    log = run_root / 'logs' / f'{platform}_{row["taskId"]}_opencode.jsonl'
    if root_session_id_from_log(log) != root_id:
        raise ValueError('Retained root session does not match actual JSONL')
    inventory = load(Path(audit['inventoryPath']))
    by_parent: dict[str, list[str]] = {}
    for session in inventory['sessions']:
        by_parent.setdefault(session['parentID'], []).append(session['sessionID'])
    exports = {sid: Path(source).read_bytes() for sid, source in audit['exportPaths'].items()}
    fresh = subagent_audit.audit_sessions(root_id, candidate, lambda sid: exports[sid],
                allowed_shell_commands=fixed_shell_allowlist(platform, candidate),
                discover_children=lambda sid: by_parent.get(sid, []))
    _crosscheck_isolation_history(log, {sid: json.loads(data) for sid, data in exports.items()}, inventory, root_id)
    return isolation_availability(fresh)


def resume_checkpoint_rows(prior: dict[str, Any], candidate_root: Path, run_root: Path) -> list[dict[str, Any]]:
    """Retain generated checkpoints, including unverified legacy rows, without rerunning."""
    retained = []
    for original in prior.get('tasks', []):
        availability = original.get('availability', 'available')
        if availability not in {'available', 'isolation_unverified', 'isolation_violation'} and not original.get('completedCheckpointPreserved'):
            continue
        row = dict(original)
        if row.get('evaluationRepairRequired') and row.get('completedCheckpointPreserved'):
            row.update(resumeDisposition='preserve_completed_checkpoint_do_not_regenerate',
                       requiredAction='Explicit evaluator-only repair or a new run ID is required.')
            retained.append(row)
            continue
        try:
            availability = _validate_retained_isolation(row,
                candidate_root / str(row['platform']) / str(row['taskId']), str(row['platform']), run_root)
        except Exception:
            availability = 'isolation_unverified'
        row.update({'availability': availability, 'completedCheckpointPreserved': True})
        if availability != 'available':
            row.update({'historicalAvailability': original.get('historicalAvailability', original.get('availability', 'available')),
                        'benchmarkMetricsAvailable': False,
                        'metricAvailability': {'codeGeneration': False, 'compile': False, 'semanticTestcase': False},
                        'isolationEvaluationRepairRequired': True,
                        'resumeDisposition': 'preserve_completed_checkpoint_do_not_regenerate',
                        'requiredAction': 'Use a new run ID or explicit evaluator-only recursive isolation repair; do not rerun this candidate.'})
        retained.append(row)
    return retained


def archive_candidate_baseline(candidate: Path, destination: Path, *, phase: str = 'before_agent',
                                deadline: float | None = None, skip_lfs_smudge: bool = False) -> dict[str, Any]:
    """Committed Git recovery input, NOT proof of raw working-tree bytes/modes."""
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=candidate, text=True,
                                    timeout=remaining_budget(deadline, 'baseline_archive')).strip()
    tree = subprocess.check_output(['git', 'rev-parse', 'HEAD^{tree}'], cwd=candidate, text=True,
                                  timeout=remaining_budget(deadline, 'baseline_archive')).strip()
    destination.mkdir(parents=True, exist_ok=True)
    archive = destination / (commit + '.tar.gz')
    receipt_path = archive.with_suffix('.json')
    if archive.exists():
        previous = load(receipt_path)
        data = archive.read_bytes()
        if (previous.get('commit') != commit or previous.get('tree') != tree or
                previous.get('bytes') != len(data) or previous.get('sha256') != hashlib.sha256(data).hexdigest()):
            raise ValueError('Existing candidate baseline archive or receipt changed')
        return previous
    archive_options = {'env': {**os.environ, 'GIT_LFS_SKIP_SMUDGE': '1'}} if skip_lfs_smudge else {}
    subprocess.run(['git', 'archive', '--format=tar.gz', '--output=' + str(archive.resolve()), commit],
                   cwd=candidate, check=True, timeout=min(120, remaining_budget(deadline, 'baseline_archive')),
                   **archive_options)
    data = archive.read_bytes()
    receipt = {'path': str(archive.resolve()), 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest(),
               'commit': commit, 'tree': tree, 'capturePhase': phase,
               'capturedAt': datetime.now().astimezone().isoformat(timespec='seconds')}
    if skip_lfs_smudge:
        receipt.update(archiveKind='committed_git_tree_recovery', rawWorkingTreeByteModeSnapshot=False,
                       lfsSmudgeSkipped=True)
    receipt_path.write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    return receipt


def run_one(task_id: str, platform: str, candidate_root: Path, run_root: Path, timeout: int, keep: bool) -> dict[str, Any]:
    started_at = datetime.now().astimezone()
    started = time.monotonic()
    deadline = started + timeout
    reserve = min(15.0, timeout * .05)
    work_deadline = deadline - reserve
    candidate = candidate_root / platform / task_id
    logs, reports, patches = (run_root / name for name in ('logs', 'reports', 'patches'))
    for directory in (logs, reports, patches):
        directory.mkdir(parents=True, exist_ok=True)
    phases = []
    current_phase = 'prepare'
    agent_invoked = False
    isolation_verified = False
    result = {
        'taskId': task_id, 'platform': platform, 'model': MODEL, 'endpoint': ENDPOINT,
        'startedAt': started_at.isoformat(timespec='seconds'), 'agentTimeoutSeconds': timeout,
        'overallTimeoutSeconds': timeout, 'taskDeadlineMonotonic': deadline,
        'taskDeadlineClockScope': 'process-local time.monotonic; scorer transfer uses system CLOCK_MONOTONIC',
        'finalizationReserveSeconds': reserve, 'agentExit': None, 'agentTimedOut': False,
        'codeGenerated': None, 'generatedCodeFiles': [], 'compile': 'unknown', 'buildExit': None,
        'availability': 'environment_unavailable', 'benchmarkMetricsAvailable': False,
        'workspacePathLeakDetected': None,
        'metricAvailability': {'codeGeneration': False, 'compile': False, 'semanticTestcase': False},
        'phases': phases,
    }

    @contextmanager
    def phase(name, *, finalizing=False):
        nonlocal current_phase
        current_phase = name
        phase_start = time.monotonic()
        row = {'phase': name, 'startedOffsetSeconds': round(phase_start-started, 6),
               'remainingAtStartSeconds': max(0, deadline-phase_start)}
        phases.append(row)
        try:
            remaining_budget(deadline if finalizing else work_deadline, name)
            yield
            if name != 'agent':
                remaining_budget(deadline if finalizing else work_deadline, name)
        finally:
            row.update(elapsedSeconds=round(time.monotonic()-phase_start, 6),
                       remainingAtEndSeconds=max(0, deadline-time.monotonic()))

    try:
        with phase('prepare'):
            require_disk_space(candidate_root)
            candidate = prepare(task_id, platform, candidate_root, deadline=work_deadline)
            if platform == 'android':
                env = environment(platform, candidate)
                result['androidBuildRecipe'] = {'version': ANDROID_BUILD_RECIPE_VERSION,
                    'argv': list(ANDROID_BUILD_ARGV), 'protectedInit': json.loads(env[android_inputs.INIT_ENV])}
                result['rawWorkingTreeBaseline'] = android_inputs.capture(candidate,
                    run_root / 'inputs' / f'{platform}_{task_id}' / 'raw-working-tree-v1', work_deadline,
                    storage_check=lambda: require_disk_space(candidate))
            baseline_options = {'skip_lfs_smudge': True} if platform == 'android' else {}
            baseline = archive_candidate_baseline(candidate, run_root / 'inputs' / f'{platform}_{task_id}',
                                                  deadline=work_deadline, **baseline_options)
            result['candidateBaseline'] = baseline
            if platform != 'android':
                env = environment(platform, candidate)
            prompt = (candidate / '_benchmark_inputs/prompt.md').read_text(encoding='utf-8')
        agent_log = logs / f'{platform}_{task_id}_opencode.jsonl'
        with phase('agent'):
            with application_build_slot(platform, candidate, deadline=work_deadline):
                if platform == 'android':
                    android_inputs.verify_current(candidate, result['rawWorkingTreeBaseline'], work_deadline)
                    android_inputs.verify_init(candidate, env, work_deadline)
                agent_invoked = True
                allowance = remaining_budget(work_deadline, 'agent')
                result['agentGrantedSeconds'] = allowance
                agent_exit = run_logged(
                    ['opencode', 'run', '--standalone', '--model', MODEL, '--format', 'json',
                     '--title', f'new benchmark {platform} {task_id}', prompt],
                    candidate, env, agent_log, allowance, protect_storage=True, deadline=work_deadline)
                result.update(agentExit=agent_exit, agentTimedOut=agent_exit == 124)
        # Reserve finalization time for an immutable, reconstructable generation
        # checkpoint even if the model has consumed all executable work budget.
        with phase('patch_archive', finalizing=True):
            changed = status_paths(candidate, deadline=deadline)
            generated = [path for path in changed if is_production(path, platform)]
            patch_receipt = archive_candidate_patch(candidate, patches / f'{platform}_{task_id}.patch',
                                                    baseline_commit=baseline['commit'], deadline=deadline)
            result.update(codeGenerated=bool(generated), generatedCodeFiles=generated,
                          candidatePatch=patch_receipt, completedGenerationCheckpoint=True)
        if result['agentTimedOut']:
            raise TaskDeadlineExceeded('agent')
        with phase('provider_diagnostics'):
            if platform == 'android':
                android_inputs.verify_init(candidate, env, work_deadline)
            provider_failure = provider_failure_kind(agent_log, deadline=work_deadline)
        if provider_failure:
            result['availability'] = provider_failure
        else:
            with phase('audit'):
                isolation_audit = audit_recursive_agent_log(agent_log, candidate, platform, run_root,
                                                            deadline=work_deadline)
                result.update(isolationAudit=isolation_audit, isolationViolations=isolation_audit.get('violations', []),
                              workspacePathLeakDetected=True if isolation_audit['availability'] == 'isolation_violation'
                              else False if isolation_audit['availability'] == 'available' else None)
                remaining_budget(work_deadline, 'audit')
            if isolation_audit['availability'] != 'available':
                result['availability'] = isolation_audit['availability']
            else:
                isolation_verified = True
                result['metricAvailability']['codeGeneration'] = True
                with phase('build'):
                    build_exit, build_command = build(platform, candidate, env,
                        logs / f'{platform}_{task_id}_build.log', deadline=work_deadline)
                    result.update(buildExit=build_exit, buildCommand=build_command)
                    if build_exit == 124:
                        raise TaskDeadlineExceeded('build')
                    result['compile'] = 'passed' if build_exit == 0 else 'failed'
                    result['metricAvailability']['compile'] = True
                with phase('build_artifact_cleanup'):
                    clean_application_build(candidate, reports / f'{platform}_{task_id}_build-artifacts.json',
                                            deadline=work_deadline)
                with phase('score'):
                    report = reports / f'{platform}_{task_id}_agent.json'
                    result['semanticReport'] = str(report)
                    score(task_id, platform, candidate, generated, build_exit, build_command, report,
                          deadline=work_deadline)
                    remaining_budget(work_deadline, 'score')
                    semantic_result = load(report)
                    rows = semantic_result.get('semantic', {}).get('cases', [])
                    complete = (semantic_result.get('observationMode') == 'runtime_state_transition'
                                and bool(rows) and all(row.get('status') in ('pass', 'fail') for row in rows))
                    result.update(availability='available', semanticCoverageComplete=complete,
                                  semanticObservationMode=semantic_result.get('observationMode'),
                                  benchmarkMetricsAvailable=complete)
                    result['metricAvailability']['semanticTestcase'] = complete
    except (TaskDeadlineExceeded, subprocess.TimeoutExpired, TimeoutError) as error:
        exhausted_phase = error.phase if isinstance(error, TaskDeadlineExceeded) else current_phase
        domain = ('model' if exhausted_phase == 'agent' and agent_invoked else
                  'evaluation' if exhausted_phase in {'audit', 'score'} else 'environment')
        result.update(availability=f'{domain}_deadline', deadlineExceededPhase=exhausted_phase,
                      deadlineDomain=domain, reason=str(error), benchmarkMetricsAvailable=False,
                      evaluationRepairRequired=bool(result.get('completedGenerationCheckpoint')),
                      completedCheckpointPreserved=bool(result.get('completedGenerationCheckpoint')))
        if domain == 'model':
            result['agentTimedOut'] = True
    except StorageProtectionError as error:
        result.update(availability='storage_protection_environment', reason=str(error))
    except android_inputs.InputIntegrityError as error:
        result.update(availability='input_integrity_environment', failurePhase=current_phase,
                      reason=str(error), benchmarkMetricsAvailable=False,
                      evaluationRepairRequired=bool(result.get('completedGenerationCheckpoint')),
                      completedCheckpointPreserved=bool(result.get('completedGenerationCheckpoint')))
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        result.update(availability='evaluation_failure' if current_phase in {'audit', 'score'} else 'environment_failure',
                      failurePhase=current_phase, reason=f'{type(error).__name__}: {error}',
                      evaluationRepairRequired=bool(result.get('completedGenerationCheckpoint')),
                      completedCheckpointPreserved=bool(result.get('completedGenerationCheckpoint')))
    finally:
        try:
            with phase('cleanup', finalizing=True):
                if not keep and candidate.exists():
                    clean_application_build(candidate,
                        reports / f'{platform}_{task_id}_finalization-build-artifacts.json', deadline=deadline)
                    clean_candidate(candidate, deadline=deadline)
                result['cleanup'] = {'completed': keep or not candidate.exists(), 'keptByRequest': keep}
        except (OSError, TimeoutError) as error:
            result['cleanup'] = {'completed': not candidate.exists(),
                                 'pendingPath': str(candidate) if candidate.exists() else None, 'reason': str(error)}
            if isinstance(error, TimeoutError):
                result['cleanupDeadlineExceeded'] = True
                if result['availability'] == 'available':
                    result.update(availability='environment_deadline', deadlineExceededPhase='cleanup',
                                  deadlineDomain='environment', benchmarkMetricsAvailable=False,
                                  evaluationRepairRequired=True, completedCheckpointPreserved=True)
        if not isolation_verified:
            result['metricAvailability'] = {'codeGeneration': False, 'compile': False, 'semanticTestcase': False}
        finished = time.monotonic()
        result.update(finishedAt=datetime.now().astimezone().isoformat(timespec='seconds'),
                      durationSeconds=round(finished-started, 3),
                      deadlineOverrunSeconds=max(0, round(finished-deadline, 6)),
                      timingScope='One overall interval including prepare, lock waits, agent, audit, build, score and cleanup.')
        budget_path = reports / f'{platform}_{task_id}_execution-budget.json'
        budget_path.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
        result['executionBudgetRecord'] = _artifact_binding(budget_path)
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
        candidate = candidate_root / platform / task_id
        fallback_deadline = time.monotonic() + timeout
        escaped = True
        try:
            result = run_one(task_id, platform, candidate_root, run_root, timeout, keep)
            escaped = False
        except StorageProtectionError as error:
            return {"taskId": task_id, "platform": platform, "model": MODEL, "endpoint": ENDPOINT,
                    "availability": "storage_protection_environment", "reason": str(error),
                    "benchmarkMetricsAvailable": False}
        finally:
            # Normal results already performed deadline-bound cleanup. Do not
            # restart an unbounded deletion after a timed-out cleanup checkpoint.
            if escaped and not keep:
                try:
                    clean_candidate(candidate, deadline=fallback_deadline)
                except (OSError, TimeoutError):
                    pass
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
        "observationMode": "runtime_state_transition",
        "semanticCoverageComplete": bool(results) and all(row.get("availability") == "available" and
            row.get("semanticCoverageComplete", False) for row in results),
        "calibrationRequiredBeforePublication": True,
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


def write_manifest_checkpoint(run_root: Path, manifest: dict[str, Any]) -> None:
    """Keep one current manifest, retaining earlier immutable checkpoints by hash."""
    destination = run_root / "eval_manifest.json"
    for source in (destination, run_root / 'eval_manifest.partial.json'):
        if not source.exists():
            continue
        previous = source.read_bytes()
        history = run_root / "manifest_history" / (hashlib.sha256(previous).hexdigest() + ".json")
        history.parent.mkdir(parents=True, exist_ok=True)
        if not history.exists():
            history.write_bytes(previous)
    encoded = json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    temporary = destination.with_suffix(".json.tmp")
    temporary.write_text(encoded, encoding="utf-8")
    temporary.replace(destination)
    partial = run_root / "eval_manifest.partial.json"
    temporary = partial.with_suffix(".json.tmp")
    temporary.write_text(encoded, encoding="utf-8")
    temporary.replace(partial)


def validate_resume_scope(prior: dict[str, Any]) -> None:
    inactive = {str(row.get("taskId", "")) for row in prior.get("tasks", [])} - set(task_ids())
    if inactive:
        raise ValueError("Run contains excluded/inactive tasks; preserve it and use a new run ID: " + ", ".join(sorted(inactive)))


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
    if not args.resume and (any((run_root / name).exists() for name in
            ('eval_manifest.json', 'eval_manifest.partial.json')) or
            list((run_root / 'logs').glob('*_opencode.jsonl'))):
        raise ValueError('Run already contains generation evidence; use --resume or a new run ID')
    run_root.mkdir(parents=True, exist_ok=True)
    candidate_root = (args.candidate_root or ROOT.parent / ".ltb-new-tasks-eval" / args.run_id).resolve()
    partial_manifest = run_root / "eval_manifest.partial.json"
    previous: list[dict[str, Any]] = []
    started_at = datetime.now().astimezone()
    checkpoint = partial_manifest if partial_manifest.exists() else run_root / 'eval_manifest.json'
    if args.resume and checkpoint.exists():
        prior = load(checkpoint)
        validate_resume_scope(prior)
        previous = resume_checkpoint_rows(prior, candidate_root, run_root)
        started_at = datetime.fromisoformat(prior["startedAt"])
    elif args.resume and list((run_root / 'logs').glob('*_opencode.jsonl')):
        raise ValueError('Generation evidence exists without checkpoint; preserve it and use a new run or evaluator repair')
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
                write_manifest_checkpoint(run_root, manifest_payload(
                    args.run_id, started_at, candidate_root, args.keep_candidates, results, "partial"))
                submit_next(platform)
    expected = len(tasks) * len(platforms)
    complete = len(results) == expected and all(row.get("availability", "available") == "available" for row in results)
    manifest = manifest_payload(args.run_id, started_at, candidate_root, args.keep_candidates, results, "complete" if complete else "partial")
    write_manifest_checkpoint(run_root, manifest)
    if not args.keep_candidates and candidate_root.exists():
        # Never recursively delete retained legacy candidates on a no-work resume.
        try:
            candidate_root.rmdir()
        except OSError:
            pass
    failed = [row for row in results if row.get("availability", "available") != "available" or
              row.get("agentExit") != 0 or row.get("buildExit") != 0 or row.get("runnerError")]
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
