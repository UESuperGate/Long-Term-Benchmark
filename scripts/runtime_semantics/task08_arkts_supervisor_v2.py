#!/usr/bin/env python3
"""Versioned entry-gate successor; reuse the reviewed v1 clock/ownership protocol."""
import argparse
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.runtime_semantics import task08_arkts_focus_build_v3 as builder

spec = importlib.util.spec_from_file_location('task08_supervisor_v2_private_v1', ROOT / 'scripts/runtime_semantics/task08_arkts_supervisor_v1.py')
support = importlib.util.module_from_spec(spec)
spec.loader.exec_module(support)
support.builder = builder
support.SCHEMA = 'task08.arkts.fresh-controls.supervisor.v2.original-entry-bound'
original_closure = support.process_closure_gate


def closure():
    result = original_closure()
    result['files'].extend(support.record(p) for p in (Path(__file__), Path(builder.previous.__file__), builder.GATE))
    return result


support.process_closure_gate = closure
run = support.run


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--timeout', type=float, default=3600)
    parser.add_argument('--coordinator-release', action='store_true')
    args = parser.parse_args()
    print(json.dumps(run(args.plan, args.output, args.timeout, args.coordinator_release), indent=2))
