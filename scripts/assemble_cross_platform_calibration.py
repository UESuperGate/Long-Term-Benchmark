#!/usr/bin/env python3
"""Assemble calibrated Android and ArkTS rows for the shared contract."""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "state_tests" / "canonical" / "cross_platform_contract.json"
ANDROID = ROOT / "verification_reports" / "android_minimax_m3_cross37_portable_semantic.json"
ARKTS = ROOT / "verification_reports" / "cross_platform_arkts_golden_calibration.json"
OUTPUT = ROOT / "verification_reports" / "cross_platform_golden_calibration.json"


def counts(rows: list[dict]) -> dict[str, int]:
    values = Counter(row["semanticStatus"] for row in rows)
    return {status: values[status] for status in ("passed", "failed", "not_scored")} | {"total": len(rows)}


def android_rows(report: dict) -> list[dict]:
    rows = []
    for source_role, target_role in (("base", "base"), ("final", "groundtruth_final")):
        for source in report[source_role]["rows"]:
            rows.append({
                "caseId": source["caseId"],
                "taskId": source["taskId"],
                "traceDigest": source["traceDigest"],
                "semanticStatus": source["semanticStatus"],
                "platform": "android",
                "targetId": f"{source['taskId']}:android:{target_role}",
                "targetRole": target_role,
                "evidenceSource": source["evidenceSource"],
                "clauses": source["clauses"],
            })
    return rows


def main() -> int:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    android_report = json.loads(ANDROID.read_text(encoding="utf-8"))
    arkts_report = json.loads(ARKTS.read_text(encoding="utf-8"))
    if not android_report.get("polarityValid"):
        raise ValueError(f"invalid Android calibration: {ANDROID}")

    all_rows = android_rows(android_report) + arkts_report["cases"]
    case_count = len(contract["cases"])
    groups = {}
    for platform in ("android", "arkts"):
        for role in ("base", "groundtruth_final"):
            selected = [row for row in all_rows if row["platform"] == platform and row["targetRole"] == role]
            groups[f"{platform}:{role}"] = counts(selected)
    valid = all(
        value["not_scored"] == 0
        and value["total"] == case_count
        and (value["failed"] == case_count if key.endswith(":base") else value["passed"] == case_count)
        for key, value in groups.items()
    )
    payload = {
        "schemaVersion": 2,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "contract": str(CONTRACT.relative_to(ROOT)),
        "caseCount": case_count,
        "allPolarityValid": valid,
        "counts": groups,
        "androidCalibrationEvidence": str(ANDROID.relative_to(ROOT)),
        "arktsCalibrationEvidence": str(ARKTS.relative_to(ROOT)),
        "cases": all_rows,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUTPUT), "allPolarityValid": valid, "counts": groups}, ensure_ascii=False))
    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
