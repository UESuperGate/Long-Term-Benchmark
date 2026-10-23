#!/usr/bin/env python3
"""Prepare and, only when explicitly authorized, run Wikipedia 05 agent evals.

The ``preflight`` command is device-free and never invokes OpenCode. The ``run``
command is separately gated because it invokes OpenCode and native evaluators.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import shlex
import shutil
import subprocess
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Any


TASK_ID = "05_evergreen_account"
PLATFORMS = ("android", "arkts")
MODEL = "minimax-token-plan/MiniMax-M3"
ENDPOINT = "https://api.minimaxi.com/v1"
OVERALL_TIMEOUT_SECONDS = 3600
MODEL_MAX_SECONDS = 2700
MIN_FREE_BYTES = 8 * 1024**3

MIGRATION = Path(__file__).resolve().parents[1]
PROJECT = MIGRATION.parents[1]
ROOT = PROJECT.parents[1]
TASK = PROJECT / "tasks" / TASK_ID
REFERENCE_RUNNER = PROJECT / "migrations/tools/run_wikipedia_03_04_agent_eval.py"
PARITY_VALIDATOR = ROOT / "skills/migration-skill/scripts/validate_transition_parity.py"
AUDIT_HELPER = ROOT / "scripts/opencode_subagent_audit.py"

GRADLE = Path.home() / ".gradle/wrapper/dists/gradle-8.14.3-bin/cv11ve7ro1n3o1j4so8xd9n66/gradle-8.14.3/bin/gradle"
ANDROID_JAVA = Path("/opt/homebrew/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home")
ANDROID_SDK = Path.home() / "Library/Android/sdk"
DEVECO_JAVA = Path("/Applications/DevEco-Studio.app/Contents/jbr/Contents/Home")
HVIGOR = Path("/Applications/DevEco-Studio.app/Contents/tools/hvigor/bin/hvigorw")
OH_SDK = Path.home() / "Library/OpenHarmony/Sdk/23"
HDC = OH_SDK / "toolchains/hdc"
ANDROID_BUILD_LOCK = "/tmp/long-term-benchmark-android-full-build.lock"
ARKTS_BUILD_LOCK = "/tmp/long-term-benchmark-arkts-full-build.lock"


def load_reference() -> Any:
    spec = importlib.util.spec_from_file_location("wikipedia_03_04_agent_reference", REFERENCE_RUNNER)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load reference runner: {REFERENCE_RUNNER}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


REF = load_reference()


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


def environment(candidate: Path, platform: str, hdc_target: str | None = None) -> dict[str, str]:
    env = os.environ.copy()
    java = ANDROID_JAVA if platform == "android" else DEVECO_JAVA
    env.update({
        "PWD": str(candidate),
        "OLDPWD": str(candidate),
        "JAVA_HOME": str(java),
        "ANDROID_HOME": str(ANDROID_SDK),
        "ANDROID_SDK_ROOT": str(ANDROID_SDK),
        "OHOS_BASE_SDK_HOME": str(OH_SDK.parent),
        "DEVECO_SDK_HOME": str(OH_SDK),
        "HDC": str(HDC),
    })
    if hdc_target:
        env["HDC_TARGET"] = hdc_target
    env["PATH"] = os.pathsep.join([
        str(java / "bin"),
        str(ANDROID_SDK / "platform-tools"),
        str(HVIGOR.parent),
        "/Applications/DevEco-Studio.app/Contents/tools/ohpm/bin",
        env.get("PATH", ""),
    ])
    return env


def public_transitions(contract: dict[str, Any]) -> dict[str, Any]:
    return {
        "schemaVersion": 1,
        "taskId": contract["taskId"],
        "description": "Public scenarios only. Expected observations, digests, evidence, and evaluator bindings are private.",
        "cases": [{
            "caseId": case["caseId"],
            "functionalArea": case.get("functionalArea"),
            "given": case["given"],
            "event": case["event"],
            "invariants": case.get("invariants", []),
        } for case in contract["cases"]],
    }


def path_policy(candidate: Path, *, protect_orchestration: bool) -> dict[str, str]:
    root = str(candidate.resolve())
    policy = {
        "*": "allow",
        "../*": "deny",
        "../**": "deny",
        "/*": "deny",
        f"{root}": "allow",
        f"{root}/*": "allow",
        f"{root}/**": "allow",
    }
    if protect_orchestration:
        for relative in (".git", "_benchmark_scaffold", "build-agent.sh", "opencode.json"):
            for pattern in (
                relative, f"{relative}/*", f"{relative}/**",
                f"{root}/{relative}", f"{root}/{relative}/*", f"{root}/{relative}/**",
            ):
                policy[pattern] = "deny"
    return policy


def opencode_config(candidate: Path, build_command: list[str]) -> dict[str, Any]:
    root = str(candidate.resolve())
    reads = path_policy(candidate, protect_orchestration=True)
    edits = path_policy(candidate, protect_orchestration=True)
    for relative in ("_benchmark_inputs", "_benchmark_scaffold", ".git", "build-agent.sh", "opencode.json"):
        for pattern in (
            relative, f"{relative}/*", f"{relative}/**",
            f"{root}/{relative}", f"{root}/{relative}/*", f"{root}/{relative}/**",
        ):
            edits[pattern] = "deny"
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
            "final, benchmark, evaluator, report, result, or hidden paths."
        )}},
        "permission": {
            "*": "deny",
            "read": reads,
            "edit": edits,
            "glob": reads,
            "grep": reads,
            "list": reads,
            "task": "allow",
            "webfetch": "deny",
            "websearch": "deny",
            "external_directory": "deny",
            "shell": shell,
            "bash": shell,
        },
    }


def sanitize_android(candidate: Path) -> None:
    gradle = candidate / "app/build.gradle.kts"
    text = gradle.read_text(encoding="utf-8")
    runner = '        testInstrumentationRunner = "org.wikipedia.benchmark.evergreen.native.NativeEvergreenInstrumentation"\n'
    tests = '        getByName("androidTest") { kotlin.srcDirs("../../../shared/native_test/kotlin") }\n'
    if runner not in text or tests not in text:
        raise RuntimeError("Android evaluator wiring changed; refusing to expose or silently retain it")
    gradle.write_text(text.replace(runner, "").replace(tests, ""), encoding="utf-8")


def write_build_script(candidate: Path, platform: str) -> list[str]:
    if platform == "android":
        command = [str(GRADLE), "-p", ".", "--no-daemon", "--offline", ":app:assembleDebug"]
        lock = ANDROID_BUILD_LOCK
    else:
        command = [str(HVIGOR), "--mode", "module", "-p", "product=default", "-p", "module=entry@default", "assembleHap", "--no-daemon"]
        lock = ARKTS_BUILD_LOCK
    encoded = json.dumps(command)
    body = f'''#!/usr/bin/env bash
set -euo pipefail
python3 - "{lock}" '{encoded}' <<'PY'
import fcntl, json, subprocess, sys
lock_path, command = sys.argv[1], json.loads(sys.argv[2])
with open(lock_path, "a+") as stream:
    fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
    raise SystemExit(subprocess.run(command).returncode)
PY
'''
    script = candidate / "build-agent.sh"
    script.write_text(body, encoding="utf-8")
    script.chmod(0o755)
    return ["bash", "build-agent.sh"]


def prompt_for(platform: str, build_command: list[str]) -> str:
    owner = (
        "The Android production entry is BenchmarkActivity and its page owner is EvergreenPageOwner."
        if platform == "android" else
        "The OpenHarmony production entry is EntryAbility and its ArkUI page owner is exposed by Index."
    )
    return f"""Implement {TASK_ID} completely in this {platform} candidate.

Read `_benchmark_inputs/requirement.md` and `_benchmark_inputs/public_transitions.json`. Inspect the visible base and implement the requested behavior in real production code. {owner}

Rules:
- Work only in this candidate directory. Never inspect parent, sibling, home, network, final, evaluator, report, result, or hidden paths.
- Subagents are allowed and inherit exactly the same workspace boundary.
- Do not create case-ID switches, marker facts, semantic projections, evaluator APIs, or source-observer shortcuts.
- Preserve unrelated behavior. Implement application-owned state, persistence, effects, page wiring, failure recovery, and cleanup.
- Run `{shlex.join(build_command)}` exactly as written and repair production compilation within the total task budget.

Finish with a concise summary of changed production files and remaining blockers.
"""


def prepare_visible_candidate(platform: str, candidate: Path) -> tuple[list[str], str]:
    source = MIGRATION / ("android/native/base" if platform == "android" else "arkts/base")
    REF.copy_candidate(source, candidate)
    if platform == "android":
        sanitize_android(candidate)
    build = write_build_script(candidate, platform)
    inputs = candidate / "_benchmark_inputs"
    inputs.mkdir()
    shutil.copy2(TASK / "requirement.md", inputs / "requirement.md")
    dump(inputs / "public_transitions.json", public_transitions(load(MIGRATION / "canonical/transitions.json")))
    prompt = prompt_for(platform, build)
    dump(candidate / "opencode.json", opencode_config(candidate, build))
    return build, prompt


def recursive_keys(value: Any) -> set[str]:
    if isinstance(value, dict):
        return set(value) | set().union(*(recursive_keys(item) for item in value.values()), set())
    if isinstance(value, list):
        return set().union(*(recursive_keys(item) for item in value), set())
    return set()


def static_candidate_audit(platform: str, candidate: Path, build: list[str], prompt: str) -> dict[str, Any]:
    public = load(candidate / "_benchmark_inputs/public_transitions.json")
    leaked = sorted(recursive_keys(public) & {
        "expected", "traceDigest", "evidence", "polarity", "setup", "key", "bindings",
        "androidProduction", "androidTests", "androidRuntimeTrace",
    })
    files = sorted(path.relative_to(candidate).as_posix() for path in candidate.rglob("*") if path.is_file())
    forbidden = {"final", "evaluator", "evaluators", "report", "reports", "results"}
    exposed = [name for name in files if {part.lower() for part in Path(name).parts} & forbidden]
    config = load(candidate / "opencode.json")
    permission = config["permission"]
    shell = permission["shell"]
    root = str(candidate.resolve())
    checks = {
        "defaultDenied": permission.get("*") == "deny",
        "networkDenied": permission.get("webfetch") == "deny" and permission.get("websearch") == "deny",
        "externalDirectoryDenied": permission.get("external_directory") == "deny",
        "subagentsAllowed": permission.get("task") == "allow",
        "parentDenied": all(permission[name].get("../**") == "deny" and permission[name].get("/*") == "deny"
                            for name in ("read", "edit", "glob", "grep", "list")),
        "candidateReallowed": all(permission[name].get(f"{root}/**") == "allow"
                                  for name in ("read", "edit", "glob", "grep", "list")),
        "inputsImmutable": permission["edit"].get("_benchmark_inputs/**") == "deny",
        "orchestrationUnreadable": all(permission["read"].get(name) == "deny" for name in ("build-agent.sh", "opencode.json")),
        "shellDefaultDenied": shell.get("*") == "deny",
        "exactBuildAllowed": shell.get(shlex.join(build)) == "allow",
    }
    cases = public.get("cases", [])
    passed = public.get("taskId") == TASK_ID and len(cases) == 10 and not leaked and not exposed and all(checks.values())
    return {
        "platform": platform,
        "passed": passed,
        "candidateFileCount": len(files),
        "candidateFiles": files,
        "publicCaseCount": len(cases),
        "forbiddenPublicKeys": leaked,
        "forbiddenVisiblePaths": exposed,
        "configurationChecks": checks,
        "requirement": artifact(candidate / "_benchmark_inputs/requirement.md"),
        "publicTransitions": artifact(candidate / "_benchmark_inputs/public_transitions.json"),
        "promptSha256": hashlib.sha256(prompt.encode()).hexdigest(),
        "buildCommand": build,
    }


def protected_files(candidate: Path) -> dict[str, dict[str, Any]]:
    names = ("_benchmark_inputs/requirement.md", "_benchmark_inputs/public_transitions.json", "build-agent.sh", "opencode.json")
    return {name: artifact(candidate / name) for name in names}


def verify_protected(candidate: Path, expected: dict[str, dict[str, Any]]) -> dict[str, Any]:
    rows = []
    for name, before in expected.items():
        path = candidate / name
        same = path.is_file() and path.stat().st_size == before["bytes"] and sha256(path) == before["sha256"]
        rows.append({"path": name, "unchanged": same})
    return {"passed": all(row["unchanged"] for row in rows), "files": rows}


def initialize_baseline(candidate: Path, evidence_dir: Path) -> tuple[str, dict[str, Any], dict[str, dict[str, Any]]]:
    subprocess.run(["git", "init", "-q"], cwd=candidate, check=True)
    subprocess.run(["git", "add", "-A"], cwd=candidate, check=True)
    subprocess.run([
        "git", "-c", "user.name=Benchmark Runner", "-c", "user.email=benchmark@localhost",
        "commit", "-q", "-m", "clean-room base",
    ], cwd=candidate, check=True)
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=candidate, text=True).strip()
    inputs = evidence_dir / "inputs"
    snapshot = REF.tree_snapshot(candidate, inputs / "raw-tree.json")
    archive = REF.baseline_archive(candidate, inputs / "baseline.tar.gz", commit)
    return commit, {"commit": commit, "rawTree": snapshot, "archive": archive}, protected_files(candidate)


def run_build(platform: str, candidate: Path, build: list[str], log: Path, timeout: float) -> int:
    return REF.run_logged(build, candidate, log, timeout, environment(candidate, platform), True)


def inject_android_evaluator(candidate: Path) -> None:
    gradle = candidate / "app/build.gradle.kts"
    text = gradle.read_text(encoding="utf-8")
    anchor = "        versionName = \"1.0\"\n"
    if anchor not in text:
        raise RuntimeError("Android candidate no longer exposes the supported defaultConfig ABI")
    text = text.replace(anchor, anchor + '        testInstrumentationRunner = "org.wikipedia.benchmark.evergreen.native.NativeEvergreenInstrumentation"\n', 1)
    gradle.write_text(text, encoding="utf-8")
    destination = candidate / "app/src/androidTest/kotlin/org/wikipedia/benchmark/evergreen/native"
    destination.mkdir(parents=True, exist_ok=True)
    shutil.copy2(
        MIGRATION / "android/shared/native_test/kotlin/org/wikipedia/benchmark/evergreen/native/NativeEvergreenInstrumentation.kt",
        destination / "NativeEvergreenInstrumentation.kt",
    )


def hidden_compile(platform: str, candidate: Path, log: Path, timeout: float) -> int:
    if platform == "android":
        inject_android_evaluator(candidate)
        command = [str(GRADLE), "-p", str(candidate), "--no-daemon", "--offline", ":app:assembleDebug", ":app:assembleDebugAndroidTest"]
        with REF.android_build_slot(candidate):
            return REF.run_logged(command, candidate, log, timeout, environment(candidate, platform), True)
    command = ["python3", str(MIGRATION / "evaluator/build_arkts_calibration.py"), "--project", str(candidate)]
    return REF.run_logged(command, MIGRATION, log, timeout, environment(candidate, platform), True)


def prepare_control(platform: str, role: str, candidate: Path) -> None:
    source = MIGRATION / (f"android/native/{role}" if platform == "android" else f"arkts/{role}")
    REF.copy_candidate(source, candidate)
    if platform == "android":
        sanitize_android(candidate)


def run_parity_validator(output: Path) -> dict[str, Any]:
    command = [
        "python3", str(PARITY_VALIDATOR),
        "--android", str(MIGRATION / "android/bindings.json"),
        "--arkts", str(MIGRATION / "arkts/bindings.json"),
        "--output", str(output),
    ]
    completed = subprocess.run(command, text=True, capture_output=True, check=False)
    payload = load(output) if output.is_file() else {}
    return {"passed": completed.returncode == 0 and payload.get("valid") is True, "exitCode": completed.returncode,
            "output": artifact(output) if output.is_file() else None}


def mark_ephemeral(value: Any, temporary_root: Path) -> Any:
    if isinstance(value, dict):
        result = {key: mark_ephemeral(item, temporary_root) for key, item in value.items()}
        path = result.get("path")
        if isinstance(path, str) and path.startswith(str(temporary_root)):
            result["path"] = None
            result["capture"] = "ephemeral preflight artifact; hash and byte count retained"
        return result
    if isinstance(value, list):
        return [mark_ephemeral(item, temporary_root) for item in value]
    return value


def cli_help_valid() -> bool:
    root_parser = parser()
    subparsers = next(action for action in root_parser._actions if isinstance(action, argparse._SubParsersAction))
    preflight_help = subparsers.choices["preflight"].format_help()
    run_help = subparsers.choices["run"].format_help()
    return (all(token in root_parser.format_help() for token in ("preflight", "run"))
            and "--output" in preflight_help
            and all(token in run_help for token in ("--authorize-opencode-and-devices", "--timeout", "--platform")))


def preflight(output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    free = require_space(ROOT)
    parity = run_parity_validator(output_dir / "transition-parity.json")
    result: dict[str, Any] = {
        "schemaVersion": 1,
        "taskId": TASK_ID,
        "runner": artifact(Path(__file__).resolve()),
        "referenceRunner": artifact(REFERENCE_RUNNER),
        "recursiveAuditHelper": artifact(AUDIT_HELPER),
        "model": MODEL,
        "endpoint": ENDPOINT,
        "overallTimeoutSeconds": OVERALL_TIMEOUT_SECONDS,
        "modelMaxSeconds": MODEL_MAX_SECONDS,
        "metricPolicy": "Only code generation rate, standalone application compile pass rate, and semantic testcase pass rate are benchmark metrics. Adapter, provider, isolation, and transport states are diagnostics; notScored is excluded from pass/fail.",
        "opencodeExecutablePresent": shutil.which("opencode") is not None,
        "minimaxCredentialFilePresent": (Path.home() / ".config/opencode/secrets/minimax-m3-key").is_file(),
        "opencodeInvoked": False,
        "deviceCommandsInvoked": False,
        "networkRequestsInvoked": False,
        "subagentsAllowed": True,
        "candidateVisibility": ["base production project", "requirement.md", "public transitions without expected observations"],
        "forbidden": ["network", "parent directories", "final", "evaluator", "reports", "results"],
        "cliHelpValidated": cli_help_valid(),
        "freeBytesBefore": free,
        "parity": parity,
        "platforms": [],
    }
    with tempfile.TemporaryDirectory(prefix="wikipedia05-agent-preflight-") as temporary:
        root = Path(temporary)
        for platform in PLATFORMS:
            platform_dir = output_dir / platform
            platform_dir.mkdir(parents=True, exist_ok=True)
            candidate = root / "visible" / platform
            build, prompt = prepare_visible_candidate(platform, candidate)
            static = static_candidate_audit(platform, candidate, build, prompt)
            visible_exit = run_build(platform, candidate, build, platform_dir / "visible-base-build.log", 1200)
            REF.cleanup_builds(candidate, platform_dir / "visible-base-cleanup.json")
            baseline, baseline_evidence, protected = initialize_baseline(candidate, platform_dir)
            empty_patch = REF.archive_patch(candidate, platform_dir / "empty.patch", baseline)
            protected_audit = verify_protected(candidate, protected)
            controls = []
            for role in ("base", "final"):
                control = root / "controls" / platform / role
                prepare_control(platform, role, control)
                compile_exit = hidden_compile(platform, control, platform_dir / f"hidden-{role}-compile.log", 1200)
                REF.cleanup_builds(control, platform_dir / f"hidden-{role}-cleanup.json")
                controls.append({"role": role, "compileExit": compile_exit, "passed": compile_exit == 0,
                                 "runtimeExecuted": False, "reason": "device-free preflight"})
            row = {
                **static,
                "visibleBaseCompile": {"exitCode": visible_exit, "passed": visible_exit == 0},
                "hiddenControlCompile": controls,
                "baseline": baseline_evidence,
                "protectedInputAudit": protected_audit,
                "emptyPatchArchive": empty_patch,
                "temporaryCandidatesRemovedAfterPreflight": True,
            }
            row["passed"] = (static["passed"] and visible_exit == 0 and protected_audit["passed"]
                             and empty_patch["reconstructionVerified"] and all(item["passed"] for item in controls))
            result["platforms"].append(mark_ephemeral(row, root))
    result["freeBytesAfter"] = shutil.disk_usage(ROOT).free
    result["passed"] = parity["passed"] and result["cliHelpValidated"] and all(row["passed"] for row in result["platforms"])
    result["status"] = "ready_for_explicit_formal_authorization" if result["passed"] else "preflight_failed"
    result["generatedAt"] = datetime.now().astimezone().isoformat(timespec="seconds")
    dump(output_dir / "preflight.json", result)
    return result


def source_manifest(platform: str, candidate: Path, output: Path) -> dict[str, Any]:
    root = candidate / ("app/src/main" if platform == "android" else "entry/src/main")
    suffixes = {".kt", ".java", ".xml"} if platform == "android" else {".ets", ".ts", ".json5", ".json"}
    files = []
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.suffix.lower() in suffixes:
            files.append({"path": path.relative_to(candidate).as_posix(), "bytes": path.stat().st_size, "sha256": sha256(path)})
    payload = {"schemaVersion": 1, "platform": platform, "classification": "agent candidate production bytes",
               "sourceObserver": False, "files": files}
    dump(output, payload)
    return artifact(output)


def semantic_metrics(report: dict[str, Any]) -> dict[str, Any]:
    summary = report.get("summary", {})
    passed = int(summary.get("pass", 0))
    failed = int(summary.get("fail", 0))
    not_scored = int(summary.get("notScored", 0))
    scored = passed + failed
    return {"passed": passed, "failed": failed, "notScored": not_scored, "scored": scored,
            "total": int(summary.get("total", passed + failed + not_scored)),
            "rate": round(passed / scored, 6) if scored else None,
            "policy": "notScored is excluded from pass and fail"}


def execute_hidden(platform: str, candidate: Path, run_dir: Path, deadline: float,
                   hdc_target: str) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    build_exit = hidden_compile(platform, candidate, run_dir / "hidden-runtime-build.log", remaining(deadline, "hidden_runtime_build"))
    diagnostics: dict[str, Any] = {"runtimeCompileExit": build_exit,
                                   "classification": "adapter/transport diagnostic, excluded from application compile metric"}
    if build_exit:
        return None, diagnostics
    output = run_dir / "semantic.json"
    if platform == "android":
        command = ["python3", str(MIGRATION / "evaluator/run_android_semantics.py"), "--project", str(candidate),
                   "--role", "agent", "--output", str(output)]
        env = environment(candidate, platform)
    else:
        command = ["python3", str(MIGRATION / "evaluator/run_arkts_semantics.py"), "--project", str(candidate),
                   "--role", "agent", "--output", str(output), "--target", hdc_target]
        env = environment(candidate, platform, hdc_target)
    semantic_exit = REF.run_logged(command, MIGRATION, run_dir / "semantic-runtime.log",
                                   remaining(deadline, "semantic_runtime"), env)
    diagnostics.update(semanticExit=semantic_exit, semanticCommand=command)
    return (load(output), diagnostics) if output.is_file() else (None, diagnostics)


def generation_snapshot(candidate: Path, platform: str) -> tuple[list[str], dict[str, Any]]:
    changed = REF.changed_paths(candidate)
    production = REF.production_files(changed, platform)
    return changed, REF.generation_audit(candidate, production)


def remove_stale_outputs(platform: str) -> None:
    for path in (
        MIGRATION / "results" / f"{platform}-agent.json",
        MIGRATION / "results" / f"{platform}-agent.raw.json",
        MIGRATION / "results/agent-patches" / f"{platform}-agent.patch",
        MIGRATION / "results/agent-patches" / f"{platform}-agent-generated-files.json",
    ):
        path.unlink(missing_ok=True)


def run_one(platform: str, run_id: str, candidate_root: Path, hdc_target: str) -> dict[str, Any]:
    run_dir = MIGRATION / "results/agent-runs" / run_id / platform
    run_dir.mkdir(parents=True, exist_ok=True)
    candidate = candidate_root / platform
    started = time.monotonic()
    deadline = started + OVERALL_TIMEOUT_SECONDS
    result: dict[str, Any] = {
        "schemaVersion": 1, "runId": run_id, "taskId": TASK_ID, "platform": platform,
        "runner": "OpenCode", "model": MODEL, "endpoint": ENDPOINT,
        "overallTimeoutSeconds": OVERALL_TIMEOUT_SECONDS, "subagentsAllowed": True,
        "semanticFeedbackDuringGeneration": False, "apiKeyRecorded": False,
        "availability": "environment_failure", "benchmarkMetricsAvailable": False,
        "startedAt": datetime.now().astimezone().isoformat(timespec="seconds"),
    }
    try:
        remove_stale_outputs(platform)
        require_space(candidate_root)
        build, prompt = prepare_visible_candidate(platform, candidate)
        static = static_candidate_audit(platform, candidate, build, prompt)
        if not static["passed"]:
            raise RuntimeError("candidate visibility audit failed")
        preflight_exit = run_build(platform, candidate, build, run_dir / "preflight-build.log",
                                   min(1200, remaining(deadline, "visible_preflight")))
        if preflight_exit:
            raise RuntimeError(f"clean visible base build failed with exit {preflight_exit}")
        REF.cleanup_builds(candidate, run_dir / "preflight-cleanup.json")
        baseline, baseline_evidence, protected = initialize_baseline(candidate, run_dir)
        result.update(candidateBaseline={"static": static, **baseline_evidence}, publicBuildCommand=build)
        log = run_dir / "opencode.jsonl"
        allowance = min(MODEL_MAX_SECONDS, remaining(deadline, "agent"))
        result["agentGrantedSeconds"] = allowance
        command = ["opencode", "run", "--standalone", "--model", MODEL, "--format", "json",
                   "--title", f"Wikipedia {TASK_ID} {platform}", prompt]
        result["agentCommand"] = [*command[:-1], "<task-local prompt sha256:" + hashlib.sha256(prompt.encode()).hexdigest() + ">"]
        try:
            agent_exit = REF.run_logged(command, candidate, log, allowance, environment(candidate, platform, hdc_target), True)
            timed_out = False
        except subprocess.TimeoutExpired:
            agent_exit, timed_out = 124, True
        result.update(agentExit=agent_exit, agentTimedOut=timed_out)
        REF.cleanup_builds(candidate, run_dir / "agent-build-cleanup.json")
        protected_audit = verify_protected(candidate, protected)
        changed, generation = generation_snapshot(candidate, platform)
        patch = REF.archive_patch(candidate, run_dir / f"{platform}-agent.patch", baseline)
        dump(run_dir / f"{platform}-agent-generated-files.json", {
            "schemaVersion": 1, "changedFiles": changed,
            "generatedProductionFiles": generation["changedProductionFiles"], "audit": generation,
        })
        result.update(protectedInputAudit=protected_audit, candidatePatch=patch, codeGeneration=generation)
        external = REF.provider_failure(log)
        if external:
            result.update(availability=external, externalFailure=True)
            return result
        if timed_out:
            result.update(availability="model_timeout", externalFailure=False)
            return result
        if not protected_audit["passed"]:
            result.update(availability="protected_input_integrity_failure", externalFailure=False)
            return result
        isolation = REF.audit_sessions(log, candidate, build, run_dir / "isolation-audit.json", deadline)
        result["isolationAudit"] = isolation
        if isolation["availability"] != "available":
            result["availability"] = isolation["availability"]
            return result
        compile_exit = run_build(platform, candidate, build, run_dir / "production-build.log",
                                 remaining(deadline, "production_build"))
        compile_result = {"passed": compile_exit == 0, "exitCode": compile_exit, "command": build,
                          "scope": "standalone candidate application production compile"}
        result["compile"] = compile_result
        REF.cleanup_builds(candidate, run_dir / "production-build-cleanup.json")
        result["candidateSourceManifest"] = source_manifest(platform, candidate, run_dir / "candidate-source-manifest.json")
        report, diagnostics = execute_hidden(platform, candidate, run_dir, deadline, hdc_target)
        result["diagnostics"] = diagnostics
        if report is None:
            result.update(availability="evaluation_failure", benchmarkMetricsAvailable=False)
            return result
        metrics = semantic_metrics(report)
        report["codeGeneration"] = generation
        report["compile"] = compile_result
        report.setdefault("diagnostics", {})["runtimeCompile"] = diagnostics
        dump(run_dir / "semantic.json", report)
        result.update(availability="available", benchmarkMetricsAvailable=True, semanticTestcase=metrics,
                      semanticReport=artifact(run_dir / "semantic.json"),
                      rawSemanticReport=artifact(run_dir / "semantic.raw.json") if (run_dir / "semantic.raw.json").is_file() else None)
        shutil.copy2(run_dir / "semantic.json", MIGRATION / "results" / f"{platform}-agent.json")
        if (run_dir / "semantic.raw.json").is_file():
            shutil.copy2(run_dir / "semantic.raw.json", MIGRATION / "results" / f"{platform}-agent.raw.json")
        patches = MIGRATION / "results/agent-patches"
        patches.mkdir(parents=True, exist_ok=True)
        shutil.copy2(run_dir / f"{platform}-agent.patch", patches / f"{platform}-agent.patch")
        shutil.copy2(run_dir / f"{platform}-agent-generated-files.json", patches / f"{platform}-agent-generated-files.json")
        return result
    except TimeoutError as error:
        result.update(availability="overall_timeout", reason=str(error), benchmarkMetricsAvailable=False)
        return result
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        result.update(availability="environment_failure", reason=f"{type(error).__name__}: {error}", benchmarkMetricsAvailable=False)
        return result
    finally:
        cleanup_error = None
        try:
            if candidate.exists():
                REF.cleanup_builds(candidate, run_dir / "final-cleanup-artifacts.json")
                shutil.rmtree(candidate)
        except OSError as error:
            cleanup_error = str(error)
        result.update(
            finishedAt=datetime.now().astimezone().isoformat(timespec="seconds"),
            durationSeconds=round(time.monotonic() - started, 3),
            timingScope="One 3600s top-level deadline covers clean-room preflight, OpenCode, recursive subagent audit, application compile, native semantic scoring, and cleanup; subagent durations are not added.",
            cleanup={"completed": not candidate.exists(), "error": cleanup_error},
        )
        result["credentialAudit"] = REF.redact_secret_artifacts(run_dir)
        REF.finalize_metric_availability(result)
        dump(run_dir / "run.json", result)


def summarize(rows: list[dict[str, Any]], run_id: str) -> dict[str, Any]:
    measured = [row for row in rows if row.get("benchmarkMetricsAvailable")]
    code_pass = sum(row.get("codeGeneration", {}).get("passed") is True for row in measured)
    compile_pass = sum(row.get("compile", {}).get("passed") is True for row in measured)
    semantic_pass = sum(row.get("semanticTestcase", {}).get("passed", 0) for row in measured)
    semantic_scored = sum(row.get("semanticTestcase", {}).get("scored", 0) for row in measured)
    not_scored = sum(row.get("semanticTestcase", {}).get("notScored", 0) for row in measured)
    payload = {
        "schemaVersion": 1, "runId": run_id, "taskId": TASK_ID, "model": MODEL, "endpoint": ENDPOINT,
        "runs": rows,
        "benchmarkMetrics": {
            "codeGeneration": {"passed": code_pass, "total": len(measured), "rate": round(code_pass / len(measured), 6) if measured else None},
            "compile": {"passed": compile_pass, "total": len(measured), "rate": round(compile_pass / len(measured), 6) if measured else None},
            "semanticTestcase": {"passed": semantic_pass, "scored": semantic_scored, "notScored": not_scored,
                                 "rate": round(semantic_pass / semantic_scored, 6) if semantic_scored else None},
        },
        "metricPolicy": "Only code generation rate, standalone application compile pass rate, and semantic testcase pass rate are benchmark metrics. Adapter, provider, isolation, and transport states are diagnostics.",
    }
    dump(MIGRATION / "results/agent-evaluation-summary.json", payload)
    return payload


def command_preflight(args: argparse.Namespace) -> int:
    result = preflight(args.output.resolve())
    print(json.dumps({"status": result["status"], "passed": result["passed"],
                      "report": str((args.output / "preflight.json").resolve())}, ensure_ascii=False))
    return 0 if result["passed"] else 2


def command_run(args: argparse.Namespace) -> int:
    if not args.authorize_opencode_and_devices:
        raise ValueError("formal run requires --authorize-opencode-and-devices from the main thread")
    if args.timeout != OVERALL_TIMEOUT_SECONDS:
        raise ValueError("Wikipedia 05 requires exactly 3600 seconds per top-level platform run")
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", args.run_id):
        raise ValueError("run id must contain lowercase letters, digits, underscores, and hyphens only")
    platforms = PLATFORMS if args.platform == "all" else (args.platform,)
    candidate_root = (args.candidate_root or ROOT.parent / ".ltb-wikipedia-05-agent" / args.run_id).resolve()
    candidate_root.mkdir(parents=True, exist_ok=True)
    rows = []
    for platform in platforms:
        print(json.dumps({"event": "run_start", "taskId": TASK_ID, "platform": platform}), flush=True)
        row = run_one(platform, args.run_id, candidate_root, args.hdc_target)
        rows.append(row)
        print(json.dumps({"event": "run_complete", "platform": platform, "availability": row["availability"],
                          "semantic": row.get("semanticTestcase")}), flush=True)
    summarize(rows, args.run_id)
    shutil.rmtree(candidate_root, ignore_errors=True)
    return 0 if len(rows) == len(platforms) and all(row.get("benchmarkMetricsAvailable") for row in rows) else 2


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description="Wikipedia 05 isolated OpenCode + MiniMax-M3 agent evaluation runner")
    subparsers = value.add_subparsers(dest="command", required=True)
    check = subparsers.add_parser("preflight", help="device-free clean-room, policy, build, and hidden ABI checks; never invokes OpenCode")
    check.add_argument("--output", type=Path, default=MIGRATION / "provenance/agent-runner-preflight")
    check.set_defaults(handler=command_preflight)
    run = subparsers.add_parser("run", help="formal generation and native scoring; requires explicit authorization")
    run.add_argument("--authorize-opencode-and-devices", action="store_true")
    run.add_argument("--platform", choices=("all", *PLATFORMS), default="all")
    run.add_argument("--run-id", default=f"wikipedia-05-minimax-m3-{datetime.now():%Y%m%d-%H%M%S}")
    run.add_argument("--timeout", type=int, default=OVERALL_TIMEOUT_SECONDS)
    run.add_argument("--candidate-root", type=Path)
    run.add_argument("--hdc-target", default="127.0.0.1:10178")
    run.set_defaults(handler=command_run)
    return value


def main() -> int:
    args = parser().parse_args()
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
