#!/usr/bin/env python3
"""Hash-verify and remove reconstructable Task17 ArkTS HAP copies."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

try:
    from runtime_semantics.task17_arkts_owner_verify import verify_matrix
except ModuleNotFoundError:  # Imported as scripts.cleanup_* by unit tests.
    from scripts.runtime_semantics.task17_arkts_owner_verify import verify_matrix


ROOT = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def remove_haps(evidence_root: Path) -> list[dict]:
    evidence_root = evidence_root.resolve()
    removed = []
    for report_path in sorted(evidence_root.rglob("device-build-report.json")):
        report = json.loads(report_path.read_text(encoding="utf-8"))
        for artifact in report.get("haps", []):
            path = Path(artifact["path"]).resolve()
            if path.suffix != ".hap" or not path.is_relative_to(evidence_root):
                raise ValueError(f"Refusing non-owned HAP path: {path}")
            if not path.is_file():
                raise ValueError(f"Expected retained HAP is missing: {path}")
            if artifact.get("bytes") != path.stat().st_size or artifact.get("sha256") != sha256(path):
                raise ValueError(f"HAP differs from retained build metadata: {path}")
            record = {"path": str(path), "bytes": path.stat().st_size,
                      "sha256": artifact["sha256"], "buildReport": str(report_path)}
            path.unlink()
            record["deleted"] = not path.exists()
            removed.append(record)
    return removed


def atomic_write(path: Path, value: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--matrix-root", type=Path, required=True)
    parser.add_argument("--dev-root", type=Path)
    args = parser.parse_args()
    matrix_root = args.matrix_root.resolve()
    matrix_path = matrix_root / "matrix.json"
    cleanup_path = matrix_root / "binary-cleanup.json"
    if cleanup_path.exists():
        raise SystemExit(f"Refusing existing cleanup receipt: {cleanup_path}")
    verified_before = verify_matrix(matrix_path)
    matrix_record = {"path": str(matrix_path), "bytes": matrix_path.stat().st_size,
                     "sha256": sha256(matrix_path)}
    groups = [{"root": str(matrix_root), "artifacts": remove_haps(matrix_root)}]
    if args.dev_root:
        dev_root = args.dev_root.resolve()
        groups.append({"root": str(dev_root), "artifacts": remove_haps(dev_root)})
    verified_after = verify_matrix(matrix_path)
    artifacts = [item for group in groups for item in group["artifacts"]]
    receipt = {
        "schemaVersion": 1,
        "taskId": "17_pinned_messages",
        "policy": "delete_hash_verified_reconstructable_haps_after_completed_device_execution",
        "matrix": matrix_record,
        "verifiedBefore": verified_before,
        "verifiedAfter": verified_after,
        "groups": groups,
        "artifactsDeleted": len(artifacts),
        "bytesDeleted": sum(item["bytes"] for item in artifacts),
        "reportsAndNativeEvidenceRetained": True,
    }
    atomic_write(cleanup_path, receipt)
    print(json.dumps({"receipt": str(cleanup_path), "artifactsDeleted": len(artifacts),
                      "bytesDeleted": receipt["bytesDeleted"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
