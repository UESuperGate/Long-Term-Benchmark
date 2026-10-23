#!/usr/bin/env python3
"""Prepare or run the isolated WordPress 05 MiniMax-M3 agent evaluation."""

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


MIGRATION = Path(__file__).resolve().parents[1]
MIGRATIONS = MIGRATION.parent
PROJECT = MIGRATIONS.parent
ROOT = PROJECT.parents[1]
TASK = PROJECT / "tasks/05_domain_management"
REFERENCE_RUNNER = MIGRATIONS / "tools/run_wordpress_03_04_agent_eval.py"
TASK_ID = "05_domain_management"
PLATFORMS = ("android", "arkts")
TIMEOUT_SECONDS = 3600
MODEL_MAX_SECONDS = 3000
MODEL = "minimax-token-plan/MiniMax-M3"
ENDPOINT = "https://api.minimaxi.com/v1"
GRADLE = Path.home() / ".gradle/wrapper/dists/gradle-8.14.3-bin/cv11ve7ro1n3o1j4so8xd9n66/gradle-8.14.3/bin/gradle"
HVIGOR = Path("/Applications/DevEco-Studio.app/Contents/tools/hvigor/bin/hvigorw")
ANDROID_JAVA_HOME = Path("/opt/homebrew/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home")
ARKTS_JAVA_HOME = Path("/Applications/DevEco-Studio.app/Contents/jbr/Contents/Home")
ANDROID_SDK = Path.home() / "Library/Android/sdk"
OH_SDK = Path.home() / "Library/OpenHarmony/Sdk/23"


def load_reference() -> Any:
    spec = importlib.util.spec_from_file_location("wordpress_03_04_agent_runner", REFERENCE_RUNNER)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load reference runner {REFERENCE_RUNNER}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


COMMON = load_reference()


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected JSON object")
    return value


def dump(path: Path, value: Any) -> None:
    COMMON.dump(path, value)


def sha256(path: Path) -> str:
    return COMMON.sha256(path)


def artifact(path: Path) -> dict[str, Any]:
    return COMMON.artifact(path)


def platform_environment(candidate: Path, platform: str) -> dict[str, str]:
    env = os.environ.copy()
    java_home = ANDROID_JAVA_HOME if platform == "android" else ARKTS_JAVA_HOME
    env.update({
        "PWD": str(candidate),
        "OLDPWD": str(candidate),
        "JAVA_HOME": str(java_home),
        "ANDROID_HOME": str(ANDROID_SDK),
        "ANDROID_SDK_ROOT": str(ANDROID_SDK),
        "DEVECO_SDK_HOME": str(OH_SDK),
        "OHOS_BASE_SDK_HOME": str(OH_SDK.parent),
    })
    env["PATH"] = os.pathsep.join([
        str(java_home / "bin"),
        str(ANDROID_SDK / "platform-tools"),
        str(HVIGOR.parent),
        "/Applications/DevEco-Studio.app/Contents/tools/ohpm/bin",
        env.get("PATH", ""),
    ])
    return env


def source_project(platform: str, role: str = "base") -> Path:
    return MIGRATION / platform / role


def build_command(platform: str, *, hidden: bool = False, candidate: Path | None = None) -> list[str]:
    if not hidden:
        return ["bash", "build-agent.sh"]
    if candidate is None:
        raise ValueError("hidden builds require a candidate path")
    if platform == "android":
        return [str(GRADLE), "-p", str(candidate), "--no-daemon", "--offline", "assembleDebug", "assembleDebugAndroidTest"]
    return [str(HVIGOR), "--no-daemon", "--mode", "module", "-p", "module=entry@default", "assembleHap"]


def public_transitions() -> dict[str, Any]:
    contract = load(MIGRATION / "canonical/transitions.json")
    return {
        "schemaVersion": 1,
        "taskId": contract["taskId"],
        "description": "Public scenarios only; expected observations and evaluator bindings remain hidden.",
        "cases": [{
            "caseId": case["caseId"],
            "functionalArea": case.get("functionalArea"),
            "given": case["given"],
            **({"setup": case["setup"]} if "setup" in case else {}),
            "event": case["event"],
            "invariants": case.get("invariants", []),
        } for case in contract["cases"]],
    }


def candidate_config(candidate: Path, command: list[str]) -> dict[str, Any]:
    config = COMMON.opencode_config(candidate, command)
    config["model"] = MODEL
    root = str(candidate.resolve())
    paths = config["permission"]["read"]
    paths["../*"] = "deny"
    paths["../**"] = "deny"
    for capability in ("edit", "glob", "list"):
        config["permission"][capability]["../*"] = "deny"
        config["permission"][capability]["../**"] = "deny"
    protected = (
        "_benchmark_inputs/requirement.md",
        "_benchmark_inputs/public_transitions.json",
        "_benchmark_inputs/prompt.md",
        "build-agent.sh",
        "opencode.json",
    )
    for relative in protected:
        config["permission"]["edit"][relative] = "deny"
        config["permission"]["edit"][f"{root}/{relative}"] = "deny"
    return config


def normal_arkts_entry() -> str:
    return """import { UIAbility } from '@kit.AbilityKit';
import { window } from '@kit.ArkUI';
import { DomainPageRuntime } from '../pages/DomainPageOwner';

export default class EntryAbility extends UIAbility {
  onWindowStageCreate(stage: window.WindowStage): void {
    DomainPageRuntime.configureDefault(this.context);
    stage.loadContent('pages/Index');
  }
}
"""


def sanitize_visible_candidate(candidate: Path, platform: str) -> None:
    if platform == "android":
        gradle = candidate / "build.gradle.kts"
        text = gradle.read_text(encoding="utf-8")
        text = re.sub(r"^\s*testApplicationId\s*=.*\n", "", text, flags=re.MULTILINE)
        text = re.sub(r"^\s*testInstrumentationRunner\s*=.*\n", "", text, flags=re.MULTILINE)
        text = re.sub(r"^\s*sourceSets\.getByName\(\"androidTest\"\).*\n", "", text, flags=re.MULTILINE)
        gradle.write_text(text, encoding="utf-8")
        return
    shutil.rmtree(candidate / "entry/src/main/ets/evaluator", ignore_errors=True)
    (candidate / "entry/src/main/ets/entryability/EntryAbility.ets").write_text(normal_arkts_entry(), encoding="utf-8")


def write_build_script(candidate: Path, platform: str) -> list[str]:
    script = candidate / "build-agent.sh"
    if platform == "android":
        body = f'#!/usr/bin/env bash\nset -euo pipefail\n"{GRADLE}" -p . --no-daemon --offline assembleDebug\n'
    else:
        body = f'#!/usr/bin/env bash\nset -euo pipefail\n"{HVIGOR}" --no-daemon --mode module -p module=entry@default assembleHap\n'
    script.write_text(body, encoding="utf-8")
    script.chmod(0o755)
    return build_command(platform)


def prompt_text(platform: str, command: list[str]) -> str:
    location = (
        "Production sources are under src/main."
        if platform == "android"
        else "The app entry is entry/src/main/ets/pages/Index.ets; page-owner and domain state live under entry/src/main/ets."
    )
    return f"""Implement WordPress task 05_domain_management completely in this {platform} candidate.

Read `_benchmark_inputs/requirement.md` and `_benchmark_inputs/public_transitions.json`. Inspect the visible base and implement the requested behavior in real production code. {location}

Rules:
- Work only in this candidate directory. Never inspect parent, sibling, home, network, final, evaluator, report, or hidden paths.
- Subagents are allowed and inherit exactly the same workspace boundary.
- Do not create case-ID switches, marker facts, semantic projections, evaluator APIs, or source-observer shortcuts.
- Preserve unrelated behavior. Implement application-owned state, effects, UI/page wiring, failure recovery, and cleanup.
- Run `{shlex.join(command)}` exactly as written and repair production compilation within the task budget.

Finish with a concise summary of changed production files and remaining blockers.
"""


def prepare_visible_candidate(platform: str, candidate: Path, evidence_dir: Path) -> tuple[list[str], str, dict[str, Any]]:
    COMMON.copy_candidate(source_project(platform), candidate)
    sanitize_visible_candidate(candidate, platform)
    command = write_build_script(candidate, platform)
    inputs = candidate / "_benchmark_inputs"
    inputs.mkdir()
    shutil.copy2(TASK / "requirement.md", inputs / "requirement.md")
    dump(inputs / "public_transitions.json", public_transitions())
    (inputs / "prompt.md").write_text(prompt_text(platform, command), encoding="utf-8")
    dump(candidate / "opencode.json", candidate_config(candidate, command))
    validate_visible_candidate(candidate, platform, command)
    subprocess.run(["git", "init", "-q"], cwd=candidate, check=True)
    subprocess.run(["git", "add", "-A"], cwd=candidate, check=True)
    subprocess.run([
        "git", "-c", "user.name=Benchmark Runner", "-c", "user.email=benchmark@localhost",
        "commit", "-q", "-m", "clean-room base",
    ], cwd=candidate, check=True)
    baseline = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=candidate, text=True).strip()
    snapshot = COMMON.tree_snapshot(candidate, evidence_dir / f"{platform}-visible-tree.json")
    return command, baseline, {"tree": snapshot, "baselineCommit": baseline}


def recursive_keys(value: Any) -> set[str]:
    if isinstance(value, dict):
        return set(value) | set().union(*(recursive_keys(item) for item in value.values()), set())
    if isinstance(value, list):
        return set().union(*(recursive_keys(item) for item in value), set())
    return set()


def validate_visible_candidate(candidate: Path, platform: str, command: list[str]) -> None:
    public = load(candidate / "_benchmark_inputs/public_transitions.json")
    forbidden_public = {"expected", "traceDigest", "polarity", "evidence"}
    leaked = recursive_keys(public) & forbidden_public
    if leaked:
        raise RuntimeError(f"public transitions expose hidden fields: {sorted(leaked)}")
    if len(public.get("cases", [])) != 10:
        raise RuntimeError("public transitions must contain ten cases")
    forbidden_parts = {"final", "evaluator", "report", "reports"}
    visible_paths = [path.relative_to(candidate) for path in candidate.rglob("*") if ".git" not in path.parts]
    for relative in visible_paths:
        if {part.lower() for part in relative.parts} & forbidden_parts:
            raise RuntimeError(f"candidate exposes forbidden path {relative}")
        full = candidate / relative
        if full.is_symlink() and not full.resolve().is_relative_to(candidate.resolve()):
            raise RuntimeError(f"candidate contains external symlink {relative}")
    config = load(candidate / "opencode.json")
    permission = config.get("permission", {})
    if permission.get("task") != "allow" or permission.get("webfetch") != "deny" or permission.get("websearch") != "deny":
        raise RuntimeError("subagent or network policy differs from benchmark isolation")
    if permission.get("external_directory") != "deny":
        raise RuntimeError("external-directory access is not denied")
    shell = permission.get("shell", {})
    if shell.get("*") != "deny" or shell.get(shlex.join(command)) != "allow":
        raise RuntimeError("shell policy does not exclusively expose the pinned build")
    for relative in ("_benchmark_inputs/requirement.md", "_benchmark_inputs/public_transitions.json", "_benchmark_inputs/prompt.md", "build-agent.sh", "opencode.json"):
        rules = permission.get("edit", {})
        if rules.get(relative) != "deny":
            raise RuntimeError(f"protected input is editable: {relative}")
    production_roots = [candidate / "src/main"] if platform == "android" else [candidate / "entry/src/main/ets"]
    for root in production_roots:
        for path in root.rglob("*"):
            if path.is_file() and any(marker in path.read_text(encoding="utf-8", errors="ignore") for marker in ("traceDigest", "SemanticProbe", "LTB_RUNTIME:")):
                raise RuntimeError(f"visible production contains evaluator marker: {path.relative_to(candidate)}")


def run_build(platform: str, candidate: Path, command: list[str], log: Path, timeout: float) -> int:
    if platform == "android":
        with COMMON.android_build_slot(candidate):
            return COMMON.run_logged(command, candidate, log, timeout, platform_environment(candidate, platform), True)
    return COMMON.run_logged(command, candidate, log, timeout, platform_environment(candidate, platform), True)


def inject_android_evaluator(candidate: Path) -> dict[str, Any]:
    destination = candidate / "src/androidTest/java/evaluator/domains/SemanticInstrumentation.java"
    android_test = candidate / "src/androidTest"
    if android_test.exists() and any(android_test.rglob("*")):
        raise RuntimeError("candidate already contains androidTest sources; hidden adapter injection is ambiguous")
    destination.parent.mkdir(parents=True, exist_ok=True)
    source = MIGRATION / "android/evaluator/src/androidTest/java/evaluator/domains/SemanticInstrumentation.java"
    shutil.copy2(source, destination)
    gradle = candidate / "build.gradle.kts"
    text = gradle.read_text(encoding="utf-8")
    app = re.search(r'applicationId\s*=\s*"([^"]+)"', text)
    if app is None:
        raise RuntimeError("candidate applicationId is unavailable for hidden instrumentation")
    text = re.sub(r"^\s*testApplicationId\s*=.*\n", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*testInstrumentationRunner\s*=.*\n", "", text, flags=re.MULTILINE)
    anchor = re.search(r'^(\s*)applicationId\s*=.*$', text, flags=re.MULTILINE)
    if anchor is None:
        raise RuntimeError("candidate defaultConfig cannot be bound to hidden instrumentation")
    indent = anchor.group(1)
    addition = f'\n{indent}testApplicationId = "{app.group(1)}.test"\n{indent}testInstrumentationRunner = "evaluator.domains.SemanticInstrumentation"'
    text = text[:anchor.end()] + addition + text[anchor.end():]
    gradle.write_text(text, encoding="utf-8")
    return {"source": artifact(source), "destination": str(destination.relative_to(candidate)), "productionLogicInjected": False}


def inject_arkts_evaluator(candidate: Path) -> dict[str, Any]:
    destination = candidate / "entry/src/main/ets/evaluator/SemanticProbe.ets"
    if destination.parent.exists():
        raise RuntimeError("candidate already contains an evaluator directory; hidden adapter injection is ambiguous")
    destination.parent.mkdir(parents=True)
    source = MIGRATION / "arkts/final/entry/src/main/ets/evaluator/SemanticProbe.ets"
    entry_source = MIGRATION / "arkts/final/entry/src/main/ets/entryability/EntryAbility.ets"
    shutil.copy2(source, destination)
    shutil.copy2(entry_source, candidate / "entry/src/main/ets/entryability/EntryAbility.ets")
    return {
        "source": artifact(source),
        "entryHook": artifact(entry_source),
        "destination": str(destination.relative_to(candidate)),
        "productionLogicInjected": False,
    }


def inject_hidden(platform: str, candidate: Path) -> dict[str, Any]:
    return inject_android_evaluator(candidate) if platform == "android" else inject_arkts_evaluator(candidate)


def toolchain_inventory() -> dict[str, Any]:
    opencode = shutil.which("opencode")
    paths = {
        "referenceRunner": REFERENCE_RUNNER,
        "gradle": GRADLE,
        "androidJava": ANDROID_JAVA_HOME / "bin/java",
        "androidSdk": ANDROID_SDK,
        "hvigor": HVIGOR,
        "arktsJava": ARKTS_JAVA_HOME / "bin/java",
        "openHarmonySdk": OH_SDK,
    }
    missing = [name for name, path in paths.items() if not path.exists()]
    if opencode is None:
        missing.append("opencode")
    return {
        "ready": not missing,
        "missing": missing,
        "paths": {name: str(path) for name, path in paths.items()},
        "opencode": {"path": opencode, "sha256": sha256(Path(opencode)) if opencode else None, "invoked": False},
        "credential": {
            "path": "~/.config/opencode/secrets/minimax-m3-key",
            "present": (Path.home() / ".config/opencode/secrets/minimax-m3-key").is_file(),
            "contentRead": False,
            "recorded": False,
        },
    }


def static_check(output: Path) -> dict[str, Any]:
    transitions = public_transitions()
    toolchains = toolchain_inventory()
    result = {
        "schemaVersion": 1,
        "taskId": TASK_ID,
        "status": "ready" if toolchains["ready"] else "blocked",
        "runner": artifact(Path(__file__).resolve()),
        "referenceRunner": artifact(REFERENCE_RUNNER),
        "model": MODEL,
        "endpoint": ENDPOINT,
        "overallTimeoutSeconds": TIMEOUT_SECONDS,
        "agentMaxSeconds": MODEL_MAX_SECONDS,
        "subagentsAllowed": True,
        "publicTransitionCases": len(transitions["cases"]),
        "publicTransitionHiddenKeys": sorted(recursive_keys(transitions) & {"expected", "traceDigest", "polarity", "evidence"}),
        "toolchains": toolchains,
        "formalRunStarted": False,
        "opencodeInvoked": False,
        "deviceCommandsInvoked": False,
    }
    dump(output, result)
    if result["status"] != "ready" or result["publicTransitionHiddenKeys"]:
        raise RuntimeError("static agent-runner check failed")
    return result


def preflight_platform(platform: str, root: Path, evidence_dir: Path) -> dict[str, Any]:
    platform_dir = evidence_dir / platform
    platform_dir.mkdir(parents=True, exist_ok=True)
    base = root / f"{platform}-visible-base"
    command, baseline, visible = prepare_visible_candidate(platform, base, platform_dir)
    visible_exit = run_build(platform, base, command, platform_dir / "visible-base-build.log", 1200)
    if visible_exit:
        raise RuntimeError(f"{platform} visible base preflight build failed")
    COMMON.cleanup_builds(base, platform_dir / "visible-base-cleanup.json")
    archive = COMMON.baseline_archive(base, platform_dir / "visible-base.tar.gz", baseline)
    hidden_base = inject_hidden(platform, base)
    hidden_base_exit = run_build(platform, base, build_command(platform, hidden=True, candidate=base), platform_dir / "hidden-base-build.log", 1200)
    if hidden_base_exit:
        raise RuntimeError(f"{platform} hidden base compile preflight failed")
    COMMON.cleanup_builds(base, platform_dir / "hidden-base-cleanup.json")

    final = root / f"{platform}-hidden-final"
    COMMON.copy_candidate(source_project(platform, "final"), final)
    sanitize_visible_candidate(final, platform)
    write_build_script(final, platform)
    hidden_final = inject_hidden(platform, final)
    hidden_final_exit = run_build(platform, final, build_command(platform, hidden=True, candidate=final), platform_dir / "hidden-final-build.log", 1200)
    if hidden_final_exit:
        raise RuntimeError(f"{platform} hidden final compile preflight failed")
    COMMON.cleanup_builds(final, platform_dir / "hidden-final-cleanup.json")
    return {
        "platform": platform,
        "visibleBaseCompile": visible_exit == 0,
        "hiddenBaseCompile": hidden_base_exit == 0,
        "hiddenFinalCompile": hidden_final_exit == 0,
        "visibleCandidate": visible,
        "baselineArchive": archive,
        "hiddenBaseInjection": hidden_base,
        "hiddenFinalInjection": hidden_final,
        "semanticRuntimeStarted": False,
        "deviceCommandsInvoked": False,
        "opencodeInvoked": False,
    }


def preflight(platforms: list[str], output: Path) -> dict[str, Any]:
    COMMON.require_space(ROOT)
    static = static_check(output.parent / "agent-runner-static.json")
    with tempfile.TemporaryDirectory(prefix="wordpress-05-agent-preflight-") as temporary:
        temp = Path(temporary)
        rows = [preflight_platform(platform, temp, output.parent) for platform in platforms]
    result = {
        "schemaVersion": 1,
        "taskId": TASK_ID,
        "status": "ready_for_authorized_execution",
        "model": MODEL,
        "endpoint": ENDPOINT,
        "overallTimeoutSecondsPerPlatformRun": TIMEOUT_SECONDS,
        "subagentsAllowed": True,
        "candidateInputs": ["platform base", "requirement.md", "public transitions without expected"],
        "forbidden": ["network", "parent directories", "final", "evaluator", "reports"],
        "static": static,
        "platforms": rows,
        "formalRunStarted": False,
        "opencodeInvoked": False,
        "deviceCommandsInvoked": False,
        "temporaryCandidatesRemoved": True,
    }
    dump(output, result)
    return result


def hidden_semantic_command(platform: str, candidate: Path, run_dir: Path) -> list[str]:
    if platform == "android":
        return [
            "python3", str(MIGRATION / "android/evaluator/run_semantic.py"),
            "--project", str(candidate), "--role", "agent",
            "--output", str(run_dir / "semantic.json"),
            "--raw-dir", str(run_dir / "runtime-raw"),
        ]
    return [
        "python3", str(MIGRATION / "arkts/evaluator/run_semantic.py"),
        "--project", str(candidate), "--role", "agent", "--output", str(run_dir / "semantic.json"),
    ]


def execute_hidden(platform: str, candidate: Path, run_dir: Path, deadline: float) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    injection = inject_hidden(platform, candidate)
    dump(run_dir / "hidden-injection.json", injection)
    hidden_build = build_command(platform, hidden=True, candidate=candidate)
    build_exit = run_build(platform, candidate, hidden_build, run_dir / "hidden-build.log", COMMON.remaining(deadline, "hidden_build"))
    diagnostics: dict[str, Any] = {"runtimeCompileExit": build_exit, "classification": "adapter diagnostic", "injection": injection}
    if build_exit:
        return None, diagnostics
    semantic = hidden_semantic_command(platform, candidate, run_dir)
    semantic_exit = COMMON.run_logged(
        semantic, MIGRATION, run_dir / "semantic-runtime.log",
        COMMON.remaining(deadline, "semantic_runtime"), platform_environment(candidate, platform),
    )
    diagnostics["semanticExit"] = semantic_exit
    report = run_dir / "semantic.json"
    return (load(report), diagnostics) if report.is_file() else (None, diagnostics)


def execute_one(platform: str, run_id: str, candidate_root: Path, timeout: int) -> dict[str, Any]:
    run_dir = MIGRATION / "results/agent-runs" / run_id / platform
    run_dir.mkdir(parents=True, exist_ok=True)
    candidate = candidate_root / platform
    result: dict[str, Any] = {
        "schemaVersion": 1,
        "runId": run_id,
        "taskId": TASK_ID,
        "platform": platform,
        "runner": "OpenCode",
        "model": MODEL,
        "endpoint": ENDPOINT,
        "overallTimeoutSeconds": timeout,
        "subagentsAllowed": True,
        "semanticFeedbackDuringGeneration": False,
        "apiKeyRecorded": False,
        "availability": "environment_failure",
        "benchmarkMetricsAvailable": False,
    }
    started: float | None = None
    try:
        command, baseline, visible = prepare_visible_candidate(platform, candidate, run_dir / "inputs")
        preflight_exit = run_build(platform, candidate, command, run_dir / "preflight-build.log", 1200)
        if preflight_exit:
            raise RuntimeError("clean visible base preflight build failed")
        COMMON.cleanup_builds(candidate, run_dir / "preflight-artifacts.json")
        visible["archive"] = COMMON.baseline_archive(candidate, run_dir / "inputs/baseline.tar.gz", baseline)
        result.update(candidateBaseline=visible, publicBuildCommand=command)

        started = time.monotonic()
        deadline = started + timeout
        result["startedAt"] = datetime.now().astimezone().isoformat(timespec="seconds")
        prompt = (candidate / "_benchmark_inputs/prompt.md").read_text(encoding="utf-8")
        log = run_dir / "opencode.jsonl"
        allowance = min(MODEL_MAX_SECONDS, COMMON.remaining(deadline, "agent"))
        result["agentGrantedSeconds"] = allowance
        agent_command = [
            "opencode", "run", "--standalone", "--model", MODEL, "--format", "json",
            "--title", f"WordPress {TASK_ID} {platform}", prompt,
        ]
        result["agentCommand"] = [*agent_command[:-1], "@_benchmark_inputs/prompt.md"]
        try:
            agent_exit = COMMON.run_logged(agent_command, candidate, log, allowance, platform_environment(candidate, platform), True)
            timed_out = False
        except subprocess.TimeoutExpired:
            agent_exit, timed_out = 124, True
        result.update(agentExit=agent_exit, agentTimedOut=timed_out)

        paths = COMMON.changed_paths(candidate)
        generated = COMMON.production_files(paths, platform)
        audit = COMMON.generation_audit(candidate, generated)
        patch = COMMON.archive_patch(candidate, run_dir / f"{platform}-agent.patch", baseline)
        dump(run_dir / f"{platform}-agent-generated-files.json", {
            "schemaVersion": 1,
            "changedFiles": paths,
            "generatedProductionFiles": generated,
            "audit": audit,
        })
        result.update(candidatePatch=patch, codeGeneration=audit)
        external = COMMON.provider_failure(log)
        result["generationDiagnostics"] = {
            "providerFailure": external,
            "timedOut": timed_out,
            "agentExit": agent_exit,
            "classification": "diagnostic; benchmark metrics are evaluated independently after termination",
        }
        if external and not generated:
            result.update(availability=external, externalFailure=True, reason="provider failed before production code generation")
            return result
        result["externalFailure"] = bool(external)
        isolation = COMMON.terminal_audit(log, candidate, command, run_dir / "isolation-audit-terminal.json", deadline)
        result["isolationAudit"] = isolation
        if isolation["availability"] != "available":
            result["availability"] = isolation["availability"]
            return result

        compile_exit = run_build(platform, candidate, command, run_dir / "production-build.log", COMMON.remaining(deadline, "production_build"))
        result["compile"] = {"passed": compile_exit == 0, "exitCode": compile_exit, "command": command}
        COMMON.cleanup_builds(candidate, run_dir / "production-build-artifacts.json")
        if compile_exit:
            report = COMMON.not_scored_report(TASK_ID, platform, "candidate production compile failed")
            diagnostics = {"runtimeCompileExit": None, "semanticExit": None, "classification": "semantic runtime not started"}
        else:
            report, diagnostics = execute_hidden(platform, candidate, run_dir, deadline)
        result["diagnostics"] = diagnostics
        if report is None:
            report = COMMON.not_scored_report(TASK_ID, platform, "hidden runtime adapter did not compile or bind")
        metrics = COMMON.semantic_metrics(report)
        report["codeGeneration"] = audit
        report["compile"] = result["compile"]
        report.setdefault("diagnostics", {})["runtimeCompile"] = diagnostics
        dump(run_dir / "semantic.json", report)
        result.update(
            availability="available",
            benchmarkMetricsAvailable=True,
            semanticTestcase=metrics,
            semanticReport=artifact(run_dir / "semantic.json"),
        )
        shutil.copy2(run_dir / "semantic.json", MIGRATION / "results" / f"{platform}-agent.json")
        patches = MIGRATION / "results/agent-patches"
        patches.mkdir(parents=True, exist_ok=True)
        shutil.copy2(run_dir / f"{platform}-agent.patch", patches / f"{platform}-agent.patch")
        shutil.copy2(run_dir / f"{platform}-agent-generated-files.json", patches / f"{platform}-agent-generated-files.json")
        return result
    except TimeoutError as error:
        result.update(availability="overall_timeout", reason=str(error), benchmarkMetricsAvailable=False)
        return result
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        result.update(
            availability="environment_failure" if started is None else "evaluation_failure",
            reason=f"{type(error).__name__}: {error}",
            benchmarkMetricsAvailable=False,
        )
        return result
    finally:
        cleanup_error = None
        try:
            if candidate.exists():
                COMMON.cleanup_builds(candidate, run_dir / "final-cleanup-artifacts.json")
                shutil.rmtree(candidate)
        except OSError as error:
            cleanup_error = str(error)
        if started is not None:
            result.update(
                finishedAt=datetime.now().astimezone().isoformat(timespec="seconds"),
                durationSeconds=round(time.monotonic() - started, 3),
                timingScope="Top-level run from OpenCode through audit, build, runtime scoring, and cleanup; subagent durations are not added.",
            )
        result["cleanup"] = {"completed": not candidate.exists(), "error": cleanup_error}
        result["credentialAudit"] = COMMON.redact_secret_artifacts(run_dir)
        dump(run_dir / "run.json", result)


def summarize(run_id: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    available = [row for row in rows if row.get("benchmarkMetricsAvailable")]
    code_passed = sum(row.get("codeGeneration", {}).get("passed") is True for row in available)
    compile_passed = sum(row.get("compile", {}).get("passed") is True for row in available)
    semantic_passed = sum(row.get("semanticTestcase", {}).get("passed", 0) for row in available)
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
            "codeGeneration": {"passed": code_passed, "total": len(available), "rate": round(code_passed / len(available), 6) if available else None},
            "compile": {"passed": compile_passed, "total": len(available), "rate": round(compile_passed / len(available), 6) if available else None},
            "semanticTestcase": {"passed": semantic_passed, "scored": semantic_scored, "notScored": not_scored, "rate": round(semantic_passed / semantic_scored, 6) if semantic_scored else None},
        },
        "metricPolicy": "Only code generation, application compile, and semantic testcase pass rate are benchmark metrics. Adapter, provider, isolation, and transport states are diagnostics.",
    }
    dump(MIGRATION / "results/agent-evaluation-summary.json", payload)
    return payload


def execute(platforms: list[str], run_id: str, candidate_root: Path, timeout: int) -> dict[str, Any]:
    if timeout != TIMEOUT_SECONDS:
        raise ValueError("WordPress 05 formal runs require exactly 3600 seconds per top-level platform run")
    COMMON.require_space(ROOT)
    rows = [execute_one(platform, run_id, candidate_root, timeout) for platform in platforms]
    summary = summarize(run_id, rows)
    shutil.rmtree(candidate_root, ignore_errors=True)
    return summary


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description="WordPress 05 isolated OpenCode + MiniMax-M3 agent runner")
    mode = value.add_mutually_exclusive_group(required=True)
    mode.add_argument("--static-check", action="store_true", help="Validate paths, toolchains, public-input redaction, and policy without builds")
    mode.add_argument("--preflight", action="store_true", help="Build visible and hidden controls offline; never invoke OpenCode or a device")
    mode.add_argument("--execute", action="store_true", help="Start the authorized formal agent run, including runtime device scoring")
    value.add_argument("--platform", action="append", choices=PLATFORMS, help="Platform to check or run; repeat for both (default: both)")
    value.add_argument("--timeout", type=int, default=TIMEOUT_SECONDS, help="Overall deadline per top-level platform run; must be 3600")
    value.add_argument("--run-id", help="Formal run identifier; required with --execute")
    value.add_argument("--candidate-root", type=Path, help="Formal clean-room candidate root")
    value.add_argument("--output", type=Path, help="Static/preflight report path")
    return value


def main() -> int:
    args = parser().parse_args()
    platforms = list(dict.fromkeys(args.platform or PLATFORMS))
    default_evidence = MIGRATION / "provenance/agent-runner-preflight"
    if args.static_check:
        output = (args.output or default_evidence / "agent-runner-static.json").resolve()
        result = static_check(output)
    elif args.preflight:
        output = (args.output or default_evidence / "preflight.json").resolve()
        result = preflight(platforms, output)
    else:
        if not args.run_id:
            raise ValueError("--execute requires an explicit --run-id from the authorizing main thread")
        candidate_root = (args.candidate_root or ROOT.parent / ".ltb-wordpress-05-agent" / args.run_id).resolve()
        candidate_root.mkdir(parents=True, exist_ok=False)
        result = execute(platforms, args.run_id, candidate_root, args.timeout)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
