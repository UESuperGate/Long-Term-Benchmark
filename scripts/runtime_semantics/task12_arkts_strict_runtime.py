#!/usr/bin/env python3
"""Live source-parameterized OpenHarmony device evaluator for Task12."""

from __future__ import annotations

import json
from pathlib import Path
import re
import time

try:
    from . import task12_13_formal_core as formal
    from . import task12_13_runtime_support as support
    from . import task12_live_entry_validation as entry_validation
    from .task14_15_formal_core import build_arkts_application
except ImportError:
    import task12_13_formal_core as formal
    import task12_13_runtime_support as support
    import task12_live_entry_validation as entry_validation
    from task14_15_formal_core import build_arkts_application


ROOT = formal.ROOT
TASK_ID = "12_report_room"
BASE_RUNNER = ROOT / "scripts/runtime_semantics/Task12BaseDeviceEntry.cjs"
FINAL_RUNNER = ROOT / "scripts/runtime_semantics/Task12FinalDevice.cjs"
HDC = Path.home() / "Library/OpenHarmony/Sdk/23/toolchains/hdc"


def retry_transport_failure(log_text: str, attempt: int) -> bool:
    return attempt < 3 and ("ETIMEDOUT" in log_text or "timed out" in log_text.lower() or
                            "Device not found or connected" in log_text)


def _bundle_name(source: Path) -> str:
    value = (source / "AppScope/app.json5").read_text(encoding="utf-8")
    match = re.search(r'"bundleName"\s*:\s*"([^"]+)"', value)
    if not match:
        raise ValueError("Task12 candidate AppScope/app.json5 has no bundleName")
    return match.group(1)


def _derived_runner(*, template: Path, target: Path, bundle: str, hap: Path,
                    build_report: Path, contract: Path, serial: str, port: int) -> None:
    source = template.read_text(encoding="utf-8")
    log_name_expression = "args.slice(0, 3).join('-').replace(/[^a-zA-Z0-9._-]/g, '_')"
    safe_log_name_expression = "safeCommandLogStem(args)"
    safe_log_name_helper = """
const safeCommandLogStem = args => {
  const full = args.slice(0, 3).join('-').replace(/[^a-zA-Z0-9._-]/g, '_');
  if (full.length <= 96) return full;
  return full.slice(0, 72) + '-' + sha(Buffer.from(full)).slice(0, 16);
};
const predicateSampleReady = (predicate, nodes) => {
  try { return predicate(nodes); }
  catch (error) {
    if (/^Expected one visible [a-zA-Z0-9_]+, found 0$/.test(error.message)) return false;
    throw error;
  }
};
const readDeviceLayout = (run, directory, remote) => {
  for (let attempt = 0; attempt < 5; attempt++) {
    const text = run(['shell', 'cat', remote], directory);
    try { return JSON.parse(text); }
    catch (error) {
      if (!(error instanceof SyntaxError) || !error.message.includes('Unexpected end of JSON')) throw error;
      if (attempt === 4) throw error;
      Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, 50);
    }
  }
};
"""
    replacements = [
        ("const root = path.resolve(__dirname, '../..');", f"const root = {json.dumps(str(ROOT))};"),
        ("const hdc = path.join(process.env.HOME, 'Library/OpenHarmony/Sdk/23/toolchains/hdc');",
         f"const hdc = {json.dumps(str(HDC))};\nconst hdcTargetArgs = {json.dumps(['-t', serial])};"),
        ("spawnSync(hdc, args,", "spawnSync(hdc, [...hdcTargetArgs, ...args],"),
    ]
    for before, after in replacements:
        if before not in source:
            raise ValueError(f"Task12 device-runner shape changed: {before}")
        source = source.replace(before, after)
    if source.count(log_name_expression) != 1:
        raise ValueError("Task12 device-runner command log naming shape changed")
    source = source.replace(log_name_expression, safe_log_name_expression)
    helper_anchor = "const sleep = milliseconds => new Promise(resolve => setTimeout(resolve, milliseconds));\n"
    if source.count(helper_anchor) != 1:
        raise ValueError("Task12 device-runner helper anchor changed")
    source = source.replace(helper_anchor, helper_anchor + safe_log_name_helper, 1)
    if template == BASE_RUNNER:
        source = source.replace("if (request.url.endsWith('/joined_rooms')) response.end",
                                "if (request.url === '/_matrix/client/versions') response.end(JSON.stringify({versions: ['v1.13']}));\n      else if (request.url.endsWith('/joined_rooms')) response.end")
        source = source.replace("const data = run(['shell', 'cat', remote], directory);\n    const parsed = JSON.parse(data);",
                                "const parsed = readDeviceLayout(run, directory, remote);")
        absence = "reportMatches(details).length || reportMatches(stable).length) throw new Error('Common start or stable entry absence failed');"
        if source.count(absence) != 1:
            raise ValueError("Task12 common device entry shape changed")
        source = source.replace(absence, "false) throw new Error('Common starting state failed');\n"
                                "      const available = reportMatches(details).length > 0;\n"
                                "      if (available !== (reportMatches(stable).length > 0)) throw new Error('Unstable report entry');")
        row_anchor = "      rows.push({ caseId: spec.caseId, traceDigest: spec.traceDigest, status: 'fail', transitionExecuted: false,"
        availability = """      if (available) {
        const entry = requireOne(stable.nodes, 'report_room_entry');
        if (entry.enabled !== 'true') throw new Error('Report entry is not enabled');
        rows.push({caseId: spec.caseId, traceDigest: spec.traceDigest, status: 'pass',
          discovery: {entryAvailable: true, caseRunId, positiveControl: 'leave_confirmation_and_cancel',
            requests: caseRequests, layouts: [details.artifact, stable.artifact, confirmation.artifact, restored.artifact]}});
        run(['uninstall', bundleName], directory);
        continue;
      }
"""
        if source.count(row_anchor) != 1:
            raise ValueError("Task12 common device row shape changed")
        source = source.replace(row_anchor, availability + row_anchor)
        request_sequence = "'/_matrix/client/v3/joined_rooms|/_matrix/client/v3/rooms/!room%3Aexample.org/state' ||"
        if source.count(request_sequence) != 1:
            raise ValueError("Task12 common device HTTP sequence shape changed")
        source = source.replace(request_sequence,
                                "('/_matrix/client/v3/joined_rooms|/_matrix/client/v3/rooms/!room%3Aexample.org/state' +\n"
                                "          (available ? '|/_matrix/client/versions' : '')) ||")
        source = source.replace("passed: 0, failed: rows.length, notScored: 0, cases: rows",
                                "passed: rows.filter(row => row.status === 'pass').length, failed: rows.filter(row => row.status === 'fail').length, notScored: 0, cases: rows")
    else:
        source = source.replace("JSON.parse(run(['shell', 'cat', remote], directory))",
                                "readDeviceLayout(run, directory, remote)")
    cleanup_anchor = "      const cleanup = path.join(output, 'cleanup');"
    if source.count(cleanup_anchor) != 1:
        raise ValueError("Task12 device cleanup audit anchor changed")
    source = source.replace(cleanup_anchor,
                            "      fs.writeFileSync(path.join(output, 'server-requests.audit.json'), JSON.stringify(requests, null, 2));\n" + cleanup_anchor)
    predicate_before = "if (predicate(latest.nodes)) return"
    if source.count(predicate_before) != 1:
        raise ValueError("Task12 device-runner bounded wait shape changed")
    source = source.replace(predicate_before, "if (predicateSampleReady(predicate, latest.nodes)) return", 1)
    source, bundle_count = re.subn(r"const bundleName = '[^']+';", f"const bundleName = {json.dumps(bundle)};", source, count=1)
    source, hap_count = re.subn(r"const hap = path\.join\(root, '[^']+'\);", f"const hap = {json.dumps(str(hap))};", source, count=1)
    source, report_count = re.subn(r"const buildReport = path\.join\(root, '[^']+'\);",
                                   f"const buildReport = {json.dumps(str(build_report))};", source, count=1)
    source, contract_count = re.subn(
        r"const contractFile = path\.join\(root,\s*'[^']+'\);",
        f"const contractFile = {json.dumps(str(contract))};", source, count=1,
    )
    source, port_count = re.subn(r"const port = \d+;", f"const port = {port};", source, count=1)
    if (bundle_count, hap_count, report_count, contract_count, port_count) != (1, 1, 1, 1, 1):
        raise ValueError("Task12 device-runner constants could not be source-parameterized exactly")
    target.write_text(source, encoding="utf-8")


def evaluate(*, task, platform: str, source: Path, role: str, output: Path,
             deadline: float, device_serial: str | None = None) -> dict:
    if platform != "arkts":
        raise ValueError("Task12 ArkTS evaluator received another platform")
    source = source.resolve()
    serial = device_serial or "127.0.0.1:5555"
    contract = formal.load(task.contract)
    evidence = output.with_suffix(".arkts-evidence")
    evidence.mkdir(parents=True, exist_ok=False)
    build_dir = evidence / "application-build"
    build = build_arkts_application(
        source=source, output=build_dir, deadline=deadline, label=f"task12-{role}",
    )
    if build.get("passed") is not True or build.get("productionUnchanged") is not True:
        raise RuntimeError("Task12 source-specific application HAP did not compile cleanly")
    hap = Path(build["hap"]["path"]).resolve()
    shim = {
        "schemaVersion": 1,
        "status": "built_not_executed",
        "role": role,
        "source": str(source),
        "productionUnchanged": build["productionUnchanged"],
        "sourceUnchanged": build["productionUnchanged"],
        "copiedProductionUnchanged": build.get("copiedProductionUnchanged"),
        "temporaryProjectRemoved": build.get("temporaryProjectRemoved"),
        "hap": build["hap"],
        "applicationBuild": formal.file_record(build_dir / "application-build.json"),
    }
    shim_path = evidence / "device-build-report.json"
    formal.write(shim_path, shim)
    attempts = []

    def execute_stage(stage, template, port):
        derived = evidence / f"task12-{stage}-device.generated.cjs"
        _derived_runner(template=template, target=derived, bundle=_bundle_name(source), hap=hap,
                        build_report=shim_path, contract=task.contract, serial=serial, port=port)
        for attempt in range(1, 4):
            device_output = evidence / f"{stage}-execution-attempt-{attempt}"
            log = evidence / f"{stage}-command-attempt-{attempt}.log"
            try:
                support.run(
                    ["node", str(derived), "--output", str(device_output)], deadline=deadline,
                    phase=f"Task12 {role} OpenHarmony device runtime attempt {attempt}", log=log,
                )
                attempts.append({"stage": stage, "attempt": attempt, "status": "completed", "log": formal.file_record(log)})
                name = "arkts_12_report_room_base.device-entry.json" if template == BASE_RUNNER else "arkts_12_report_room_final.device.json"
                return device_output / name, log, derived
            except RuntimeError:
                text = log.read_text(encoding="utf-8") if log.is_file() else ""
                attempts.append({"attempt": attempt, "status": "transport_failed",
                                 "retryable": retry_transport_failure(text, attempt),
                                 "log": formal.file_record(log) if log.is_file() else None})
                if not retry_transport_failure(text, attempt):
                    raise
                support.wait_hdc_connected(
                    serial=serial, deadline=deadline,
                    log=evidence / f"{stage}-hdc-readiness-retry-{attempt}.log",
                )
        raise RuntimeError("Task12 device runtime produced no execution attempt")

    with support.arkts_device_lock(serial=serial, deadline=deadline):
        support.wait_hdc_connected(serial=serial, deadline=deadline, log=evidence / "hdc-readiness.log")
        discovery_path, log, derived = execute_stage("common-entry", BASE_RUNNER, 18731)
        discovery = formal.load(discovery_path)
        discovered = discovery.get("semantic", {}).get("cases", [])
        missing = len(discovered) == 10 and all(row.get("status") == "fail" and
                    row.get("entryFailureEvidence", {}).get("reportEntryCount") == 0 for row in discovered)
        available = len(discovered) == 10 and all(row.get("status") == "pass" and
                    row.get("discovery", {}).get("entryAvailable") is True for row in discovered)
        if missing:
            raw_path = discovery_path
        elif available:
            raw_path, log, derived = execute_stage("final", FINAL_RUNNER, 18732)
        else:
            raise RuntimeError("Task12 common production UI prefix incomplete or inconsistent")
    raw = formal.load(raw_path)
    if raw.get("diagnostics", {}).get("cleanup", {}).get("ownedAppUninstalled") is not True:
        raise RuntimeError("Task12 device runner did not uninstall its owned application")
    if missing:
        assessment = entry_validation.arkts.verify(raw_path)
        assessment["rawReport"] = formal.file_record(raw_path)
        verified_path = evidence / "independent-device-entry-verification.json"
        formal.write(verified_path, assessment)
        rows = entry_validation.entry_rows(
            contract, raw, raw_path, "arkts", device_verification=formal.file_record(verified_path),
        )
    else:
        rows = support.canonical_rows(contract, raw.get("semantic", {}).get("cases", []), role=role)
    lineage = formal.calibrator_lineage(task, "arkts")
    return support.strict_report(
        task=task, platform="arkts", source=source, role=role, rows=rows,
        runtime_compile={"passed": True, "status": "passed",
                         "scope": "source-specific production HAP plus device evaluator"},
        lineage=lineage, runtime_kind="openharmony api23 device uitest production arkvm",
        transport="transport_completed",
        evidence={"build": formal.file_record(shim_path), "raw": formal.file_record(raw_path),
                  "commonEntry": formal.file_record(discovery_path),
                  "runner": formal.file_record(derived), "log": formal.file_record(log),
                  "executionAttempts": attempts},
        output=output,
    )


def main() -> int:
    args = support.parse_args(__doc__ or "Task12 ArkTS strict runtime")
    try:
        from .task12_formal_agent import SPEC
    except ImportError:
        from task12_formal_agent import SPEC
    report = evaluate(task=SPEC, platform="arkts", source=args.source, role=args.role,
                      output=args.output, deadline=time.monotonic() + args.deadline_seconds,
                      device_serial=args.device_serial)
    print(json.dumps({"output": str(args.output), "semantic": report["semantic"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
