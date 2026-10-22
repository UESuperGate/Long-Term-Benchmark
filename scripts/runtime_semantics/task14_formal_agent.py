#!/usr/bin/env python3
"""Formal source-parameterized scorer for Task14 on Android and ArkTS."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Optional

import android_robolectric
import android_runner
from android_robolectric_ui_resources import compile_resources
import task14_15_formal_core as core
import task14_15_android_entry_evidence as entry_evidence
import task14_15_device_lease as device_lease
import task14_15_arkts_entry_evidence as arkts_entry_evidence


ROOT = core.ROOT
TASK_ID = "14_join_room_by_address"
CONTRACT = ROOT / "benchmark_tasks/14_join_room_by_address/transitions.json"
ASSETS = ROOT / "state_tests/runtime/android/14_join_room_by_address"
ONBOARDING_CONFIG = "appconfig/src/main/kotlin/io/element/android/appconfig/OnBoardingConfig.kt"
ANDROID_FINAL_FEATURE_ENTRY = (
    "features/createroom/impl/src/main/kotlin/io/element/android/features/createroom/impl/"
    "joinbyaddress/JoinRoomByAddressNode.kt")
ANDROID_ENTRY_CASE = "jr_state_001_entry_opens_address_flow"
ANDROID_RENDERED_CASES = {
    "jr_state_003_invalid_after_continue",
    "jr_state_007_not_found_recovers",
    "jr_state_008_timeout_recovers",
}
ARKTS_DEVICE_CASES = {
    "jr_state_001_entry_opens_address_flow", "jr_state_003_invalid_after_continue",
    "jr_state_007_not_found_recovers",
}
ARKTS_CLOCK_CASE = "jr_state_002_update_trims_and_debounces"
ARKTS_ARKVM_CASES = {
    "jr_state_004_valid_address_resolves", "jr_state_005_found_then_continue_navigates",
    "jr_state_006_continue_waits_for_resolution", "jr_state_008_timeout_recovers",
    "jr_state_009_dismiss_closes_flow",
}
ARKTS_DEVICE_MAX_ATTEMPTS = {
    "jr_state_001_entry_opens_address_flow": 1,
    "jr_state_003_invalid_after_continue": 1,
    "jr_state_007_not_found_recovers": 6,
}


def _raw_rows(report: dict) -> list[dict]:
    return report.get("observations") or report.get("semantic", {}).get("cases", [])


def _healthy(report: dict) -> bool:
    value = report.get("runtimeCompile", {})
    return value.get("status") == "passed" or value.get("passed") is True


def _missing_entry_rows(report: dict, contract: dict, report_path: Path) -> Optional[list[dict]]:
    raw = {row.get("key"): row for row in _raw_rows(report)}
    result = []
    for spec in contract["cases"]:
        row = raw.get(spec["key"])
        observed = (row or {}).get("observed", {})
        missing = bool(row) and (row.get("status") == "fail" or observed.get("failureKind") ==
                                 "semantic_missing_feature_entry") and \
            observed.get("joinActionCount") == 0 and observed.get("transitionExecuted") is False
        if not missing:
            return None
        result.append(entry_evidence.entry_row(
            row, spec, report_path, report["provenance"]["productionSources"]))
    return result


def _prefer_production_contributes_node(configuration: Path) -> Path:
    config = core.load(configuration)
    production = [path for path in config.get("sources", [])
                  if path.endswith("anvilannotations/src/main/kotlin/io/element/android/"
                                   "anvilannotations/ContributesNode.kt")]
    stubs = [path for path in config.get("evaluatorSources", [])
             if Path(path).name == "Annotations.kt"]
    if len(production) != 1 or len(stubs) != 1:
        raise RuntimeError(
            "Task14 entry config must contain one immutable production ContributesNode and one legacy stub")
    config["evaluatorSources"] = [path for path in config["evaluatorSources"] if path not in stubs]
    config["formalDerivation"] = {
        "removedEvaluatorStub": stubs[0],
        "replacementProductionSource": production[0],
    }
    core.write(configuration, config)
    return configuration


def _final_rows(entry: dict, rendered: dict, domain: dict, contract: dict) -> list[dict]:
    entry_rows = {row.get("key"): row for row in _raw_rows(entry)}
    rendered_rows = {row.get("key"): row for row in _raw_rows(rendered)}
    domain_rows = {row.get("key"): row for row in _raw_rows(domain)}
    result = []
    for spec in contract["cases"]:
        if spec["caseId"] == ANDROID_ENTRY_CASE:
            raw = entry_rows.get(spec["key"])
        elif spec["caseId"] in ANDROID_RENDERED_CASES:
            raw = rendered_rows.get(spec["key"])
        else:
            raw = domain_rows.get(spec["key"])
        if raw is None:
            raise RuntimeError(f"Task14 strict runtime row missing: {spec['caseId']}")
        result.append({**raw, "caseId": spec["caseId"], "key": spec["key"],
                       "traceDigest": spec["traceDigest"]})
    return result


def _android_runtime(*, source: Path, output: Path, deadline: float, smoke: bool) -> dict:
    contract = core.load(CONTRACT)
    evidence = output.with_name(output.stem + "_evidence")
    if evidence.exists():
        raise FileExistsError(f"Refusing existing evidence: {evidence}")
    evidence.mkdir(parents=True)
    reports = {}
    failure = None
    rows = []
    removed_temporary_tree = None
    android_robolectric.compile_resources = compile_resources
    with tempfile.TemporaryDirectory(prefix="task14-formal-agent-") as raw:
        temporary = Path(raw)
        try:
            with core.bounded_file_lock(ROOT / "state_tests/runtime/android/.build.lock", deadline,
                                        "Task14 shared Android runtime lock"):
                core.require_build_space()
                if entry_evidence.prefix_closure.reviewed_source(TASK_ID, core.directory_digest(source)):
                    baseline_config = _prefer_production_contributes_node(
                        core.prepared_android_config(
                            source, ASSETS / "baseline_entry/adapter.json", temporary,
                            extra_sources=[ONBOARDING_CONFIG]))
                    reports["entry_probe"] = android_robolectric.run_slice(
                        TASK_ID, "agent", source.resolve(), ASSETS / "baseline_entry", baseline_config,
                        evidence / "entry-probe.json",
                        core.remaining_deadline(deadline, "Task14 base entry probe"))
                    if not _healthy(reports["entry_probe"]):
                        raise RuntimeError("Task14 base entry probe did not compile")
                    rows = [] if smoke else (_missing_entry_rows(
                        reports["entry_probe"], contract, evidence / "entry-probe.json") or [])
                    if not smoke and not rows:
                        raise RuntimeError("Task14 base entry probe did not prove missing feature entry")
                else:
                    final_config = _prefer_production_contributes_node(
                        core.prepared_android_config(
                            source, ASSETS / "final_entry/adapter.json", temporary,
                            extra_sources=[ONBOARDING_CONFIG]))
                    reports["entry"] = android_robolectric.run_slice(
                        TASK_ID, "agent", source.resolve(), ASSETS / "final_entry", final_config,
                        evidence / "final-entry.json",
                        core.remaining_deadline(deadline, "Task14 final entry"))
                    if not _healthy(reports["entry"]):
                        raise RuntimeError("Task14 final entry runtime slice did not compile")
                    if smoke:
                        rows = []
                    else:
                        reports["domain"] = android_runner.run(
                            TASK_ID, "agent", source.resolve(), evidence / "domain.json",
                            core.remaining_deadline(deadline, "Task14 domain"),
                            adapter_config=ASSETS / "adapter.json")
                        if not _healthy(reports["domain"]):
                            raise RuntimeError("Task14 final domain runtime slice did not compile")
                        rendered_config = core.prepared_android_config(
                            source, ASSETS / "rendered/adapter.json", temporary)
                        reports["rendered"] = android_robolectric.run_slice(
                            TASK_ID, "agent", source.resolve(), ASSETS / "rendered",
                            rendered_config, evidence / "rendered.json",
                            core.remaining_deadline(deadline, "Task14 rendered UI transitions"))
                        if not _healthy(reports["rendered"]):
                            raise RuntimeError("Task14 rendered UI runtime slice did not compile")
                        rows = _final_rows(
                            reports["entry"], reports["rendered"], reports["domain"], contract)
        except Exception as error:
            failure = f"{type(error).__name__}: {error}"
        finally:
            removed_temporary_tree = core.tree_artifact_record(temporary)
    temporary_removed = not temporary.exists()
    retained = {"path": str(evidence), "files": [], "binariesRetained": False}
    for path in sorted(item for item in evidence.rglob("*") if item.is_file()):
        if path.suffix.lower() in core.BINARY_SUFFIXES:
            path.unlink()
            continue
        retained["files"].append({"path": path.relative_to(evidence).as_posix(),
                                  "bytes": path.stat().st_size, "sha256": core.sha256(path)})
    runtime_passed = bool(reports) and all(_healthy(report) for report in reports.values()) and failure is None
    report = core.normalized_runtime_report(
        task_id=TASK_ID, platform="android", source=source, contract=contract, rows=rows,
        runtime_passed=runtime_passed, transport="host_runtime_completed" if runtime_passed else "failed",
        retained=retained, temporary_removed=temporary_removed, reason=failure)
    report["diagnostics"]["cleanup"]["removedTemporaryBuildTree"] = removed_temporary_tree
    entry_evidence.attach_production_evidence(report, reports, source, evidence)
    core.write(output, report)
    return report


def _run(command: list[str], *, deadline: float, phase: str, log: Path,
         environment: Optional[dict] = None) -> None:
    process = subprocess.run(command, cwd=ROOT, env=environment, capture_output=True, text=True,
                             timeout=core.remaining_deadline(deadline, phase), check=False)
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text((process.stdout or "") + (process.stderr or ""), encoding="utf-8")
    if process.returncode:
        raise RuntimeError(f"{phase} failed with exit {process.returncode}; see {log}")


def _bundle_name(source: Path) -> str:
    text = (source / "AppScope/app.json5").read_text(encoding="utf-8")
    match = re.search(r"\bbundleName\s*:\s*['\"]([^'\"]+)", text)
    if not match:
        match = re.search(r"['\"]bundleName['\"]\s*:\s*['\"]([^'\"]+)", text)
    if not match:
        raise ValueError("Task14 candidate bundleName is unavailable")
    return match.group(1)


def _task14_base_device(*, source: Path, evidence: Path, deadline: float) -> tuple[list[dict], list[dict]]:
    build_dir = evidence / "base-application"
    build = core.build_arkts_application(source=source, output=build_dir, deadline=deadline,
                                         label="task14-base-runtime")
    build_report = build_dir / "application-build.json"
    hap = Path(build["hap"]["path"])
    original = ROOT / "scripts/runtime_semantics/Task14BaseAllDevice.cjs"
    script = original.read_text(encoding="utf-8")
    replacements = {
        "const root = path.resolve(__dirname, '../..');": f"const root = {json.dumps(str(ROOT))};",
        "const bundleName = 'com.qingyu.elementx.joinaddress.base';":
            f"const bundleName = {json.dumps(_bundle_name(source))};",
        "const buildReport = path.join(root,\n  'experiment_results/runtime_transition_20261020/task14_repair/real_flow_v2/builds/base-attempt3/report.json');":
            f"const buildReport = {json.dumps(str(build_report))};",
        "const hap = path.join(path.dirname(buildReport), 'entry-default-unsigned.hap');":
            f"const hap = {json.dumps(str(hap))};",
        "build.role !== 'base'": "build.role !== 'agent'",
        "platform: 'arkts', role: 'base',": "platform: 'arkts', role: 'agent',",
        ("invariantChecks: spec.invariants.map(text => ({ text, passed: false,\n"
         "          reason: 'The final-version join-by-address transition cannot execute from this base UI.' })),"):
            "invariantChecks: [], unevaluatedInvariants: spec.invariants,",
    }
    for old, new in replacements.items():
        if script.count(old) != 1:
            raise RuntimeError(f"Task14 base runner derivation point changed: {old[:50]}")
        script = script.replace(old, new)
    script = device_lease.derive_js_lock_borrowing(script)
    derived = evidence / "task14-base-source-parameterized.cjs"
    derived.write_text(script, encoding="utf-8")
    output = evidence / "base-device"
    node = "/Applications/DevEco-Studio.app/Contents/tools/node/bin/node"
    _run([node, str(derived), "--output", str(output)], deadline=deadline,
         phase="Task14 base missing-entry device runtime", log=evidence / "base-device.log")
    report = core.load(output / "report.json")
    semantic = report.get("semantic", {})
    if report.get("status") != "passed" or (
            semantic.get("passed"), semantic.get("failed"), semantic.get("notScored")) != (0, 9, 0):
        raise RuntimeError("Task14 base device runtime did not prove 0P/9F/0NS")
    contract = core.load(CONTRACT)
    specs = {item["caseId"]: item for item in contract["cases"]}
    rows = []
    for raw in semantic.get("cases", []):
        spec = specs.get(raw.get("caseId"))
        if spec is None:
            raise RuntimeError("Task14 base device runtime returned an unknown canonical case")
        rows.append(arkts_entry_evidence.entry_row(
            raw, spec, output / "report.json", build["sources"]))
    removed = core.remove_binary_artifacts(evidence)
    return rows, removed


def _retained_evidence(evidence: Path) -> dict:
    files = []
    for path in sorted(item for item in evidence.rglob("*") if item.is_file()):
        if path.suffix.lower() in core.BINARY_SUFFIXES:
            raise RuntimeError(f"Task14 retained binary escaped cleanup: {path}")
        files.append({"path": path.relative_to(evidence).as_posix(), "bytes": path.stat().st_size,
                      "sha256": core.sha256(path)})
    return {"path": str(evidence), "files": files, "binariesRetained": False}


def _normalize_pole_row(raw: dict, spec: dict, runtime: str) -> dict:
    return {**raw, "caseId": spec["caseId"], "key": spec["key"],
            "traceDigest": spec["traceDigest"], "runtime": runtime}


def _task14_device_rows(*, source: Path, evidence: Path, deadline: float,
                        device_serial: Optional[str], specs: dict) -> tuple[dict, list[dict], dict]:
    rows = {}
    removed = []
    attempts = {}
    for case_id in sorted(ARKTS_DEVICE_CASES):
        maximum = ARKTS_DEVICE_MAX_ATTEMPTS[case_id]
        last_reason = "device runtime did not return a canonical row"
        for attempt in range(1, maximum + 1):
            device_output = evidence / f"device-original-ui-{case_id}-attempt-{attempt}.json"
            device = core.arkts_runtime_evaluate(
                task_id=TASK_ID, contract_path=CONTRACT, source=source, output=device_output,
                deadline=deadline, smoke=False, device_serial=device_serial,
                selected_case_ids={case_id},
                builder_environment={"TASK14_ORIGINAL_MODULE_IMPORT": "after-page-ready"})
            attempts[case_id] = attempt
            for item in device.get("diagnostics", {}).get("cleanup", {}).get("removedBinaries", []):
                removed.append({**item, "path": f"{case_id}/attempt-{attempt}/" + item.get("path", "")})
            candidates = [item for item in device.get("semantic", {}).get("cases", [])
                          if item.get("caseId") == case_id]
            raw = candidates[0] if len(candidates) == 1 else None
            scoreable = raw is not None and raw.get("status") in {"pass", "fail"}
            healthy = device.get("runtimeCompile", {}).get("passed") is True and \
                device.get("diagnostics", {}).get("transport") == "transport_completed"
            if scoreable and healthy:
                rows[case_id] = _normalize_pole_row(
                    raw, specs[case_id], "openharmony_api23_device_original_ui")
                break
            if raw is not None:
                last_reason = raw.get("reason") or raw.get("failureKind") or last_reason
            else:
                last_reason = device.get("diagnostics", {}).get("reason") or last_reason
        if case_id not in rows:
            raise RuntimeError(
                f"Task14 original-UI pole remained unscored after {maximum} isolated attempt(s) "
                f"for {case_id}: {last_reason}")
    return rows, removed, attempts


def _task14_final_poles(*, source: Path, evidence: Path, deadline: float,
                        device_serial: Optional[str]) -> tuple[list[dict], list[dict]]:
    contract = core.load(CONTRACT)
    specs = {item["caseId"]: item for item in contract["cases"]}
    rows, removed, device_attempts = _task14_device_rows(
        source=source, evidence=evidence, deadline=deadline, device_serial=device_serial,
        specs=specs)

    node = "/Applications/DevEco-Studio.app/Contents/tools/node/bin/node"
    clock_output = evidence / "host-virtual-clock.json"
    _run([node, str(ROOT / "state_tests/runtime/arkts/Task14Clock.cjs"),
          "--source", str(source), "--role", "agent", "--output", str(clock_output)],
         deadline=deadline, phase="Task14 virtual-clock production runtime",
         log=evidence / "host-virtual-clock.log")
    clock = core.load(clock_output)
    clock_rows = [item for item in clock.get("semantic", {}).get("cases", [])
                  if item.get("caseId") == ARKTS_CLOCK_CASE]
    if len(clock_rows) != 1 or clock_rows[0].get("status") not in {"pass", "fail"}:
        raise RuntimeError("Task14 virtual-clock pole did not produce canonical case002")
    rows[ARKTS_CLOCK_CASE] = _normalize_pole_row(
        clock_rows[0], specs[ARKTS_CLOCK_CASE], "host_transpiled_virtual_clock_production")

    arkvm_output = evidence / "arkvm-production"
    _run([node, str(ROOT / "scripts/runtime_semantics/arkts_native_smoke.cjs"),
          "--bundle", TASK_ID, "--role", "agent", "--source", str(source),
          "--contract", str(CONTRACT), "--output-dir", str(arkvm_output)],
         deadline=deadline, phase="Task14 ArkVM production-module runtime",
         log=evidence / "arkvm-production.log")
    arkvm_report = core.load(arkvm_output / "reports" / f"arkts_{TASK_ID}_agent.json")
    if arkvm_report.get("runtimeCompile", {}).get("passed") is not True:
        raise RuntimeError("Task14 ArkVM production-module packaging did not pass")
    arkvm_rows = {item.get("caseId"): item for item in arkvm_report.get("semantic", {}).get("cases", [])}
    for case_id in ARKTS_ARKVM_CASES:
        raw = arkvm_rows.get(case_id)
        if raw is None or raw.get("status") not in {"pass", "fail"}:
            raise RuntimeError(f"Task14 ArkVM pole did not produce scoreable {case_id}")
        rows[case_id] = _normalize_pole_row(raw, specs[case_id],
                                            "native_previewer_arkvm_production_module")
    removed.extend(core.remove_binary_artifacts(arkvm_output))
    if set(rows) != set(specs):
        raise RuntimeError("Task14 exact four-pole composition is incomplete")
    (evidence / "device-original-ui-attempts.json").write_text(
        json.dumps(device_attempts, indent=2) + "\n", encoding="utf-8")
    return [rows[item["caseId"]] for item in contract["cases"]], removed


def _arkts_runtime(*, source: Path, output: Path, deadline: float, smoke: bool,
                   device_serial: Optional[str]) -> dict:
    contract = core.load(CONTRACT)
    evidence = output.with_name(output.stem + "_evidence")
    if evidence.exists():
        raise FileExistsError(f"Refusing existing evidence: {evidence}")
    evidence.mkdir(parents=True)
    rows = []
    removed = []
    failure = None
    runtime_passed = False
    try:
        if smoke:
            build = core.build_arkts_application(source=source, output=evidence / "candidate-smoke",
                                                 deadline=deadline, label="task14-agent-smoke")
            if build.get("passed") is not True:
                raise RuntimeError("Task14 candidate application smoke build did not pass")
            removed.extend(core.remove_binary_artifacts(evidence / "candidate-smoke"))
        elif arkts_entry_evidence.closure.reviewed_source(TASK_ID, core.directory_digest(source)):
            rows, base_removed = _task14_base_device(source=source, evidence=evidence,
                                                     deadline=deadline)
            removed.extend(base_removed)
        else:
            rows, final_removed = _task14_final_poles(
                source=source, evidence=evidence, deadline=deadline, device_serial=device_serial)
            removed.extend(final_removed)
        runtime_passed = True
    except Exception as error:
        failure = f"{type(error).__name__}: {error}"
    removed.extend(core.remove_binary_artifacts(evidence))
    report = core.normalized_runtime_report(
        task_id=TASK_ID, platform="arkts", source=source, contract=contract, rows=rows,
        runtime_passed=runtime_passed, transport="transport_completed" if runtime_passed else "failed",
        retained=_retained_evidence(evidence), temporary_removed=True, reason=failure)
    report["diagnostics"]["cleanup"]["removedBinaries"] = removed
    report["diagnostics"]["evidenceComposition"] = {
        "base": "API23 device missing-entry with isolated install per case",
        "final": {
            "deviceOriginalUi": sorted(ARKTS_DEVICE_CASES),
            "hostVirtualClockProduction": [ARKTS_CLOCK_CASE],
            "arkvmProductionModule": sorted(ARKTS_ARKVM_CASES),
        },
    }
    core.attach_arkts_production_evidence(report, source, evidence)
    core.write(output, report)
    return report


def evaluate_runtime(*, platform: str, source: Path, output: Path, deadline: float,
                     smoke: bool, device_serial: Optional[str] = None) -> dict:
    if platform == "android":
        return _android_runtime(source=source, output=output, deadline=deadline, smoke=smoke)
    if platform == "arkts":
        return _arkts_runtime(source=source, output=output, deadline=deadline, smoke=smoke,
                              device_serial=device_serial)
    raise ValueError("platform must be android or arkts")


def dispatch(*, platform: str, source: Path, base_source: Path, final_source: Path,
             output: Path, compile_passed: bool | None, compile_command: str,
             timeout: float = 3600, evaluator=evaluate_runtime, monotonic=time.monotonic,
             device_serial: Optional[str] = None) -> dict:
    context_factory = None
    runtime_evaluator = evaluator
    owns_device = evaluator is evaluate_runtime or getattr(evaluator, "task14_15_device_runtime", False)
    if platform == "arkts" and device_serial is not None:
        def runtime_evaluator(**kwargs):
            return evaluator(**kwargs, device_serial=device_serial)
        runtime_evaluator.task14_15_device_runtime = owns_device
    if platform == "arkts" and owns_device:
        context_factory = lambda deadline: device_lease.task_scope(TASK_ID, deadline, device_serial=device_serial)
    return core.score(task_id=TASK_ID, contract_path=CONTRACT, platform=platform, source=source,
                      base_source=base_source, final_source=final_source, output=output,
                      compile_passed=compile_passed, compile_command=compile_command,
                      evaluator=runtime_evaluator, timeout=timeout, monotonic=monotonic,
                      context_factory=context_factory)


score = dispatch


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--platform", choices=("android", "arkts"), required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--base-source", type=Path, required=True)
    parser.add_argument("--final-source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--compile-passed", choices=("true", "false"), required=True)
    parser.add_argument("--compile-command", required=True)
    parser.add_argument("--timeout-seconds", type=float, default=3600)
    args = parser.parse_args()
    report = dispatch(platform=args.platform, source=args.source, base_source=args.base_source,
                      final_source=args.final_source, output=args.output,
                      compile_passed=args.compile_passed == "true", compile_command=args.compile_command,
                      timeout=args.timeout_seconds)
    core.write(args.output, report)
    print(json.dumps({"output": str(args.output), "publication": report["publication"],
                      "semantic": {key: report["semantic"][key]
                                   for key in ("passed", "failed", "notScored")}}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
