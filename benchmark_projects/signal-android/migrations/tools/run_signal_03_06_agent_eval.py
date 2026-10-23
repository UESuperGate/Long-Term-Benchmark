#!/usr/bin/env python3
"""Run four isolated OpenCode + MiniMax-M3 evaluations for Signal 03/06."""

from __future__ import annotations

import argparse
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
import time
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[4]
PROJECT = ROOT / "benchmark_projects/signal-android"
MIGRATIONS = PROJECT / "migrations"
TASKS = PROJECT / "tasks"
TOOLS = MIGRATIONS / "tools"
TASK_IDS = ("03_media_editor", "06_numberless_registration")
PLATFORMS = ("android", "arkts")
MODEL = "minimax-token-plan/MiniMax-M3"
ENDPOINT = "https://api.minimaxi.com/v1"
MIN_FREE_BYTES = 8 * 1024**3
MODEL_MAX_SECONDS = 3000
ANDROID_BUILD_LOCK = "/tmp/long-term-benchmark-android-full-build.lock"
ANDROID_DEVICE_LOCK = "/tmp/long-term-benchmark-android-device.lock"
ARKTS_BUILD_LOCK = "/tmp/long-term-benchmark-full-build.lock"
HVIGOR = Path("/Applications/DevEco-Studio.app/Contents/tools/hvigor/bin/hvigorw")
JAVA_HOME = Path("/Applications/DevEco-Studio.app/Contents/jbr/Contents/Home")
ANDROID_SDK = Path.home() / "Library/Android/sdk"
OH_SDK = Path.home() / "Library/OpenHarmony/Sdk/23"
HDC = OH_SDK / "toolchains/hdc"


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


def environment(candidate: Path, hdc_target: str | None = None) -> dict[str, str]:
    env = os.environ.copy()
    env.update({
        "PWD": str(candidate),
        "OLDPWD": str(candidate),
        "JAVA_HOME": str(JAVA_HOME),
        "ANDROID_HOME": str(ANDROID_SDK),
        "ANDROID_SDK_ROOT": str(ANDROID_SDK),
        "OHOS_BASE_SDK_HOME": str(OH_SDK.parent),
        "DEVECO_SDK_HOME": str(OH_SDK),
        "HDC": str(HDC),
    })
    if hdc_target:
        env["HDC_TARGET"] = hdc_target
    env["PATH"] = os.pathsep.join([
        str(JAVA_HOME / "bin"), str(ANDROID_SDK / "platform-tools"), str(HVIGOR.parent),
        "/Applications/DevEco-Studio.app/Contents/tools/ohpm/bin", env.get("PATH", ""),
    ])
    return env


def terminate(process: subprocess.Popen[Any]) -> None:
    if process.poll() is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
        process.wait(timeout=15)
    except (ProcessLookupError, subprocess.TimeoutExpired):
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait()


def run_logged(command: list[str], cwd: Path, log: Path, timeout: float,
               env: dict[str, str] | None = None, protect_space: bool = False) -> int:
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


def copy_candidate(source: Path, destination: Path) -> None:
    if destination.exists():
        shutil.rmtree(destination)

    def ignored(_: str, names: list[str]) -> set[str]:
        return set(names) & {".git", ".gradle", ".hvigor", "build", "oh_modules", "node_modules", "__pycache__"}

    shutil.copytree(source, destination, ignore=ignored)


def public_transitions(contract: dict[str, Any]) -> dict[str, Any]:
    return {
        "schemaVersion": 1,
        "taskId": contract["taskId"],
        "description": "Public scenarios only; expected observations and evaluator bindings remain hidden.",
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
    edits = dict(paths)
    protected = ("_benchmark_inputs", "_benchmark_scaffold")
    for directory in protected:
        for pattern in (f"{directory}/*", f"{directory}/**", f"{root}/{directory}/*", f"{root}/{directory}/**"):
            edits[pattern] = "deny"
    for name in ("build-agent.sh", "opencode.json"):
        edits[name] = "deny"
        edits[f"{root}/{name}"] = "deny"
    for name in ("IMMUTABLE_SOURCES.json", "SOURCE_MANIFEST.json", "tools/build.sh"):
        edits[name] = "deny"
        edits[f"{root}/{name}"] = "deny"
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
        "agent": {"explore": {"steps": 20, "prompt": (
            "Explore only this candidate directory. Never access parent, sibling, home, network, "
            "final, benchmark, evaluator, report, or hidden paths."
        )}},
        "permission": {
            "*": "deny", "read": paths, "edit": edits, "glob": paths, "grep": "allow",
            "list": paths, "task": "allow", "webfetch": "deny", "websearch": "deny",
            "external_directory": "deny", "shell": shell, "bash": shell,
        },
    }


def write_build_scaffold(candidate: Path, platform: str) -> list[str]:
    scaffold = candidate / "_benchmark_scaffold"
    scaffold.mkdir()
    shutil.copy2(TOOLS / "with_device_lock.py", scaffold / "with_device_lock.py")
    if platform == "android":
        shutil.copy2(TOOLS / "compile_kotlin_slice.sh", scaffold / "compile_kotlin_slice.sh")
        (scaffold / "evaluator-src").mkdir()
        body = f"""#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")" && pwd)"
export EVALUATOR_SRC="$root/_benchmark_scaffold/evaluator-src"
export COMPILE_KOTLIN_SLICE="$root/_benchmark_scaffold/compile_kotlin_slice.sh"
python3 "$root/_benchmark_scaffold/with_device_lock.py" --lock {ANDROID_BUILD_LOCK} -- \\
  bash "$root/tools/build.sh" "$root" "$root/build/public"
"""
    else:
        body = f"""#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")" && pwd)"
python3 "$root/_benchmark_scaffold/with_device_lock.py" --lock {ARKTS_BUILD_LOCK} -- \\
  "{HVIGOR}" --no-daemon --mode module -p module=entry@default assembleHap
"""
    build = candidate / "build-agent.sh"
    build.write_text(body, encoding="utf-8")
    build.chmod(0o755)
    return ["bash", "build-agent.sh"]


def prepare_candidate(task_id: str, platform: str, candidate: Path) -> tuple[list[str], str]:
    migration = MIGRATIONS / task_id
    copy_candidate(migration / platform / "base", candidate)
    build_command = write_build_scaffold(candidate, platform)
    inputs = candidate / "_benchmark_inputs"
    inputs.mkdir()
    shutil.copy2(TASKS / task_id / "requirement.md", inputs / "requirement.md")
    dump(inputs / "public_transitions.json", public_transitions(load(migration / "canonical/transitions.json")))
    platform_note = (
        "Production sources are under immutable-src; src/main/AndroidManifest.xml and stubs are visible build support."
        if platform == "android" else
        "The app entry is entry/src/main/ets/pages/Index.ets and production stores are under entry/src/main/ets/feature."
    )
    prompt = f"""Implement {task_id} completely in this {platform} candidate.

Read `_benchmark_inputs/requirement.md` and `_benchmark_inputs/public_transitions.json`. Inspect the visible base and implement the requested behavior in real production code. {platform_note}

Rules:
- Work only in this candidate directory. Never inspect parent, sibling, home, network, final, evaluator, report, or hidden paths.
- Subagents are allowed and inherit exactly the same workspace boundary.
- Do not create case-ID switches, marker facts, semantic projections, evaluator APIs, or source-observer shortcuts.
- Preserve unrelated behavior. Implement application-owned state, persistence, effects, UI/page wiring, failure recovery, and cleanup.
- Run `{shlex.join(build_command)}` exactly as written and repair production compilation within the task budget.

Finish with a concise summary of changed production files and remaining blockers.
"""
    (inputs / "prompt.md").write_text(prompt, encoding="utf-8")
    dump(candidate / "opencode.json", opencode_config(candidate, build_command))
    return build_command, prompt


def cleanup_builds(project: Path, receipt: Path) -> None:
    removable: list[Path] = []
    binaries: list[dict[str, Any]] = []
    names = {"build", ".gradle", ".hvigor", ".cxx", "oh_modules", "node_modules", "__pycache__", ".benchmark-tool-home"}
    for parent, directories, _ in os.walk(project):
        root = Path(parent)
        if root.name in names:
            removable.append(root)
            directories[:] = []
            for path in root.rglob("*"):
                if path.is_file() and path.suffix.lower() in {".apk", ".aab", ".hap", ".har", ".app", ".abc", ".so"}:
                    binaries.append({"path": str(path.relative_to(project)), "bytes": path.stat().st_size, "sha256": sha256(path)})
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


def tree_snapshot(candidate: Path, output: Path) -> dict[str, Any]:
    rows = []
    for path in sorted(candidate.rglob("*")):
        if ".git" in path.parts:
            continue
        relative = path.relative_to(candidate).as_posix()
        info = path.lstat()
        row: dict[str, Any] = {"path": relative, "mode": stat.S_IMODE(info.st_mode)}
        if path.is_symlink():
            row.update(type="symlink", target=os.readlink(path))
        elif path.is_file():
            row.update(type="file", bytes=info.st_size, sha256=sha256(path))
        else:
            row.update(type="directory")
        rows.append(row)
    dump(output, {"schemaVersion": 1, "root": str(candidate), "entries": rows})
    return artifact(output)


def initialize_baseline(candidate: Path, run_dir: Path) -> tuple[str, dict[str, Any], dict[str, dict[str, Any]]]:
    subprocess.run(["git", "init", "-q"], cwd=candidate, check=True)
    subprocess.run(["git", "add", "-A"], cwd=candidate, check=True)
    subprocess.run([
        "git", "-c", "user.name=Benchmark Runner", "-c", "user.email=benchmark@localhost",
        "commit", "-q", "-m", "clean-room base",
    ], cwd=candidate, check=True)
    baseline = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=candidate, text=True).strip()
    inputs = run_dir / "inputs"
    raw = tree_snapshot(candidate, inputs / "raw-tree.json")
    archive_path = inputs / "baseline.tar.gz"
    subprocess.run(["git", "archive", "--format=tar.gz", "--output", str(archive_path), baseline], cwd=candidate, check=True)
    shutil.copytree(candidate / "_benchmark_inputs", inputs / "public", dirs_exist_ok=True)
    protected_paths = [candidate / "build-agent.sh", candidate / "opencode.json"]
    protected_paths.extend(path for path in (
        candidate / "IMMUTABLE_SOURCES.json",
        candidate / "SOURCE_MANIFEST.json",
        candidate / "tools/build.sh",
    ) if path.is_file())
    protected_paths.extend(path for root in (candidate / "_benchmark_inputs", candidate / "_benchmark_scaffold") for path in root.rglob("*") if path.is_file())
    protected = {str(path.relative_to(candidate)): artifact(path) | {"mode": stat.S_IMODE(path.stat().st_mode)} for path in protected_paths}
    return baseline, {
        "rawTree": raw,
        "archive": {**artifact(archive_path), "commit": baseline, "capturePhase": "after_preflight_cleanup_before_agent"},
        "publicInputs": [artifact(path) for path in sorted((inputs / "public").rglob("*")) if path.is_file()],
    }, protected


def verify_protected(candidate: Path, expected: dict[str, dict[str, Any]]) -> dict[str, Any]:
    changed = []
    for relative, record in expected.items():
        path = candidate / relative
        if not path.is_file() or sha256(path) != record["sha256"] or path.stat().st_size != record["bytes"] or stat.S_IMODE(path.stat().st_mode) != record["mode"]:
            changed.append(relative)
    return {"passed": not changed, "protectedCount": len(expected), "changedOrMissing": changed}


def changed_paths(candidate: Path) -> list[str]:
    changed = subprocess.check_output(["git", "diff", "HEAD", "--name-only", "--no-renames", "-z"], cwd=candidate)
    untracked = subprocess.check_output(["git", "ls-files", "--others", "--exclude-standard", "-z"], cwd=candidate)
    return sorted({os.fsdecode(path) for path in (changed + untracked).split(b"\0") if path})


def production_files(paths: list[str], platform: str) -> list[str]:
    suffixes = {".kt", ".java", ".xml", ".kts"} if platform == "android" else {".ets", ".ts", ".json5"}
    excluded = {"build", ".gradle", ".hvigor", "oh_modules", "node_modules", "_benchmark_inputs", "_benchmark_scaffold"}
    return [path for path in paths if Path(path).suffix.lower() in suffixes and not (set(Path(path).parts) & excluded) and path != "opencode.json"]


def generation_audit(candidate: Path, generated: list[str]) -> dict[str, Any]:
    issues: list[str] = []
    forbidden_parts = {"probe", "probes", "evaluator", "test", "tests", "androidtest", "fixture", "fixtures"}
    for relative in generated:
        path = Path(relative)
        if {part.lower() for part in path.parts} & forbidden_parts or "probe" in path.stem.lower():
            issues.append(f"evaluator-like generated path: {relative}")
            continue
        full = candidate / path
        if full.is_file():
            content = full.read_text(encoding="utf-8", errors="ignore")
            for marker in ("traceDigest", "LTB_RUNTIME", "SemanticProbe", "BENCHMARK_CASE"):
                if marker in content:
                    issues.append(f"forbidden evaluator marker {marker} in {relative}")
    return {
        "passed": bool(generated) and not issues,
        "changedProductionFiles": generated,
        "sourceArtifacts": [artifact(candidate / path) for path in generated if (candidate / path).is_file()],
        "issues": issues,
    }


def archive_patch(candidate: Path, output: Path, baseline: str) -> dict[str, Any]:
    subprocess.run(["git", "add", "-N", "--", "."], cwd=candidate, check=True)
    patch = subprocess.check_output(["git", "diff", "--binary", "--full-index", "--no-renames", baseline, "--"], cwd=candidate)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(patch)
    with tempfile.TemporaryDirectory(prefix="signal-agent-replay-") as temporary:
        temporary_path = Path(temporary)
        replay_env = {**os.environ, "GIT_INDEX_FILE": str(temporary_path / "replay-index")}
        subprocess.run(["git", "read-tree", baseline], cwd=candidate, env=replay_env, check=True)
        if patch:
            subprocess.run(["git", "apply", "--cached", "--binary", "--whitespace=nowarn", "-"], cwd=candidate, env=replay_env, input=patch, check=True)
        replay_tree = subprocess.check_output(["git", "write-tree"], cwd=candidate, env=replay_env, text=True).strip()
        actual_env = {**os.environ, "GIT_INDEX_FILE": str(temporary_path / "actual-index")}
        subprocess.run(["git", "read-tree", baseline], cwd=candidate, env=actual_env, check=True)
        subprocess.run(["git", "add", "-A", "--", "."], cwd=candidate, env=actual_env, check=True)
        actual_tree = subprocess.check_output(["git", "write-tree"], cwd=candidate, env=actual_env, text=True).strip()
    if replay_tree != actual_tree:
        raise RuntimeError("binary patch does not reconstruct the scored candidate tree")
    return {**artifact(output), "baselineCommit": baseline, "tree": replay_tree, "reconstructionVerified": True}


def root_session_id(log: Path) -> str:
    first = None
    ids: set[str] = set()
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


def audit_sessions(log: Path, candidate: Path, build: list[str], output: Path, deadline: float) -> dict[str, Any]:
    helper = ROOT / "scripts/opencode_subagent_audit.py"
    spec = importlib.util.spec_from_file_location("signal_opencode_audit", helper)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load recursive OpenCode audit helper")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    root_id = root_session_id(log)
    inventory = module.read_db_session_inventory(Path.home() / ".local/share/opencode/opencode.db", root_id, deadline=deadline)
    by_parent: dict[str | None, list[str]] = {}
    for session in inventory["sessions"]:
        by_parent.setdefault(session["parentID"], []).append(session["sessionID"])
    archive_dir = output.parent / "sessions"
    loader = module.CliExportLoader(archive_dir, output.stem, deadline=deadline)
    allowed = [command for command, decision in opencode_config(candidate, build)["permission"]["shell"].items() if decision == "allow"]
    audit = module.audit_sessions(
        root_id, candidate, loader, allowed_shell_commands=allowed,
        discover_children=lambda sid: by_parent.get(sid, []), deadline=deadline,
    )
    inventory_path = archive_dir / f"{output.stem}_session-inventory.json"
    dump(inventory_path, inventory)
    completed = {(row.get("sessionID"), row.get("callID")) for row in audit.get("records", []) if row.get("status") == "completed"}
    escaped = any(
        violation.get("code") in {"outside_candidate_path", "network_tool_access"}
        and violation.get("callID") is not None
        and (violation.get("sessionID"), violation.get("callID")) in completed
        for violation in audit.get("violations", [])
    )
    availability = (
        "isolation_violation" if escaped else
        "available" if audit.get("complete") is True and audit.get("valid") is True and not audit.get("violations") else
        "isolation_unverified"
    )
    audit.update({
        "schema": "opencode_recursive_isolation_v1", "candidate": str(candidate.resolve()),
        "rootSessionID": root_id, "allowedShellCommands": sorted(allowed),
        "reviewedHelper": artifact(helper), "inventory": artifact(inventory_path),
        "sessionExports": {sid: artifact(path) for sid, path in loader.paths.items()},
        "timingScope": "Top-level run only; subagent timestamps are forensic and are not summed.",
        "availability": availability,
    })
    dump(output, audit)
    return {"availability": availability, **artifact(output)}


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
        status = detail.get("statusCode", detail.get("status", error.get("status") if isinstance(error, dict) else None))
        kind = str(error.get("type", error.get("name", ""))) if isinstance(error, dict) else ""
        if kind == "provider.quota" or status in (402, 429):
            return "provider_quota"
        if kind in {"provider.auth", "provider.authentication"} or status in (401, 403):
            return "provider_auth"
        if kind.startswith("provider.") or status is not None:
            return "provider_transport"
        return "agent_runtime_error"
    return None


def redact_secret_artifacts(root: Path) -> dict[str, Any]:
    secret_path = Path.home() / ".config/opencode/secrets/minimax-m3-key"
    secret = secret_path.read_bytes().strip() if secret_path.is_file() else b""
    hits: list[str] = []
    if secret:
        for path in root.rglob("*"):
            if not path.is_file() or path.stat().st_size > 50 * 1024 * 1024:
                continue
            data = path.read_bytes()
            if secret in data:
                path.write_bytes(data.replace(secret, b"[REDACTED_MINIMAX_KEY]"))
                hits.append(str(path.relative_to(root)))
    return {"apiKeyRecorded": False, "redactedArtifactCount": len(hits), "redactedArtifacts": hits}


def source_manifest(task_id: str, platform: str, candidate: Path, output: Path) -> dict[str, Any]:
    if platform == "android":
        root = candidate / "immutable-src"
        suffixes = {".kt", ".java"}
        original = load(candidate / "IMMUTABLE_SOURCES.json")
        payload = {
            "schemaVersion": 2,
            "sourceCommit": original.get("sourceCommit"),
            "classification": "agent_candidate_production_bytes",
            "files": [],
        }
    else:
        root = candidate / "entry/src/main/ets"
        suffixes = {".ets", ".ts"}
        app = load(candidate / "AppScope/app.json5")
        payload = {
            "schemaVersion": 1,
            "platform": "arkts",
            "bundleName": app["app"]["bundleName"],
            "apiVersion": 23,
            "sourceObserver": False,
            "classification": "agent_candidate_production_bytes",
            "files": [],
        }
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.suffix.lower() in suffixes and ".benchmark-evaluator" not in path.parts:
            relative = path.relative_to(root) if platform == "android" else path.relative_to(candidate)
            payload["files"].append({"path": relative.as_posix(), "gitBlob": None, "sha256": sha256(path), "bytes": path.stat().st_size} if platform == "android" else {"path": relative.as_posix(), "sha256": sha256(path), "bytes": path.stat().st_size})
    dump(output, payload)
    return artifact(output)


def semantic_metrics(report: dict[str, Any]) -> dict[str, Any]:
    semantic = report.get("semantic", {})
    summary = semantic.get("summary", semantic)
    passed = int(summary.get("passed", 0))
    failed = int(summary.get("failed", 0))
    not_scored = int(summary.get("notScored", 0))
    scored = passed + failed
    return {
        "passed": passed, "failed": failed, "notScored": not_scored, "scored": scored,
        "total": int(summary.get("total", passed + failed + not_scored)),
        "rate": round(passed / scored, 6) if scored else None,
        "policy": "notScored is excluded from both pass and fail",
    }


def not_scored_report(task_id: str, platform: str, diagnostic: str) -> dict[str, Any]:
    contract = load(MIGRATIONS / task_id / "canonical/transitions.json")
    cases = [{
        "caseId": case["caseId"], "key": case.get("key"), "traceDigest": case["traceDigest"],
        "status": "not_scored", "observed": None, "effects": [], "invariantChecks": [],
        "productionBodies": [], "checkpoints": [], "diagnostic": diagnostic,
    } for case in contract["cases"]]
    return {
        "schemaVersion": 1, "taskId": task_id, "platform": platform, "role": "agent",
        "observationMode": "runtime_state_transition",
        "semantic": {"cases": cases, "passed": 0, "failed": 0, "notScored": len(cases), "total": len(cases)},
        "diagnostics": {"adapter": "unavailable", "transport": "not_attempted", "reason": diagnostic},
    }


def lock_command(lock: str, command: list[str]) -> list[str]:
    return ["python3", str(TOOLS / "with_device_lock.py"), "--lock", lock, "--", *command]


def hidden_evaluation(task_id: str, platform: str, candidate: Path, run_dir: Path,
                      source_manifest_path: Path, runtime_id: str, deadline: float,
                      hdc_target: str) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    migration = MIGRATIONS / task_id
    if platform == "android":
        build = lock_command(ANDROID_BUILD_LOCK, ["bash", str(TOOLS / "build_android_focused_candidate.sh"), str(candidate), str(migration)])
        run = lock_command(ANDROID_DEVICE_LOCK, [
            "node", str(TOOLS / "run_android_focused_candidate.mjs"), "--project", str(candidate),
            "--migration", str(migration), "--role", "agent", "--run-id", runtime_id,
            "--output", str(run_dir / "semantic.json"), "--source-manifest", str(source_manifest_path),
        ])
        env = environment(candidate)
    else:
        device_hash = hashlib.sha256(hdc_target.encode()).hexdigest()[:16]
        build = lock_command(ARKTS_BUILD_LOCK, ["bash", str(TOOLS / "build_arkts_focused_candidate.sh"), str(candidate), str(migration), str(source_manifest_path)])
        run = lock_command(f"/tmp/ltb-arkts-device-{device_hash}", [
            "node", str(TOOLS / "run_arkts_focused_candidate.mjs"), "--project", str(candidate),
            "--migration", str(migration), "--role", "agent", "--run-id", runtime_id,
            "--output", str(run_dir / "semantic.json"), "--source-manifest", str(source_manifest_path),
        ])
        env = environment(candidate, hdc_target)
    build_exit = run_logged(build, candidate, run_dir / "runtime-build.log", remaining(deadline, "runtime_compile"), env, True)
    diagnostics: dict[str, Any] = {
        "runtimeCompileExit": build_exit,
        "runtimeCompileCommand": build,
        "classification": "adapter/transport diagnostic, excluded from compile metric",
    }
    if build_exit:
        return None, diagnostics
    semantic_exit = run_logged(run, candidate, run_dir / "runtime-semantic.log", remaining(deadline, "native_runtime"), env)
    diagnostics.update(semanticExit=semantic_exit, semanticCommand=run)
    report = run_dir / "semantic.json"
    return (load(report), diagnostics) if report.is_file() else (None, diagnostics)


def hdc_target() -> str:
    result = subprocess.run([str(HDC), "list", "targets"], text=True, capture_output=True, check=True)
    target = next((line.strip() for line in result.stdout.splitlines() if line.strip()), "")
    if not target:
        raise RuntimeError("no OpenHarmony API23 target")
    return target


def preflight(task_id: str, platform: str, candidate: Path, run_dir: Path) -> tuple[list[str], str, dict[str, Any], dict[str, dict[str, Any]]]:
    require_space(candidate.parent)
    build, _ = prepare_candidate(task_id, platform, candidate)
    code = run_logged(build, candidate, run_dir / "preflight-build.log", 1200, environment(candidate), True)
    if code:
        raise RuntimeError(f"clean base public build failed with exit {code}")
    cleanup_builds(candidate, run_dir / "preflight-artifacts.json")
    baseline, evidence, protected = initialize_baseline(candidate, run_dir)
    return build, baseline, evidence, protected


def remove_stale_agent_outputs(migration: Path, platform: str) -> None:
    for path in (
        migration / "results" / f"{platform}-agent.json",
        migration / "results/agent-patches" / f"{platform}-agent.patch",
        migration / "results/agent-patches" / f"{platform}-agent-generated-files.json",
    ):
        path.unlink(missing_ok=True)


def run_one(task_id: str, platform: str, run_id: str, candidate_root: Path,
            timeout: int, target: str) -> dict[str, Any]:
    migration = MIGRATIONS / task_id
    run_dir = migration / "results/agent-runs" / run_id / platform
    run_dir.mkdir(parents=True, exist_ok=True)
    candidate = candidate_root / task_id / platform
    result: dict[str, Any] = {
        "schemaVersion": 1, "runId": run_id, "taskId": task_id, "platform": platform,
        "runner": "OpenCode", "model": MODEL, "endpoint": ENDPOINT,
        "overallTimeoutSeconds": timeout, "subagentsAllowed": True,
        "semanticFeedbackDuringGeneration": False, "apiKeyRecorded": False,
        "availability": "environment_failure", "benchmarkMetricsAvailable": False,
    }
    started: float | None = None
    try:
        remove_stale_agent_outputs(migration, platform)
        build, baseline, evidence, protected = preflight(task_id, platform, candidate, run_dir)
        result.update(candidateBaseline=evidence, publicBuildCommand=build,
                      opencodeVersion=subprocess.check_output(["opencode", "--version"], text=True).strip())
        started = time.monotonic()
        deadline = started + timeout
        result["startedAt"] = datetime.now().astimezone().isoformat(timespec="seconds")
        prompt = (candidate / "_benchmark_inputs/prompt.md").read_text(encoding="utf-8")
        log = run_dir / "opencode.jsonl"
        allowance = min(MODEL_MAX_SECONDS, remaining(deadline, "agent"))
        result["agentGrantedSeconds"] = allowance
        command = [
            "opencode", "run", "--standalone", "--model", MODEL, "--format", "json",
            "--title", f"Signal {task_id} {platform}", prompt,
        ]
        result["agentCommand"] = [*command[:-1], "@_benchmark_inputs/prompt.md"]
        try:
            agent_exit = run_logged(command, candidate, log, allowance, environment(candidate, target), True)
            timed_out = False
        except subprocess.TimeoutExpired:
            agent_exit, timed_out = 124, True
        result.update(agentExit=agent_exit, agentTimedOut=timed_out)
        cleanup_builds(candidate, run_dir / "agent-build-artifacts.json")
        protected_audit = verify_protected(candidate, protected)
        result["protectedInputAudit"] = protected_audit
        paths = changed_paths(candidate)
        generated = production_files(paths, platform)
        generation = generation_audit(candidate, generated)
        patch = archive_patch(candidate, run_dir / "agent.patch", baseline)
        dump(run_dir / "generated-files.json", {
            "schemaVersion": 1, "changedFiles": paths, "generatedProductionFiles": generated, "audit": generation,
        })
        result.update(candidatePatch=patch, codeGeneration=generation)
        external = provider_failure(log)
        if external:
            result.update(availability=external, externalFailure=True)
            return result
        if timed_out:
            result.update(availability="model_timeout", externalFailure=False)
            return result
        if not protected_audit["passed"]:
            result.update(availability="protected_input_integrity_failure", externalFailure=False)
            return result
        isolation = audit_sessions(log, candidate, build, run_dir / "isolation-audit.json", deadline)
        result["isolationAudit"] = isolation
        if isolation["availability"] != "available":
            result["availability"] = isolation["availability"]
            return result
        compile_exit = run_logged(build, candidate, run_dir / "production-build.log", remaining(deadline, "production_build"), environment(candidate, target), True)
        result["compile"] = {"passed": compile_exit == 0, "exitCode": compile_exit, "command": build, "scope": "standalone candidate application production compile"}
        cleanup_builds(candidate, run_dir / "production-build-artifacts.json")
        source_manifest_path = run_dir / "candidate-source-manifest.json"
        result["candidateSourceManifest"] = source_manifest(task_id, platform, candidate, source_manifest_path)
        runtime_id = re.sub(r"[^a-z0-9-]", "-", f"{run_id}-{task_id}-{platform}").strip("-").lower()
        report, diagnostics = hidden_evaluation(task_id, platform, candidate, run_dir, source_manifest_path, runtime_id, deadline, target)
        result["diagnostics"] = diagnostics
        if report is None:
            report = not_scored_report(task_id, platform, "hidden runtime adapter did not compile, bind, or execute")
        metrics = semantic_metrics(report)
        report["codeGeneration"] = generation
        report["compile"] = result["compile"]
        report.setdefault("diagnostics", {})["runtimeCompile"] = diagnostics
        dump(run_dir / "semantic.json", report)
        result.update(
            availability="available", benchmarkMetricsAvailable=True, semanticTestcase=metrics,
            semanticReport=artifact(run_dir / "semantic.json"),
        )
        shutil.copy2(run_dir / "semantic.json", migration / "results" / f"{platform}-agent.json")
        patches = migration / "results/agent-patches"
        patches.mkdir(parents=True, exist_ok=True)
        shutil.copy2(run_dir / "agent.patch", patches / f"{platform}-agent.patch")
        shutil.copy2(run_dir / "generated-files.json", patches / f"{platform}-agent-generated-files.json")
        return result
    except TimeoutError as error:
        result.update(availability="overall_timeout", reason=str(error), benchmarkMetricsAvailable=False)
        return result
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        result.update(
            availability="environment_failure" if started is None else "evaluation_failure",
            reason=f"{type(error).__name__}: {error}", benchmarkMetricsAvailable=False,
        )
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
                timingScope="Top-level run from OpenCode invocation through audit, build, native runtime scoring, and cleanup; subagent durations are not added.",
            )
        result["cleanup"] = {"completed": not candidate.exists(), "error": cleanup_error}
        result["credentialAudit"] = redact_secret_artifacts(run_dir)
        dump(run_dir / "run.json", result)


def summarize(task_id: str, rows: list[dict[str, Any]], run_id: str) -> None:
    available = [row for row in rows if row.get("benchmarkMetricsAvailable")]
    code_pass = sum(row.get("codeGeneration", {}).get("passed") is True for row in available)
    compile_pass = sum(row.get("compile", {}).get("passed") is True for row in available)
    semantic_pass = sum(row.get("semanticTestcase", {}).get("passed", 0) for row in available)
    semantic_scored = sum(row.get("semanticTestcase", {}).get("scored", 0) for row in available)
    not_scored = sum(row.get("semanticTestcase", {}).get("notScored", 0) for row in available)
    policy = "Only code generation, standalone application compile, and semantic testcase pass rate are benchmark metrics. Adapter and transport are diagnostics. notScored is excluded from pass/fail."
    payload = {
        "schemaVersion": 1, "runId": run_id, "taskId": task_id, "model": MODEL, "endpoint": ENDPOINT,
        "runs": rows,
        "benchmarkMetrics": {
            "codeGeneration": {"passed": code_pass, "total": len(available), "rate": round(code_pass / len(available), 6) if available else None},
            "compile": {"passed": compile_pass, "total": len(available), "rate": round(compile_pass / len(available), 6) if available else None},
            "semanticTestcase": {"passed": semantic_pass, "scored": semantic_scored, "notScored": not_scored, "rate": round(semantic_pass / semantic_scored, 6) if semantic_scored else None},
        },
        "metricPolicy": policy,
    }
    migration = MIGRATIONS / task_id
    dump(migration / "results/agent-evaluation-summary.json", payload)
    manifest = load(migration / "manifest.json")
    manifest["agentResult"] = "completed" if len(available) == 2 else "partially_unavailable"
    manifest["agentEvaluation"] = {
        "runId": run_id, "summary": "results/agent-evaluation-summary.json",
        "timeoutSecondsPerRun": 3600, "modelId": MODEL, "apiKeyRecorded": False,
    }
    dump(migration / "manifest.json", manifest)
    results_manifest = load(migration / "results/manifest.json")
    results_manifest["status"] = "android_and_arkts_calibrated_and_agent_evaluated" if len(available) == 2 else "agent_evaluation_partially_unavailable"
    results_manifest.setdefault("reports", {})["androidAgent"] = "android-agent.json"
    results_manifest.setdefault("reports", {})["arktsAgent"] = "arkts-agent.json"
    results_manifest["agentEvaluation"] = "agent-evaluation-summary.json"
    results_manifest["policy"] = policy
    dump(migration / "results/manifest.json", results_manifest)


def verify_binary_free() -> dict[str, Any]:
    suffixes = {".apk", ".aab", ".hap", ".har", ".app", ".abc", ".so"}
    retained = []
    for task_id in TASK_IDS:
        root = MIGRATIONS / task_id
        retained.extend(str(path.relative_to(root)) for path in root.rglob("*") if path.is_file() and path.suffix.lower() in suffixes)
    return {"passed": not retained, "retainedBinaryPaths": sorted(retained)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", default=f"signal-03-06-minimax-m3-{datetime.now():%Y%m%d-%H%M%S}")
    parser.add_argument("--timeout", type=int, default=3600)
    parser.add_argument("--candidate-root", type=Path)
    args = parser.parse_args()
    if args.timeout != 3600:
        raise ValueError("this benchmark round requires exactly 3600 seconds per top-level run")
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", args.run_id):
        raise ValueError("run id must contain lowercase letters, digits, and hyphens only")
    require_space(ROOT)
    target = hdc_target()
    candidate_root = (args.candidate_root or ROOT.parent / ".ltb-signal-agent" / args.run_id).resolve()
    candidate_root.mkdir(parents=True, exist_ok=True)
    round_started = datetime.now().astimezone()
    rows: list[dict[str, Any]] = []
    for task_id in TASK_IDS:
        for platform in PLATFORMS:
            print(json.dumps({"event": "run_start", "taskId": task_id, "platform": platform}), flush=True)
            row = run_one(task_id, platform, args.run_id, candidate_root, args.timeout, target)
            rows.append(row)
            print(json.dumps({
                "event": "run_complete", "taskId": task_id, "platform": platform,
                "availability": row["availability"], "semantic": row.get("semanticTestcase"),
            }), flush=True)
    for task_id in TASK_IDS:
        summarize(task_id, [row for row in rows if row["taskId"] == task_id], args.run_id)
    round_finished = datetime.now().astimezone()
    binary_audit = verify_binary_free()
    summary = {
        "runId": args.run_id, "startedAt": round_started.isoformat(timespec="seconds"),
        "finishedAt": round_finished.isoformat(timespec="seconds"),
        "elapsedSeconds": round((round_finished - round_started).total_seconds(), 3),
        "runtime": {"android": "API37 ART", "arkts": "OpenHarmony API23 ArkVM", "hdcTarget": target},
        "binaryFreeRetainedEvidence": binary_audit,
        "runs": rows,
    }
    for task_id in TASK_IDS:
        dump(MIGRATIONS / task_id / "results/agent-runs" / args.run_id / "round-summary.json", summary)
    shutil.rmtree(candidate_root, ignore_errors=True)
    print(json.dumps({"runId": args.run_id, "binaryFree": binary_audit["passed"], "runs": [
        {"taskId": row["taskId"], "platform": row["platform"], "availability": row["availability"]}
        for row in rows
    ]}, ensure_ascii=False))
    return 0 if all(row.get("benchmarkMetricsAvailable") for row in rows) and binary_audit["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
