#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


EXPECTED = {
    "results/android-base.json": {"passed": 0, "failed": 10, "notScored": 0, "total": 10},
    "results/android-final.json": {"passed": 10, "failed": 0, "notScored": 0, "total": 10},
    "provenance/android-no-change-control.json": {"passed": 0, "failed": 10, "notScored": 0, "total": 10},
    "provenance/android-known-final-control.json": {"passed": 10, "failed": 0, "notScored": 0, "total": 10},
}


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--migration", type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    migration = args.migration.resolve()
    runtime = migration / "android/focused-runtime"
    task_contract = migration.parents[1] / "tasks/03_site_picker/transitions.json"
    canonical = migration / "canonical/transitions.json"
    errors: list[str] = []

    if canonical.read_bytes() != task_contract.read_bytes():
        errors.append("canonical transition contract differs from the extracted task")

    source_rows = []
    for role in ("base", "final"):
        project = runtime / role
        manifest_path = project / "upstream-source-manifest.json"
        manifest = load(manifest_path)
        compiled_files = manifest.get("compiledFiles", {})
        for row in manifest["files"]:
            immutable = project / "upstream-immutable" / row["path"]
            immutable_hash = sha256(immutable)
            if immutable_hash != row["sha256"]:
                errors.append(f"{role}:{row['path']}: immutable source mismatch")
            compiled_relative = compiled_files.get(row["path"])
            compiled_hash = None
            if compiled_relative:
                compiled = runtime / "evaluator" / f"{role}-production" / compiled_relative
                compiled_hash = sha256(compiled)
                if compiled_hash != row["sha256"]:
                    errors.append(f"{role}:{compiled_relative}: compiled source mismatch")
            source_rows.append(
                {
                    "role": role,
                    "path": row["path"],
                    "gitBlob": row["gitBlob"],
                    "sha256": row["sha256"],
                    "compiledPath": compiled_relative,
                    "compiledSha256": compiled_hash,
                }
            )

    calibration = []
    for relative, expected in EXPECTED.items():
        report = load(migration / relative)
        actual = report["semantic"]["summary"]
        if actual != expected:
            errors.append(f"{relative}: expected {expected}, got {actual}")
        if report["diagnostics"]["sourceIntegrity"] != "passed":
            errors.append(f"{relative}: source integrity did not pass")
        calibration.append(
            {
                "report": relative,
                "role": report["role"],
                "summary": actual,
                "adapter": report["diagnostics"]["adapter"],
                "transport": report["diagnostics"]["transport"],
                "reportSha256": sha256(migration / relative),
            }
        )

    audit = {
        "schemaVersion": 1,
        "taskId": "03_site_picker",
        "status": "passed" if not errors else "failed",
        "canonicalContract": {
            "path": "canonical/transitions.json",
            "sha256": sha256(canonical),
            "byteIdenticalToTask": canonical.read_bytes() == task_contract.read_bytes(),
        },
        "sourceBytes": source_rows,
        "calibration": calibration,
        "errors": errors,
    }
    encoded = json.dumps(audit, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
