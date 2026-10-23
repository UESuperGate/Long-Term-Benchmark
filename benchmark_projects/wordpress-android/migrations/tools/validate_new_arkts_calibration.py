#!/usr/bin/env python3
"""Validate WordPress 03/04 ArkTS runtime calibration artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


TASKS = ("03_site_picker", "04_new_stats")
EXPECTED = {
    "base": {"passed": 0, "failed": 10, "notScored": 0, "total": 10},
    "final": {"passed": 10, "failed": 0, "notScored": 0, "total": 10},
    "no-change-control": {"passed": 0, "failed": 10, "notScored": 0, "total": 10},
    "known-final-control": {"passed": 10, "failed": 0, "notScored": 0, "total": 10},
    "fail-closed-control": {"passed": 0, "failed": 0, "notScored": 10, "total": 10},
}


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_task(migration: Path) -> None:
    task = migration.name
    contract_path = migration / "canonical/transitions.json"
    contract = load(contract_path)
    android_audit = load(migration / "provenance/android-runtime-audit.json")
    assert digest(contract_path) == android_audit["canonicalContract"]["sha256"]
    canonical_ids = [(case["caseId"], case["key"], case["traceDigest"]) for case in contract["cases"]]
    assert len(canonical_ids) == 10 and len(set(canonical_ids)) == 10

    binding = load(migration / "arkts/bindings.json")
    assert binding["taskId"] == task
    assert binding["observationMode"] == "runtime_state_transition"
    assert [(row["caseId"], row["traceDigest"]) for row in binding["cases"]] == [
        (case["caseId"], case["traceDigest"]) for case in contract["cases"]
    ]

    for name, expected in EXPECTED.items():
        report = load(migration / "results" / f"arkts-{name}.json")
        assert report["taskId"] == task
        assert report["observationMode"] == "runtime_state_transition"
        assert report["semantic"]["summary"] == expected
        assert report["diagnostics"]["sourceObserver"] is False
        assert report["diagnostics"]["roleAffectsVerdict"] is False
        rows = report["semantic"]["cases"]
        assert [(row["caseId"], row["key"], row["traceDigest"]) for row in rows] == canonical_ids
        if name != "fail-closed-control":
            assert report["compile"]["passed"] is True
            assert report["device"]["apiLevel"] == 23
            for row in rows:
                assert row["status"] != "not_scored"
                assert row["runtimeEvidence"]["evaluatorStoreWrites"] == 0
                assert row["runtimeEvidence"]["detachedControllers"] == 0
                assert row["runtimeEvidence"]["storageReopened"] is True
                assert all(check["passed"] for check in row["runtimeBoundaryChecks"])
        else:
            assert report["diagnostics"]["transport"] == "unavailable"
            assert report["diagnostics"]["productionEntryExecuted"] is False

    build_evidence = load(migration / "provenance/arkts-build-evidence.json")
    evidence_by_role = {row["role"]: row for row in build_evidence["builds"]}
    assert build_evidence["taskId"] == task
    assert set(evidence_by_role) == {"base", "final"}

    for role in ("base", "final"):
        project = migration / "arkts" / role
        haps = list((project / "entry/build").rglob("*.hap"))
        evidence = evidence_by_role[role]
        report = load(migration / evidence["report"]["path"])
        assert report["compile"]["passed"] is True
        assert report["compile"]["hapSha256"] == evidence["hap"]["sha256"]
        assert report["compile"]["hapBytes"] == evidence["hap"]["bytes"]
        assert re.fullmatch(r"[0-9a-f]{64}", evidence["hap"]["sha256"])
        assert evidence["hap"]["bytes"] > 0
        build_log = migration / evidence["buildLog"]["path"]
        report_path = migration / evidence["report"]["path"]
        assert digest(build_log) == evidence["buildLog"]["sha256"]
        assert digest(report_path) == evidence["report"]["sha256"]
        if haps:
            assert len(haps) == 1
            assert digest(haps[0]) == evidence["hap"]["sha256"]
            assert haps[0].stat().st_size == evidence["hap"]["bytes"]
        else:
            assert "removed only after hashes" in build_evidence["cleanupPolicy"]
        production = project / "entry/src/main/ets"
        for path in production.rglob("*.ets"):
            if "evaluator" in path.parts:
                continue
            text = path.read_text(encoding="utf-8")
            assert not re.search(r"\bcaseId\b|\btraceDigest\b|\bexpected\b", text), path
            assert not any(case_id in text for case_id, _, _ in canonical_ids), path
        probe = (production / "evaluator/SemanticProbe.ets").read_text(encoding="utf-8")
        assert "expected" not in probe and "traceDigest" not in probe and "caseId" not in probe

    scorer = (migration.parent / "tools/run_arkts_state_transition.py").read_text(encoding="utf-8")
    assert 'parser.add_argument("--project"' in scorer
    assert "if args.role" not in scorer and "args.role ==" not in scorer
    ownership = load(migration / "arkts/source_ownership.json")
    assert ownership["sourceObserver"] is False
    assert ownership["roleAffectsVerdict"] is False
    assert ownership["caseIdSwitchInCandidateProduction"] is False
    assert ownership["arbitraryStandaloneCandidateDirectory"] is True
    parity = load(migration / "provenance/transition-parity.json")
    assert parity["byteIdentical"] is True and parity["assertionsRelaxed"] is False
    assert len(parity["cases"]) == 10 and all(row["androidBound"] and row["arktsBound"] for row in parity["cases"])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--migrations", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--task", action="append", choices=TASKS)
    args = parser.parse_args()
    for task in args.task or TASKS:
        validate_task(args.migrations.resolve() / task)
        print(f"{task}: ArkTS calibration validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
