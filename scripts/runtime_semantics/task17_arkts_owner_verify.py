#!/usr/bin/env python3
"""Verify the Task17 owner-bound ArkTS runtime matrix and retained evidence."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "benchmark_tasks/17_pinned_messages/transitions.json"
RUNTIME = "openharmony_api23_device_uitest_candidate_page_owner_matrix_room_port"
OBSERVATION = "openharmony_api23_native_candidate_page_owner_and_matrix_room_port"


class VerificationError(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise VerificationError(message)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_record(record: dict, label: str) -> Path:
    require(isinstance(record, dict), f"{label}: record missing")
    raw = record.get("path")
    require(isinstance(raw, str) and raw, f"{label}: path missing")
    path = Path(raw)
    path = path if path.is_absolute() else ROOT / path
    require(path.is_file(), f"{label}: file missing: {path}")
    require(record.get("bytes") == path.stat().st_size, f"{label}: byte count changed")
    require(record.get("sha256") == sha256(path), f"{label}: digest changed")
    return path


def load_record(record: dict, label: str) -> tuple[Path, dict]:
    path = resolve_record(record, label)
    try:
        return path, json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise VerificationError(f"{label}: invalid JSON: {error}") from error


def verify_matrix(matrix_path: Path) -> dict:
    matrix_path = matrix_path.resolve()
    document = json.loads(matrix_path.read_text(encoding="utf-8"))
    require(document.get("schemaVersion") == 1, "wrong matrix schema")
    require(document.get("taskId") == "17_pinned_messages", "wrong task")
    require(document.get("runtime") == RUNTIME, "wrong runtime")
    require(document.get("complete") is True, "matrix incomplete")
    require(document.get("calibrationValid") is True, "calibration invalid")
    require(document.get("roleBudgetSeconds") == 3600, "role budget is not 3600 seconds")

    contract_path = resolve_record(document.get("contract"), "contract")
    require(contract_path.resolve() == CONTRACT.resolve(), "matrix does not bind the active contract")
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    require(len(contract.get("cases", [])) == 9, "Task17 contract must contain nine cases")
    resolve_record(document.get("evaluator", {}).get("build"), "evaluator build")
    resolve_record(document.get("evaluator", {}).get("execute"), "evaluator execute")

    rows = document.get("rows")
    expected = [(role, spec["caseId"], spec["traceDigest"])
                for role in ("base", "final", "agent") for spec in contract["cases"]]
    require(isinstance(rows, list) and len(rows) == len(expected), "matrix must contain 27 rows")
    actual = [(row.get("role"), row.get("caseId"), row.get("traceDigest")) for row in rows]
    require(actual == expected, "matrix role/case/trace order changed")

    counts: dict[str, dict[str, int]] = {}
    for index, row in enumerate(rows):
        role, case_id, trace_digest = expected[index]
        label = f"{role}/{case_id}"
        require(row.get("status") in {"pass", "fail"}, f"{label}: unscored row")
        require(row.get("compile") is True, f"{label}: application compile failed")
        require(row.get("runtimeCompile") is True, f"{label}: runtime compile failed")

        _, build = load_record(row.get("build"), f"{label} build")
        require(build.get("role") == role and build.get("caseId") == case_id,
                f"{label}: build identity mismatch")
        require(build.get("compile", {}).get("passed") is True and
                build.get("runtimeCompile", {}).get("passed") is True,
                f"{label}: build did not pass")
        require(build.get("productionUnchanged") is True and
                build.get("copiedProductionUnchanged") is True and
                build.get("temporaryProjectRemoved") is True,
                f"{label}: production/build isolation incomplete")
        owner = build.get("task17Owner", {})
        observer = build.get("nativeUIObserver", {})
        require(owner.get("role") == role and owner.get("caseId") == case_id,
                f"{label}: owner build provenance missing")
        require(observer.get("productionUnchanged") is True and
                observer.get("binding", {}).get("evaluatorRole") == role and
                observer.get("binding", {}).get("behaviorClassification") ==
                "runtime_candidate_page_owner_and_room_port",
                f"{label}: owner binding provenance missing")

        _, execution = load_record(row.get("execution"), f"{label} execution")
        require(execution.get("status") == "transport_completed" and
                execution.get("transportCompleted") is True and
                execution.get("candidateAbsentBeforeInstall") is True and
                execution.get("productionUnchanged") is True and
                execution.get("cleanup", {}).get("ownedAppUninstalled") is True,
                f"{label}: fresh device transport/cleanup incomplete")
        matching = [item for item in execution.get("rows", [])
                    if item.get("caseId") == case_id and item.get("traceDigest") == trace_digest]
        require(len(matching) == 1 and matching[0].get("status") == row["status"],
                f"{label}: execution row mismatch")

        _, native = load_record(row.get("nativeResult"), f"{label} native result")
        require(native.get("taskId") == "17_pinned_messages" and
                native.get("role") == role and native.get("caseId") == case_id and
                native.get("traceDigest") == trace_digest and
                native.get("status") == row["status"], f"{label}: native identity mismatch")
        require(native.get("observationLevel") == OBSERVATION, f"{label}: wrong observation level")
        require(native.get("unsupportedObservations") == [] and
                native.get("missingObservations") == [] and
                native.get("missingInvariants") == [], f"{label}: incomplete semantic observation")
        require(native.get("checkpoints", [{}])[0].get("label") == "task17_owner_before_event" and
                native.get("checkpoints", [{}, {}])[-1].get("label") == "task17_owner_after_event",
                f"{label}: ordered owner checkpoints missing")
        transition = native.get("evidence", [{}])[0].get("nativeTransition", {})
        require(transition.get("entryExecuted") is True and transition.get("evaluatorRole") == role,
                f"{label}: candidate entry did not execute")
        if role == "base":
            require(transition.get("semanticFeatureAbsent") is True and
                    transition.get("basePositiveControl", {}).get("clickedBannerNext") is True and
                    transition.get("basePositiveControl", {}).get("finalEntryAbsent") is True,
                    f"{label}: base absence positive control incomplete")
        else:
            require(transition.get("eventExecuted") is True and
                    transition.get("binding", {}).get("configuredBeforeScoredAbilityStart") is True and
                    transition.get("binding", {}).get("importCompleted") is True and
                    transition.get("fixture", {}).get("calls"),
                    f"{label}: owner/service transition incomplete")
        counts.setdefault(role, {"pass": 0, "fail": 0})[row["status"]] += 1

    require(counts["base"] == {"pass": 0, "fail": 9}, "base polarity changed")
    require(counts["final"] == {"pass": 9, "fail": 0}, "final polarity changed")
    require(sum(counts["agent"].values()) == 9, "agent result incomplete")
    for role, role_counts in counts.items():
        require(document.get("roles", {}).get(role, {}).get("semantic") == role_counts,
                f"{role}: summary differs from rows")
        require(document["roles"][role].get("applicationCompile") == "passed",
                f"{role}: application compile summary missing")
        if role in {"base", "final"}:
            require(document["roles"][role].get("polarityValid") is True,
                    f"{role}: polarity summary invalid")
    return {"validated": True, "matrix": str(matrix_path), "rows": len(rows), "roles": counts,
            "durationSeconds": document.get("durationSeconds")}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("matrix", type=Path)
    print(json.dumps(verify_matrix(parser.parse_args().matrix), indent=2))
