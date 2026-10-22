#!/usr/bin/env python3
"""Hash-clean only owned Task10 binding debug scratch, retaining native snapshots."""
import argparse
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.runtime_semantics.tasks10_11_formal_scorer import candidate_smoke
from scripts.runtime_semantics.tasks10_11_runtime_evidence import record

EVIDENCE = ROOT / "experiment_results/runtime_transition_20261020/task10_fresh_m3_binding_v2"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--reconstruction", type=Path, default=EVIDENCE / "reconstruction.json")
    parser.add_argument("--source-only", action="store_true")
    args = parser.parse_args()
    if args.output_dir.exists():
        raise ValueError("Refusing to replace cleanup evidence")
    args.output_dir.mkdir(parents=True)
    reconstruction = json.loads(args.reconstruction.read_text())
    source = Path(reconstruction["source"])
    paths = [EVIDENCE / name / "temporary" for name in
             ("smoke-001", "smoke-002", "smoke-003", "smoke-004", "smoke-005", "candidate-v1")]
    if args.source_only:
        paths = []
    if source.exists():
        if not source.name.startswith("ltb-task10-frozen-") or source.parent == ROOT:
            raise ValueError("Unexpected owned candidate directory")
        current = candidate_smoke(source, "arkts")
        if current["inventorySha256"] != reconstruction["inventory"]["inventorySha256"]:
            raise ValueError("Frozen candidate changed before cleanup")
        paths.append(source)
    entries = []
    for path in paths:
        if not path.is_dir():
            continue
        files, retained = [], []
        for item in sorted(path.rglob("*")):
            if not item.is_file():
                continue
            files.append(record(item))
            if item.name == "native-result.json":
                target = args.output_dir / "readable-debug-native" / path.parent.name / item.relative_to(path)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(item, target)
                retained.append(record(target))
        entries.append({"directory": str(path), "files": files, "readableNativeEvidence": retained,
                        "bytes": sum(item["bytes"] for item in files), "deleted": False})
    result = {"phase": "hash_recorded_before_delete", "directories": entries,
              "scope": "owned frozen candidate copy only" if args.source_only else "owned debug attempts and frozen candidate copy only",
              "debugNativeEvidenceIsFormalScore": False, "acceptedReportsModified": False,
              "originalPatch": record(Path(reconstruction["patch"])),
              "oldRawReportsRetained": True, "oldDebugInputsBecomeHashOnly": True}
    target = args.output_dir / "cleanup.json"
    target.write_text(json.dumps(result, indent=2) + "\n")
    for entry in entries:
        shutil.rmtree(entry["directory"])
        entry["deleted"] = not Path(entry["directory"]).exists()
    result.update(phase="completed", removedBytes=sum(entry["bytes"] for entry in entries),
                  retainedReadableBytes=sum(item["bytes"] for entry in entries for item in entry["readableNativeEvidence"]))
    result["netLogicalBytesReleased"] = result["removedBytes"] - result["retainedReadableBytes"]
    target.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({key: result[key] for key in
                      ("phase", "removedBytes", "retainedReadableBytes", "netLogicalBytesReleased")}))


if __name__ == "__main__":
    main()
