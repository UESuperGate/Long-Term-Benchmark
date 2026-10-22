#!/usr/bin/env python3
"""Formal source-parameterized revision-3 scorer for Task15 on both platforms."""

from __future__ import annotations

import argparse
import copy
import json
import re
import shutil
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
import task15_capability_probe
import task15_device_scheduling
import task15_native_environment


ROOT = core.ROOT
TASK_ID = "15_account_deactivation"
CONTRACT = ROOT / (
    "experiment_results/runtime_transition_20261020/contract_audit/revision_3/after/"
    "15_account_deactivation/transitions.json")
ASSETS = ROOT / "state_tests/runtime/android/15_account_deactivation"
MODAL_INVARIANT = (
    "the loading modal blocks form interaction without changing the form values or duplicating the request")
ANDROID_PREFERENCE_CASE = "ad_state_001_capability_gates_entry"
ANDROID_MODAL_CASE = "ad_state_006_confirm_sends_payload"
ANDROID_RENDERED_CASES = {"ad_state_003_password_enables_submit", "ad_state_008_failure_preserves_form"}
ANDROID_FINAL_FEATURE_ENTRY = (
    "features/deactivation/impl/src/main/kotlin/io/element/android/features/logout/impl/"
    "AccountDeactivationPresenter.kt")
ANDROID_DOMAIN_CASES = {
    "ad_state_002_default_form_blocks_submit",
    "ad_state_004_erase_data_option", "ad_state_005_first_submit_confirms",
    "ad_state_007_success_completes",
    "ad_state_009_retry_bypasses_confirmation", "ad_state_010_close_dialog_resets_action",
}
ARKTS_NATIVE_CASES = {
    "ad_state_001_capability_gates_entry", "ad_state_005_first_submit_confirms",
    "ad_state_006_confirm_sends_payload", "ad_state_008_failure_preserves_form",
    "ad_state_009_retry_bypasses_confirmation",
}
ARKTS_HOST_CASES = {
    "ad_state_002_default_form_blocks_submit", "ad_state_003_password_enables_submit",
    "ad_state_004_erase_data_option", "ad_state_007_success_completes",
    "ad_state_010_close_dialog_resets_action",
}


def _raw_rows(report: dict) -> list[dict]:
    return report.get("observations") or report.get("semantic", {}).get("cases", [])


def _healthy(report: dict) -> bool:
    value = report.get("runtimeCompile", {})
    return value.get("status") == "passed" or value.get("passed") is True


def _base_rows(report: dict, contract: dict, report_path: Path) -> Optional[list[dict]]:
    raw = {row.get("key"): row for row in _raw_rows(report)}
    result = []
    expected_prefix = {
        "settingsVisible": True,
        "positiveControl": "notification_settings_click",
        "positiveControlInvoked": True,
        "deactivateEntryVisible": False,
        "transitionExecuted": False,
    }
    for spec in contract["cases"]:
        row = raw.get(spec["key"])
        if row is None or row.get("status") != "pass" or row.get("observed") != expected_prefix:
            return None
        result.append(entry_evidence.entry_row(
            row, spec, report_path, report["provenance"]["productionSources"]))
    return result


def _checkpoint(row: dict, name: str) -> dict:
    return next((item.get("state", {}) for item in row.get("checkpoints", [])
                 if item.get("name") == name), {})


def _modal_row(raw: dict, spec: dict) -> dict:
    activated = _checkpoint(raw, "confirmation_control_activated")
    before = _checkpoint(raw, "loading_modal_before_global_input")
    after = _checkpoint(raw, "loading_modal_after_global_input")
    state_fields = ("password", "eraseData", "action", "requests")
    before_state = {key: before[key] for key in state_fields}
    after_state = {key: after[key] for key in state_fields}
    requests = activated.get("requests", [])
    if not requests:
        raise RuntimeError("Task15 modal runtime did not capture a deactivation request")
    return {
        "caseId": spec["caseId"], "key": spec["key"], "traceDigest": spec["traceDigest"],
        "status": "pass" if raw.get("status") == "pass" else "fail",
        "runtime": "robolectric_rendered_compose_global_input",
        "observed": {"action": "loading", "effect": "deactivate_account", "payload": requests[0]},
        "checkpoints": raw.get("checkpoints", []),
        "invariantChecks": [{
            "invariant": MODAL_INVARIANT,
            "status": "pass" if raw.get("observed", {}).get("formInputBlocked") is True and
            raw.get("observed", {}).get("requestCount") == 1 and before_state == after_state else "fail",
            "evidence": {"beforeGlobalInput": before, "afterGlobalInput": after,
                         "dispatches": raw.get("observed", {}).get("dispatches", [])},
        }],
    }


def _final_rows(preferences: dict, domain: dict, modal: dict, contract: dict) -> list[dict]:
    preference_rows = _raw_rows(preferences)
    modal_rows = _raw_rows(modal)
    if len(preference_rows) != 1 or len(modal_rows) != 3:
        raise RuntimeError("Task15 rendered conjunction did not return one row per isolated probe")
    rendered = {row["key"]: row for row in modal_rows}
    domain_rows = {row.get("key"): row for row in _raw_rows(domain)}
    result = []
    for spec in contract["cases"]:
        key = spec["key"]
        if spec["caseId"] == ANDROID_PREFERENCE_CASE:
            row = copy.deepcopy(preference_rows[0])
        elif spec["caseId"] == ANDROID_MODAL_CASE:
            row = _modal_row(rendered["loading_modal_blocks_input"], spec)
        elif spec["caseId"] in ANDROID_RENDERED_CASES:
            row = copy.deepcopy(rendered[key])
        elif spec["caseId"] in ANDROID_DOMAIN_CASES:
            row = copy.deepcopy(domain_rows.get(key))
            if row is None:
                raise RuntimeError(f"Task15 strict domain row missing: {spec['caseId']}")
        else:
            raise RuntimeError(f"Task15 Android evidence pole missing: {spec['caseId']}")
        row.update(caseId=spec["caseId"], key=key, traceDigest=spec["traceDigest"])
        result.append(row)
    return result


def _android_runtime(*, source: Path, output: Path, deadline: float, smoke: bool) -> dict:
    contract = core.load(CONTRACT)
    evidence = output.with_name(output.stem + "_evidence")
    if evidence.exists():
        raise FileExistsError(f"Refusing existing evidence: {evidence}")
    evidence.mkdir(parents=True)
    reports = {}
    rows = []
    failure = None
    removed_temporary_tree = None
    android_robolectric.compile_resources = compile_resources
    with tempfile.TemporaryDirectory(prefix="task15-formal-agent-") as raw:
        temporary = Path(raw)
        try:
            with core.bounded_file_lock(Path("/tmp/long-term-benchmark-android-full-build.lock"), deadline,
                                        "Task15 global Android build/probe lock"), \
                    core.bounded_file_lock(ROOT / "state_tests/runtime/android/.build.lock", deadline,
                                        "Task15 shared Android runtime lock"):
                core.require_build_space()
                if entry_evidence.prefix_closure.reviewed_source(TASK_ID, core.directory_digest(source)):
                    base_config = core.prepared_android_config(
                        source, ASSETS / "revision3/base-adapter.json", temporary)
                    reports["entry_probe"] = android_robolectric.run_slice(
                        TASK_ID, "agent", source.resolve(), ASSETS / "revision3", base_config,
                        evidence / "entry-probe.json", core.remaining_deadline(deadline, "Task15 entry probe"))
                    if not _healthy(reports["entry_probe"]):
                        raise RuntimeError("Task15 entry probe did not compile")
                    if not smoke:
                        rows = _base_rows(reports["entry_probe"], contract, evidence / "entry-probe.json") or []
                        if not rows:
                            raise RuntimeError("Task15 base entry runtime did not prove the missing feature entry")
                else:
                    preference_config = core.prepared_android_config(
                        source, ASSETS / "revision3/final-preferences-adapter.json", temporary)
                    reports["preferences"] = android_robolectric.run_slice(
                        TASK_ID, "agent", source.resolve(), ASSETS / "revision3", preference_config,
                        evidence / "preferences.json",
                        core.remaining_deadline(deadline, "Task15 preferences"))
                    if not _healthy(reports["preferences"]):
                        raise RuntimeError("Task15 preferences runtime did not compile")
                    if not smoke:
                        modal_config = core.prepared_android_config(
                            source, ASSETS / "rendered/adapter.json", temporary,
                            keys=["password_enables_submit", "loading_modal_blocks_input", "failure_preserves_form"])
                        reports["domain"] = android_runner.run(
                            TASK_ID, "agent", source.resolve(), evidence / "domain.json",
                            core.remaining_deadline(deadline, "Task15 domain"),
                            adapter_config=ASSETS / "adapter.json")
                        reports["modal"] = android_robolectric.run_slice(
                            TASK_ID, "agent", source.resolve(), ASSETS / "rendered", modal_config,
                            evidence / "modal.json", core.remaining_deadline(deadline, "Task15 modal"))
                        if not all(_healthy(reports[name]) for name in ("preferences", "domain", "modal")):
                            raise RuntimeError("Task15 revision-3 strict runtime conjunction did not compile")
                        rows = _final_rows(reports["preferences"], reports["domain"], reports["modal"], contract)
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


def _run(command: list[str], *, deadline: float, phase: str, log: Path) -> None:
    process = subprocess.run(command, cwd=ROOT, capture_output=True, text=True,
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
        raise ValueError("Task15 candidate bundleName is unavailable")
    return match.group(1)


def _retained_evidence(evidence: Path) -> dict:
    files = []
    for path in sorted(item for item in evidence.rglob("*") if item.is_file()):
        if path.suffix.lower() in core.BINARY_SUFFIXES:
            raise RuntimeError(f"Task15 retained binary escaped cleanup: {path}")
        files.append({"path": path.relative_to(evidence).as_posix(), "bytes": path.stat().st_size,
                      "sha256": core.sha256(path)})
    return {"path": str(evidence), "files": files, "binariesRetained": False}


def _hash_remove_tree(path: Path, evidence: Path) -> list[dict]:
    removed = []
    if not path.exists():
        return removed
    for item in sorted(candidate for candidate in path.rglob("*") if candidate.is_file()):
        removed.append({"path": item.relative_to(evidence).as_posix(), "bytes": item.stat().st_size,
                        "sha256": core.sha256(item)})
    shutil.rmtree(path)
    return removed


def _derive_base_command_logs(script: str) -> str:
    original = "const label = args.slice(0, 3).join('-').replace(/[^a-zA-Z0-9._-]/g, '_');"
    if script.count(original) != 1:
        raise RuntimeError("Task15 base command log derivation changed")
    return script.replace(original,
        "const label = args.slice(0, 3).join('-').replace(/[^a-zA-Z0-9._-]/g, '_').slice(0, 120) + "
        "'-' + digest(Buffer.from(JSON.stringify(args))).slice(0, 16);")


def _derive_base_install_ownership(script: str) -> str:
    anchor = "if (!run(['install', '-r', hap], [0], 120000).includes('install bundle successfully')) {"
    if script.count(anchor) != 1:
        raise RuntimeError("Task15 base install ownership derivation changed")
    # The immediately preceding inventory already rejects any preinstalled bundle.
    # Install can succeed before log persistence throws, so cleanup must own the attempt.
    return script.replace(anchor, "appOwned = true;\n      " + anchor)


def _task15_base_device(*, source: Path, evidence: Path, deadline: float,
                        device_serial: Optional[str]) -> tuple[list[dict], list[dict]]:
    build_dir = evidence / "base-application"
    build = core.build_arkts_application(source=source, output=build_dir, deadline=deadline,
                                         label="task15-base-runtime")
    build_report = build_dir / "application-build.json"
    hap = Path(build["hap"]["path"])
    original = ROOT / "scripts/runtime_semantics/Task15BaseAllDevice.cjs"
    script = original.read_text(encoding="utf-8")
    replacements = {
        "const root = path.resolve(__dirname, '../..');": f"const root = {json.dumps(str(ROOT))};",
        "const bundleName = 'com.qingyu.elementx.deactivation.base';":
            f"const bundleName = {json.dumps(_bundle_name(source))};",
        "const buildReport = path.join(root,\n  'experiment_results/runtime_transition_20261020/task15_repair/v3/build-base-eexist-repair/report.json');":
            f"const buildReport = {json.dumps(str(build_report))};",
        "const hapRecord = build.haps?.[0];": "const hapRecord = build.hap;",
        "build.role !== 'base'": "build.role !== 'agent'",
        "build.compile?.passed !== true": "build.passed !== true",
        "build.productionCopyUnchanged !== true": "build.copiedProductionUnchanged !== true",
        "build.temporaryWorkspaceRemoved !== true": "build.temporaryProjectRemoved !== true",
        "for (const source of build.production) {": "for (const source of build.sources) {",
        "production: build.production, source:": "production: build.sources, source:",
        "platform: 'arkts', role: 'base',": "platform: 'arkts', role: 'agent',",
        ("invariantChecks: spec.invariants.map(text => ({ text, passed: false,\n"
         "          reason: 'The final-version deactivation transition cannot execute from this base settings UI.' })),"):
            "invariantChecks: [], unevaluatedInvariants: spec.invariants,",
    }
    for old, new in replacements.items():
        count = script.count(old)
        if count != 1:
            raise RuntimeError(f"Task15 base runner derivation point changed: {old[:50]} ({count})")
        script = script.replace(old, new)
    script = _derive_base_command_logs(script)
    script = task15_device_scheduling.base_case_leases(script,
        serial=_discover_device(device_serial, deadline), deadline=deadline)
    script = _derive_base_install_ownership(script)
    derived = evidence / "task15-base-source-parameterized.cjs"
    derived.write_text(script, encoding="utf-8")
    output = evidence / "base-device"
    node = "/Applications/DevEco-Studio.app/Contents/tools/node/bin/node"
    _run([node, str(derived), "--output", str(output)], deadline=deadline,
         phase="Task15 base missing-entry device runtime", log=evidence / "base-device.log")
    report = core.load(output / "report.json")
    semantic = report.get("semantic", {})
    if report.get("status") != "passed" or (
            semantic.get("passed"), semantic.get("failed"), semantic.get("notScored")) != (0, 10, 0):
        raise RuntimeError("Task15 base device runtime did not prove 0P/10F/0NS")
    contract = core.load(CONTRACT)
    specs = {item["caseId"]: item for item in contract["cases"]}
    rows = []
    for raw in semantic.get("cases", []):
        spec = specs.get(raw.get("caseId"))
        if spec is None:
            raise RuntimeError("Task15 base device runtime returned an unknown canonical case")
        rows.append(arkts_entry_evidence.entry_row(
            raw, spec, output / "report.json", build["sources"]))
    return rows, core.remove_binary_artifacts(evidence)


def _discover_device(requested: Optional[str], deadline: float) -> str:
    if requested:
        return requested
    hdc = Path.home() / "Library/OpenHarmony/Sdk/23/toolchains/hdc"
    process = subprocess.run([str(hdc), "list", "targets"], capture_output=True, text=True,
                             timeout=min(30, core.remaining_deadline(deadline, "Task15 device discovery")))
    targets = [line.strip() for line in process.stdout.splitlines()
               if line.strip() and line.strip() != "[Empty]"]
    if process.returncode or len(targets) != 1:
        raise RuntimeError(f"Expected one OpenHarmony API23 target, found {targets!r}")
    return targets[0]


def _native_checkpoints(case_id: str, evidence: dict) -> list[dict]:
    login = evidence.get("login", {})
    first = evidence.get("firstSubmit", {})
    pending = evidence.get("pending", {})
    failure = evidence.get("failure", {})
    retry = evidence.get("retry", {})
    values = {
        "ad_state_001_capability_gates_entry": [("before_login", {
            "entryVisible": not login["entryHiddenBeforeLogin"] if isinstance(login.get("entryHiddenBeforeLogin"), bool) else None}),
                                                  ("after_capability_login", login)],
        "ad_state_005_first_submit_confirms": [("form_ready", login), ("first_submit", first)],
        "ad_state_006_confirm_sends_payload": [("confirmed", first), ("request_pending", pending)],
        "ad_state_008_failure_preserves_form": [("request_pending", pending), ("request_failed", failure)],
        "ad_state_009_retry_bypasses_confirmation": [("request_failed", failure), ("retry_pending", retry)],
    }
    return [{"name": name, "state": copy.deepcopy(state)} for name, state in values[case_id]]


def _derive_native_environment(script: str) -> str:
    anchor = "await device('screen-wakeup', ['shell', 'power-shell', 'wakeup']);"
    if script.count(anchor) != 1:
        raise RuntimeError("Task15 certificate permission preflight derivation changed")
    preflight = """let certificatePermissionReady = false;
    for (let attempt = 1; attempt <= 50; attempt++) {
      const inventory = await device('certificate-permission-' + attempt,
        ['shell', 'atm', 'dump', '-t', '-b', bundleName]);
      const token = JSON.parse(inventory.slice(inventory.indexOf('{')));
      const permission = token.permStateList?.find(item => item.permissionName === 'ohos.permission.ACCESS_CERT_MANAGER');
      if (permission?.grantStatus === 0) { certificatePermissionReady = true; break; }
      await sleep(100);
    }
    if (!certificatePermissionReady) throw new Error('Test-only certificate permission did not become ready');
    await device('force-stop-owned-app-before-test', ['shell', 'aa', 'force-stop', bundleName]);
    """
    return script.replace(anchor, preflight + anchor)


def _task15_native_rows(*, source: Path, evidence: Path, contract: dict, deadline: float,
                        device_serial: Optional[str]) -> tuple[dict[str, dict], list[dict]]:
    core.require_build_space()
    original = ROOT / "scripts/runtime_semantics/task15_native_e2e.cjs"
    script = original.read_text(encoding="utf-8")
    verifier = ROOT / "state_tests/runtime/arkts/native/Task15NativeE2E.verifier.cjs"
    replacements = {
        "require('../../state_tests/runtime/arkts/native/Task15NativeE2E.verifier.cjs')":
            f"require({json.dumps(str(verifier))})",
        "const root = path.resolve(__dirname, '../..');": f"const root = {json.dumps(str(ROOT))};",
        ("const source = path.join(root, 'final_" +
         "dev_nodes/15_account_deactivation_final_0_6_3');"):
            f"const source = {json.dumps(str(source.resolve()))};",
        "'--fixture', 'bundle', '--role', 'final', '--case'":
            "'--fixture', 'bundle', '--role', 'agent', '--case'",
    }
    for old, new in replacements.items():
        expected = 2 if old == "const root = path.resolve(__dirname, '../..');" else 1
        if script.count(old) != expected:
            raise RuntimeError(f"Task15 E2E derivation point changed: {old[:60]}")
        script = script.replace(old, new, 1)
    script = task15_device_scheduling.native_scenario_lease(script, deadline=deadline)
    script = _derive_native_environment(script)
    fixture, installer = task15_native_environment.prepare(evidence)
    script = task15_native_environment.derive_runtime(script, fixture, installer)
    derived = evidence / "task15-native-e2e-source-parameterized.cjs"
    derived.write_text(script, encoding="utf-8")
    output = evidence / "native-e2e"
    node = "/Applications/DevEco-Studio.app/Contents/tools/node/bin/node"
    _run([node, str(derived), "--output-dir", str(output), "--serial",
          _discover_device(device_serial, deadline)], deadline=deadline,
         phase="Task15 native HTTPS ArkUI E2E", log=evidence / "native-e2e.log")
    run = core.load(output / "run.json")
    execution = output / "execution"
    verification = core.load(execution / "verification.json")
    native_evidence = core.load(execution / "native-e2e-evidence.json")
    provider = core.load(execution / "provider-transcript.json")
    native_result = core.load(execution / "native-result.json")
    if run.get("status") != "passed" or (verification.get("passed"), verification.get("total")) != (15, 15):
        raise RuntimeError("Task15 independent native E2E verifier did not pass 15/15")
    if run.get("cleanup") != {"appUninstalled": True, "reverseRemoved": True,
                               "serverClosed": True, "privateKeysRemoved": True}:
        raise RuntimeError("Task15 native E2E cleanup is incomplete")
    if native_result.get("role") != "agent":
        raise RuntimeError("Task15 native E2E was not built in agent role")
    for item in run.get("sourceHashes", []):
        path = source / item["path"]
        if not path.is_file() or core.sha256(path) != item["sha256"]:
            raise RuntimeError(f"Task15 native E2E source binding changed: {item['path']}")
    login = native_evidence.get("login", {})
    first = native_evidence.get("firstSubmit", {})
    pending = native_evidence.get("pending", {})
    failure = native_evidence.get("failure", {})
    retry = native_evidence.get("retry", {})
    requests = [item for item in provider.get("requests", []) if item.get("kind") == "deactivation"]
    entry_color = login.get("entryInspector", {}).get("$attrs", {}).get("foregroundColor")
    native_observed = {
        "ad_state_001_capability_gates_entry": {"deactivateEntryVisible": login.get("entryVisible"),
            "entryStyle": "destructive" if entry_color == "#FFB42318" else entry_color},
        "ad_state_005_first_submit_confirms": {"action": first.get("action"),
            "requestCount": first.get("logicalServiceCalls"),
            "confirmationVisible": first.get("confirmationVisible")},
        "ad_state_006_confirm_sends_payload": {"action": pending.get("action"),
            "effect": "deactivate_account" if requests else None,
            "payload": {"password": pending.get("passwordAfterInputAttempt"),
                        "eraseData": requests[0].get("body", {}).get("erase") if requests else None}},
        "ad_state_008_failure_preserves_form": {"action": failure.get("action"),
            "password": failure.get("password"), "eraseData": failure.get("eraseData"),
            "retryEnabled": failure.get("retryVisible")},
        "ad_state_009_retry_bypasses_confirmation": {"action": retry.get("action"),
            "requestCount": retry.get("logicalServiceCalls"),
            "confirmationVisible": retry.get("confirmationVisible")},
    }
    invariant_pass = {
        "ad_state_001_capability_gates_entry": login.get("entryHiddenBeforeLogin") is True,
        "ad_state_005_first_submit_confirms": first.get("logicalServiceCalls") == 0,
        "ad_state_006_confirm_sends_payload": pending.get("modalVisible") is True and
            pending.get("passwordAfterInputAttempt") == "secret" and
            pending.get("eraseDataAfterInputAttempt") is True and
            pending.get("logicalServiceCalls") == 1 and len(requests) == 4,
        "ad_state_008_failure_preserves_form": failure.get("action") == "failure" and
            failure.get("loadingModalVisible") is False,
        "ad_state_009_retry_bypasses_confirmation": retry.get("password") == "secret" and
            retry.get("eraseData") is True and retry.get("confirmationVisible") is False,
    }
    specs = {item["caseId"]: item for item in contract["cases"]}
    rows = {}
    for case_id in ARKTS_NATIVE_CASES:
        spec = specs[case_id]
        rows[case_id] = {
            "caseId": case_id, "key": spec["key"], "traceDigest": spec["traceDigest"],
            "status": "pass" if invariant_pass[case_id] else "fail",
            "failureKind": None if invariant_pass[case_id] else "semantic_state_mismatch",
            "runtime": "openharmony_api23_device_https_arkui",
            "observed": native_observed[case_id],
            "checkpoints": _native_checkpoints(case_id, native_evidence),
            "invariantChecks": [{"invariant": text,
                                  "status": "pass" if invariant_pass[case_id] else "fail",
                                  "evidence": {"verificationPassed": verification.get("passed"),
                                               "verificationTotal": verification.get("total")}}
                                 for text in spec.get("invariants", [])],
        }
    removed = []
    for intermediate in (output / "build", output / "certificates", output / "preserved-work"):
        removed.extend(_hash_remove_tree(intermediate, evidence))
    removed.extend(core.remove_binary_artifacts(output))
    return rows, removed


def _task15_final_poles(*, source: Path, evidence: Path, contract: dict, deadline: float,
                        device_serial: Optional[str]) -> tuple[list[dict], list[dict]]:
    node = "/Applications/DevEco-Studio.app/Contents/tools/node/bin/node"
    host_output = evidence / "host-production-presenter.json"
    _run([node, str(ROOT / "scripts/runtime_semantics/arkts_runtime.cjs"), "--task", TASK_ID,
          "--source", str(source), "--role", "agent", "--output", str(host_output)],
         deadline=deadline, phase="Task15 host production-presenter runtime",
         log=evidence / "host-production-presenter.log")
    host = core.load(host_output)
    host_rows = {item.get("caseId"): item for item in host.get("semantic", {}).get("cases", [])}
    specs = {item["caseId"]: item for item in contract["cases"]}
    rows = {}
    for case_id in ARKTS_HOST_CASES:
        raw = host_rows.get(case_id)
        if raw is None or raw.get("status") not in {"pass", "fail"}:
            raise RuntimeError(f"Task15 host pole did not produce scoreable {case_id}")
        spec = specs[case_id]
        rows[case_id] = {**raw, "caseId": case_id, "key": spec["key"],
                         "traceDigest": spec["traceDigest"],
                         "runtime": "host_transpiled_current_production_presenter"}
    native_rows, removed = _task15_native_rows(
        source=source, evidence=evidence, contract=contract, deadline=deadline,
        device_serial=device_serial)
    capability = task15_capability_probe.evaluate(
        source=source, output=evidence / "unsupported-capability", deadline=deadline,
        device_serial=device_serial)
    unsupported = core.load(evidence / "unsupported-capability/observation.json")
    capability_row = native_rows["ad_state_001_capability_gates_entry"]
    capability_row["checkpoints"].extend(unsupported["checkpoints"])
    capability_row["invariantChecks"] = [{
        "invariant": text, "status": "pass" if capability["invariantPassed"] else "fail",
        "evidence": {"unsupportedCapability": {"path": str(evidence / "unsupported-capability/report.json"),
            "sha256": core.sha256(evidence / "unsupported-capability/report.json")},
            "observed": unsupported.get("observed")}}
        for text in specs["ad_state_001_capability_gates_entry"]["invariants"]]
    if not capability["invariantPassed"]:
        capability_row.update(status="fail", failureKind="semantic_state_mismatch")
    removed.extend(capability["removedBinaries"])
    rows.update(native_rows)
    if set(rows) != set(specs):
        raise RuntimeError("Task15 exact four-pole composition is incomplete")
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
                                                 deadline=deadline, label="task15-agent-smoke")
            if build.get("passed") is not True:
                raise RuntimeError("Task15 candidate application smoke build did not pass")
            removed.extend(core.remove_binary_artifacts(evidence / "candidate-smoke"))
        elif arkts_entry_evidence.closure.reviewed_source(TASK_ID, core.directory_digest(source)):
            rows, base_removed = _task15_base_device(source=source, evidence=evidence,
                                                     deadline=deadline, device_serial=device_serial)
            removed.extend(base_removed)
        else:
            rows, final_removed = _task15_final_poles(
                source=source, evidence=evidence, contract=contract, deadline=deadline,
                device_serial=device_serial)
            removed.extend(final_removed)
        runtime_passed = True
    except Exception as error:
        failure = f"{type(error).__name__}: {error}"
    for intermediate in (evidence / "native-e2e/build", evidence / "native-e2e/certificates",
                         evidence / "native-e2e/preserved-work"):
        removed.extend(_hash_remove_tree(intermediate, evidence))
    removed.extend(core.remove_binary_artifacts(evidence))
    report = core.normalized_runtime_report(
        task_id=TASK_ID, platform="arkts", source=source, contract=contract, rows=rows,
        runtime_passed=runtime_passed, transport="transport_completed" if runtime_passed else "failed",
        retained=_retained_evidence(evidence), temporary_removed=True, reason=failure)
    packaging = []
    for path in (evidence / "base-application/application-build.json",
                 evidence / "candidate-smoke/application-build.json",
                 evidence / "unsupported-capability/build/device-build-report.json"):
        if path.is_file():
            build = core.load(path)
            packaging.append({"path": str(path), "sha256": core.sha256(path),
                "passed": build.get("passed", build.get("runtimeCompile", {}).get("passed"))})
    native_run = evidence / "native-e2e/run.json"
    if native_run.is_file():
        native = core.load(native_run)
        packaging.append({"path": str(native_run), "sha256": core.sha256(native_run),
            "passed": bool(native.get("buildReport") and native.get("productionUnchanged") is True and
                           native.get("copiedProductionUnchanged") is True and len(native.get("haps", [])) >= 2)})
    if packaging and all(item["passed"] is True for item in packaging):
        report["runtimeCompile"] = {"passed": True, "status": "passed",
            "scope": "actual evaluator HAP packaging; runtime transport/readiness is separate"}
    report["diagnostics"]["runtimePackagingEvidence"] = packaging
    report["diagnostics"]["cleanup"]["removedBinaries"] = removed
    report["diagnostics"]["evidenceComposition"] = {
        "base": "API23 device missing-entry with isolated install per case",
        "final": {"deviceHttpsArkUi": sorted(ARKTS_NATIVE_CASES),
                  "hostProductionPresenter": sorted(ARKTS_HOST_CASES)},
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
    # Each original UI scenario owns its lease after packaging, not the scorer group.
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
