#!/usr/bin/env python3
"""Run isolated OpenCode agent evaluations for Wikipedia tasks 03 and 04."""

from __future__ import annotations

import argparse
import concurrent.futures
import fcntl
import hashlib
import importlib.util
import json
import os
import re
import shlex
import shutil
import signal
import stat
import subprocess
import tarfile
import tempfile
import threading
import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[4]
PROJECT = ROOT / "benchmark_projects/wikipedia-android"
MIGRATIONS = PROJECT / "migrations"
TASKS = PROJECT / "tasks"
TOOLS = MIGRATIONS / "tools"
TASK_IDS = ("03_explore_feed", "04_reading_lists")
PLATFORMS = ("android", "arkts")
MODEL = "minimax-token-plan/MiniMax-M3"
ENDPOINT = "https://api.minimaxi.com/v1"
MIN_FREE_BYTES = 8 * 1024**3
ANDROID_BUILD_LOCK = Path("/tmp/long-term-benchmark-android-full-build.lock")
HVIGOR = Path("/Applications/DevEco-Studio.app/Contents/tools/hvigor/bin/hvigorw")
ANDROID_SDK = Path.home() / "Library/Android/sdk"
OH_SDK = Path.home() / "Library/OpenHarmony/Sdk/23"
JAVA_HOME = Path("/opt/homebrew/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home")
MODEL_MAX_SECONDS = 2700


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected JSON object")
    return value


def dump(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def artifact(path: Path) -> dict[str, Any]:
    return {"path": str(path), "bytes": path.stat().st_size, "sha256": sha256(path)}


def require_space(path: Path) -> int:
    probe = path
    while not probe.exists():
        probe = probe.parent
    free = shutil.disk_usage(probe).free
    if free < MIN_FREE_BYTES:
        raise RuntimeError(f"disk safety line: {free} bytes free, {MIN_FREE_BYTES} required")
    return free


def remaining(deadline: float, phase: str) -> float:
    value = deadline - time.monotonic()
    if value <= 0:
        raise TimeoutError(f"overall 3600s deadline exhausted during {phase}")
    return value


def environment(candidate: Path) -> dict[str, str]:
    env = os.environ.copy()
    env.update({
        "PWD": str(candidate),
        "OLDPWD": str(candidate),
        "JAVA_HOME": str(JAVA_HOME),
        "ANDROID_HOME": str(ANDROID_SDK),
        "ANDROID_SDK_ROOT": str(ANDROID_SDK),
        "DEVECO_SDK_HOME": str(OH_SDK),
    })
    env["PATH"] = os.pathsep.join([
        str(JAVA_HOME / "bin"),
        str(ANDROID_SDK / "platform-tools"),
        str(HVIGOR.parent),
        "/Applications/DevEco-Studio.app/Contents/tools/ohpm/bin",
        env.get("PATH", ""),
    ])
    return env


def terminate(process: subprocess.Popen[Any]) -> None:
    if process.poll() is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        process.wait(timeout=15)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait()


def run_logged(command: list[str], cwd: Path, log: Path, timeout: float,
               env: dict[str, str] | None = None, protect_space: bool = False) -> int:
    if timeout <= 0:
        raise TimeoutError("no subprocess budget remains")
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("w", encoding="utf-8") as stream:
        process = subprocess.Popen(
            command, cwd=cwd, env=env or os.environ.copy(), stdout=stream,
            stderr=subprocess.STDOUT, text=True, start_new_session=True,
        )
        started = time.monotonic()
        try:
            while True:
                if protect_space:
                    require_space(cwd)
                left = timeout - (time.monotonic() - started)
                if left <= 0:
                    raise subprocess.TimeoutExpired(command, timeout)
                try:
                    return process.wait(timeout=min(5, left))
                except subprocess.TimeoutExpired:
                    if time.monotonic() - started >= timeout:
                        raise
        except BaseException:
            terminate(process)
            raise


@contextmanager
def android_build_slot(path: Path):
    require_space(path)
    with ANDROID_BUILD_LOCK.open("a+") as stream:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        try:
            require_space(path)
            yield
        finally:
            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def expand(command: list[str], values: dict[str, Path | str]) -> list[str]:
    mapping = {key: str(value) for key, value in values.items()}
    return [part.format_map(mapping) for part in command]


def copy_candidate(source: Path, destination: Path) -> None:
    if destination.exists():
        shutil.rmtree(destination)

    def ignored(_: str, names: list[str]) -> set[str]:
        discarded = {".git", ".gradle", ".hvigor", "build", "oh_modules", "node_modules", "__pycache__"}
        return set(names) & discarded

    shutil.copytree(source, destination, ignore=ignored)


def public_transitions(contract: dict[str, Any]) -> dict[str, Any]:
    return {
        "schemaVersion": 1,
        "taskId": contract["taskId"],
        "description": "Public scenarios. Evaluator bindings, expected observations, and reports are private.",
        "cases": [{
            "caseId": case["caseId"],
            "functionalArea": case.get("functionalArea"),
            "given": case["given"],
            "event": case["event"],
            "invariants": case.get("invariants", []),
        } for case in contract["cases"]],
    }


def opencode_config(candidate: Path, build_command: list[str]) -> dict[str, Any]:
    root = str(candidate.resolve())
    paths = {"*": "allow", "/*": "deny", f"{root}/*": "allow"}
    edit = dict(paths)
    for pattern in (
        "_benchmark_inputs/*", "_benchmark_inputs/**",
        f"{root}/_benchmark_inputs/*", f"{root}/_benchmark_inputs/**",
    ):
        edit[pattern] = "deny"
    shell = {
        "*": "deny",
        "pwd": "allow",
        "ls": "allow",
        "git status --short": "allow",
        "git diff --stat": "allow",
        "git diff --name-only": "allow",
        shlex.join(build_command): "allow",
    }
    return {
        "$schema": "https://opencode.ai/config.json",
        "agent": {"explore": {
            "steps": 12,
            "prompt": "Explore only this candidate directory. Never access parent, sibling, home, network, final, benchmark, evaluator, or report paths.",
        }},
        "permission": {
            "*": "deny",
            "read": paths,
            "edit": edit,
            "glob": paths,
            "grep": "allow",
            "list": paths,
            "task": "allow",
            "webfetch": "deny",
            "websearch": "deny",
            "external_directory": "deny",
            "shell": shell,
            "bash": shell,
        },
    }


def prepare_candidate(task_id: str, platform: str, candidate: Path,
                      run_dir: Path) -> tuple[list[str], str]:
    migration = MIGRATIONS / task_id
    execution = load(migration / "execution.json")[platform]
    source = migration / execution["baseProject"]
    copy_candidate(source, candidate)
    values = {"project": candidate, "migration": migration, "candidate": candidate}
    if execution.get("agentScaffoldCommand"):
        command = expand(execution["agentScaffoldCommand"], values)
        code = run_logged(command, migration, run_dir / "preflight-scaffold.log", 600, environment(candidate))
        if code:
            raise RuntimeError(f"visible scaffold failed with exit {code}")
    build_script = candidate / "build-agent.sh"
    if platform == "android":
        build_script.write_text(
            """#!/usr/bin/env bash
set -euo pipefail
gradle_bin="${GRADLE_BIN:-$HOME/.gradle/wrapper/dists/gradle-8.14.3-bin/cv11ve7ro1n3o1j4so8xd9n66/gradle-8.14.3/bin/gradle}"
"$gradle_bin" -p . --no-daemon --offline :app:assembleDebug
""",
            encoding="utf-8",
        )
    else:
        build_script.write_text(
            """#!/usr/bin/env bash
set -euo pipefail
hvigorw="${HVIGORW:-/Applications/DevEco-Studio.app/Contents/tools/hvigor/bin/hvigorw}"
"$hvigorw" --mode module -p product=default -p module=entry@default assembleHap --no-daemon
""",
            encoding="utf-8",
        )
    build_script.chmod(0o755)
    visible_build = ["bash", "build-agent.sh"]
    inputs = candidate / "_benchmark_inputs"
    inputs.mkdir()
    shutil.copy2(TASKS / task_id / "requirement.md", inputs / "requirement.md")
    contract = load(migration / "canonical/transitions.json")
    dump(inputs / "public_transitions.json", public_transitions(contract))
    prompt = f"""Implement {task_id} completely in this {platform} candidate.

Read `_benchmark_inputs/requirement.md` and `_benchmark_inputs/public_transitions.json`, inspect the visible production scaffold, and implement the requested behavior in real production code.

Rules:
- Work only in this candidate directory. Never inspect parent, sibling, home, benchmark, final, evaluator, report, or network paths.
- Subagents are allowed and inherit exactly the same workspace boundary.
- Do not create case-ID switches, marker facts, semantic projections, evaluator APIs, or source-observer shortcuts.
- Preserve unrelated behavior. Implement application-owned state, persistence, effects, UI/page wiring, failure recovery, and cleanup.
- Run `{shlex.join(visible_build)}` exactly as written and repair compilation within the overall task budget.

Finish with a concise summary of changed production files and remaining blockers.
"""
    (inputs / "prompt.md").write_text(prompt, encoding="utf-8")
    dump(candidate / "opencode.json", opencode_config(candidate, visible_build))
    subprocess.run(["git", "init", "-q"], cwd=candidate, check=True)
    subprocess.run(["git", "add", "-A"], cwd=candidate, check=True)
    subprocess.run([
        "git", "-c", "user.name=Benchmark Runner", "-c",
        "user.email=benchmark@localhost", "commit", "-q", "-m", "clean-room base",
    ], cwd=candidate, check=True)
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=candidate, text=True).strip()
    return visible_build, commit


def tree_snapshot(candidate: Path, output: Path) -> dict[str, Any]:
    rows = []
    for path in sorted(candidate.rglob("*")):
        relative = path.relative_to(candidate).as_posix()
        if ".git" in path.parts:
            continue
        info = path.lstat()
        row: dict[str, Any] = {"path": relative, "mode": stat.S_IMODE(info.st_mode)}
        if path.is_symlink():
            row.update(type="symlink", target=os.readlink(path))
        elif path.is_file():
            row.update(type="file", bytes=info.st_size, sha256=sha256(path))
        elif path.is_dir():
            row.update(type="directory")
        rows.append(row)
    payload = {"schemaVersion": 1, "root": str(candidate), "entries": rows}
    dump(output, payload)
    return artifact(output)


def baseline_archive(candidate: Path, destination: Path, commit: str) -> dict[str, Any]:
    destination.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([
        "git", "archive", "--format=tar.gz", "--output", str(destination), commit,
    ], cwd=candidate, check=True)
    return {**artifact(destination), "commit": commit, "capturePhase": "after_preflight_cleanup_before_agent"}


def cleanup_builds(project: Path, receipt: Path) -> None:
    binaries = []
    removable: list[Path] = []
    for parent, directories, files in os.walk(project):
        root = Path(parent)
        if root.name in {"build", ".gradle", ".hvigor", ".cxx", "oh_modules", "node_modules", "__pycache__"}:
            removable.append(root)
            directories[:] = []
            for path in root.rglob("*"):
                if path.is_file() and path.suffix.lower() in {".apk", ".aab", ".hap", ".har"}:
                    binaries.append({"path": str(path.relative_to(project)), "bytes": path.stat().st_size,
                                     "sha256": sha256(path)})
        else:
            directories[:] = [name for name in directories if name != ".git"]
    for path in sorted(set(removable), key=lambda item: len(item.parts), reverse=True):
        if path.exists():
            shutil.rmtree(path)
    dump(receipt, {
        "schemaVersion": 1,
        "policy": "hash binaries before deleting build and dependency outputs",
        "artifacts": binaries,
        "removedDirectories": [str(path.relative_to(project)) for path in removable],
        "cleanupCompleted": all(not path.exists() for path in removable),
    })


def changed_paths(candidate: Path) -> list[str]:
    changed = subprocess.check_output([
        "git", "diff", "HEAD", "--name-only", "--no-renames", "-z",
    ], cwd=candidate)
    untracked = subprocess.check_output([
        "git", "ls-files", "--others", "--exclude-standard", "-z",
    ], cwd=candidate)
    return sorted({os.fsdecode(path) for path in (changed + untracked).split(b"\0") if path})


def production_files(paths: list[str], platform: str) -> list[str]:
    suffixes = {".kt", ".kts", ".java", ".xml"} if platform == "android" else {".ets", ".ts", ".json5"}
    excluded = {"build", ".gradle", ".hvigor", "oh_modules", "node_modules", "_benchmark_inputs"}
    source_prefix = "app/src/main/" if platform == "android" else "entry/src/main/"
    return [path for path in paths if path.startswith(source_prefix)
            and Path(path).suffix.lower() in suffixes
            and not (set(Path(path).parts) & excluded)]


def generation_audit(candidate: Path, generated: list[str]) -> dict[str, Any]:
    issues = []
    # `generated` contains production roots only. Candidate-owned unit tests are
    # legitimate supporting work and must never be treated as evaluator code.
    forbidden_parts = {"probe", "probes", "evaluator", "evaluators", "fixture", "fixtures"}
    for relative in generated:
        path = Path(relative)
        if {part.lower() for part in path.parts} & forbidden_parts or "probe" in path.stem.lower():
            issues.append(f"evaluator-like generated path: {relative}")
            continue
        full = candidate / path
        if full.is_file():
            text = full.read_text(encoding="utf-8", errors="ignore")
            for marker in ("traceDigest", "LTB_RUNTIME", "SemanticProbe"):
                if marker in text:
                    issues.append(f"forbidden evaluator marker {marker} in {relative}")
    return {"passed": bool(generated) and not issues, "changedProductionFiles": generated, "issues": issues}


def object_value(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def measured_metrics(result: dict[str, Any]) -> dict[str, bool]:
    code_generation = result.get("codeGeneration")
    compile_result = result.get("compile")
    semantic = result.get("semanticTestcase")
    return {
        "codeGeneration": isinstance(code_generation, dict) and isinstance(code_generation.get("passed"), bool),
        "compile": isinstance(compile_result, dict) and isinstance(compile_result.get("passed"), bool),
        "semanticTestcase": isinstance(semantic, dict) and isinstance(semantic.get("scored"), int),
    }


def finalize_metric_availability(result: dict[str, Any]) -> None:
    availability = measured_metrics(result)
    result["metricAvailability"] = availability
    # A failed metric is still a measured benchmark result.
    result["benchmarkMetricsAvailable"] = all(availability.values())
    isolation = object_value(result.get("isolationAudit")).get("availability")
    result["runIntegrity"] = {
        "isolation": isolation or "not_audited",
        "validForPublication": isolation == "available" and result["benchmarkMetricsAvailable"],
    }


def archive_patch(candidate: Path, destination: Path, baseline: str) -> dict[str, Any]:
    if destination.exists():
        destination.unlink()
    subprocess.run(["git", "add", "-N", "--", "."], cwd=candidate, check=True)
    patch = subprocess.check_output([
        "git", "diff", "--binary", "--full-index", "--no-renames", "--no-ext-diff", baseline, "--",
    ], cwd=candidate)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(patch)
    with tempfile.TemporaryDirectory(prefix="wiki-agent-replay-") as temporary:
        index = Path(temporary) / "index"
        env = {**os.environ, "GIT_INDEX_FILE": str(index)}
        subprocess.run(["git", "read-tree", baseline], cwd=candidate, env=env, check=True)
        if patch:
            subprocess.run(["git", "apply", "--cached", "--binary", "--whitespace=nowarn", "-"],
                           cwd=candidate, env=env, input=patch, check=True)
        tree = subprocess.check_output(["git", "write-tree"], cwd=candidate, env=env, text=True).strip()
    return {**artifact(destination), "baselineCommit": baseline, "tree": tree, "reconstructionVerified": True}


def root_session_id(log: Path) -> str:
    first = None
    ids = set()
    for line in log.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        value = event.get("sessionID") or event.get("part", {}).get("sessionID")
        if isinstance(value, str):
            ids.add(value)
            if first is None and event.get("type") == "step_start":
                first = value
    if first is None or ids != {first}:
        raise ValueError("OpenCode JSONL has missing or ambiguous root session")
    return first


def load_audit_module():
    path = ROOT / "scripts/opencode_subagent_audit.py"
    spec = importlib.util.spec_from_file_location("wikipedia_opencode_audit", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load OpenCode recursive audit helper")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, path


def audit_sessions(log: Path, candidate: Path, build_command: list[str], output: Path,
                   deadline: float) -> dict[str, Any]:
    module, helper = load_audit_module()
    root_id = root_session_id(log)
    inventory = module.read_db_session_inventory(
        Path.home() / ".local/share/opencode/opencode.db", root_id, deadline=deadline,
    )
    by_parent: dict[str | None, list[str]] = {}
    for session in inventory["sessions"]:
        by_parent.setdefault(session["parentID"], []).append(session["sessionID"])
    archive_dir = output.parent / "sessions"
    loader = module.CliExportLoader(archive_dir, output.stem, deadline=deadline)
    config = opencode_config(candidate, build_command)
    allowed = [command for command, decision in config["permission"]["shell"].items()
               if decision == "allow"]
    audit = module.audit_sessions(
        root_id, candidate, loader, allowed_shell_commands=allowed,
        discover_children=lambda sid: by_parent.get(sid, []), deadline=deadline,
    )
    inventory_path = archive_dir / f"{output.stem}_session-inventory.json"
    dump(inventory_path, inventory)
    audit.update({
        "schema": "opencode_recursive_isolation_v1",
        "candidate": str(candidate.resolve()),
        "rootSessionID": root_id,
        "allowedShellCommands": sorted(allowed),
        "reviewedHelper": {**artifact(helper), "path": str(helper)},
        "inventory": artifact(inventory_path),
        "sessionExports": {sid: artifact(path) for sid, path in loader.paths.items()},
        "timingScope": "Top-level run only; subagent timestamps are forensic and are not summed.",
    })
    completed = {(row.get("sessionID"), row.get("callID")) for row in audit.get("records", [])
                 if row.get("status") == "completed"}
    escaped = any(
        violation.get("code") in {"outside_candidate_path", "network_tool_access"}
        and violation.get("callID") is not None
        and (violation.get("sessionID"), violation.get("callID")) in completed
        for violation in audit.get("violations", [])
    )
    audit["availability"] = (
        "isolation_violation" if escaped else
        "available" if audit.get("complete") is True and audit.get("valid") is True and not audit.get("violations") else
        "isolation_unverified"
    )
    dump(output, audit)
    return {"availability": audit["availability"], **artifact(output)}


def provider_failure(log: Path) -> str | None:
    for line in log.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") != "error":
            continue
        error = event.get("error", {})
        detail = error.get("data", {}) if isinstance(error, dict) else {}
        detail = detail if isinstance(detail, dict) else {}
        status_code = detail.get("statusCode", detail.get("status", error.get("status") if isinstance(error, dict) else None))
        kind = str(error.get("type", error.get("name", ""))) if isinstance(error, dict) else ""
        if kind == "provider.quota" or status_code in (402, 429):
            return "provider_quota"
        if kind in {"provider.auth", "provider.authentication"} or status_code in (401, 403):
            return "provider_auth"
        if kind.startswith("provider.") or status_code is not None:
            return "provider_transport"
        return "agent_runtime_error"
    return None


def redact_secret_artifacts(root: Path) -> dict[str, Any]:
    secret_path = Path.home() / ".config/opencode/secrets/minimax-m3-key"
    secret = secret_path.read_bytes().strip() if secret_path.is_file() else b""
    hits = []
    if secret:
        for path in root.rglob("*"):
            if not path.is_file() or path.stat().st_size > 50 * 1024 * 1024:
                continue
            data = path.read_bytes()
            if secret in data:
                path.write_bytes(data.replace(secret, b"[REDACTED_MINIMAX_KEY]"))
                hits.append(str(path.relative_to(root)))
    return {"apiKeyRecorded": False, "redactedArtifactCount": len(hits), "redactedArtifacts": hits}


def semantic_metrics(report: dict[str, Any]) -> dict[str, Any]:
    semantic = report.get("semantic", {})
    passed = int(semantic.get("passed", 0))
    failed = int(semantic.get("failed", 0))
    not_scored = int(semantic.get("notScored", 0))
    denominator = passed + failed
    return {
        "passed": passed,
        "failed": failed,
        "notScored": not_scored,
        "scored": denominator,
        "total": int(semantic.get("total", passed + failed + not_scored)),
        "rate": round(passed / denominator, 6) if denominator else None,
        "policy": "notScored is excluded from both pass and fail",
    }


def execute_hidden_score(task_id: str, platform: str, candidate: Path, run_dir: Path,
                         generated_audit: dict[str, Any], compile_passed: bool, visible_build: list[str],
                         deadline: float) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    migration = MIGRATIONS / task_id
    config = load(migration / "execution.json")[platform]
    values = {
        "project": candidate,
        "candidate": candidate,
        "migration": migration,
        "role": "agent",
        "output": run_dir / "semantic.json",
    }
    prepare = expand(config["agentPrepareCommand"], values)
    code = run_logged(prepare, migration, run_dir / "hidden-prepare.log", remaining(deadline, "hidden_prepare"),
                      environment(candidate))
    diagnostics: dict[str, Any] = {"prepareExit": code}
    if code:
        return None, diagnostics
    build = expand(config["agentBuildCommand"], values)
    if platform == "android":
        # The focused harness build.sh owns the shared Android full-build lock.
        # Taking it here as well would deadlock the child on the same lock.
        require_space(candidate)
        build_exit = run_logged(build, migration, run_dir / "hidden-build.log",
                                remaining(deadline, "hidden_build"), environment(candidate), True)
    else:
        require_space(candidate)
        build_exit = run_logged(build, migration, run_dir / "hidden-build.log",
                                remaining(deadline, "hidden_build"), environment(candidate), True)
    diagnostics.update(buildExit=build_exit, classification="hidden evaluator adapter diagnostic")
    if build_exit:
        return None, diagnostics
    semantic = expand(config["agentSemanticCommand"], values)
    semantic_exit = run_logged(semantic, migration, run_dir / "semantic.log",
                               remaining(deadline, "semantic_runtime"), environment(candidate))
    diagnostics["semanticExit"] = semantic_exit
    report_path = Path(values["output"])
    if not report_path.is_file():
        return None, diagnostics
    report = load(report_path)
    # The hidden harness may patch production entrypoints to expose runtime
    # episodes. Code generation attribution must remain frozen at the clean
    # candidate state captured before prepare/build inject evaluator wiring.
    report["codeGeneration"] = generated_audit
    report.setdefault("diagnostics", {})["codeGenerationAttribution"] = {
        "snapshot": "pre_hidden_candidate",
        "hiddenHarnessExcluded": True,
    }
    report["compile"] = {"passed": compile_passed, "command": visible_build}
    report.setdefault("diagnostics", {})["runtimeCompile"] = {
        "passed": build_exit == 0,
        "classification": "hidden evaluator adapter diagnostic",
    }
    dump(report_path, report)
    return report, diagnostics


def preflight(task_id: str, platform: str, candidate: Path, run_dir: Path) -> tuple[list[str], str, dict[str, Any]]:
    require_space(candidate.parent)
    visible_build, baseline = prepare_candidate(task_id, platform, candidate, run_dir)
    env = environment(candidate)
    if platform == "android":
        with android_build_slot(candidate):
            exit_code = run_logged(visible_build, candidate, run_dir / "preflight-build.log", 1200, env, True)
    else:
        exit_code = run_logged(visible_build, candidate, run_dir / "preflight-build.log", 1200, env, True)
    if exit_code:
        raise RuntimeError(f"clean base public build failed with exit {exit_code}")
    cleanup_builds(candidate, run_dir / "preflight-artifacts.json")
    inputs = run_dir / "inputs"
    snapshot = tree_snapshot(candidate, inputs / "raw-tree.json")
    archive = baseline_archive(candidate, inputs / "baseline.tar.gz", baseline)
    return visible_build, baseline, {"rawTree": snapshot, "archive": archive}


def run_one(task_id: str, platform: str, run_id: str, candidate_root: Path,
            timeout: int) -> dict[str, Any]:
    migration = MIGRATIONS / task_id
    run_dir = migration / "results/agent-runs" / run_id / platform
    run_dir.mkdir(parents=True, exist_ok=True)
    candidate = candidate_root / task_id / platform
    result: dict[str, Any] = {
        "schemaVersion": 1,
        "runId": run_id,
        "taskId": task_id,
        "platform": platform,
        "runner": "OpenCode",
        "model": MODEL,
        "endpoint": ENDPOINT,
        "overallTimeoutSeconds": timeout,
        "subagentsAllowed": True,
        "semanticFeedbackDuringGeneration": False,
        "availability": "environment_failure",
        "benchmarkMetricsAvailable": False,
    }
    started = None
    deadline = None
    try:
        visible_build, baseline, baseline_evidence = preflight(task_id, platform, candidate, run_dir)
        result.update(candidateBaseline=baseline_evidence, publicBuildCommand=visible_build,
                      opencodeVersion=subprocess.check_output(["opencode", "--version"], text=True).strip())
        started = time.monotonic()
        deadline = started + timeout
        result["startedAt"] = datetime.now().astimezone().isoformat(timespec="seconds")
        prompt = (candidate / "_benchmark_inputs/prompt.md").read_text(encoding="utf-8")
        log = run_dir / "opencode.jsonl"
        agent_allowance = min(MODEL_MAX_SECONDS, remaining(deadline, "agent"))
        result["agentGrantedSeconds"] = agent_allowance
        try:
            agent_exit = run_logged([
                "opencode", "run", "--standalone", "--model", MODEL, "--format", "json",
                "--title", f"Wikipedia {task_id} {platform}", prompt,
            ], candidate, log, agent_allowance, environment(candidate), True)
            timed_out = False
        except subprocess.TimeoutExpired:
            agent_exit = 124
            timed_out = True
        result.update(agentExit=agent_exit, agentTimedOut=timed_out)
        # Agent-invoked public builds are diagnostics, not generated source.
        # Hash and remove them before inventorying or archiving the patch.
        cleanup_builds(candidate, run_dir / "agent-invoked-build-artifacts.json")
        paths = changed_paths(candidate)
        generated = production_files(paths, platform)
        generated_audit = generation_audit(candidate, generated)
        patch = archive_patch(candidate, run_dir / "agent.patch", baseline)
        dump(run_dir / "generated-files.json", {
            "schemaVersion": 1,
            "changedFiles": paths,
            "generatedProductionFiles": generated,
            "audit": generated_audit,
        })
        result.update(candidatePatch=patch, codeGeneration=generated_audit)
        external = provider_failure(log)
        if external:
            result.update(availability=external, externalFailure=True)
            return result
        if timed_out:
            result.update(availability="model_timeout", externalFailure=False)
            return result
        isolation = audit_sessions(log, candidate, visible_build, run_dir / "isolation-audit.json", deadline)
        result["isolationAudit"] = isolation
        if isolation["availability"] != "available":
            result["availability"] = isolation["availability"]
            return result
        env = environment(candidate)
        if platform == "android":
            with android_build_slot(candidate):
                compile_exit = run_logged(visible_build, candidate, run_dir / "production-build.log",
                                          remaining(deadline, "production_build"), env, True)
        else:
            compile_exit = run_logged(visible_build, candidate, run_dir / "production-build.log",
                                      remaining(deadline, "production_build"), env, True)
        compile_passed = compile_exit == 0
        result["compile"] = {"passed": compile_passed, "exitCode": compile_exit, "command": visible_build}
        cleanup_builds(candidate, run_dir / "production-build-artifacts.json")
        report, diagnostics = execute_hidden_score(
            task_id, platform, candidate, run_dir, generated_audit, compile_passed, visible_build, deadline,
        )
        result["diagnostics"] = diagnostics
        if report is None:
            result.update(availability="evaluation_failure", benchmarkMetricsAvailable=False)
            return result
        metrics = semantic_metrics(report)
        result.update(
            availability="available",
            benchmarkMetricsAvailable=True,
            semanticTestcase=metrics,
            semanticReport=artifact(run_dir / "semantic.json"),
            rawSemanticReport=artifact(run_dir / "semantic.raw.json") if (run_dir / "semantic.raw.json").is_file() else None,
        )
        top_report = migration / "results" / f"{platform}-agent.json"
        shutil.copy2(run_dir / "semantic.json", top_report)
        raw_report = run_dir / "semantic.raw.json"
        if raw_report.is_file():
            shutil.copy2(raw_report, migration / "results" / f"{platform}-agent.raw.json")
        patches = migration / "results/agent-patches"
        patches.mkdir(parents=True, exist_ok=True)
        shutil.copy2(run_dir / "agent.patch", patches / f"{platform}-agent.patch")
        shutil.copy2(run_dir / "generated-files.json", patches / f"{platform}-agent-generated-files.json")
        return result
    except TimeoutError as error:
        result.update(availability="overall_timeout", reason=str(error), benchmarkMetricsAvailable=False)
        return result
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        result.update(availability="environment_failure" if started is None else "evaluation_failure",
                      reason=f"{type(error).__name__}: {error}", benchmarkMetricsAvailable=False)
        return result
    finally:
        cleanup_error = None
        try:
            if candidate.exists():
                cleanup_builds(candidate, run_dir / "final-cleanup-artifacts.json")
                shutil.rmtree(candidate)
        except OSError as error:
            cleanup_error = str(error)
        if started is not None:
            result.update(
                finishedAt=datetime.now().astimezone().isoformat(timespec="seconds"),
                durationSeconds=round(time.monotonic() - started, 3),
                timingScope="Top-level run from OpenCode invocation through audit, build, runtime scoring, and cleanup; subagent durations are not added.",
            )
        result["cleanup"] = {"completed": not candidate.exists(), "error": cleanup_error}
        result["credentialAudit"] = redact_secret_artifacts(run_dir)
        finalize_metric_availability(result)
        dump(run_dir / "run.json", result)


def safe_extract_tar(archive: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive) as stream:
        for member in stream.getmembers():
            target = (destination / member.name).resolve()
            if target != destination.resolve() and destination.resolve() not in target.parents:
                raise ValueError(f"baseline archive member escapes destination: {member.name}")
        stream.extractall(destination)


def repair_evaluation(task_id: str, platform: str, run_id: str,
                      candidate_root: Path, timeout: int) -> dict[str, Any]:
    migration = MIGRATIONS / task_id
    run_dir = migration / "results/agent-runs" / run_id / platform
    run_path = run_dir / "run.json"
    result = load(run_path)
    final_isolation = run_dir / "isolation-audit-final.json"
    isolation_path = final_isolation if final_isolation.is_file() else run_dir / "isolation-audit.json"
    isolation = load(isolation_path)
    result["isolationAudit"] = {
        "availability": isolation.get("availability", "isolation_unverified"),
        **artifact(isolation_path),
    }
    candidate = candidate_root / task_id / platform
    if candidate.exists():
        shutil.rmtree(candidate)
    baseline_archive_path = run_dir / "inputs/baseline.tar.gz"
    full_patch = run_dir / "agent.patch"
    old_patch = artifact(full_patch)
    repair_started = datetime.now().astimezone()
    try:
        safe_extract_tar(baseline_archive_path, candidate)
        subprocess.run(["git", "init", "-q"], cwd=candidate, check=True)
        subprocess.run(["git", "add", "-A"], cwd=candidate, check=True)
        subprocess.run([
            "git", "-c", "user.name=Benchmark Runner", "-c",
            "user.email=benchmark@localhost", "commit", "-q", "-m", "reconstructed clean-room base",
        ], cwd=candidate, check=True)
        baseline = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=candidate, text=True).strip()
        patch_bytes = full_patch.read_bytes()
        if patch_bytes:
            subprocess.run(["git", "apply", "--binary", "--whitespace=nowarn", "-"],
                           cwd=candidate, input=patch_bytes, check=True)
        cleanup_builds(candidate, run_dir / "repair-reconstructed-build-artifacts.json")
        paths = changed_paths(candidate)
        generated = production_files(paths, platform)
        generated_audit = generation_audit(candidate, generated)
        filtered_patch = run_dir / "agent.patch.filtered"
        filtered_receipt = archive_patch(candidate, filtered_patch, baseline)
        filtered_patch.replace(full_patch)
        filtered_receipt = {**artifact(full_patch),
                            "baselineArchive": artifact(baseline_archive_path),
                            "reconstructionVerified": filtered_receipt["reconstructionVerified"]}
        dump(run_dir / "patch-rewrite.json", {
            "schemaVersion": 1,
            "reason": "Removed build/cache outputs while retaining all candidate source, tests, and configuration changes.",
            "originalUnfilteredPatch": old_patch,
            "filteredPatch": filtered_receipt,
        })
        dump(run_dir / "generated-files.json", {
            "schemaVersion": 1,
            "changedFiles": paths,
            "generatedProductionFiles": generated,
            "candidateTestFiles": [path for path in paths
                                   if "/src/test/" in f"/{path}" or "/src/androidTest/" in f"/{path}"],
            "audit": generated_audit,
        })
        deadline = time.monotonic() + timeout
        visible_build = ["bash", "build-agent.sh"]
        env = environment(candidate)
        if platform == "android":
            with android_build_slot(candidate):
                compile_exit = run_logged(visible_build, candidate, run_dir / "repair-production-build.log",
                                          remaining(deadline, "repair_production_build"), env, True)
        else:
            compile_exit = run_logged(visible_build, candidate, run_dir / "repair-production-build.log",
                                      remaining(deadline, "repair_production_build"), env, True)
        compile_result = {"passed": compile_exit == 0, "exitCode": compile_exit, "command": visible_build}
        cleanup_builds(candidate, run_dir / "repair-production-build-artifacts.json")
        report, diagnostics = execute_hidden_score(
            task_id, platform, candidate, run_dir, generated_audit, compile_exit == 0, visible_build, deadline,
        )
        result.update(candidatePatch=filtered_receipt, codeGeneration=generated_audit,
                      compile=compile_result, diagnostics=diagnostics)
        if report is not None:
            result.update(
                semanticTestcase=semantic_metrics(report),
                semanticReport=artifact(run_dir / "semantic.json"),
                rawSemanticReport=artifact(run_dir / "semantic.raw.json") if (run_dir / "semantic.raw.json").is_file() else None,
            )
        else:
            result["semanticTestcase"] = None
            result.pop("semanticReport", None)
            result.pop("rawSemanticReport", None)
        result["availability"] = (
            result["isolationAudit"]["availability"]
            if result["isolationAudit"]["availability"] != "available"
            else "available" if report is not None else "evaluation_failure"
        )
        finalize_metric_availability(result)
        repair_finished = datetime.now().astimezone()
        result["evaluationRepair"] = {
            "reason": "Evaluator-only replay after scorer and aggregation repair; model generation was not rerun.",
            "modelInvoked": False,
            "startedAt": repair_started.isoformat(timespec="seconds"),
            "finishedAt": repair_finished.isoformat(timespec="seconds"),
            "elapsedSeconds": round((repair_finished - repair_started).total_seconds(), 3),
        }
        dump(run_path, result)
        if report is not None:
            shutil.copy2(run_dir / "semantic.json", migration / "results" / f"{platform}-agent.json")
            if (run_dir / "semantic.raw.json").is_file():
                shutil.copy2(run_dir / "semantic.raw.json", migration / "results" / f"{platform}-agent.raw.json")
        patches = migration / "results/agent-patches"
        patches.mkdir(parents=True, exist_ok=True)
        shutil.copy2(full_patch, patches / f"{platform}-agent.patch")
        shutil.copy2(run_dir / "generated-files.json", patches / f"{platform}-agent-generated-files.json")
        return result
    finally:
        if candidate.exists():
            cleanup_builds(candidate, run_dir / "repair-final-cleanup-artifacts.json")
            shutil.rmtree(candidate)


def refresh_existing_report(task_id: str, platform: str, run_id: str) -> dict[str, Any]:
    migration = MIGRATIONS / task_id
    run_dir = migration / "results/agent-runs" / run_id / platform
    run_path = run_dir / "run.json"
    generated_path = run_dir / "generated-files.json"
    result = load(run_path)
    generated = load(generated_path)
    audit = generated.get("audit")
    if not isinstance(audit, dict) or not isinstance(audit.get("passed"), bool):
        raise ValueError(f"{generated_path}: pre-hidden generation audit is unavailable")
    corrected = []
    for report_path in (run_dir / "semantic.json", migration / "results" / f"{platform}-agent.json"):
        if not report_path.is_file():
            raise FileNotFoundError(report_path)
        report = load(report_path)
        report["codeGeneration"] = audit
        report.setdefault("diagnostics", {})["codeGenerationAttribution"] = {
            "snapshot": "pre_hidden_candidate",
            "source": str(generated_path.relative_to(migration)),
            "hiddenHarnessExcluded": True,
        }
        dump(report_path, report)
        corrected.append(artifact(report_path))
    result["codeGeneration"] = audit
    result["semanticReport"] = artifact(run_dir / "semantic.json")
    result["codeGenerationAttribution"] = {
        "snapshot": "pre_hidden_candidate",
        "source": artifact(generated_path),
        "hiddenHarnessExcluded": True,
        "modelInvoked": False,
        "correctedReports": corrected,
    }
    finalize_metric_availability(result)
    dump(run_path, result)
    return result


def summarize(task_id: str, rows: list[dict[str, Any]], run_id: str) -> None:
    for row in rows:
        finalize_metric_availability(row)
    code_rows = [row for row in rows if row["metricAvailability"]["codeGeneration"]]
    compile_rows = [row for row in rows if row["metricAvailability"]["compile"]]
    semantic_rows = [row for row in rows if row["metricAvailability"]["semanticTestcase"]]
    code_pass = sum(row["codeGeneration"]["passed"] is True for row in code_rows)
    compile_pass = sum(row["compile"]["passed"] is True for row in compile_rows)
    semantic_pass = sum(row["semanticTestcase"].get("passed", 0) for row in semantic_rows)
    semantic_scored = sum(row["semanticTestcase"].get("scored", 0) for row in semantic_rows)
    not_scored = sum(row["semanticTestcase"].get("notScored", 0) for row in semantic_rows)
    publication_rows = [row for row in rows if row["runIntegrity"]["validForPublication"]]
    payload = {
        "schemaVersion": 1,
        "runId": run_id,
        "taskId": task_id,
        "model": MODEL,
        "endpoint": ENDPOINT,
        "runs": rows,
        "benchmarkMetrics": {
            "codeGeneration": {"passed": code_pass, "total": len(code_rows),
                               "rate": round(code_pass / len(code_rows), 6) if code_rows else None},
            "compile": {"passed": compile_pass, "total": len(compile_rows),
                        "rate": round(compile_pass / len(compile_rows), 6) if compile_rows else None},
            "semanticTestcase": {"passed": semantic_pass, "scored": semantic_scored,
                                 "notScored": not_scored,
                                 "rate": round(semantic_pass / semantic_scored, 6) if semantic_scored else None},
        },
        "metricPolicy": "Code generation, application compile, and semantic testcase are independently available benchmark metrics. A false result is measured failure, not unavailability. Candidate-owned unit tests are permitted and are not production generation. Evaluator/probe injection into production is a code-generation violation. Adapter and transport are diagnostics. notScored is excluded from pass/fail.",
    }
    migration = MIGRATIONS / task_id
    dump(migration / "results/agent-evaluation-summary.json", payload)
    manifest = load(migration / "manifest.json")
    metrics_complete = all(row["benchmarkMetricsAvailable"] for row in rows)
    manifest["agentResult"] = (
        "completed" if len(publication_rows) == 2 else
        "completed_with_isolation_unverified" if metrics_complete else
        "partially_unavailable"
    )
    manifest["publication"] = {
        "calibrationReady": True,
        "benchmarkReady": len(publication_rows) == 2,
        "reason": "Both platform agent runs have all three metrics and verified isolation." if len(publication_rows) == 2
        else "All three metrics are measured; one or more runs lack verified isolation." if metrics_complete
        else "Measured metrics are retained independently; one or more runs lack a metric or verified isolation.",
    }
    manifest["agentEvaluation"] = {
        "runId": run_id,
        "summary": "results/agent-evaluation-summary.json",
        "timeoutSecondsPerRun": 3600,
        "modelId": MODEL,
        "apiKeyRecorded": False,
    }
    dump(migration / "manifest.json", manifest)
    results_manifest = load(migration / "results/manifest.json")
    results_manifest["status"] = "android_and_arkts_calibrated_and_agent_evaluated"
    reports = results_manifest.setdefault("reports", [])
    if not isinstance(reports, list):
        raise ValueError("results manifest reports must be a list")
    by_path = {row.get("path"): row for row in reports if isinstance(row, dict)}
    for platform in PLATFORMS:
        report = migration / "results" / f"{platform}-agent.json"
        raw = migration / "results" / f"{platform}-agent.raw.json"
        if report.is_file():
            by_path[f"results/{report.name}"] = {
                "path": f"results/{report.name}", "bytes": report.stat().st_size, "sha256": sha256(report),
            }
        if raw.is_file():
            by_path[f"results/{raw.name}"] = {
                "path": f"results/{raw.name}", "bytes": raw.stat().st_size, "sha256": sha256(raw),
            }
    summary_path = migration / "results/agent-evaluation-summary.json"
    by_path["results/agent-evaluation-summary.json"] = {
        "path": "results/agent-evaluation-summary.json",
        "bytes": summary_path.stat().st_size,
        "sha256": sha256(summary_path),
    }
    results_manifest["reports"] = [by_path[path] for path in sorted(by_path)]
    results_manifest["agentEvaluation"] = "agent-evaluation-summary.json"
    results_manifest["policy"] = payload["metricPolicy"]
    dump(migration / "results/manifest.json", results_manifest)
    evidence_path = migration / "provenance/evidence-index.json"
    evidence = load(evidence_path)
    evidence["reports"] = results_manifest["reports"]
    evidence["agentEvaluation"] = by_path["results/agent-evaluation-summary.json"]
    evidence["agentRunId"] = run_id
    dump(evidence_path, evidence)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", default=f"wikipedia_03_04_minimax_m3_{datetime.now():%Y%m%d_%H%M%S}")
    parser.add_argument("--timeout", type=int, default=3600)
    parser.add_argument("--parallel", type=int, default=2)
    parser.add_argument("--candidate-root", type=Path)
    parser.add_argument("--task", action="append", choices=TASK_IDS)
    parser.add_argument("--platform", action="append", choices=PLATFORMS)
    parser.add_argument("--repair-evaluation", action="store_true")
    parser.add_argument("--reaudit-isolation", action="store_true")
    parser.add_argument("--refresh-existing-reports", action="store_true")
    args = parser.parse_args()
    if args.timeout != 3600:
        raise ValueError("this benchmark round requires exactly 3600 seconds per top-level run")
    require_space(ROOT)
    candidate_root = (args.candidate_root or ROOT.parent / ".ltb-wikipedia-agent" / args.run_id).resolve()
    candidate_root.mkdir(parents=True, exist_ok=True)
    started_at = datetime.now().astimezone()
    selected_tasks = tuple(args.task or TASK_IDS)
    selected_platforms = tuple(args.platform or PLATFORMS)
    jobs = [(task, platform) for task in selected_tasks for platform in selected_platforms]
    if args.refresh_existing_reports:
        rows = [refresh_existing_report(task, platform, args.run_id) for task, platform in jobs]
        for task_id in selected_tasks:
            task_rows = sorted([row for row in rows if row["taskId"] == task_id],
                               key=lambda row: row["platform"])
            if set(selected_platforms) == set(PLATFORMS):
                summarize(task_id, task_rows, args.run_id)
        print(json.dumps({"runId": args.run_id, "refreshed": [
            {"taskId": row["taskId"], "platform": row["platform"],
             "codeGeneration": row["codeGeneration"]["passed"]} for row in rows
        ]}, ensure_ascii=False))
        return 0
    if args.reaudit_isolation:
        rows = []
        for task, platform in jobs:
            run_dir = MIGRATIONS / task / "results/agent-runs" / args.run_id / platform
            result = load(run_dir / "run.json")
            prior = load(run_dir / "isolation-audit.json")
            audit = audit_sessions(
                run_dir / "opencode.jsonl", Path(str(prior["candidate"])),
                result.get("publicBuildCommand", ["bash", "build-agent.sh"]),
                run_dir / "isolation-audit-final.json", time.monotonic() + 600,
            )
            result["isolationAudit"] = audit
            if audit["availability"] != "available":
                result["availability"] = audit["availability"]
            finalize_metric_availability(result)
            dump(run_dir / "run.json", result)
            rows.append(result)
        print(json.dumps({"runId": args.run_id, "reaudited": [
            {"taskId": row["taskId"], "platform": row["platform"],
             "isolation": row["isolationAudit"]["availability"]} for row in rows
        ]}, ensure_ascii=False))
        return 0 if all(row["isolationAudit"]["availability"] == "available" for row in rows) else 2
    if args.repair_evaluation:
        rows = [repair_evaluation(task, platform, args.run_id, candidate_root, args.timeout)
                for task, platform in jobs]
        for task_id in selected_tasks:
            dump(MIGRATIONS / task_id / "results/agent-runs" / args.run_id / "repair-summary.json", {
                "schemaVersion": 1, "runId": args.run_id, "modelInvoked": False,
                "runs": [row for row in rows if row["taskId"] == task_id],
            })
        if set(selected_tasks) == set(TASK_IDS) and set(selected_platforms) == set(PLATFORMS):
            for task_id in TASK_IDS:
                summarize(task_id, sorted([row for row in rows if row["taskId"] == task_id],
                                          key=lambda row: row["platform"]), args.run_id)
        shutil.rmtree(candidate_root, ignore_errors=True)
        print(json.dumps({"runId": args.run_id, "repaired": [
            {"taskId": row["taskId"], "platform": row["platform"], "availability": row["availability"]}
            for row in rows
        ]}, ensure_ascii=False))
        return 0 if all(row.get("benchmarkMetricsAvailable") for row in rows) else 2
    platform_locks = {platform: threading.Lock() for platform in PLATFORMS}

    def invoke(job: tuple[str, str]) -> dict[str, Any]:
        task_id, platform = job
        with platform_locks[platform]:
            return run_one(task_id, platform, args.run_id, candidate_root, args.timeout)

    rows: list[dict[str, Any]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.parallel) as executor:
        futures = {executor.submit(invoke, job): job for job in jobs}
        for future in concurrent.futures.as_completed(futures):
            rows.append(future.result())
    full_matrix = set(selected_tasks) == set(TASK_IDS) and set(selected_platforms) == set(PLATFORMS)
    if full_matrix:
        for task_id in TASK_IDS:
            summarize(task_id, sorted([row for row in rows if row["taskId"] == task_id],
                                      key=lambda row: row["platform"]), args.run_id)
    finished_at = datetime.now().astimezone()
    summary = {
        "runId": args.run_id,
        "startedAt": started_at.isoformat(timespec="seconds"),
        "finishedAt": finished_at.isoformat(timespec="seconds"),
        "elapsedSeconds": round((finished_at - started_at).total_seconds(), 3),
        "runs": sorted(rows, key=lambda row: (row["taskId"], row["platform"])),
    }
    for task_id in selected_tasks:
        dump(MIGRATIONS / task_id / "results/agent-runs" / args.run_id / "round-summary.json", summary)
    shutil.rmtree(candidate_root, ignore_errors=True)
    print(json.dumps({"runId": args.run_id, "runs": [
        {"taskId": row["taskId"], "platform": row["platform"], "availability": row["availability"]}
        for row in summary["runs"]
    ]}, ensure_ascii=False))
    return 0 if all(row.get("benchmarkMetricsAvailable") for row in rows) else 2


if __name__ == "__main__":
    raise SystemExit(main())
