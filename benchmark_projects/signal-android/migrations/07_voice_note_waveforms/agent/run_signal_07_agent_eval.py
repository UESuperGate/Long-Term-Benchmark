#!/usr/bin/env python3
"""Prepare and, when explicitly authorized, run the isolated Signal 07 agent eval.

The safe default surface is static preflight. The ``run`` subcommand is intentionally
gated because it invokes OpenCode and native-device evaluators.
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
import stat
import subprocess
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Any


TASK_ID = "07_voice_note_waveforms"
PLATFORMS = ("android", "arkts")
MODEL = "minimax-token-plan/MiniMax-M3"
ENDPOINT = "https://api.minimaxi.com/v1"
OVERALL_TIMEOUT_SECONDS = 3600
MODEL_MAX_SECONDS = 3000
MIN_FREE_BYTES = 8 * 1024**3

MIGRATION = Path(__file__).resolve().parents[1]
PROJECT = MIGRATION.parents[1]
ROOT = PROJECT.parents[1]
TASK = PROJECT / "tasks" / TASK_ID
REFERENCE_RUNNER = PROJECT / "migrations/tools/run_signal_03_06_agent_eval.py"
PARITY_VALIDATOR = ROOT / "skills/migration-skill/scripts/validate_transition_parity.py"
AUDIT_HELPER = ROOT / "scripts/opencode_subagent_audit.py"

GRADLE = Path.home() / ".gradle/wrapper/dists/gradle-8.14.3-bin/cv11ve7ro1n3o1j4so8xd9n66/gradle-8.14.3/bin/gradle"
GRADLE_JDK = Path("/opt/homebrew/Cellar/openjdk@17/17.0.18/libexec/openjdk.jdk/Contents/Home")
ANDROID_STUDIO_JBR = Path("/Applications/Android Studio.app/Contents/jbr/Contents/Home")
ANDROID_SDK = Path.home() / "Library/Android/sdk"
DEVECO_JBR = Path("/Applications/DevEco-Studio.app/Contents/jbr/Contents/Home")
HVIGOR = Path("/Applications/DevEco-Studio.app/Contents/tools/hvigor/bin/hvigorw")
OH_SDK = Path.home() / "Library/OpenHarmony/Sdk/23"
HDC = OH_SDK / "toolchains/hdc"

ANDROID_BUILD_LOCK = "/tmp/long-term-benchmark-android-full-build.lock"
ANDROID_DEVICE_LOCK = "/tmp/long-term-benchmark-android-device.lock"
ARKTS_BUILD_LOCK = "/tmp/long-term-benchmark-full-build.lock"


def load_reference() -> Any:
    spec = importlib.util.spec_from_file_location("signal_03_06_agent_reference", REFERENCE_RUNNER)
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


def environment(candidate: Path, hdc_target: str | None = None) -> dict[str, str]:
    env = os.environ.copy()
    env.update({
        "PWD": str(candidate),
        "OLDPWD": str(candidate),
        "JAVA_HOME": str(DEVECO_JBR),
        "ANDROID_HOME": str(ANDROID_SDK),
        "ANDROID_SDK_ROOT": str(ANDROID_SDK),
        "OHOS_BASE_SDK_HOME": str(OH_SDK.parent),
        "DEVECO_SDK_HOME": str(OH_SDK),
        "HDC": str(HDC),
    })
    if hdc_target:
        env["HDC_TARGET"] = hdc_target
    env["PATH"] = os.pathsep.join([
        str(DEVECO_JBR / "bin"),
        str(ANDROID_SDK / "platform-tools"),
        str(HVIGOR.parent),
        "/Applications/DevEco-Studio.app/Contents/tools/ohpm/bin",
        env.get("PATH", ""),
    ])
    return env


def android_environment(candidate: Path) -> dict[str, str]:
    env = environment(candidate)
    env["JAVA_HOME"] = str(ANDROID_STUDIO_JBR)
    env["PATH"] = os.pathsep.join([str(ANDROID_STUDIO_JBR / "bin"), env.get("PATH", "")])
    return env


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


def path_policy(candidate: Path, *, allow_scaffold_read: bool) -> dict[str, str]:
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
    if not allow_scaffold_read:
        for relative in (".git", "_benchmark_scaffold"):
            for pattern in (relative, f"{relative}/*", f"{relative}/**", f"{root}/{relative}", f"{root}/{relative}/*", f"{root}/{relative}/**"):
                policy[pattern] = "deny"
    return policy


def opencode_config(candidate: Path, build_command: list[str]) -> dict[str, Any]:
    root = str(candidate.resolve())
    reads = path_policy(candidate, allow_scaffold_read=False)
    edits = path_policy(candidate, allow_scaffold_read=False)
    for relative in ("_benchmark_inputs", "_benchmark_scaffold", ".git"):
        for pattern in (relative, f"{relative}/*", f"{relative}/**", f"{root}/{relative}", f"{root}/{relative}/*", f"{root}/{relative}/**"):
            edits[pattern] = "deny"
    for relative in ("build-agent.sh", "opencode.json"):
        edits[relative] = "deny"
        edits[f"{root}/{relative}"] = "deny"
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
            "final, benchmark evaluator, report, result, or hidden paths."
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


def write_build_scaffold(candidate: Path, platform: str) -> list[str]:
    scaffold = candidate / "_benchmark_scaffold"
    scaffold.mkdir()
    shutil.copy2(PROJECT / "migrations/tools/with_device_lock.py", scaffold / "with_device_lock.py")
    if platform == "android":
        body = f"""#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")" && pwd)"
export ANDROID_HOME="{ANDROID_SDK}"
export ANDROID_SDK_ROOT="$ANDROID_HOME"
export JAVA_HOME="{ANDROID_STUDIO_JBR}"
export PATH="$JAVA_HOME/bin:$PATH"
test -x "$JAVA_HOME/bin/java" && test -x "$JAVA_HOME/bin/jlink"
test -x "{GRADLE_JDK}/bin/java" && test -x "{GRADLE_JDK}/bin/jlink"
python3 "$root/_benchmark_scaffold/with_device_lock.py" --lock {ANDROID_BUILD_LOCK} -- \
  "{GRADLE}" -Dorg.gradle.java.home="{GRADLE_JDK}" -p "$root" --no-daemon --offline :app:assembleDebug
"""
    else:
        body = f"""#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")" && pwd)"
export OHOS_BASE_SDK_HOME="{OH_SDK.parent}"
export JAVA_HOME="{DEVECO_JBR}"
python3 "$root/_benchmark_scaffold/with_device_lock.py" --lock {ARKTS_BUILD_LOCK} -- \
  "{HVIGOR}" --mode module -p product=default -p module=entry@default assembleHap --no-daemon
"""
    build = candidate / "build-agent.sh"
    build.write_text(body, encoding="utf-8")
    build.chmod(0o755)
    return ["bash", "build-agent.sh"]


def prompt_for(platform: str, build_command: list[str]) -> str:
    platform_note = (
        "The Android page owner is WaveformPageOwner and its Activity wiring is visible under app/src/main."
        if platform == "android" else
        "The ArkUI page owner is WaveformPageOwner; its EntryAbility and Index wiring are visible under entry/src/main/ets."
    )
    return f"""Implement {TASK_ID} completely in this {platform} candidate.

Read `_benchmark_inputs/requirement.md` and `_benchmark_inputs/public_transitions.json`. Inspect the visible base and implement the requested behavior in real production code. {platform_note}

Rules:
- Work only in this candidate directory. Never inspect parent, sibling, home, network, final, evaluator, report, result, or hidden paths.
- Subagents are allowed and inherit exactly the same workspace boundary.
- Do not create case-ID switches, marker facts, semantic projections, evaluator APIs, or source-observer shortcuts.
- Preserve unrelated behavior. Implement application-owned state, persistence, effects, page wiring, failure recovery, and cleanup.
- Run `{shlex.join(build_command)}` exactly as written and repair production compilation within the task budget.

Finish with a concise summary of changed production files and remaining blockers.
"""


def prepare_candidate(platform: str, candidate: Path) -> tuple[list[str], str]:
    REF.copy_candidate(MIGRATION / platform / "base", candidate)
    if platform == "android":
        gradle_file = candidate / "app/build.gradle"
        source = gradle_file.read_text(encoding="utf-8")
        test_runner = "        testInstrumentationRunner 'org.signal.benchmark.waveform.evaluator.VoiceWaveformInstrumentation'\n"
        evaluator_sources = """
    sourceSets {
        androidTest.java.srcDirs += '../../evaluator/androidTest/java'
    }
"""
        if test_runner not in source or evaluator_sources not in source:
            raise RuntimeError("Android base evaluator wiring changed; refusing an incomplete clean-room copy")
        gradle_file.write_text(source.replace(test_runner, "").replace(evaluator_sources, ""), encoding="utf-8")
    build_command = write_build_scaffold(candidate, platform)
    inputs = candidate / "_benchmark_inputs"
    inputs.mkdir()
    shutil.copy2(TASK / "requirement.md", inputs / "requirement.md")
    contract = load(MIGRATION / "canonical/transitions.json")
    dump(inputs / "public_transitions.json", public_transitions(contract))
    prompt = prompt_for(platform, build_command)
    dump(candidate / "opencode.json", opencode_config(candidate, build_command))
    return build_command, prompt


def walk_keys(value: Any) -> set[str]:
    if isinstance(value, dict):
        return set(value) | set().union(*(walk_keys(item) for item in value.values()), set())
    if isinstance(value, list):
        return set().union(*(walk_keys(item) for item in value), set())
    return set()


def static_candidate_audit(platform: str, candidate: Path, build: list[str], prompt: str) -> dict[str, Any]:
    public = load(candidate / "_benchmark_inputs/public_transitions.json")
    keys = walk_keys(public)
    leaked = sorted(keys & {"expected", "traceDigest", "evidence", "polarity", "key", "bindings"})
    files = sorted(path.relative_to(candidate).as_posix() for path in candidate.rglob("*") if path.is_file())
    forbidden_components = {"final", "evaluator", "evaluators", "report", "reports", "results"}
    exposed = [path for path in files if {part.lower() for part in Path(path).parts} & forbidden_components]
    config = load(candidate / "opencode.json")
    permission = config["permission"]
    shell = permission["shell"]
    root = str(candidate.resolve())
    config_checks = {
        "defaultDenied": permission.get("*") == "deny",
        "networkDenied": permission.get("webfetch") == "deny" and permission.get("websearch") == "deny",
        "externalDirectoryDenied": permission.get("external_directory") == "deny",
        "subagentsAllowed": permission.get("task") == "allow",
        "parentDenied": permission["read"].get("../**") == "deny" and permission["read"].get("/*") == "deny",
        "candidateReallowed": permission["read"].get(f"{root}/**") == "allow",
        "scaffoldUnreadable": permission["read"].get("_benchmark_scaffold/**") == "deny",
        "inputsImmutable": permission["edit"].get("_benchmark_inputs/**") == "deny",
        "shellDefaultDenied": shell.get("*") == "deny",
        "exactBuildAllowed": shell.get(shlex.join(build)) == "allow",
    }
    public_cases = public.get("cases", [])
    passed = (
        public.get("taskId") == TASK_ID
        and len(public_cases) == 10
        and not leaked
        and not exposed
        and all(config_checks.values())
        and str(MIGRATION / "final") not in prompt
    )
    return {
        "platform": platform,
        "passed": passed,
        "candidateFileCount": len(files),
        "candidateFiles": files,
        "publicCaseCount": len(public_cases),
        "forbiddenPublicKeys": leaked,
        "forbiddenVisiblePaths": exposed,
        "configurationChecks": config_checks,
        "publicRequirement": artifact(candidate / "_benchmark_inputs/requirement.md"),
        "publicTransitions": artifact(candidate / "_benchmark_inputs/public_transitions.json"),
        "promptSha256": hashlib.sha256(prompt.encode()).hexdigest(),
        "buildCommand": build,
    }


def run_parity_validator(output: Path) -> dict[str, Any]:
    command = [
        "python3", str(PARITY_VALIDATOR),
        "--android", str(MIGRATION / "android/bindings.json"),
        "--arkts", str(MIGRATION / "arkts/bindings.json"),
        "--output", str(output),
    ]
    completed = subprocess.run(command, text=True, capture_output=True, check=False)
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        payload = {}
    return {"passed": completed.returncode == 0 and payload.get("valid") is True, "exitCode": completed.returncode, "output": artifact(output)}


def mark_ephemeral_paths(value: Any, temporary_root: Path) -> Any:
    if isinstance(value, dict):
        result = {key: mark_ephemeral_paths(item, temporary_root) for key, item in value.items()}
        path = result.get("path")
        if isinstance(path, str) and path.startswith(str(temporary_root)):
            result["path"] = None
            result["capture"] = "ephemeral preflight artifact; hash and byte count retained"
        return result
    if isinstance(value, list):
        return [mark_ephemeral_paths(item, temporary_root) for item in value]
    return value


def preflight(output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    free = require_space(ROOT)
    parity = run_parity_validator(output_dir / "parity.json")
    checks: dict[str, Any] = {
        "runner": artifact(Path(__file__).resolve()),
        "referenceRunner": artifact(REFERENCE_RUNNER),
        "recursiveAuditHelper": artifact(AUDIT_HELPER),
        "requirement": artifact(TASK / "requirement.md"),
        "canonicalContract": artifact(MIGRATION / "canonical/transitions.json"),
        "model": MODEL,
        "endpoint": ENDPOINT,
        "overallTimeoutSeconds": OVERALL_TIMEOUT_SECONDS,
        "modelMaxSeconds": MODEL_MAX_SECONDS,
        "metricPolicy": "Only code generation, standalone application compile, and semantic testcase pass rate are benchmark metrics. Adapter and transport are diagnostics; notScored is excluded from pass/fail.",
        "opencodeExecutablePresent": shutil.which("opencode") is not None,
        "minimaxCredentialFilePresent": (Path.home() / ".config/opencode/secrets/minimax-m3-key").is_file(),
        "opencodeInvoked": False,
        "deviceCommandsInvoked": False,
        "networkRequestsInvoked": False,
        "cliHelpValidated": all(token in parser().format_help() for token in ("preflight", "run")),
        "freeBytes": free,
        "parity": parity,
        "platforms": [],
    }
    with tempfile.TemporaryDirectory(prefix="signal07-agent-preflight-") as temporary:
        root = Path(temporary)
        for platform in PLATFORMS:
            candidate = root / TASK_ID / platform / "base"
            build, prompt = prepare_candidate(platform, candidate)
            audit = static_candidate_audit(platform, candidate, build, prompt)
            run_dir = root / "evidence" / platform
            baseline, baseline_evidence, protected = REF.initialize_baseline(candidate, run_dir)
            protected_audit = REF.verify_protected(candidate, protected)
            patch = REF.archive_patch(candidate, run_dir / "empty.patch", baseline)
            audit.update({
                "baseline": baseline_evidence,
                "protectedInputAudit": protected_audit,
                "emptyPatchArchive": patch,
                "temporaryCandidateRemovedAfterPreflight": True,
            })
            audit["passed"] = audit["passed"] and protected_audit["passed"] and patch["reconstructionVerified"]
            checks["platforms"].append(mark_ephemeral_paths(audit, root))
    checks["passed"] = parity["passed"] and all(row["passed"] for row in checks["platforms"])
    checks["generatedAt"] = datetime.now().astimezone().isoformat(timespec="seconds")
    checks["status"] = "ready_for_explicit_formal_authorization" if checks["passed"] else "preflight_failed"
    dump(output_dir / "preflight.json", checks)
    return checks


def remaining(deadline: float, phase: str) -> float:
    value = deadline - time.monotonic()
    if value <= 0:
        raise TimeoutError(f"overall 3600s deadline exhausted during {phase}")
    return value


def source_manifest(platform: str, candidate: Path, output: Path) -> dict[str, Any]:
    if platform == "android":
        roots = [candidate / "app/src/main"]
        suffixes = {".java", ".kt", ".xml"}
        payload: dict[str, Any] = {
            "schemaVersion": 1,
            "platform": platform,
            "apiVersion": 37,
            "sourceObserver": False,
            "classification": "agent_candidate_production_bytes",
            "files": [],
        }
    else:
        roots = [candidate / "entry/src/main/ets"]
        suffixes = {".ets", ".ts"}
        payload = {
            "schemaVersion": 1,
            "platform": platform,
            "apiVersion": 23,
            "sourceObserver": False,
            "classification": "agent_candidate_production_bytes",
            "files": [],
        }
    for root in roots:
        for path in sorted(root.rglob("*")):
            if path.is_file() and path.suffix.lower() in suffixes:
                payload["files"].append({
                    "path": path.relative_to(candidate).as_posix(),
                    "sha256": sha256(path),
                    "bytes": path.stat().st_size,
                })
    dump(output, payload)
    return artifact(output)


def public_build_command(platform: str) -> list[str]:
    return ["bash", "build-agent.sh"]


def hidden_evaluation(platform: str, candidate: Path, run_dir: Path, deadline: float, hdc_target: str | None) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    output = run_dir / "semantic.json"
    if platform == "android":
        hidden = candidate.parent / "evaluator"
        shutil.copytree(MIGRATION / "android/evaluator", hidden)
        gradle_file = candidate / "app/build.gradle"
        source = gradle_file.read_text(encoding="utf-8")
        source += """

// Evaluator-owned overlay injected only after the agent process exits.
android {
    defaultConfig {
        testInstrumentationRunner 'org.signal.benchmark.waveform.evaluator.VoiceWaveformInstrumentation'
    }
    sourceSets {
        androidTest.java.srcDirs += '../../evaluator/androidTest/java'
    }
}
"""
        gradle_file.write_text(source, encoding="utf-8")
        command = [
            "python3", str(PROJECT / "migrations/tools/with_device_lock.py"), "--lock", ANDROID_BUILD_LOCK, "--",
            str(GRADLE), f"-Dorg.gradle.java.home={GRADLE_JDK}", "-p", str(candidate), "--no-daemon", "--offline",
            ":app:assembleDebug", ":app:assembleDebugAndroidTest",
        ]
        build_exit = REF.run_logged(command, candidate, run_dir / "runtime-build.log", remaining(deadline, "runtime_compile"), android_environment(candidate), True)
        diagnostics: dict[str, Any] = {"runtimeCompileExit": build_exit, "runtimeCompileCommand": command, "classification": "adapter/transport diagnostic, excluded from compile metric"}
        if build_exit:
            return None, diagnostics
        semantic = [
            "python3", str(PROJECT / "migrations/tools/with_device_lock.py"), "--lock", ANDROID_DEVICE_LOCK, "--",
            "python3", str(MIGRATION / "evaluator/run_android_semantics.py"), "--project", str(candidate),
            "--role", "agent", "--output", str(output),
        ]
        env = android_environment(candidate)
        env["LTB_ANDROID_DEVICE_LOCK_HELD"] = "1"
    else:
        diagnostics = {"classification": "adapter/transport diagnostic, excluded from compile metric"}
        semantic = [
            "python3", str(MIGRATION / "evaluator/run_arkts_semantics.py"), "--project", str(candidate),
            "--role", "agent", "--output", str(output),
        ]
        env = environment(candidate, hdc_target or "127.0.0.1:10178")
    semantic_exit = REF.run_logged(semantic, candidate, run_dir / "runtime-semantic.log", remaining(deadline, "native_runtime"), env)
    diagnostics.update(semanticExit=semantic_exit, semanticCommand=semantic)
    return (load(output), diagnostics) if output.is_file() else (None, diagnostics)


def formal_preflight(platform: str, candidate: Path, run_dir: Path) -> tuple[list[str], str, dict[str, Any], dict[str, dict[str, Any]]]:
    require_space(candidate.parent)
    build, prompt = prepare_candidate(platform, candidate)
    static = static_candidate_audit(platform, candidate, build, prompt)
    if not static["passed"]:
        raise RuntimeError("candidate visibility preflight failed")
    code = REF.run_logged(build, candidate, run_dir / "preflight-build.log", 1200, environment(candidate), True)
    if code:
        raise RuntimeError(f"clean base public build failed with exit {code}")
    REF.cleanup_builds(candidate, run_dir / "preflight-artifacts.json")
    baseline, evidence, protected = REF.initialize_baseline(candidate, run_dir)
    return build, prompt, {"static": static, **evidence}, protected


def changed_production_files(candidate: Path, platform: str) -> tuple[list[str], dict[str, Any]]:
    paths = REF.changed_paths(candidate)
    generated = REF.production_files(paths, platform)
    return paths, REF.generation_audit(candidate, generated)


def remove_stale_outputs(platform: str) -> None:
    for path in (
        MIGRATION / "results" / f"{platform}-agent.json",
        MIGRATION / "results/agent-patches" / f"{platform}-agent.patch",
        MIGRATION / "results/agent-patches" / f"{platform}-agent-generated-files.json",
    ):
        path.unlink(missing_ok=True)


def run_one(platform: str, run_id: str, candidate_root: Path, hdc_target: str | None) -> dict[str, Any]:
    run_dir = MIGRATION / "results/agent-runs" / run_id / platform
    run_dir.mkdir(parents=True, exist_ok=True)
    candidate = candidate_root / TASK_ID / platform / "base"
    result: dict[str, Any] = {
        "schemaVersion": 1,
        "runId": run_id,
        "taskId": TASK_ID,
        "platform": platform,
        "runner": "OpenCode",
        "model": MODEL,
        "endpoint": ENDPOINT,
        "overallTimeoutSeconds": OVERALL_TIMEOUT_SECONDS,
        "subagentsAllowed": True,
        "semanticFeedbackDuringGeneration": False,
        "apiKeyRecorded": False,
        "availability": "environment_failure",
        "benchmarkMetricsAvailable": False,
    }
    started: float | None = None
    try:
        remove_stale_outputs(platform)
        build, prompt, evidence, protected = formal_preflight(platform, candidate, run_dir)
        result.update(candidateBaseline=evidence, publicBuildCommand=build)
        started = time.monotonic()
        deadline = started + OVERALL_TIMEOUT_SECONDS
        result["startedAt"] = datetime.now().astimezone().isoformat(timespec="seconds")
        log = run_dir / "opencode.jsonl"
        allowance = min(MODEL_MAX_SECONDS, remaining(deadline, "agent"))
        result["agentGrantedSeconds"] = allowance
        command = [
            "opencode", "run", "--standalone", "--model", MODEL, "--format", "json",
            "--title", f"Signal {TASK_ID} {platform}", prompt,
        ]
        result["agentCommand"] = [*command[:-1], "<task-local prompt sha256:" + hashlib.sha256(prompt.encode()).hexdigest() + ">"]
        try:
            agent_exit = REF.run_logged(command, candidate, log, allowance, environment(candidate, hdc_target), True)
            timed_out = False
        except subprocess.TimeoutExpired:
            agent_exit, timed_out = 124, True
        result.update(agentExit=agent_exit, agentTimedOut=timed_out)
        REF.cleanup_builds(candidate, run_dir / "agent-build-artifacts.json")
        protected_audit = REF.verify_protected(candidate, protected)
        result["protectedInputAudit"] = protected_audit
        changed, generation = changed_production_files(candidate, platform)
        patch = REF.archive_patch(candidate, run_dir / "agent.patch", evidence["archive"]["commit"])
        dump(run_dir / "generated-files.json", {"schemaVersion": 1, "changedFiles": changed, "generatedProductionFiles": generation["changedProductionFiles"], "audit": generation})
        result.update(candidatePatch=patch, codeGeneration=generation)
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
        compile_exit = REF.run_logged(build, candidate, run_dir / "production-build.log", remaining(deadline, "production_build"), environment(candidate, hdc_target), True)
        result["compile"] = {"passed": compile_exit == 0, "exitCode": compile_exit, "command": build, "scope": "standalone candidate application production compile"}
        REF.cleanup_builds(candidate, run_dir / "production-build-artifacts.json")
        manifest_path = run_dir / "candidate-source-manifest.json"
        result["candidateSourceManifest"] = source_manifest(platform, candidate, manifest_path)
        report, diagnostics = hidden_evaluation(platform, candidate, run_dir, deadline, hdc_target)
        result["diagnostics"] = diagnostics
        if report is None:
            report = REF.not_scored_report(TASK_ID, platform, "hidden runtime adapter did not compile, bind, or execute")
        metrics = REF.semantic_metrics(report)
        report["codeGeneration"] = generation
        report["compile"] = result["compile"]
        report.setdefault("diagnostics", {})["runtimeCompile"] = diagnostics
        dump(run_dir / "semantic.json", report)
        result.update(availability="available", benchmarkMetricsAvailable=True, semanticTestcase=metrics, semanticReport=artifact(run_dir / "semantic.json"))
        shutil.copy2(run_dir / "semantic.json", MIGRATION / "results" / f"{platform}-agent.json")
        patches = MIGRATION / "results/agent-patches"
        patches.mkdir(parents=True, exist_ok=True)
        shutil.copy2(run_dir / "agent.patch", patches / f"{platform}-agent.patch")
        shutil.copy2(run_dir / "generated-files.json", patches / f"{platform}-agent-generated-files.json")
        return result
    except TimeoutError as error:
        result.update(availability="overall_timeout", reason=str(error), benchmarkMetricsAvailable=False)
        return result
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        result.update(availability="environment_failure" if started is None else "evaluation_failure", reason=f"{type(error).__name__}: {error}", benchmarkMetricsAvailable=False)
        return result
    finally:
        cleanup_error = None
        try:
            if candidate.exists():
                REF.cleanup_builds(candidate, run_dir / "final-cleanup-artifacts.json")
                shutil.rmtree(candidate)
            hidden = candidate.parent / "evaluator"
            if hidden.exists():
                shutil.rmtree(hidden)
        except OSError as error:
            cleanup_error = str(error)
        if started is not None:
            result.update(
                finishedAt=datetime.now().astimezone().isoformat(timespec="seconds"),
                durationSeconds=round(time.monotonic() - started, 3),
                timingScope="Top-level run from OpenCode invocation through audit, build, native runtime scoring, and cleanup; subagent durations are not added.",
            )
        result["cleanup"] = {"completed": not candidate.exists(), "error": cleanup_error}
        result["credentialAudit"] = REF.redact_secret_artifacts(run_dir)
        dump(run_dir / "run.json", result)


def summarize(rows: list[dict[str, Any]], run_id: str) -> dict[str, Any]:
    available = [row for row in rows if row.get("benchmarkMetricsAvailable")]
    code_pass = sum(row.get("codeGeneration", {}).get("passed") is True for row in available)
    compile_pass = sum(row.get("compile", {}).get("passed") is True for row in available)
    semantic_pass = sum(row.get("semanticTestcase", {}).get("passed", 0) for row in available)
    semantic_scored = sum(row.get("semanticTestcase", {}).get("scored", 0) for row in available)
    not_scored = sum(row.get("semanticTestcase", {}).get("notScored", 0) for row in available)
    payload = {
        "schemaVersion": 1,
        "runId": run_id,
        "taskId": TASK_ID,
        "model": MODEL,
        "endpoint": ENDPOINT,
        "runs": rows,
        "benchmarkMetrics": {
            "codeGeneration": {"passed": code_pass, "total": len(available), "rate": round(code_pass / len(available), 6) if available else None},
            "compile": {"passed": compile_pass, "total": len(available), "rate": round(compile_pass / len(available), 6) if available else None},
            "semanticTestcase": {"passed": semantic_pass, "scored": semantic_scored, "notScored": not_scored, "rate": round(semantic_pass / semantic_scored, 6) if semantic_scored else None},
        },
        "metricPolicy": "Only code generation, standalone application compile, and semantic testcase pass rate are benchmark metrics. Adapter and transport are diagnostics; notScored is excluded from pass/fail.",
    }
    dump(MIGRATION / "results/agent-evaluation-summary.json", payload)
    return payload


def command_preflight(args: argparse.Namespace) -> int:
    result = preflight(args.output.resolve())
    print(json.dumps({"status": result["status"], "passed": result["passed"], "report": str((args.output / "preflight.json").resolve())}, ensure_ascii=False))
    return 0 if result["passed"] else 2


def command_run(args: argparse.Namespace) -> int:
    if not args.authorize_opencode_and_devices:
        raise ValueError("formal run requires --authorize-opencode-and-devices from the main thread")
    if args.timeout != OVERALL_TIMEOUT_SECONDS:
        raise ValueError("Signal 07 requires exactly 3600 seconds per top-level platform run")
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", args.run_id):
        raise ValueError("run id must contain lowercase letters, digits, underscores, and hyphens only")
    platforms = PLATFORMS if args.platform == "all" else (args.platform,)
    candidate_root = (args.candidate_root or ROOT.parent / ".ltb-signal-07-agent" / args.run_id).resolve()
    candidate_root.mkdir(parents=True, exist_ok=True)
    rows = []
    for platform in platforms:
        print(json.dumps({"event": "run_start", "taskId": TASK_ID, "platform": platform}), flush=True)
        row = run_one(platform, args.run_id, candidate_root, args.hdc_target)
        rows.append(row)
        print(json.dumps({"event": "run_complete", "platform": platform, "availability": row["availability"], "semantic": row.get("semanticTestcase")}), flush=True)
    summary = summarize(rows, args.run_id)
    return 0 if len(rows) == len(platforms) and all(row.get("benchmarkMetricsAvailable") for row in rows) else 2


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description="Signal 07 isolated OpenCode + MiniMax-M3 agent evaluation runner")
    subparsers = value.add_subparsers(dest="command", required=True)
    check = subparsers.add_parser("preflight", help="static clean-room and policy checks; never invokes OpenCode or devices")
    check.add_argument("--output", type=Path, default=MIGRATION / "provenance/agent-runner-preflight")
    check.set_defaults(handler=command_preflight)
    run = subparsers.add_parser("run", help="formal generation and native scoring; requires explicit authorization")
    run.add_argument("--authorize-opencode-and-devices", action="store_true")
    run.add_argument("--platform", choices=("all", *PLATFORMS), default="all")
    run.add_argument("--run-id", default=f"signal-07-minimax-m3-{datetime.now():%Y%m%d-%H%M%S}")
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
