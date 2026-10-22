#!/usr/bin/env python3
"""Live source-parameterized OpenHarmony device evaluator for Task13 revision 5."""

from __future__ import annotations

import json
from pathlib import Path
import time

try:
    from . import task12_13_formal_core as formal
    from . import task12_13_runtime_support as support
    from .task14_15_formal_core import build_arkts_application
    from . import task13_page_owner_entry_audit_v8 as entry_audit
except ImportError:
    import task12_13_formal_core as formal
    import task12_13_runtime_support as support
    from task14_15_formal_core import build_arkts_application
    import task13_page_owner_entry_audit_v8 as entry_audit


ROOT = formal.ROOT
TASK_ID = "13_user_verification"
BUILD = ROOT / "scripts/runtime_semantics/task13_arkts_revision5_build.cjs"
EXECUTE = ROOT / "scripts/runtime_semantics/task13_arkts_revision5_execute.cjs"
COMMON_ENTRY = ROOT / "scripts/runtime_semantics/Task13CommonDeviceEntry.cjs"


def retry_device_attempt(statuses: list[str | None], expected: str, attempt: int) -> bool:
    return not (len(statuses) == 10 and all(status == expected for status in statuses)) and \
        "not_scored" in statuses and attempt < 3


def reject_unexecuted_base_projection(contract, rows):
    specs = {item["caseId"]: item for item in contract["cases"]}
    for row in rows:
        spec = specs[row["caseId"]]
        row.update(
            status="not_scored", transitionExecuted=False, observed=None, invariantChecks=[],
            unevaluatedInvariants=spec["invariants"], unobservedExpectedFields=list(spec["expected"]),
            notScoredPhase="given" if spec["key"] == "identity_violation_surfaces" else "entry_evidence",
            reason=("The retained base adapter projects unavailable post-state and false invariants; "
                    "these are not executed observations. A source-bound missing-entry policy is required."
                    if spec["key"] != "identity_violation_surfaces" else
                    "Base runtime did not establish the encrypted-room identity-violation given; "
                    "missing production inputs cannot be scored as semantic failures."),
        )
    return rows


def evaluate(*, task, platform: str, source: Path, role: str, output: Path,
             deadline: float, device_serial: str | None = None) -> dict:
    if platform != "arkts":
        raise ValueError("Task13 ArkTS evaluator received another platform")
    source = source.resolve()
    deadline -= 60  # Keep cleanup inside the caller's single overall deadline.
    support.remaining(deadline, 'Task13 work plus cleanup reserve')
    if (formal.sha256(task.contract) != formal.sha256(task.audited_contract) or
            formal.sha256(task.contract) != task.expected_contract_sha256):
        raise ValueError("Task13 canonical contract differs from its pinned audited revision5")
    serial = device_serial or "127.0.0.1:5555"
    contract = formal.load(task.contract)
    evidence = output.with_suffix(".arkts-evidence")
    evidence.mkdir(parents=True, exist_ok=False)
    inventory_path = evidence / "source-inventory.json"
    inventory = formal.source_inventory(source)
    formal.write(inventory_path, inventory)
    build_dir = evidence / "device-build"
    common_build = evidence / "common-application-build"
    application = build_arkts_application(source=source, output=common_build, deadline=deadline,
                                          label="task13-common-profile")
    if application.get("passed") is not True or application.get("productionUnchanged") is not True:
        raise RuntimeError("Task13 common profile HAP did not compile")
    with support.arkts_device_lock(serial=serial, deadline=deadline):
        support.wait_hdc_connected(serial=serial, deadline=deadline, log=evidence / "discovery-hdc-readiness.log")
        support.run(["node", str(COMMON_ENTRY), "--source", str(source), "--output", str(evidence / "common-entry"),
                     "--build-report", str(common_build / "application-build.json"), "--serial", serial,
                     "--hdc", str(Path.home() / "Library/OpenHarmony/Sdk/23/toolchains/hdc")],
                    deadline=deadline, phase="Task13 common production profile UI", log=evidence / "common-entry.log")
    discovery_path = evidence / "common-entry/discovery.json"
    discovery = formal.load(discovery_path)
    internal_role = discovery.get("observedBinding")
    if (internal_role not in {"base", "final"} or discovery.get("source") != str(source) or
            discovery.get("freshInstall") is not True or discovery.get("ownedAppUninstalled") is not True or
            discovery.get("status") != "production_common_entry_completed" or not discovery.get("positiveControl")):
        raise RuntimeError("Task13 production UI discovery was not source bound or complete")
    build_log = evidence / "build-command.log"
    support.run(
        ["node", str(BUILD), "--source", str(source), "--role", internal_role,
         "--entry-discovery", str(discovery_path),
         "--output-dir", str(build_dir)],
        deadline=deadline, phase=f"Task13 {role} ArkTS runtime build", log=build_log,
    )
    build_path = build_dir / "device-build-report.json"
    build = formal.load(build_path)
    if (build.get("status") != "built_not_executed" or
            build.get("runtimeCompile", {}).get("passed") is not True or
            build.get("productionUnchanged") is not True or
            build.get("copiedProductionUnchanged") is not True or
            build.get("standaloneAppCompile", {}).get("passed") is not True or
            build.get("ohosTestCompile", {}).get("passed") is not True):
        raise RuntimeError("Task13 source-specific device runtime did not compile cleanly")
    execution_records = []
    raw = None
    raw_path = None
    execution_log = None
    expected_status = "fail" if internal_role == "base" else "pass"
    for attempt in range(1, 4):
        execution_dir = evidence / f"device-execution-attempt-{attempt}"
        execution_log = evidence / f"device-command-attempt-{attempt}.log"
        support.run(
            ["node", str(EXECUTE), str(build_path), serial, str(execution_dir)],
            deadline=deadline, phase=f"Task13 {role} OpenHarmony device runtime attempt {attempt}",
            log=execution_log,
        )
        raw_path = execution_dir / "device-execution.json"
        raw = formal.load(raw_path)
        if (raw.get("status") != "transport_completed" or raw.get("transportCompleted") is not True or
                raw.get("cleanup", {}).get("ownedAppUninstalled") is not True or
                raw.get("candidateAbsentBeforeInstall") is not True):
            raise RuntimeError("Task13 device transport, fresh install, or cleanup is incomplete")
        statuses = [row.get("status") for row in raw.get("rows", [])]
        execution_records.append({
            "attempt": attempt, "statuses": statuses,
            "report": formal.file_record(raw_path), "log": formal.file_record(execution_log),
        })
        if internal_role == "base":
            # Missing entry rows intentionally have no downstream SAS observation.
            # Review their real native prefix separately, not by expected polarity.
            break
        if len(statuses) == task.case_count and all(status == expected_status for status in statuses):
            break
        if not retry_device_attempt(statuses, expected_status, attempt):
            break
    if raw is None or raw_path is None or execution_log is None:
        raise RuntimeError("Task13 device runtime produced no execution report")
    rows = support.canonical_rows(contract, raw.get("rows", []), role=role)
    if internal_role == "base":
        assessment = entry_audit.inspect_report(raw_path, build_path, inventory=inventory, contract=contract)
        formal.write(evidence / "common-entry-validation.json", assessment)
        native_rows = {row["caseId"]: row for row in raw["rows"]}
        for index, spec in enumerate(contract["cases"][:9]):
            rows[index] = entry_audit.entry_row(spec, native_rows[spec["caseId"]], raw_path,
                                                build_path, inventory_path)
    lineage = formal.calibrator_lineage(task, "arkts")
    return support.strict_report(
        task=task, platform="arkts", source=source, role=role, rows=rows,
        runtime_compile={"passed": True, "status": "passed",
                         "scope": "standalone application HAP and ohosTest HAP"},
        lineage=lineage, runtime_kind="openharmony api23 device arkvm native ui",
        transport="transport_completed",
        evidence={"build": formal.file_record(build_path), "execution": formal.file_record(raw_path),
                  "sourceInventory": formal.file_record(inventory_path),
                  "commonEntry": formal.file_record(discovery_path),
                  "buildLog": formal.file_record(build_log), "executionLog": formal.file_record(execution_log),
                  "executionAttempts": execution_records},
        output=output,
    )


def main() -> int:
    args = support.parse_args(__doc__ or "Task13 ArkTS strict runtime")
    try:
        from .task13_formal_agent import SPEC
    except ImportError:
        from task13_formal_agent import SPEC
    report = evaluate(task=SPEC, platform="arkts", source=args.source, role=args.role,
                      output=args.output, deadline=time.monotonic() + args.deadline_seconds,
                      device_serial=args.device_serial)
    print(json.dumps({"output": str(args.output), "semantic": report["semantic"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
