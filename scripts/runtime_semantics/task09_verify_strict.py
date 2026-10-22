#!/usr/bin/env python3
"""Independently verify Task09 four-pole runtime evidence and ArkTS app builds."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import shutil
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
TASK = "09_spaces_lifecycle"
DEFAULT_CONTRACT = ROOT / "benchmark_tasks" / TASK / "transitions.json"


class VerificationError(AssertionError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise VerificationError(message)


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"Expected JSON object: {path}")
    return value


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def contained(path_value: str | Path) -> Path:
    path = Path(path_value)
    if not path.is_absolute():
        path = ROOT / path
    path = path.resolve()
    require(path == ROOT or ROOT in path.parents, f"Evidence path escapes repository: {path}")
    return path


def verify_record(record: dict[str, Any], label: str) -> Path:
    require(isinstance(record, dict), f"{label}: artifact record missing")
    require(all(key in record for key in ("path", "bytes", "sha256")), f"{label}: malformed artifact record")
    path = contained(record["path"])
    require(path.is_file(), f"{label}: artifact missing: {path}")
    data = path.read_bytes()
    require(len(data) == record["bytes"], f"{label}: byte count differs")
    require(digest(data) == record["sha256"], f"{label}: SHA-256 differs")
    return path


def expected_subset(expected: Any, observed: Any, label: str) -> None:
    if isinstance(expected, dict):
        require(isinstance(observed, dict), f"{label}: expected object")
        for key, value in expected.items():
            require(key in observed, f"{label}: missing {key}")
            expected_subset(value, observed[key], f"{label}.{key}")
    elif isinstance(expected, list):
        require(observed == expected, f"{label}: list differs")
    else:
        require(observed == expected, f"{label}: value differs")


def invariant_identity(check: dict[str, Any]) -> str | None:
    return check.get("invariant", check.get("description", check.get("text")))


def invariant_passed(check: dict[str, Any]) -> bool:
    return check.get("passed") is True or check.get("status") == "pass"


def read_source(source: Path, record: dict[str, Any], commit: str | None) -> bytes:
    relative = record.get("path")
    require(isinstance(relative, str) and not Path(relative).is_absolute(), "production source path must be relative")
    if commit:
        try:
            return subprocess.check_output(
                ["git", "-C", str(source), "show", f"{commit}:{relative}"], stderr=subprocess.DEVNULL
            )
        except subprocess.SubprocessError as error:
            raise VerificationError(f"Cannot read immutable source {commit}:{relative}") from error
    path = (source / relative).resolve()
    require(source == path or source in path.parents, f"production source escapes candidate: {relative}")
    require(path.is_file(), f"production source missing: {relative}")
    return path.read_bytes()


def verify_source_records(records: list[dict[str, Any]], source: Path, commit: str | None, label: str) -> None:
    require(isinstance(records, list) and records, f"{label}: production source inventory missing")
    seen: set[str] = set()
    for record in records:
        relative = record.get("path")
        require(relative not in seen, f"{label}: duplicate production source: {relative}")
        seen.add(relative)
        data = read_source(source, record, commit)
        require(record.get("sha256") == digest(data), f"{label}: source SHA-256 differs: {relative}")
        if "bytes" in record:
            require(record["bytes"] == len(data), f"{label}: source byte count differs: {relative}")


def retain_production_input(source: Path, destination: Path, expected: list[dict]) -> dict:
    """Retain exact replay inputs, not a claim about historical unread model inputs."""
    source = source.resolve()
    inventory = {item['path']: item['sha256'] for item in expected}
    actual = {path.relative_to(source).as_posix(): digest(path.read_bytes())
              for path in (source / 'entry/src/main').rglob('*') if path.is_file()}
    require(actual == inventory, 'Replay source differs from original archived production inventory')
    require(not destination.exists(), 'Refusing to overwrite replay input snapshot')
    destination.mkdir(parents=True)
    records = []
    for relative in sorted(actual):
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / relative, target)
        data = target.read_bytes()
        records.append({'path': str(target.resolve()), 'originalPath': relative,
                        'bytes': len(data), 'sha256': digest(data)})
    manifest = {'schemaVersion': 1, 'taskId': TASK, 'platform': 'arkts',
                'originalSource': str(source), 'capturePhase': 'exact_candidate_semantic_replay',
                'historicalModelBaselineAttestation': False, 'files': records}
    (destination / 'input.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return manifest


def verify_arkts_candidate(report_path: Path, input_path: Path, contract: dict) -> dict:
    """Verify arbitrary P/F outcomes against raw device bytes and frozen input files."""
    try:
        from ..run_runtime_transition_matrix import validate_report
    except ImportError:
        import sys
        sys.path.insert(0, str(ROOT / 'scripts'))
        from run_runtime_transition_matrix import validate_report
    report, inputs = load(report_path), load(input_path)
    require((report.get('taskId'), report.get('platform'), report.get('role')) ==
            (TASK, 'arkts', 'agent'), 'Wrong standalone candidate identity')
    require(Path(report.get('source', report.get('target', ''))).resolve() ==
            Path(inputs['originalSource']).resolve(), 'Frozen input belongs to another candidate')
    require(inputs.get('taskId') == TASK and inputs.get('platform') == 'arkts', 'Wrong input snapshot identity')
    require(report.get('publication', {}).get('eligible') is True and
            report.get('runtimeCompile', {}).get('passed') is True and
            report['runtimeCompile'].get('status') == 'passed', 'Incomplete runtime/cleanup cannot be scored')
    validate_report(report, contract)
    require(all(row['status'] in {'pass', 'fail'} for row in report['semantic']['cases']),
            'Candidate has unscored canonical cases')
    inventory = {}
    for item in inputs['files']:
        verify_record(item, 'frozen production input')
        require(item['originalPath'] not in inventory, 'Duplicate frozen production input')
        inventory[item['originalPath']] = item['sha256']
    identities = set()
    for row in report['semantic']['cases']:
        require(not row.get('entryFailureEvidence'), 'This candidate verifier requires executed lifecycle transitions')
        build_path = verify_record(row['build'], 'candidate build')
        execution_path = verify_record(row['execution'], 'candidate device execution')
        raw_path = verify_record(row['nativeResult'], 'candidate native result')
        build, execution, raw = (load(path) for path in (build_path, execution_path, raw_path))
        require(all(row.get(key) == value for key, value in raw.items()),
                'Normalized candidate row differs from actual native output')
        require(execution.get('rows') == [raw] and execution.get('status') == 'transport_completed' and
                execution.get('transportCompleted') is True and execution.get('candidateAbsentBeforeInstall') is True and
                execution.get('cleanup', {}).get('ownedAppUninstalled') is True,
                'Fresh candidate execution incomplete')
        require(execution['buildReport']['sha256'] == row['build']['sha256'] and
                execution['rowArtifact']['sha256'] == row['nativeResult']['sha256'] and
                execution['rowArtifact']['bytes'] == row['nativeResult']['bytes'], 'Device build/result binding changed')
        identity = (execution.get('executionNonce'), execution.get('pid'))
        require(bool(identity[0]) and bool(identity[1]) and identity not in identities,
                'Reused or missing candidate device execution')
        identities.add(identity)
        require(build.get('source') == inputs['originalSource'] and
                build.get('runtimeCompile', {}).get('passed') is True and
                all(build.get(key) is True for key in
                    ('productionUnchanged', 'copiedProductionUnchanged', 'temporaryProjectRemoved')),
                'Original production packaging binding missing')
        require({item['path']: item['sha256'] for item in build['production']} == inventory,
                'Packaged candidate differs from frozen source bytes')
        for fixture in [*build['nativeUIObserver']['fixtures'], build['nativeUIObserver']['installer']]:
            path = Path(fixture.get('source', fixture.get('file', ''))).resolve()
            require(path.is_relative_to(ROOT / 'state_tests/runtime/arkts') and
                    digest(path.read_bytes()) == fixture['sha256'], 'Executed evaluator differs from reviewed module')
        for command in execution['commands']:
            path = (execution_path.parent / command['log']).resolve()
            require(path.is_relative_to(execution_path.parent) and digest(path.read_bytes()) == command['sha256'],
                    'Retained device command log changed')
    return {'verified': True, 'taskId': TASK, 'platform': 'arkts', 'caseCount': len(identities),
            'sourceFiles': len(inventory), 'passed': sum(row['status'] == 'pass' for row in report['semantic']['cases']),
            'failed': sum(row['status'] == 'fail' for row in report['semantic']['cases'])}


def verify_contract_record(report: dict[str, Any], contract_path: Path, label: str) -> None:
    record = report.get("contract")
    require(isinstance(record, dict), f"{label}: contract record missing")
    require(record.get("sha256") == digest(contract_path.read_bytes()), f"{label}: contract SHA-256 differs")


def verify_runtime(report: dict[str, Any], *, platform: str, role: str, source: Path,
                   contract: dict[str, Any], contract_path: Path,
                   require_navigation: bool = True) -> dict[str, int]:
    source = source.resolve()
    label = f"{platform}/{role}"
    require((report.get("taskId"), report.get("platform"), report.get("role")) == (TASK, platform, role),
            f"{label}: identity mismatch")
    require(report.get("observationMode") == "runtime_state_transition", f"{label}: not runtime-state evidence")
    require(report.get("runtimeCompile", {}).get("passed") is True and
            report.get("runtimeCompile", {}).get("status") == "passed", f"{label}: runtime packaging failed")
    require(report.get("publication", {}).get("eligible") is True, f"{label}: report is not publishable")
    target = report.get("target", report.get("source"))
    require(target is not None and Path(target).resolve() == source, f"{label}: candidate source binding differs")
    verify_contract_record(report, contract_path, label)

    specs = contract["cases"]
    semantic = report.get("semantic", {})
    expected_counts = {"total": 9, "passed": 0 if role == "base" else 9,
                       "failed": 9 if role == "base" else 0, "notScored": 0}
    require({key: semantic.get(key) for key in expected_counts} == expected_counts, f"{label}: wrong polarity")
    rows = semantic.get("cases", [])
    require([row.get("caseId") for row in rows] == [spec["caseId"] for spec in specs],
            f"{label}: canonical case order differs")

    provenance = report.get("provenance", {})
    commit = provenance.get("commit") if platform == "android" and role in {"base", "final"} else None
    report_sources = provenance.get("productionSources", [])
    if platform == "android":
        verify_source_records(report_sources, source, commit, label)

    entry_observations = set()
    for row, spec in zip(rows, specs):
        scope = f"{label}/{spec['caseId']}"
        if platform == 'arkts':
            try:
                from .task09_arkts_entry_evidence import legacy_projection, validate_entry_failure
            except ImportError:
                from task09_arkts_entry_evidence import legacy_projection, validate_entry_failure
            require(not legacy_projection(row) or bool(row.get('entryFailureEvidence')),
                    f'{scope}: withdrawn synthetic base lifecycle post-state')
        require(row.get("caseId") == spec["caseId"], f"{scope}: canonical case ID differs")
        if row.get("key") is not None:
            require(row["key"] == spec["key"], f"{scope}: canonical key differs")
        require(row.get("traceDigest") == spec["traceDigest"], f"{scope}: trace digest differs")
        require(row.get("status") == ("fail" if role == "base" else "pass"), f"{scope}: verdict differs")
        require(isinstance(row.get("checkpoints"), list) and len(row["checkpoints"]) >= 2,
                f"{scope}: before/event/after runtime checkpoints missing")
        if platform == 'arkts' and row.get('entryFailureEvidence'):
            try:
                validate_entry_failure(row, report, entry_observations, contract=contract)
            except ValueError as error:
                raise VerificationError(str(error)) from error
            continue
        checks = row.get("invariantChecks", [])
        require([invariant_identity(item) for item in checks] == spec.get("invariants", []),
                f"{scope}: invariant identity differs")
        if role == "final":
            expected_subset(spec["expected"], row.get("observed"), f"{scope}.observed")
            require(all(invariant_passed(item) for item in checks), f"{scope}: final invariant failed")
        else:
            mismatch = bool(row.get("assertionFailures")) or bool(row.get("reason")) or \
                any(not invariant_passed(item) for item in checks)
            require(mismatch, f"{scope}: base failure has no semantic mismatch evidence")

        if platform == "arkts":
            require(row.get("freshInstall") is True, f"{scope}: fresh install not proved")
            cleanup = row.get("hapCleanup", {})
            if not cleanup:
                build_path = Path(row.get("build", {}).get("path", ""))
                cleanup_path = build_path.parent / "hap-cleanup.json"
                require(cleanup_path.is_file(), f"{scope}: copied HAP cleanup manifest missing")
                cleanup = load(cleanup_path)
            require(cleanup.get("copiedHapsDeleted") is True and
                    cleanup.get("metadataRetainedInBuildReport") is True and
                    cleanup.get("files"), f"{scope}: copied HAP cleanup evidence missing")
            require(all(item.get("deleted") is True and item.get("bytes", 0) > 0 and
                        len(item.get("sha256", "")) == 64 for item in cleanup["files"]),
                    f"{scope}: copied HAP cleanup metadata malformed")
            verify_source_records(row.get("productionSources", []), source, None, scope)
            verify_record(row.get("build", {}), f"{scope}/build")
            execution_path = verify_record(row.get("execution", {}), f"{scope}/execution")
            verify_record(row.get("nativeResult", {}), f"{scope}/native-result")
            execution = load(execution_path)
            require(execution.get("transportCompleted") is True and
                    execution.get("candidateAbsentBeforeInstall") is True and
                    execution.get("cleanup", {}).get("ownedAppUninstalled") is True,
                    f"{scope}: transport/fresh-state cleanup incomplete")

    if platform == "android" and role == "final" and require_navigation:
        navigation = report.get("navigation", {}).get("report")
        require(isinstance(navigation, dict), f"{label}: independent case009 navigation report missing")
        navigation_report = load(verify_record(navigation, f"{label}/navigation"))
        nav_provenance = navigation_report.get("provenance", {})
        verify_source_records(nav_provenance.get("productionSources", []), source,
                              nav_provenance.get("commit"), f"{label}/navigation")
    if platform == "arkts":
        require(report.get("deviceLocksPresentAfter") == [], f"{label}: shared device lock leaked")
    return expected_counts


def verify_arkts_app_build(report: dict[str, Any], *, role: str, source: Path,
                           contract_path: Path) -> None:
    label = f"arkts/{role}/application-build"
    require((report.get("taskId"), report.get("platform"), report.get("role")) == (TASK, "arkts", role),
            f"{label}: identity mismatch")
    require(Path(report.get("source", "")).resolve() == source, f"{label}: source binding differs")
    require(report.get("compile", {}).get("passed") is True and
            report.get("compile", {}).get("scope") == "standalone_candidate_application_hap",
            f"{label}: standalone HAP build failed")
    require(report.get("runtimeCompile", {}).get("status") == "not_run",
            f"{label}: standalone compile was mixed with runtime packaging")
    require(report.get("productionStableDuringBuild") is True and
            report.get("productionBefore") == report.get("productionAfter"),
            f"{label}: source changed during build")
    require(report.get("temporaryProjectRemoved") is True, f"{label}: temporary project leaked")
    for item in report.get("productionBefore", []):
        data = read_source(source, item, None)
        require(item.get("sha256") == digest(data), f"{label}: current source differs: {item.get('path')}")
    require(report.get("haps"), f"{label}: HAP artifact missing")
    for index, item in enumerate(report["haps"]):
        verify_record(item, f"{label}/hap-{index}")
    for index, command in enumerate(report.get("commands", [])):
        require(command.get("exitCode") == 0, f"{label}: build command failed")
        verify_record(command.get("log", {}), f"{label}/command-{index}")
    verify_contract_record(report, contract_path, label)


def verify_all(*, contract_path: Path, android_base_path: Path, android_final_path: Path,
               arkts_base_path: Path, arkts_final_path: Path, android_source: Path,
               arkts_base_source: Path, arkts_final_source: Path,
               arkts_base_build_path: Path, arkts_final_build_path: Path) -> dict[str, Any]:
    contract_path = contract_path.resolve()
    contract = load(contract_path)
    require(contract.get("taskId") == TASK and len(contract.get("cases", [])) == 9,
            "Task09 canonical contract must contain nine cases")
    require(len({case.get("caseId") for case in contract["cases"]}) == 9, "Task09 case IDs must be unique")
    results = {
        "androidBase": verify_runtime(load(android_base_path), platform="android", role="base",
                                      source=android_source.resolve(), contract=contract, contract_path=contract_path),
        "androidFinal": verify_runtime(load(android_final_path), platform="android", role="final",
                                       source=android_source.resolve(), contract=contract, contract_path=contract_path),
        "arktsBase": verify_runtime(load(arkts_base_path), platform="arkts", role="base",
                                    source=arkts_base_source.resolve(), contract=contract, contract_path=contract_path),
        "arktsFinal": verify_runtime(load(arkts_final_path), platform="arkts", role="final",
                                     source=arkts_final_source.resolve(), contract=contract, contract_path=contract_path),
    }
    verify_arkts_app_build(load(arkts_base_build_path), role="base", source=arkts_base_source.resolve(),
                           contract_path=contract_path)
    verify_arkts_app_build(load(arkts_final_build_path), role="final", source=arkts_final_source.resolve(),
                           contract_path=contract_path)
    return {"schemaVersion": 1, "taskId": TASK, "validated": True,
            "observationMode": "runtime_state_transition", "contractSha256": digest(contract_path.read_bytes()),
            "results": results,
            "applicationBuilds": {"arktsBase": "passed", "arktsFinal": "passed"}}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--android-base", type=Path, required=True)
    parser.add_argument("--android-final", type=Path, required=True)
    parser.add_argument("--arkts-base", type=Path, required=True)
    parser.add_argument("--arkts-final", type=Path, required=True)
    parser.add_argument("--android-source", type=Path, required=True)
    parser.add_argument("--arkts-base-source", type=Path, required=True)
    parser.add_argument("--arkts-final-source", type=Path, required=True)
    parser.add_argument("--arkts-base-build", type=Path, required=True)
    parser.add_argument("--arkts-final-build", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = verify_all(contract_path=args.contract, android_base_path=args.android_base,
                            android_final_path=args.android_final, arkts_base_path=args.arkts_base,
                            arkts_final_path=args.arkts_final, android_source=args.android_source,
                            arkts_base_source=args.arkts_base_source, arkts_final_source=args.arkts_final_source,
                            arkts_base_build_path=args.arkts_base_build,
                            arkts_final_build_path=args.arkts_final_build)
    except VerificationError as error:
        result = {"schemaVersion": 1, "taskId": TASK, "validated": False, "error": str(error)}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result))
    return 0 if result["validated"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
