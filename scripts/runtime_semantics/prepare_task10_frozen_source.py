#!/usr/bin/env python3
"""Reconstruct a frozen Task10 patch for evaluator work, without model feedback."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.runtime_semantics.tasks10_11_formal_scorer import candidate_smoke


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--patch", type=Path, required=True)
    parser.add_argument("--patch-sha256", required=True)
    parser.add_argument("--original-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("Existing reconstruction evidence")
    data = args.patch.read_bytes()
    if hashlib.sha256(data).hexdigest() != args.patch_sha256:
        raise ValueError("Frozen patch changed")
    source = Path(tempfile.mkdtemp(prefix="ltb-task10-frozen-"))
    try:
        shutil.copytree(args.base, source, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns(".git", "build", ".hvigor", "oh_modules", "node_modules"))
        subprocess.run(["git", "apply", "--binary", str(args.patch.resolve())], cwd=source, check=True)
        smoke = candidate_smoke(source, "arkts")
        original_report = json.loads(args.original_report.read_text())
        original = original_report["diagnostics"]["candidateSmoke"]
        expected = original["inventorySha256"]
        if smoke["inventorySha256"] != expected:
            raise ValueError("Reconstructed source differs from originally scored candidate inventory")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps({"source": str(source), "patch": str(args.patch.resolve()),
            "patchSha256": args.patch_sha256, "inventory": smoke, "originalInventory": original,
            "modelInvoked": False, "productionModifiedBeyondFrozenPatch": False}, indent=2) + "\n")
        print(source)
    except BaseException:
        shutil.rmtree(source)
        raise


if __name__ == "__main__":
    main()
