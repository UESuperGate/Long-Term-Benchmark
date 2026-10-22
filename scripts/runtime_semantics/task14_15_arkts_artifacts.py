"""ArkTS-only hash-bound evidence reads under canonical benchmark evidence roots."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
TASKS = {"14_join_room_by_address", "15_account_deactivation"}
POLICY_ID = "task14_15.arkts.canonical-evidence-roots.v1"


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def _canonical_path(value, *, directory=False):
    root = ROOT.resolve(strict=True)
    path = Path(value)
    path = path if path.is_absolute() else root / path
    resolved = path.resolve(strict=True)
    anchors = tuple(root / name for name in ("experiment_results", "eval_runs"))
    require(any(anchor.resolve() == anchor and resolved.is_relative_to(anchor) for anchor in anchors),
            "ArkTS runtime evidence outside canonical experiment_results/eval_runs roots")
    require(resolved.is_dir() if directory else resolved.is_file(),
            "ArkTS runtime evidence is not a directory" if directory else
            "ArkTS runtime evidence is not a regular file")
    return resolved


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def row_digest(row):
    return hashlib.sha256(json.dumps(row, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def artifact(path):
    path = _canonical_path(path)
    data = path.read_bytes()
    return {"path": str(path), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def bound(record, *, inventory=None):
    if isinstance(record, dict) and "bytes" not in record and inventory is not None:
        require(isinstance(inventory, dict) and isinstance(inventory.get("files"), list),
                "ArkTS runtime artifact has no retained size inventory")
        root = _canonical_path(inventory["path"], directory=True)
        target = _canonical_path(record["path"])
        matches = []
        for item in inventory["files"]:
            relative = Path(item["path"])
            require(not relative.is_absolute() and ".." not in relative.parts,
                    "ArkTS retained inventory path escapes its root")
            if (root / relative).resolve() == target:
                matches.append(item)
        require(len(matches) == 1 and matches[0].get("sha256") == record.get("sha256") and
                "bytes" in matches[0], "ArkTS runtime artifact has no unique hash-bound size inventory")
        record = {**record, "bytes": matches[0]["bytes"]}
    require(isinstance(record, dict) and {"path", "bytes", "sha256"} <= record.keys(),
            "ArkTS runtime artifact requires path, bytes and SHA256")
    require(isinstance(record["path"], str) and bool(record["path"]) and
            type(record["bytes"]) is int and record["bytes"] >= 0 and
            isinstance(record["sha256"], str) and re.fullmatch(r"[0-9a-f]{64}", record["sha256"]) is not None,
            "ArkTS runtime artifact has invalid path, bytes or SHA256")
    path = _canonical_path(record["path"])
    data = path.read_bytes()
    require(len(data) == record["bytes"] and hashlib.sha256(data).hexdigest() == record["sha256"],
            "ArkTS runtime artifact digest changed")
    return data
