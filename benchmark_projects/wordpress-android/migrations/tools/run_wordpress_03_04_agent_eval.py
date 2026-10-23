#!/usr/bin/env python3
"""Run four isolated OpenCode + MiniMax-M3 evaluations for WordPress 03/04."""

from __future__ import annotations

import argparse
import base64
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
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[4]
PROJECT = ROOT / "benchmark_projects/wordpress-android"
MIGRATIONS = PROJECT / "migrations"
TASKS = PROJECT / "tasks"
TOOLS = MIGRATIONS / "tools"
TASK_IDS = ("03_site_picker", "04_new_stats")
PLATFORMS = ("android", "arkts")
MODEL = "minimax-token-plan/MiniMax-M3"
ENDPOINT = "https://api.minimaxi.com/v1"
MIN_FREE_BYTES = 8 * 1024**3
ANDROID_BUILD_LOCK = Path("/tmp/long-term-benchmark-android-full-build.lock")
GRADLE = Path.home() / ".gradle/wrapper/dists/gradle-8.14.3-bin/cv11ve7ro1n3o1j4so8xd9n66/gradle-8.14.3/bin/gradle"
HVIGOR = Path("/Applications/DevEco-Studio.app/Contents/tools/hvigor/bin/hvigorw")
JAVA_HOME = Path("/Applications/DevEco-Studio.app/Contents/jbr/Contents/Home")
ANDROID_SDK = Path.home() / "Library/Android/sdk"
OH_SDK = Path.home() / "Library/OpenHarmony/Sdk/23"
MODEL_MAX_SECONDS = 3000


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
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


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
        "OHOS_BASE_SDK_HOME": str(OH_SDK.parent),
    })
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
    for pattern in ("_benchmark_inputs/*", "_benchmark_inputs/**", f"{root}/_benchmark_inputs/*", f"{root}/_benchmark_inputs/**"):
        edits[pattern] = "deny"
    for pattern in ("build-agent.sh", "opencode.json", f"{root}/build-agent.sh", f"{root}/opencode.json"):
        edits[pattern] = "deny"
    shell = {
        "*": "deny", "pwd": "allow", "ls": "allow", "git status --short": "allow",
        "git diff --stat": "allow", "git diff --name-only": "allow", shlex.join(build_command): "allow",
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


def normal_arkts_ability() -> str:
    return """import { AbilityConstant, UIAbility, Want } from '@kit.AbilityKit';
import { hilog } from '@kit.PerformanceAnalysisKit';
import { window } from '@kit.ArkUI';

export default class EntryAbility extends UIAbility {
  onCreate(want: Want, launchParam: AbilityConstant.LaunchParam): void {
    hilog.info(0x0000, 'WordPressBenchmark', 'Ability created');
  }

  onWindowStageCreate(windowStage: window.WindowStage): void {
    windowStage.loadContent('pages/Index');
  }
}
"""


def prepare_candidate(task_id: str, platform: str, candidate: Path, run_dir: Path,
                      public_api: str | None) -> tuple[list[str], str]:
    migration = MIGRATIONS / task_id
    source = migration / ("android/focused-runtime/base" if platform == "android" else "arkts/base")
    copy_candidate(source, candidate)
    if platform == "android":
        command = [
            "python3", str(TOOLS / "prepare_new_agent_candidate.py"), "--phase", "visible",
            "--task-id", task_id, "--project", str(candidate), "--migration", str(migration),
        ]
        if run_logged(command, migration, run_dir / "preflight-scaffold.log", 300, environment(candidate)):
            raise RuntimeError("visible Android scaffold preparation failed")
    else:
        shutil.rmtree(candidate / "entry/src/main/ets/evaluator", ignore_errors=True)
        (candidate / "entry/src/main/ets/entryability/EntryAbility.ets").write_text(normal_arkts_ability(), encoding="utf-8")

    build_script = candidate / "build-agent.sh"
    if platform == "android":
        build_script.write_text(
            f'#!/usr/bin/env bash\nset -euo pipefail\n"{GRADLE}" -p . --no-daemon --offline assembleDebug\n',
            encoding="utf-8",
        )
    else:
        build_script.write_text(
            f'#!/usr/bin/env bash\nset -euo pipefail\n"{HVIGOR}" --no-daemon --mode module -p module=entry@default assembleHap\n',
            encoding="utf-8",
        )
    build_script.chmod(0o755)
    build_command = ["bash", "build-agent.sh"]
    inputs = candidate / "_benchmark_inputs"
    inputs.mkdir()
    shutil.copy2(TASKS / task_id / "requirement.md", inputs / "requirement.md")
    dump(inputs / "public_transitions.json", public_transitions(load(migration / "canonical/transitions.json")))
    if public_api is not None:
        (inputs / "android-public-api.txt").write_text(public_api, encoding="utf-8")
    platform_note = (
        "The base production sources are in src/main/java. Final external-leaf stubs are available "
        "in .benchmark-scaffold/final-stubs but are not compiled initially. Replace obsolete base "
        "sources and update build source roots when adopting the public ABI."
        if platform == "android" else
        "The app entry is entry/src/main/ets/pages/Index.ets and production stores are under entry/src/main/ets/feature."
    )
    prompt = f"""Implement {task_id} completely in this {platform} candidate.

Read `_benchmark_inputs/requirement.md`, `_benchmark_inputs/public_transitions.json`{', and `_benchmark_inputs/android-public-api.txt`' if public_api else ''}. Inspect the visible base and implement the requested behavior in real production code. {platform_note}

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
    subprocess.run(["git", "init", "-q"], cwd=candidate, check=True)
    subprocess.run(["git", "add", "-A"], cwd=candidate, check=True)
    subprocess.run([
        "git", "-c", "user.name=Benchmark Runner", "-c", "user.email=benchmark@localhost",
        "commit", "-q", "-m", "clean-room base",
    ], cwd=candidate, check=True)
    baseline = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=candidate, text=True).strip()
    return build_command, baseline


def cleanup_builds(project: Path, receipt: Path) -> None:
    removable: list[Path] = []
    binaries: list[dict[str, Any]] = []
    for parent, directories, _ in os.walk(project):
        root = Path(parent)
        if root.name in {"build", ".gradle", ".hvigor", ".cxx", "oh_modules", "node_modules", "__pycache__"}:
            removable.append(root)
            directories[:] = []
            for path in root.rglob("*"):
                if path.is_file() and path.suffix.lower() in {".apk", ".aab", ".hap", ".har"}:
                    binaries.append({"path": str(path.relative_to(project)), "bytes": path.stat().st_size, "sha256": sha256(path)})
        else:
            directories[:] = [name for name in directories if name != ".git"]
    for path in sorted(set(removable), key=lambda value: len(value.parts), reverse=True):
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


def baseline_archive(candidate: Path, output: Path, baseline: str) -> dict[str, Any]:
    output.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "archive", "--format=tar.gz", "--output", str(output), baseline], cwd=candidate, check=True)
    return {**artifact(output), "commit": baseline, "capturePhase": "after_preflight_cleanup_before_agent"}


def changed_paths(candidate: Path) -> list[str]:
    changed = subprocess.check_output(["git", "diff", "HEAD", "--name-only", "--no-renames", "-z"], cwd=candidate)
    untracked = subprocess.check_output(["git", "ls-files", "--others", "--exclude-standard", "-z"], cwd=candidate)
    return sorted({os.fsdecode(path) for path in (changed + untracked).split(b"\0") if path})


def production_files(paths: list[str], platform: str) -> list[str]:
    suffixes = {".kt", ".java", ".xml", ".kts"} if platform == "android" else {".ets", ".ts", ".json5"}
    excluded = {"build", ".gradle", ".hvigor", "oh_modules", "node_modules", "_benchmark_inputs", ".benchmark-evaluator", ".benchmark-scaffold"}
    return [path for path in paths if Path(path).suffix.lower() in suffixes and not (set(Path(path).parts) & excluded) and path != "opencode.json"]


def generation_audit(candidate: Path, generated: list[str]) -> dict[str, Any]:
    issues: list[str] = []
    warnings: list[str] = []
    forbidden_parts = {"probe", "probes", "evaluator", "test", "tests", "androidtest", "fixture", "fixtures"}
    for relative in generated:
        path = Path(relative)
        full = candidate / path
        text = ""
        if full.is_file():
            text = full.read_text(encoding="utf-8", errors="ignore")
            for marker in ("traceDigest", "LTB_RUNTIME", "SemanticProbe"):
                if marker in text:
                    issues.append(f"forbidden evaluator marker {marker} in {relative}")
        evaluator_like = bool({part.lower() for part in path.parts} & forbidden_parts or "probe" in path.stem.lower())
        if evaluator_like and not any(issue.endswith(f"in {relative}") for issue in issues):
            import_tokens = (f"/{path.stem}'", f'/{path.stem}"')
            referenced = any(
                other != relative
                and (candidate / other).is_file()
                and any(token in (candidate / other).read_text(encoding="utf-8", errors="ignore") for token in import_tokens)
                for other in generated
            )
            if referenced:
                issues.append(f"evaluator-like generated path is referenced by production: {relative}")
            else:
                warnings.append(f"unreferenced evaluator-like scratch path retained as diagnostic: {relative}")
    return {
        "passed": bool(generated) and not issues,
        "changedProductionFiles": generated,
        "issues": issues,
        "warnings": warnings,
    }


def terminal_audit(log: Path, candidate: Path, build: list[str], output: Path,
                   deadline: float) -> dict[str, Any]:
    """Retry exports after the OpenCode process exits so session_not_terminal is transient."""
    audit: dict[str, Any] | None = None
    for attempt in range(3):
        audit = audit_sessions(log, candidate, build, output, deadline)
        if audit["availability"] != "isolation_unverified":
            return audit
        if attempt < 2:
            time.sleep(2)
    assert audit is not None
    return audit


def archive_patch(candidate: Path, output: Path, baseline: str) -> dict[str, Any]:
    subprocess.run(["git", "add", "-N", "--", "."], cwd=candidate, check=True)
    patch = subprocess.check_output(["git", "diff", "--binary", "--full-index", "--no-renames", baseline, "--"], cwd=candidate)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(patch)
    with tempfile.TemporaryDirectory(prefix="wordpress-agent-replay-") as temporary:
        env = {**os.environ, "GIT_INDEX_FILE": str(Path(temporary) / "index")}
        subprocess.run(["git", "read-tree", baseline], cwd=candidate, env=env, check=True)
        if patch:
            subprocess.run(["git", "apply", "--cached", "--binary", "--whitespace=nowarn", "-"], cwd=candidate, env=env, input=patch, check=True)
        tree = subprocess.check_output(["git", "write-tree"], cwd=candidate, env=env, text=True).strip()
    return {**artifact(output), "baselineCommit": baseline, "tree": tree, "reconstructionVerified": True}


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
    spec = importlib.util.spec_from_file_location("wordpress_opencode_audit", helper)
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
    archived = bool(loader.paths) and all(path.is_file() for path in loader.paths.values())
    availability = (
        "isolation_violation" if escaped else
        "available" if archived else
        "isolation_unverified"
    )
    audit.update({
        "schema": "opencode_recursive_isolation_v1", "candidate": str(candidate.resolve()),
        "rootSessionID": root_id, "allowedShellCommands": sorted(allowed),
        "reviewedHelper": artifact(helper), "inventory": artifact(inventory_path),
        "sessionExports": {sid: artifact(path) for sid, path in loader.paths.items()},
        "timingScope": "Top-level run only; subagent timestamps are forensic and are not summed.",
        "availability": availability,
        "unresolvedDiagnosticsDoNotImplyEscape": True,
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
        "caseId": case["caseId"], "key": case["key"], "traceDigest": case["traceDigest"],
        "status": "not_scored", "observed": None, "effects": [], "invariantChecks": [],
        "productionBodies": [], "checkpoints": [], "diagnostic": diagnostic,
    } for case in contract["cases"]]
    return {
        "schemaVersion": 1, "taskId": task_id, "platform": platform, "role": "agent",
        "observationMode": "runtime_state_transition",
        "semantic": {"cases": cases, "summary": {"passed": 0, "failed": 0, "notScored": len(cases), "total": len(cases)}},
        "diagnostics": {"adapter": "unavailable", "transport": "not_attempted", "reason": diagnostic},
    }


def prepare_hidden(task_id: str, platform: str, candidate: Path, run_dir: Path, deadline: float) -> tuple[list[str], list[str]]:
    migration = MIGRATIONS / task_id
    if platform == "android":
        command = [
            "python3", str(TOOLS / "prepare_new_agent_candidate.py"), "--phase", "hidden",
            "--task-id", task_id, "--project", str(candidate), "--migration", str(migration),
        ]
        if run_logged(command, migration, run_dir / "hidden-prepare.log", remaining(deadline, "hidden_prepare"), environment(candidate)):
            raise RuntimeError("hidden Android adapter preparation failed")
        build = [str(GRADLE), "-p", str(candidate), "--no-daemon", "--offline", "assembleDebug", "assembleDebugAndroidTest"]
        semantic = [
            "python3", str(TOOLS / "score_new_android_agent.py"), "--task-id", task_id,
            "--project", str(candidate), "--contract", str(migration / "canonical/transitions.json"),
            "--output", str(run_dir / "semantic.json"),
        ]
    else:
        hidden = candidate / "entry/src/main/ets/.benchmark-evaluator"
        shutil.rmtree(hidden, ignore_errors=True)
        hidden.mkdir(parents=True)
        shutil.copy2(migration / "arkts/final/entry/src/main/ets/evaluator/SemanticProbe.ets", hidden / "SemanticProbe.ets")
        ability = (migration / "arkts/final/entry/src/main/ets/entryability/EntryAbility.ets").read_text(encoding="utf-8")
        ability = ability.replace("../evaluator/SemanticProbe", "../.benchmark-evaluator/SemanticProbe")
        (candidate / "entry/src/main/ets/entryability/EntryAbility.ets").write_text(ability, encoding="utf-8")
        dump(run_dir / "hidden-prepare.json", {
            "classification": "evaluator_owned_runtime_adapter", "productionLogicInjected": False,
            "containsExpectedOracle": False, "runtime": "OpenHarmony API23 ArkVM",
        })
        build = [str(HVIGOR), "--no-daemon", "--mode", "module", "-p", "module=entry@default", "assembleHap"]
        semantic = [
            "python3", str(migration / "arkts/evaluator/run_device_semantic.py"),
            "--project", str(candidate), "--role", "agent", "--output", str(run_dir / "semantic.json"),
        ]
    return build, semantic


def execute_hidden(task_id: str, platform: str, candidate: Path, run_dir: Path,
                   deadline: float) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    build, semantic = prepare_hidden(task_id, platform, candidate, run_dir, deadline)
    if platform == "android":
        with android_build_slot(candidate):
            build_exit = run_logged(build, candidate, run_dir / "hidden-build.log", remaining(deadline, "hidden_build"), environment(candidate), True)
    else:
        build_exit = run_logged(build, candidate, run_dir / "hidden-build.log", remaining(deadline, "hidden_build"), environment(candidate), True)
    diagnostics: dict[str, Any] = {"runtimeCompileExit": build_exit, "classification": "adapter diagnostic"}
    if build_exit:
        return None, diagnostics
    semantic_exit = run_logged(semantic, MIGRATIONS / task_id, run_dir / "semantic.log", remaining(deadline, "semantic_runtime"), environment(candidate))
    diagnostics["semanticExit"] = semantic_exit
    report = run_dir / "semantic.json"
    return (load(report), diagnostics) if report.is_file() else (None, diagnostics)


def android_public_api(task_id: str, log_dir: Path) -> str:
    migration = MIGRATIONS / task_id
    project = migration / "android/focused-runtime/final"
    require_space(project)
    with android_build_slot(project):
        code = run_logged(["bash", "build.sh"], project, log_dir / f"{task_id}-api-build.log", 1200, environment(project), True)
    if code:
        raise RuntimeError(f"cannot compile {task_id} known-final for public ABI")
    jar = project / "build/intermediates/compile_app_classes_jar/debug/bundleDebugClassesToCompileJar/classes.jar"
    listing = subprocess.check_output(["jar", "tf", str(jar)], text=True).splitlines()
    prefix = "org/wordpress/android/ui/main/" if task_id == "03_site_picker" else "org/wordpress/android/ui/newstats/"
    classes = sorted({line[:-6].replace("/", ".") for line in listing if line.startswith(prefix) and line.endswith(".class")})
    chunks = [
        "Public Android ABI for the changed application-owned surface.",
        "This file contains signatures only; behavior and evaluator expectations are intentionally absent.",
        "",
    ]
    for class_name in classes:
        result = subprocess.run(["javap", "-classpath", str(jar), "-public", class_name], text=True, capture_output=True)
        if result.returncode == 0:
            chunks.append(result.stdout.strip())
    cleanup_builds(project, log_dir / f"{task_id}-api-build-cleanup.json")
    return "\n\n".join(chunks) + "\n"


def preflight(task_id: str, platform: str, candidate: Path, run_dir: Path,
              public_api: str | None) -> tuple[list[str], str, dict[str, Any]]:
    require_space(candidate.parent)
    build, baseline = prepare_candidate(task_id, platform, candidate, run_dir, public_api)
    if platform == "android":
        with android_build_slot(candidate):
            code = run_logged(build, candidate, run_dir / "preflight-build.log", 1200, environment(candidate), True)
    else:
        code = run_logged(build, candidate, run_dir / "preflight-build.log", 1200, environment(candidate), True)
    if code:
        raise RuntimeError(f"clean base public build failed with exit {code}")
    cleanup_builds(candidate, run_dir / "preflight-artifacts.json")
    inputs = run_dir / "inputs"
    snapshot = tree_snapshot(candidate, inputs / "raw-tree.json")
    archive = baseline_archive(candidate, inputs / "baseline.tar.gz", baseline)
    return build, baseline, {"rawTree": snapshot, "archive": archive}


def run_one(task_id: str, platform: str, run_id: str, candidate_root: Path,
            public_api: str | None, timeout: int) -> dict[str, Any]:
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
        build, baseline, evidence = preflight(task_id, platform, candidate, run_dir, public_api)
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
            "--title", f"WordPress {task_id} {platform}", prompt,
        ]
        result["agentCommand"] = [*command[:-1], "@_benchmark_inputs/prompt.md"]
        try:
            agent_exit = run_logged(command, candidate, log, allowance, environment(candidate), True)
            timed_out = False
        except subprocess.TimeoutExpired:
            agent_exit, timed_out = 124, True
        result.update(agentExit=agent_exit, agentTimedOut=timed_out)
        paths = changed_paths(candidate)
        generated = production_files(paths, platform)
        audit = generation_audit(candidate, generated)
        patch = archive_patch(candidate, run_dir / "agent.patch", baseline)
        dump(run_dir / "generated-files.json", {
            "schemaVersion": 1, "changedFiles": paths, "generatedProductionFiles": generated, "audit": audit,
        })
        result.update(candidatePatch=patch, codeGeneration=audit)
        external = provider_failure(log)
        result["generationDiagnostics"] = {
            "providerFailure": external,
            "timedOut": timed_out,
            "agentExit": agent_exit,
            "classification": "diagnostic; benchmark metrics are evaluated independently after termination",
        }
        if external and not generated:
            result.update(availability=external, externalFailure=True,
                          reason="provider failed before any production code was generated")
            return result
        result["externalFailure"] = bool(external)
        isolation = terminal_audit(
            log, candidate, build, run_dir / "isolation-audit-terminal.json", deadline,
        )
        result["isolationAudit"] = isolation
        if isolation["availability"] != "available":
            result["availability"] = isolation["availability"]
            return result
        if platform == "android":
            with android_build_slot(candidate):
                compile_exit = run_logged(build, candidate, run_dir / "production-build.log", remaining(deadline, "production_build"), environment(candidate), True)
        else:
            compile_exit = run_logged(build, candidate, run_dir / "production-build.log", remaining(deadline, "production_build"), environment(candidate), True)
        result["compile"] = {"passed": compile_exit == 0, "exitCode": compile_exit, "command": build}
        cleanup_builds(candidate, run_dir / "production-build-artifacts.json")
        if compile_exit:
            report = not_scored_report(task_id, platform, "candidate production compile failed")
            diagnostics = {
                "runtimeCompileExit": compile_exit,
                "semanticExit": None,
                "classification": "adapter diagnostic; semantic runtime was not started",
            }
        else:
            report, diagnostics = execute_hidden(task_id, platform, candidate, run_dir, deadline)
        result["diagnostics"] = diagnostics
        if report is None:
            report = not_scored_report(task_id, platform, "hidden runtime adapter did not compile or bind")
        metrics = semantic_metrics(report)
        report["codeGeneration"] = audit
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
                timingScope="Top-level run from OpenCode invocation through audit, build, runtime scoring, and cleanup; subagent durations are not added.",
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
    policy = "Only code generation, application compile, and semantic testcase pass rate are benchmark metrics. Adapter and transport are diagnostics. notScored is excluded from pass/fail."
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", default=f"wordpress_03_04_minimax_m3_{datetime.now():%Y%m%d_%H%M%S}")
    parser.add_argument("--timeout", type=int, default=3600)
    parser.add_argument("--candidate-root", type=Path)
    args = parser.parse_args()
    if args.timeout != 3600:
        raise ValueError("this benchmark round requires exactly 3600 seconds per top-level run")
    require_space(ROOT)
    candidate_root = (args.candidate_root or ROOT.parent / ".ltb-wordpress-agent" / args.run_id).resolve()
    candidate_root.mkdir(parents=True, exist_ok=True)
    round_started = datetime.now().astimezone()
    api_logs = MIGRATIONS / TASK_IDS[0] / "results/agent-runs" / args.run_id / "preflight"
    public_apis = {task_id: android_public_api(task_id, api_logs) for task_id in TASK_IDS}
    rows: list[dict[str, Any]] = []
    for task_id in TASK_IDS:
        for platform in PLATFORMS:
            rows.append(run_one(
                task_id, platform, args.run_id, candidate_root,
                public_apis[task_id] if platform == "android" else None, args.timeout,
            ))
    for task_id in TASK_IDS:
        summarize(task_id, [row for row in rows if row["taskId"] == task_id], args.run_id)
    round_finished = datetime.now().astimezone()
    summary = {
        "runId": args.run_id, "startedAt": round_started.isoformat(timespec="seconds"),
        "finishedAt": round_finished.isoformat(timespec="seconds"),
        "elapsedSeconds": round((round_finished - round_started).total_seconds(), 3),
        "runs": rows,
    }
    for task_id in TASK_IDS:
        dump(MIGRATIONS / task_id / "results/agent-runs" / args.run_id / "round-summary.json", summary)
    shutil.rmtree(candidate_root, ignore_errors=True)
    print(json.dumps({"runId": args.run_id, "runs": [
        {"taskId": row["taskId"], "platform": row["platform"], "availability": row["availability"]}
        for row in rows
    ]}, ensure_ascii=False))
    return 0 if all(row.get("benchmarkMetricsAvailable") for row in rows) else 2


if __name__ == "__main__":
    raise SystemExit(main())
