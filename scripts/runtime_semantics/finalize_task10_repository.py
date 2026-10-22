#!/usr/bin/env python3
"""Bind Task10 real device evidence, validate publicly, then hash-clean artifacts."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.runtime_semantics.task10_repository_evidence import attach_child, validate_report
from scripts.runtime_semantics.tasks10_11_formal_scorer import cleanup_evidence_artifacts
from scripts.runtime_semantics.tasks10_11_runtime_evidence import record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", type=Path)
    parser.add_argument("--artifacts", type=Path)
    parser.add_argument("--bound", type=Path)
    parser.add_argument("--original-report", type=Path)
    parser.add_argument("--frozen-patch", type=Path)
    parser.add_argument("--reconstruction", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists():
        raise ValueError("Refusing previous audit/output directory")
    args.output_dir.mkdir(parents=True)
    contract_path = ROOT / "benchmark_tasks/10_media_upload_quality/transitions.json"
    contract = json.loads(contract_path.read_text())
    status = {"publicAccepted": False, "integrityAccepted": False, "sourceObserverUsed": False,
              "contract": record(contract_path), "productionModified": False, "modelInvoked": False}
    try:
        if args.bound:
            report = json.loads(args.bound.read_text())
            validate_report(report, contract)
            status["inputBoundReport"] = record(args.bound)
        else:
            if not args.raw or not args.artifacts:
                raise ValueError("Raw runtime and its actual artifacts are required")
            status["rawReport"] = record(args.raw)
            report = attach_child(json.loads(args.raw.read_text()), contract, args.artifacts, args.output_dir / "audit")
        validate_report(report, contract)
        if args.original_report or args.frozen_patch or args.reconstruction:
            if not all((args.original_report, args.frozen_patch, args.reconstruction)):
                raise ValueError("All frozen real-agent provenance inputs are required")
            reconstruction = json.loads(args.reconstruction.read_text())
            original = json.loads(args.original_report.read_text())
            patch_sha = hashlib.sha256(args.frozen_patch.read_bytes()).hexdigest()
            if (reconstruction["patchSha256"] != patch_sha or reconstruction["inventory"]["inventorySha256"] !=
                    original["diagnostics"]["candidateSmoke"]["inventorySha256"]):
                raise ValueError("Frozen real-agent production patch binding changed")
            report.update(modelAgentResult=True, inputKind="frozen_real_MiniMax_M3_candidate")
            report["provenance"]["frozenCandidate"] = {"patch": record(args.frozen_patch),
                "originalRunReport": record(args.original_report), "reconstruction": record(args.reconstruction),
                "productionInventorySha256": reconstruction["inventory"]["inventorySha256"],
                "modelGenerationRepeated": False, "originalCompileReceipt": original["compile"],
                "compileMetricOverwritten": False}
        target = args.output_dir / "accepted.runtime.json"
        target.write_text(json.dumps(report, indent=2) + "\n")
        status.update(publicAccepted=True, integrityAccepted=True, report=record(target),
                      semantic={key: value for key, value in report["semantic"].items() if key != "cases"})
    except ValueError as error:
        status["error"] = str(error)
        draft = args.output_dir / "audit/diagnostic.pending-public.runtime.json"
        if draft.exists():
            status["diagnosticPendingPublic"] = record(draft)
    finally:
        draft = args.output_dir / "audit/diagnostic.pending-public.runtime.json"
        if args.artifacts and (status["publicAccepted"] or draft.exists()):
            status["cleanup"] = cleanup_evidence_artifacts(args.output_dir, args.artifacts)
        (args.output_dir / "status.json").write_text(json.dumps(status, indent=2) + "\n")
    print(json.dumps(status, indent=2))
    return 0 if status["publicAccepted"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
