#!/usr/bin/env python3
"""Source-parameterized Task16 Android revision-5 strict agent scorer."""

from __future__ import annotations

import argparse
import copy
import fcntl
import hashlib
import json
import re
import shutil
import tempfile
import time
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional

try:
    from . import android_robolectric, android_runner, android_robolectric_ui_resources
except ImportError:
    import android_robolectric
    import android_runner
    import android_robolectric_ui_resources


ROOT = Path(__file__).resolve().parents[2]
TASK = "16_identity_reset"
ASSETS = ROOT / "state_tests/runtime/android/16_identity_reset"
CONTRACT = ROOT / "benchmark_tasks/16_identity_reset/transitions.json"


def record(path: Path) -> dict:
    data = path.read_bytes()
    return {"path": str(path.resolve()), "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}


def remaining(deadline: float, phase: str) -> float:
    value = deadline - time.monotonic()
    if value <= 0:
        raise TimeoutError(f"{phase} exceeded the formal scorer deadline")
    return value


def storage_guard() -> None:
    if shutil.disk_usage(ROOT).free < 8 * 1024 ** 3:
        raise RuntimeError("storage_protection_environment: less than 8 GiB free")


def snapshot_report(source: Path, evidence: Path, name: str, report: dict) -> None:
    for item in report.get("provenance", {}).get("productionSources", []):
        destination = evidence / "production-sources" / item["path"]
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / item["path"], destination)
    for item in report.get("provenance", {}).get("evaluatorSources", []):
        destination = evidence / "evaluator-sources" / ("" if name == "entry" else name) / Path(item["path"]).name
        destination.parent.mkdir(parents=True, exist_ok=True)
        if Path(item["path"]).resolve() != destination.resolve():
            shutil.copyfile(item["path"], destination)


def run_slice(source: Path, config: Path, output: Path, deadline: float) -> dict:
    """Use the existing real AAR resource linker for every rendered slice."""
    original_compile = android_robolectric.compile_resources
    original_prepare = android_robolectric.prepare
    def prepare(configuration, work):
        environment = original_prepare(configuration, work)
        environment["jvmArgs"] += [f"-Druntime.contract.path={CONTRACT}",
                                   f"-Druntime.rendered.output={output.with_suffix('')}"]
        return environment
    def compile_resources(candidate, configuration, work, java_home):
        compiler = android_robolectric_ui_resources.compile_resources if configuration.get("resources") else original_compile
        return compiler(candidate, configuration, work, java_home)
    android_robolectric.compile_resources = compile_resources
    android_robolectric.prepare = prepare
    try:
        result = android_robolectric.run_slice(TASK, "agent", source, config.parent, config, output,
                                               remaining(deadline, "Task16 runtime slice"))
        result.setdefault("provenance", {})["packagingSources"] = [record(Path(__file__)),
            record(Path(android_robolectric_ui_resources.__file__)), record(config)]
        saved = output.parent / "configurations" / config.name
        saved.parent.mkdir(exist_ok=True)
        shutil.copyfile(config, saved)
        output.write_text(json.dumps(result, indent=2) + "\n")
        return result
    finally:
        android_robolectric.compile_resources = original_compile
        android_robolectric.prepare = original_prepare


def filesystem_closure(source: Path, seeds: List[str]) -> List[str]:
    """Resolve the existing token-based source closure from standalone candidate bytes."""
    records = {}
    symbols = defaultdict(set)
    packages = defaultdict(dict)
    for file in sorted(source.rglob("*.kt")):
        relative = file.relative_to(source).as_posix()
        if "/src/main/" not in relative or relative.split("/", 1)[0] not in {"features", "libraries", "services"}:
            continue
        code = file.read_text(errors="replace")
        package_match = re.search(r"^package ([\w.]+)", code, re.M)
        if not package_match:
            continue
        package = package_match.group(1)
        imports = re.findall(r"^import ([\w.*]+)", code, re.M)
        clean = re.sub(r"/\*.*?\*/|//[^\n]*", "", code, flags=re.S)
        names = set(re.findall(r"^(?:(?:public|internal|private|open|sealed|data|enum|annotation|value|fun|abstract|inline) )*(?:class|interface|object|typealias) (\w+)", clean, re.M))
        names.update(re.findall(r"^(?:(?:public|internal|private|suspend|inline|tailrec|operator|infix)\s+)*fun (?:<[^\n]+?>\s+)?(?:[^\n(]+\.)?(\w+)\(", clean, re.M))
        names.update(re.findall(r"^(?:internal |private |public )?(?:const )?(?:val|var) (?:[^\n ]+\.)?(\w+)\b", clean, re.M))
        records[relative] = (package, imports, clean)
        for name in names:
            symbols[package + "." + name].add(relative)
            packages[package].setdefault(name, set()).add(relative)
    selected = set()
    pending = list(seeds)
    while pending:
        path = pending.pop()
        if path in selected:
            continue
        if path not in records:
            raise ValueError(f"Production entrypoint absent in standalone candidate: {path}")
        selected.add(path)
        package, imports, clean = records[path]
        tokens = set(re.findall(r"\b\w+\b", clean))
        for name, paths in packages[package].items():
            if name in tokens:
                pending.extend(paths - selected)
        for imported in imports:
            if not imported.startswith("io.element.android.") or imported.startswith("io.element.android.wysiwyg."):
                continue
            lookup = imported
            while lookup and lookup not in symbols:
                lookup = lookup.rpartition(".")[0]
            if lookup:
                pending.extend(symbols[lookup] - selected)
    return sorted(selected)


def prepared_config(source: Path, config_path: Path, temporary: Path) -> Path:
    config = json.loads(config_path.read_text())
    if config.get("sourceClosure"):
        config["sources"] = filesystem_closure(source, config["entrypoints"])
        config["sourceClosure"] = False
    config["evaluatorSources"] = [str((config_path.parent / path).resolve()) for path in config["evaluatorSources"]]
    if config_path.parent.name == "common_prefix":
        config["sources"] += [
            "features/ftue/impl/src/main/kotlin/io/element/android/features/ftue/impl/sessionverification/FtueSessionVerificationFlowNode.kt",
            "features/securebackup/api/src/main/kotlin/io/element/android/features/securebackup/api/SecureBackupEntryPoint.kt",
            "features/verifysession/api/src/main/kotlin/io/element/android/features/verifysession/api/VerifySessionEntryPoint.kt",
        ]
        for module in config["resources"]:
            for directory in module.pop("directories", []):
                module["files"] += [path.relative_to(source).as_posix() for path in sorted((source / directory).glob("*")) if path.is_file()]
        view = source / config["entrypoints"][0]
        binding = temporary / "VerifyEntryBinding.kt"
        binding.write_bytes(binding_bytes(view.read_text()))
        config["evaluatorSources"] = [str(binding) if Path(path).name == binding.name else path for path in config["evaluatorSources"]]
    target = temporary / (config_path.parent.name + "-" + config_path.name)
    target.write_text(json.dumps(config, indent=2) + "\n")
    return target


def rows(report: dict) -> List[dict]:
    return report.get("observations") or report.get("semantic", {}).get("cases", [])


def row_for(report: dict, key: str) -> Optional[dict]:
    return next((row for row in rows(report) if row.get("key") == key), None)


def compare(expected, observed, prefix="") -> List[dict]:
    mismatches = []
    for key, value in expected.items():
        field = f"{prefix}.{key}" if prefix else key
        if key not in observed:
            mismatches.append({"field": field, "expected": value, "observed": "<missing>"})
        elif isinstance(value, dict) and isinstance(observed[key], dict):
            mismatches.extend(compare(value, observed[key], field))
        elif type(value) is not type(observed[key]) or value != observed[key]:
            mismatches.append({"field": field, "expected": value, "observed": observed[key]})
    return mismatches


def slice_healthy(report: dict) -> bool:
    return report.get("runtimeCompile", {}).get("status") == "passed" and not report.get("error")


try:
    from .task16_android_prefix_evidence import base_rows, valid_prefix, validate_prefix_failure, binding_bytes
except ImportError:
    from task16_android_prefix_evidence import base_rows, valid_prefix, validate_prefix_failure, binding_bytes


def revision5_failure_row(raw: dict, spec: dict) -> dict:
    checkpoints = {item["name"]: item["state"] for item in raw.get("checkpoints", [])}
    stable = raw.get("observed", {})
    retry = checkpoints.get("retry_probe", {})
    evidence = next((item.get("evidence", {}) for item in raw.get("invariantChecks", [])
                     if item.get("invariant") == "a missing handle is treated as failure rather than success"), {})
    sequence = evidence.get("stateSequence", [])
    return {"failureObserved": "failure" in sequence, "stateSequence": sequence,
            "stableHandleState": stable.get("handleState"), "screen": stable.get("screen"),
            "progressVisible": stable.get("progressVisible"), "retryEnabled": stable.get("retryEnabled"),
            "retryHandleState": retry.get("handleState")}


def assemble_final(contract: dict, reports: Dict[str, dict]) -> List[dict]:
    flow_keys = {"confirm_starts_handle", "password_handle_routes", "oidc_handle_routes_and_resets",
                 "handle_failure_recovers", "cancel_cleans_up"}
    password_keys = {"password_submit_calls_handle", "password_failure_clears_on_edit"}
    result = []
    for spec in contract["cases"]:
        key = spec["key"]
        dependencies = ["entry"]
        if key in {"continue_requests_confirmation", "dismiss_confirmation"}:
            dependencies += ["root", "primary"]
            ui, domain = row_for(reports["root"], key), row_for(reports["primary"], key)
            observed = copy.deepcopy((ui or {}).get("observed", {}))
            checks = copy.deepcopy((ui or {}).get("invariantChecks", []))
            statuses = [(item or {}).get("status") for item in (ui, domain)]
            raw_status = ("fail" if "fail" in statuses else "pass") if all(status in {"pass", "fail"} for status in statuses) else None
        elif key in flow_keys:
            dependencies += ["flow"]
            raw = row_for(reports["flow"], key)
            observed = copy.deepcopy((raw or {}).get("observed", {}))
            checks = copy.deepcopy((raw or {}).get("invariantChecks", []))
            raw_status = (raw or {}).get("status")
            if key == "handle_failure_recovers" and raw:
                observed = revision5_failure_row(raw, spec)
                checks = [
                    {"invariant": spec["invariants"][0], "status": "pass" if observed["failureObserved"] else "fail",
                     "evidence": {"stateSequence": observed["stateSequence"]}},
                    {"invariant": spec["invariants"][1], "status": "pass" if observed["stableHandleState"] == "uninitialized" and observed["retryEnabled"] else "fail",
                     "evidence": observed},
                    {"invariant": spec["invariants"][2], "status": "pass" if observed["retryHandleState"] == "loading" else "fail",
                     "evidence": observed},
                ]
                raw_status = "pass"
        elif key in password_keys:
            dependencies += ["password"]
            raw = row_for(reports["password"], key)
            observed = copy.deepcopy((raw or {}).get("observed", {}))
            checks = copy.deepcopy((raw or {}).get("invariantChecks", []))
            raw_status = (raw or {}).get("status")
        else:
            dependencies += ["password", "verification"]
            ui, watcher = row_for(reports["password"], key), row_for(reports["verification"], key)
            observed = {**copy.deepcopy((ui or {}).get("observed", {})),
                        **copy.deepcopy((watcher or {}).get("observed", {}))}
            checks = copy.deepcopy((watcher or {}).get("invariantChecks", []))
            statuses = [(item or {}).get("status") for item in (ui, watcher)]
            raw_status = ("fail" if "fail" in statuses else "pass") if all(status in {"pass", "fail"} for status in statuses) else None
        healthy = all(slice_healthy(reports[name]) for name in dependencies)
        healthy = healthy and all(
            len((row_for(reports[name], key) or {}).get("checkpoints", [])) >= 2
            and bool(reports[name].get("provenance", {}).get("productionSources")) for name in dependencies)
        entry = row_for(reports["entry"], key)
        healthy = healthy and valid_prefix(entry, reports["entry"]) and entry["observed"].get("entryAvailable") is True
        invariant_map = {item.get("invariant"): item for item in checks}
        missing = [text for text in spec.get("invariants", []) if text not in invariant_map]
        failing = [text for text in spec.get("invariants", []) if invariant_map.get(text, {}).get("status") != "pass"]
        mismatches = compare(spec["expected"], observed)
        status = "not_scored" if not healthy or raw_status not in {"pass", "fail"} or missing else (
            "fail" if raw_status == "fail" or mismatches or failing else "pass")
        result.append({"caseId": spec["caseId"], "key": key, "traceDigest": spec["traceDigest"],
                       "status": status, "observed": observed, "expectedMismatches": mismatches,
                       "checkpoints": [dict(copy.deepcopy(point), runtimeSlice=name)
                                       for name in dependencies for point in (row_for(reports[name], key) or {}).get("checkpoints", [])],
                       "productionSources": [dict(copy.deepcopy(item), runtimeSlice=name)
                                             for name in dependencies for item in reports[name].get("provenance", {}).get("productionSources", [])],
                       "invariantChecks": checks, "runtimeSlices": dependencies,
                       "reason": None if status in {"pass", "fail"} else "Required strict runtime slice did not compile or execute."})
    return result


def score(source: Path, output: Path, deadline: float) -> dict:
    source, output = source.resolve(), output.resolve()
    if output.exists():
        raise FileExistsError(f"Refusing existing Task16 scorer output: {output}")
    evidence = output.with_name(output.stem + "_evidence")
    if evidence.exists():
        raise FileExistsError(f"Refusing existing Task16 evidence: {evidence}")
    evidence.mkdir(parents=True)
    contract = json.loads(CONTRACT.read_text())
    reports = {}
    configurations = {
        "entry": ASSETS / "common_prefix/adapter.json", "flow": ASSETS / "flow/adapter.json",
        "root": ASSETS / "root_rendered/adapter.json", "password": ASSETS / "rendered/adapter.json",
        "verification": ASSETS / "verification/adapter.json",
    }
    lock_path = ROOT / "state_tests/runtime/android/.build.lock"
    try:
        with tempfile.TemporaryDirectory(prefix="task16-agent-config-") as raw, lock_path.open("a") as lock:
            temporary = Path(raw)
            while True:
                remaining(deadline, "Task16 shared runtime lock")
                try:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    time.sleep(0.2)
            storage_guard()
            entry_config = prepared_config(source, configurations["entry"], temporary)
            generated = evidence / "evaluator-sources"
            generated.mkdir()
            binding = temporary / "VerifyEntryBinding.kt"
            saved_binding = generated / binding.name
            shutil.copyfile(binding, saved_binding)
            entry_data = json.loads(entry_config.read_text())
            entry_data["evaluatorSources"] = [str(saved_binding) if path == str(binding) else path for path in entry_data["evaluatorSources"]]
            entry_config.write_text(json.dumps(entry_data, indent=2) + "\n")
            reports["entry"] = run_slice(source, entry_config, evidence / "entry.json", deadline)
            snapshot_report(source, evidence, "entry", reports["entry"])
            entry_present = len(rows(reports["entry"])) == len(contract["cases"]) and any(
                valid_prefix(row, reports["entry"]) and row.get("observed", {}).get("entryAvailable") is True for row in rows(reports["entry"]))
            entry_absent = len(rows(reports["entry"])) == len(contract["cases"]) and all(
                valid_prefix(row, reports["entry"]) and row.get("observed", {}).get("entryAvailable") is False for row in rows(reports["entry"]))
            if slice_healthy(reports["entry"]) and entry_present:
                storage_guard()
                reports["primary"] = android_runner.run(
                    TASK, "agent", source, evidence / "primary.json", remaining(deadline, "Task16 primary slice"),
                    adapter_config=ASSETS / "adapter.json")
                snapshot_report(source, evidence, "primary", reports["primary"])
                for name in ("flow", "root", "password", "verification"):
                    storage_guard()
                    config = prepared_config(source, configurations[name], temporary)
                    reports[name] = run_slice(source, config, evidence / f"{name}.json", deadline)
                    snapshot_report(source, evidence, name, reports[name])
                semantic = assemble_final(contract, reports)
                early = {row["key"]: row for row in base_rows(contract, reports["entry"], evidence / "entry.json") if row["status"] == "fail"}
                semantic = [early.get(row["key"], row) for row in semantic]
            elif slice_healthy(reports["entry"]) and entry_absent:
                semantic = base_rows(contract, reports["entry"], evidence / "entry.json")
            else:
                semantic = [{"caseId": case["caseId"], "key": case["key"], "traceDigest": case["traceDigest"],
                             "status": "not_scored", "reason": "Task16 runtime entry probe failed."}
                            for case in contract["cases"]]
    except (OSError, RuntimeError, TimeoutError, ValueError) as error:
        semantic = [{"caseId": case["caseId"], "key": case["key"], "traceDigest": case["traceDigest"],
                     "status": "not_scored", "reason": f"{type(error).__name__}: {error}"}
                    for case in contract["cases"]]
    runtime_passed = bool(reports) and all(slice_healthy(report) for report in reports.values())
    publishable = runtime_passed and all(row["status"] in {"pass", "fail"} for row in semantic)
    report = {"schemaVersion": 2, "taskId": TASK, "platform": "android", "role": "agent",
              "observationMode": "runtime_state_transition",
              "runtimeCompile": {"passed": runtime_passed, "status": "passed" if runtime_passed else "failed",
                                 "scope": "entry plus required isolated production runtime slices"},
              "semantic": {"cases": semantic},
              "provenance": {"candidateMode": "standalone_directory", "candidateSource": str(source),
                             "canonicalContract": record(CONTRACT),
                             "runtimeReports": {name: record(evidence / f"{name}.json") for name in reports}},
              "diagnostics": {"adapter": "ready" if publishable else "incomplete", "transport": "host_runtime_completed" if runtime_passed else "failed",
                              "publishableWithoutApplicationCompile": publishable,
                              "applicationCompileOwnedByParentRunner": True,
                              "environmentFailureIsNotSemanticFailure": True,
                              "cleanup": {"compilerTemporaryDirectoriesRemoved": True,
                                          "binariesRetained": False,
                                          "candidateBuildIntermediatesCreated": False}}}
    try:
        from scripts.run_runtime_transition_matrix import validate_report
    except ImportError:
        import sys
        sys.path.insert(0, str(ROOT))
        from scripts.run_runtime_transition_matrix import validate_report
    try:
        validate_report(report, contract)
        report["diagnostics"]["publicReportValidation"] = "passed"
    except (ValueError, KeyError, OSError) as error:
        report["diagnostics"].update(publicReportValidation="failed", validationError=str(error),
                                     publishableWithoutApplicationCompile=False, adapter="incomplete")
        for row in report["semantic"]["cases"]:
            row.update(status="not_scored", reason=f"Public runtime report validation failed: {error}")
    report["semantic"].update({label: sum(row["status"] == status for row in report["semantic"]["cases"])
                               for label, status in (("passed", "pass"), ("failed", "fail"), ("notScored", "not_scored"))})
    report["semantic"]["total"] = len(report["semantic"]["cases"])
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=int, default=3600)
    args = parser.parse_args()
    if args.timeout_seconds != 3600:
        parser.error("formal score timeout must be exactly 3600 seconds")
    report = score(args.source, args.output, time.monotonic() + args.timeout_seconds)
    print(json.dumps({"output": str(args.output), "publishableWithoutApplicationCompile":
                      report["diagnostics"]["publishableWithoutApplicationCompile"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
