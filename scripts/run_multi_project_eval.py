#!/usr/bin/env python3
"""Calibrate and evaluate namespaced Android/ArkTS benchmark projects."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import shlex
import shutil
import signal
import subprocess
import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "benchmark_projects"
MODEL = "minimax-token-plan/MiniMax-M3"
MIN_FREE_BYTES = 8 * 1024**3
BUILD_LOCK = Path("/tmp/long-term-benchmark-android-full-build.lock")
HVIGOR = Path("/Applications/DevEco-Studio.app/Contents/tools/hvigor/bin/hvigorw")
ANDROID_SDK = Path.home() / "Library/Android/sdk"
OH_SDK = Path.home() / "Library/OpenHarmony/Sdk"
JAVA_HOME = Path("/opt/homebrew/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home")


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected a JSON object")
    return value


def project_entry(project_id: str) -> tuple[Path, dict[str, Any]]:
    registry = load(REGISTRY / "catalog.json")
    rows = [row for row in registry["projects"] if row.get("projectId") == project_id]
    if len(rows) != 1:
        raise ValueError(f"unknown or duplicate project: {project_id}")
    path = REGISTRY / rows[0]["catalog"]
    return path.parent, load(path)


def public_transitions(contract: dict[str, Any]) -> dict[str, Any]:
    return {
        "schemaVersion": 1,
        "taskId": contract["taskId"],
        "description": "Public scenarios; evaluator expected observations and bindings are private.",
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


def environment(overrides: dict[str, str] | None = None) -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "JAVA_HOME": str(JAVA_HOME),
            "ANDROID_HOME": str(ANDROID_SDK),
            "ANDROID_SDK_ROOT": str(ANDROID_SDK),
            "DEVECO_SDK_HOME": str(OH_SDK),
        }
    )
    env["PATH"] = os.pathsep.join(
        [
            str(JAVA_HOME / "bin"),
            str(ANDROID_SDK / "platform-tools"),
            str(HVIGOR.parent),
            "/Applications/DevEco-Studio.app/Contents/tools/ohpm/bin",
            env.get("PATH", ""),
        ]
    )
    if overrides:
        env.update({key: str(value) for key, value in overrides.items()})
        if "JAVA_HOME" in overrides:
            env["PATH"] = os.pathsep.join([str(Path(overrides["JAVA_HOME"]) / "bin"), env["PATH"]])
    return env


def require_space(path: Path) -> None:
    probe = path
    while not probe.exists():
        probe = probe.parent
    free = shutil.disk_usage(probe).free
    if free < MIN_FREE_BYTES:
        raise RuntimeError(f"only {free} bytes free; at least {MIN_FREE_BYTES} required")


@contextmanager
def build_slot(platform: str, path: Path):
    require_space(path)
    if platform != "android":
        yield
        return
    with BUILD_LOCK.open("a") as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        try:
            require_space(path)
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


def run_logged(
    command: list[str],
    cwd: Path,
    log: Path,
    timeout: int,
    extra_env: dict[str, str] | None = None,
) -> int:
    log.parent.mkdir(parents=True, exist_ok=True)
    env = environment(extra_env)
    env["PWD"] = str(cwd)
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
            stream.write(json.dumps({"type": "timeout", "seconds": timeout}) + "\n")
            return 124
        except BaseException:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
            raise


def expand(command: list[str], values: dict[str, Path | str]) -> list[str]:
    return [part.format_map({key: str(value) for key, value in values.items()}) for part in command]


def validate_report(
    path: Path,
    task_id: str,
    platform: str,
    role: str,
    contract: dict[str, Any] | None = None,
) -> dict[str, Any]:
    report = load(path)
    errors: list[str] = []
    for key, expected in (
        ("taskId", task_id),
        ("platform", platform),
        ("role", role),
        ("observationMode", "runtime_state_transition"),
    ):
        if report.get(key) != expected:
            errors.append(f"{key}: expected {expected!r}, got {report.get(key)!r}")
    rows = report.get("semantic", {}).get("cases", [])
    if not isinstance(rows, list) or not rows:
        errors.append("semantic.cases must be non-empty")
        rows = []
    indexed: dict[str, dict[str, Any]] = {}
    for row in rows:
        case_id = row.get("caseId")
        if not isinstance(case_id, str) or not case_id or case_id in indexed:
            errors.append(f"invalid or duplicate caseId {case_id!r}")
            continue
        indexed[case_id] = row
        if row.get("status") not in {"pass", "fail", "not_scored"}:
            errors.append(f"invalid status for {case_id}")
        if row.get("status") in {"pass", "fail"} and len(row.get("checkpoints", [])) < 2:
            errors.append(f"{case_id}: missing before/after checkpoints")
        if row.get("status") in {"pass", "fail"} and not row.get("productionSources"):
            errors.append(f"{case_id}: missing production source provenance")
    if contract is not None:
        expected = {case["caseId"]: case["traceDigest"] for case in contract["cases"]}
        if set(indexed) != set(expected):
            errors.append("semantic case IDs differ from canonical contract")
        for case_id in set(indexed) & set(expected):
            if indexed[case_id].get("traceDigest") != expected[case_id]:
                errors.append(f"{case_id}: traceDigest differs from canonical contract")
    statuses = [row.get("status") for row in indexed.values()]
    if role == "base" and any(status != "fail" for status in statuses):
        errors.append("base polarity must be all fail with no unscored rows")
    if role == "final" and any(status != "pass" for status in statuses):
        errors.append("final polarity must be all pass with no unscored rows")
    if role == "agent" and any(status == "not_scored" for status in statuses):
        errors.append("agent report contains unscored rows")
    if role == "agent":
        for metric in ("codeGeneration", "compile"):
            if not isinstance(report.get(metric, {}).get("passed"), bool):
                errors.append(f"agent {metric}.passed must be boolean")
    return {"valid": not errors, "errors": errors, "report": report}


def copy_candidate(source: Path, destination: Path) -> None:
    if destination.exists():
        shutil.rmtree(destination)

    def ignored(_: str, names: list[str]) -> set[str]:
        evaluator_owned = {
            ".benchmark-evaluator", "evaluator", "evaluator-src", "results", "provenance", "verification",
        }
        generated = {".git", ".gradle", ".hvigor", "build", "oh_modules", "node_modules"}
        return {name for name in names if name in evaluator_owned | generated}

    shutil.copytree(source, destination, ignore=ignored)


def sanitize_candidate(candidate: Path, platform: str) -> None:
    """Remove calibration-only wiring before the clean-room base commit."""
    if platform != "arkts":
        return
    entry = candidate / "entry/src/main/ets/entryability/EntryAbility.ets"
    if not entry.is_file():
        return
    text = entry.read_text(encoding="utf-8")
    if "SemanticProbe" not in text and "LTB_RUNTIME" not in text:
        return
    entry.write_text(
        """import { UIAbility, Want } from '@kit.AbilityKit';
import { window } from '@kit.ArkUI';

export default class EntryAbility extends UIAbility {
  onCreate(want: Want): void {
  }

  onWindowStageCreate(windowStage: window.WindowStage): void {
    windowStage.loadContent('pages/Index');
  }
}
""",
        encoding="utf-8",
    )


def opencode_config(candidate: Path, build_command: list[str]) -> dict[str, Any]:
    root = str(candidate.resolve())
    paths = {"*": "allow", "/*": "deny", f"{root}/*": "allow"}
    edit = dict(paths)
    for pattern in (
        "_benchmark_inputs/*", "_benchmark_inputs/**",
        f"{root}/_benchmark_inputs/*", f"{root}/_benchmark_inputs/**",
        ".benchmark-scaffold/*", ".benchmark-scaffold/**",
        f"{root}/.benchmark-scaffold/*", f"{root}/.benchmark-scaffold/**",
    ):
        edit[pattern] = "deny"
    shell = {
        "*": "deny",
        "pwd": "allow",
        "ls": "allow",
        "git status --short": "allow",
        "git diff --stat": "allow",
        shlex.join(build_command): "allow",
    }
    return {
        "$schema": "https://opencode.ai/config.json",
        "agent": {"explore": {"steps": 12, "prompt": "Explore only this candidate directory."}},
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


def prepare_agent(
    task_dir: Path,
    source: Path,
    candidate: Path,
    build_command: list[str],
    platform: str,
    scaffold_command: list[str] | None = None,
    scaffold_cwd: Path | None = None,
    scaffold_log: Path | None = None,
    scaffold_timeout: int = 600,
    scaffold_env: dict[str, str] | None = None,
) -> None:
    copy_candidate(source, candidate)
    sanitize_candidate(candidate, platform)
    if scaffold_command:
        if scaffold_log is None:
            raise ValueError("scaffold_log is required with scaffold_command")
        scaffold_exit = run_logged(
            scaffold_command,
            scaffold_cwd or candidate,
            scaffold_log,
            scaffold_timeout,
            scaffold_env,
        )
        if scaffold_exit != 0:
            raise RuntimeError(f"agent scaffold preparation failed with exit {scaffold_exit}")
    inputs = candidate / "_benchmark_inputs"
    inputs.mkdir()
    shutil.copy2(task_dir / "requirement.md", inputs / "requirement.md")
    integration_contract = task_dir / "integration_contract.md"
    if integration_contract.is_file():
        shutil.copy2(integration_contract, inputs / "integration_contract.md")
    contract = load(task_dir / "transitions.json")
    (inputs / "public_transitions.json").write_text(
        json.dumps(public_transitions(contract), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    prompt = f"""Implement {contract['taskId']} completely in this {platform} candidate.

Read `_benchmark_inputs/requirement.md`, `_benchmark_inputs/public_transitions.json`, and the optional `_benchmark_inputs/integration_contract.md`; inspect the existing production architecture and implement the behavior in real production code.

- Work only in this candidate directory; never inspect parent, sibling, home, evaluator, final, or network paths.
- Subagents are allowed and inherit the same boundary.
- When `integration_contract.md` exists, its production API and source-placement rules are mandatory public integration requirements, not evaluator hints.
- Do not create testcase switches, marker facts, semantic projections, or evaluator-only APIs.
- Preserve unrelated behavior and implement state, effects, persistence, UI wiring, failure recovery, and cleanup.
- Run `{shlex.join(build_command)}` and repair compilation within the time budget.
"""
    (inputs / "prompt.md").write_text(prompt, encoding="utf-8")
    (candidate / "opencode.json").write_text(json.dumps(opencode_config(candidate, build_command), indent=2) + "\n")
    subprocess.run(["git", "init", "-q"], cwd=candidate, check=True)
    subprocess.run(["git", "add", "-A"], cwd=candidate, check=True)
    subprocess.run(
        ["git", "-c", "user.name=Benchmark Runner", "-c", "user.email=benchmark@localhost", "commit", "-q", "-m", "clean-room base"],
        cwd=candidate,
        check=True,
    )


def changed_production(candidate: Path, platform: str) -> list[str]:
    raw = subprocess.check_output(["git", "status", "--porcelain=v1", "--untracked-files=all"], cwd=candidate, text=True)
    suffixes = (".kt", ".kts", ".java", ".xml") if platform == "android" else (".ets", ".ts", ".json5")
    result = []
    for line in raw.splitlines():
        path = line[3:]
        if path.startswith(("_benchmark_inputs/", "opencode.json")):
            continue
        if path.endswith(suffixes) and not any(part in {"build", ".gradle", ".hvigor"} for part in Path(path).parts):
            result.append(path)
    return result


def audit_generated_production(candidate: Path, generated_files: list[str]) -> dict[str, Any]:
    issues: list[str] = []
    forbidden_parts = {"probe", "probes", "evaluator", "test", "tests", "androidtest", "fixture", "fixtures"}
    forbidden_text = ("traceDigest", "LTB_RUNTIME", "SemanticProbe")
    for relative in generated_files:
        path = Path(relative)
        lowered = {part.lower() for part in path.parts}
        if lowered & forbidden_parts or "probe" in path.stem.lower():
            issues.append(f"evaluator-like generated path: {relative}")
            continue
        full = candidate / path
        if not full.is_file():
            continue
        text = full.read_text(encoding="utf-8", errors="ignore")
        for marker in forbidden_text:
            if marker in text:
                issues.append(f"forbidden evaluator marker {marker} in {relative}")
    return {"passed": bool(generated_files) and not issues, "issues": issues}


def archive_candidate(candidate: Path, output: Path, generated_files: list[str], platform: str) -> None:
    """Retain the generated patch and inventory without retaining a full candidate copy."""
    output.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "add", "-N", "--", "."], cwd=candidate, check=True)
    patch = subprocess.check_output(
        ["git", "diff", "--binary", "--no-ext-diff", "HEAD", "--"],
        cwd=candidate,
    )
    (output / f"{platform}-agent.patch").write_bytes(patch)
    (output / f"{platform}-agent-generated-files.json").write_text(
        json.dumps({"generatedProductionFiles": generated_files}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def remove_candidate(candidate: Path, stop: Path) -> None:
    if candidate.exists():
        shutil.rmtree(candidate)
    parent = candidate.parent
    while parent != stop and parent.exists() and not any(parent.iterdir()):
        parent.rmdir()
        parent = parent.parent


def cleanup_builds(project: Path, output: Path) -> None:
    def file_sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    artifacts = []
    removable = []
    for path in project.rglob("*"):
        if path.is_file() and path.suffix.lower() in {".apk", ".aab", ".hap", ".har"}:
            artifacts.append({"path": str(path.relative_to(project)), "bytes": path.stat().st_size,
                              "sha256": file_sha256(path)})
        if path.is_dir() and path.name in {"build", ".gradle", ".hvigor", "oh_modules", "node_modules"}:
            removable.append(path)
    for path in sorted(set(removable), key=lambda value: len(value.parts), reverse=True):
        if path.exists():
            shutil.rmtree(path)
    output.write_text(json.dumps({"artifacts": artifacts, "cleanupCompleted": True}, indent=2) + "\n")


def execute_role(
    migration: Path,
    task_id: str,
    platform: str,
    role: str,
    project: Path,
    config: dict[str, Any],
    out: Path,
    timeout: int,
    generated_files: list[str] | None = None,
) -> dict[str, Any]:
    values = {"project": project, "role": role, "output": out / f"{platform}-{role}.json", "migration": migration}
    build_command = expand(config["buildCommand"], values)
    semantic_command = expand(config["semanticCommand"], values)
    with build_slot(platform, project):
        build_exit = run_logged(
            build_command,
            project,
            out / f"{platform}-{role}-build.log",
            timeout,
            config.get("environment"),
        )
    semantic_exit = None
    validation: dict[str, Any] = {"valid": False, "errors": ["build failed"]}
    if build_exit == 0:
        semantic_exit = run_logged(
            semantic_command,
            migration,
            out / f"{platform}-{role}-semantic.log",
            timeout,
            config.get("environment"),
        )
        report_path = Path(values["output"])
        if semantic_exit == 0 and report_path.is_file():
            if role == "agent":
                report = load(report_path)
                report["codeGeneration"] = {
                    "passed": bool(generated_files),
                    "changedProductionFiles": generated_files or [],
                }
                report["compile"] = {"passed": True, "command": shlex.join(build_command)}
                report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            validation = validate_report(
                report_path,
                task_id,
                platform,
                role,
                load(migration / "canonical" / "transitions.json"),
            )
        else:
            validation = {"valid": False, "errors": ["semantic command failed or report missing"]}
    cleanup_builds(project, out / f"{platform}-{role}-artifacts.json")
    return {"buildExit": build_exit, "semanticExit": semantic_exit, "validation": validation}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--task", action="append")
    parser.add_argument("--phase", choices=("calibration", "agent", "all"), default="all")
    parser.add_argument("--run-id", default=f"multi_project_minimax_m3_{datetime.now():%Y%m%d_%H%M%S}")
    parser.add_argument("--agent-timeout", type=int, default=3600)
    parser.add_argument("--build-timeout", type=int, default=3600)
    args = parser.parse_args()

    project_dir, catalog = project_entry(args.project)
    tasks = args.task or catalog["acceptedTaskIds"]
    run_root = ROOT / "eval_runs" / args.run_id / args.project
    candidate_root = ROOT.parent / f"{ROOT.name}-multi-project-eval" / args.run_id / args.project
    summary: dict[str, Any] = {"projectId": args.project, "model": MODEL, "tasks": {}}
    overall_ok = True

    for task_id in tasks:
        task_dir = project_dir / "tasks" / task_id
        migration = project_dir / "migrations" / task_id
        execution = load(migration / "execution.json")
        task_result: dict[str, Any] = {}
        out = run_root / task_id
        out.mkdir(parents=True, exist_ok=True)
        for platform in ("android", "arkts"):
            config = execution[platform]
            if args.phase in {"calibration", "all"}:
                for role in ("base", "final"):
                    project = (migration / config[f"{role}Project"]).resolve()
                    result = execute_role(migration, task_id, platform, role, project, config, out, args.build_timeout)
                    task_result[f"{platform}-{role}"] = result
                    overall_ok = overall_ok and result["validation"]["valid"]
            if args.phase in {"agent", "all"}:
                base = (migration / config["baseProject"]).resolve()
                candidate = candidate_root / task_id / platform
                values = {
                    "project": candidate,
                    "candidate": candidate,
                    "role": "agent",
                    "output": out / f"{platform}-agent.json",
                    "migration": migration,
                }
                try:
                    visible_build = expand(config.get("agentVisibleBuildCommand", config["buildCommand"]), values)
                    scaffold_command = (
                        expand(config["agentScaffoldCommand"], values)
                        if config.get("agentScaffoldCommand") else None
                    )
                    prepare_agent(
                        task_dir,
                        base,
                        candidate,
                        visible_build,
                        platform,
                        scaffold_command=scaffold_command,
                        scaffold_cwd=migration,
                        scaffold_log=out / f"{platform}-agent-scaffold.log",
                        scaffold_timeout=args.build_timeout,
                        scaffold_env=config.get("environment"),
                    )
                    base_preflight_exit = run_logged(
                        visible_build,
                        candidate,
                        out / f"{platform}-agent-base-preflight.log",
                        args.build_timeout,
                        config.get("environment"),
                    )
                    if base_preflight_exit != 0:
                        task_result[f"{platform}-agent"] = {
                            "scaffoldExit": base_preflight_exit,
                            "validation": {"valid": False, "errors": ["clean-room base visible build failed"]},
                            "candidateRetained": False,
                        }
                        overall_ok = False
                        continue
                    cleanup_builds(candidate, out / f"{platform}-agent-base-preflight-artifacts.json")
                    started = time.monotonic()
                    agent_exit = run_logged(
                        ["opencode", "run", "--standalone", "--model", MODEL, "--format", "json", "--title", f"{args.project} {task_id} {platform}",
                         (candidate / "_benchmark_inputs/prompt.md").read_text(encoding="utf-8")],
                        candidate,
                        out / f"{platform}-agent-opencode.jsonl",
                        args.agent_timeout,
                        config.get("environment"),
                    )
                    generated_files = changed_production(candidate, platform)
                    generation_audit = audit_generated_production(candidate, generated_files)
                    production_compile_exit = run_logged(
                        visible_build,
                        candidate,
                        out / f"{platform}-agent-production-build.log",
                        args.build_timeout,
                        config.get("environment"),
                    )
                    cleanup_builds(candidate, out / f"{platform}-agent-pre-eval-artifacts.json")
                    archive_candidate(candidate, out, generated_files, platform)
                    if production_compile_exit != 0:
                        agent_result = {
                            "agentExit": agent_exit,
                            "basePreflightExit": base_preflight_exit,
                            "productionCompileExit": production_compile_exit,
                            "durationSeconds": round(time.monotonic() - started, 3),
                            "generatedProductionFiles": generated_files,
                            "codeGenerationAudit": generation_audit,
                            "candidateRetained": False,
                            "validation": {
                                "valid": False,
                                "errors": ["agent production visible build failed; semantic runtime not scored"],
                            },
                        }
                        task_result[f"{platform}-agent"] = agent_result
                        overall_ok = False
                        continue
                    prepare_exit = None
                    if config.get("agentPrepareCommand"):
                        prepare_exit = run_logged(
                            expand(config["agentPrepareCommand"], values),
                            migration,
                            out / f"{platform}-agent-prepare.log",
                            args.build_timeout,
                            config.get("environment"),
                        )
                    agent_config = dict(config)
                    agent_config["buildCommand"] = config.get("agentBuildCommand", config["buildCommand"])
                    agent_config["semanticCommand"] = config.get("agentSemanticCommand", config["semanticCommand"])
                    agent_result = execute_role(
                        migration, task_id, platform, "agent", candidate, agent_config, out,
                        args.build_timeout, generated_files,
                    )
                    report_path = out / f"{platform}-agent.json"
                    if report_path.is_file():
                        report = load(report_path)
                        report["codeGeneration"] = {
                            "passed": generation_audit["passed"],
                            "changedProductionFiles": generated_files,
                            "auditIssues": generation_audit["issues"],
                        }
                        report["compile"] = {
                            "passed": production_compile_exit == 0,
                            "command": shlex.join(visible_build),
                        }
                        report["runtimeCompile"] = {
                            "passed": agent_result.get("buildExit") == 0,
                            "classification": "hidden evaluator adapter diagnostic",
                        }
                        report_path.write_text(
                            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                            encoding="utf-8",
                        )
                        agent_result["validation"] = validate_report(
                            report_path,
                            task_id,
                            platform,
                            "agent",
                            load(migration / "canonical" / "transitions.json"),
                        )
                    agent_result.update({
                        "agentExit": agent_exit,
                        "prepareExit": prepare_exit,
                        "basePreflightExit": base_preflight_exit,
                        "productionCompileExit": production_compile_exit,
                        "durationSeconds": round(time.monotonic() - started, 3),
                        "generatedProductionFiles": generated_files,
                        "codeGenerationAudit": generation_audit,
                        "candidateRetained": False,
                    })
                    task_result[f"{platform}-agent"] = agent_result
                    overall_ok = overall_ok and agent_result["validation"]["valid"]
                except Exception as error:
                    (out / f"{platform}-agent-runner-error.json").write_text(
                        json.dumps({"type": type(error).__name__, "message": str(error)}, indent=2) + "\n",
                        encoding="utf-8",
                    )
                    task_result[f"{platform}-agent"] = {
                        "validation": {"valid": False, "errors": [f"runner error: {error}"]},
                        "candidateRetained": False,
                    }
                    overall_ok = False
                finally:
                    remove_candidate(candidate, candidate_root)
        summary["tasks"][task_id] = task_result
    run_root.mkdir(parents=True, exist_ok=True)
    (run_root / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"runRoot": str(run_root), "valid": overall_ok}, ensure_ascii=False))
    return 0 if overall_ok else 2


if __name__ == "__main__":
    raise SystemExit(main())

