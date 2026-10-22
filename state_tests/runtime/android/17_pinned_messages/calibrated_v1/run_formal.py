#!/usr/bin/env python3
"""Calibrate the source-parameterized scorer; final-copy is evaluator sanity only."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT))
from scripts.runtime_semantics import task17_android_strict_agent as scorer
from scripts.runtime_semantics import task17_android_entry_evidence as policy
from scripts.run_runtime_transition_matrix import validate_report

SOURCE = ROOT / "_sources/element-x-android"
REFS = {"base": "4ecc9f46b6627f89184d66b758094a7c4a24c258",
        "final": "eff868ddf9e1caef8182e55ac59054e81526a68f",
        "base-copy": "4ecc9f46b6627f89184d66b758094a7c4a24c258",
        "final-copy": "eff868ddf9e1caef8182e55ac59054e81526a68f"}


def cleanup_manifest(directory):
    digest = hashlib.sha256()
    size, files, binaries = 0, 0, []
    for path in sorted(directory.rglob("*")):
        if not path.is_file():
            continue
        item = scorer.record(path)
        relative = path.relative_to(directory).as_posix()
        digest.update(json.dumps([relative, item["bytes"], item["sha256"]], separators=(",", ":")).encode() + b"\n")
        size += item["bytes"]
        files += 1
        if path.suffix.lower() in {".apk", ".aab", ".aar", ".jar", ".class", ".dex", ".so"}:
            binaries.append({**item, "path": relative})
    return {"path": str(directory), "bytes": size, "files": files, "sha256": digest.hexdigest(),
            "binaryArtifacts": binaries}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--roles", nargs="+", choices=list(REFS), default=list(REFS))
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    contract = json.loads(scorer.CONTRACT.read_text())
    summary = {"taskId": scorer.TASK, "purpose": "formal_scorer_calibration",
               "finalCopyIsMiniMaxResult": False, "applicationCompile": "not_run", "roles": {}}
    if (output / "summary.json").exists():
        summary = json.loads((output / "summary.json").read_text())
    for role in args.roles:
        result = output / f"{role}.json"
        if not args.validate_only:
            if shutil.disk_usage(ROOT).free < scorer.MIN_FREE_BYTES:
                raise RuntimeError("storage_protection_environment: less than 8 GiB free")
            with tempfile.TemporaryDirectory(prefix="ltb-task17-source-") as directory:
                candidate = Path(directory) / "candidate"
                candidate.mkdir()
                archive = subprocess.Popen(["git", "-C", str(SOURCE), "archive", REFS[role]], stdout=subprocess.PIPE,
                    env={**os.environ, "GIT_LFS_SKIP_SMUDGE": "1"})
                try:
                    subprocess.run(["tar", "-xf", "-", "-C", str(candidate)], stdin=archive.stdout, check=True)
                finally:
                    archive.stdout.close()
                if archive.wait() != 0:
                    raise RuntimeError("Immutable source export failed")
                report = scorer.score(candidate, result, time.monotonic() + 3600)
                report["role"] = "agent" if role.endswith("-copy") else role
                report["provenance"].update(calibrationRef=REFS[role],
                    executionPurpose="scorer_sanity_only" if role.endswith("-copy") else "polarity_calibration",
                    fixedFinalCopyIsModelResult=False)
                report["provenance"]["candidateCleanup"] = cleanup_manifest(candidate)
            report["provenance"]["candidateCleanup"]["removed"] = not candidate.exists()
            result.write_text(json.dumps(report, indent=2) + "\n")
        report = json.loads(result.read_text())
        assessment = {"counts": scorer.counts(report["semantic"]["cases"]),
                      "report": scorer.record(result), "dedicatedEntryPolicyValidated": False,
                      "sharedValidateReportPassed": False}
        used = set()
        for row in report["semantic"]["cases"]:
            if row.get("entryFailureEvidence"):
                policy.validate_entry_failure(row, report, used, contract)
        assessment["dedicatedEntryPolicyValidated"] = True
        try:
            validate_report(report, contract)
            assessment["sharedValidateReportPassed"] = True
        except ValueError as error:
            assessment["sharedValidationError"] = str(error)
        target = {"pass": 0 if role.startswith("base") else 9,
                  "fail": 9 if role.startswith("base") else 0, "not_scored": 0}
        assessment["exactPolarity"] = assessment["counts"] == target
        summary["roles"][role] = assessment
        (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
        print(json.dumps({"role": role, **assessment}), flush=True)
    summary["validated"] = len(summary["roles"]) == 4 and all(
        item["exactPolarity"] and item["sharedValidateReportPassed"] for item in summary["roles"].values())
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    return 0 if summary["validated"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
