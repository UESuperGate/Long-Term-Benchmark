#!/usr/bin/env python3
"""Task12 strict formal agent-result scorer entrypoint."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

try:
    from .task12_13_formal_core import ApplicationCompiler, ROOT, RuntimeEvaluator, TaskSpec, score as _score
except ImportError:
    from task12_13_formal_core import ApplicationCompiler, ROOT, RuntimeEvaluator, TaskSpec, score as _score


SPEC = TaskSpec(
    task_id="12_report_room",
    case_count=10,
    contract=ROOT / "experiment_results/runtime_transition_20261020/contract_audit/revision_3/after/12_report_room/transitions.json",
    calibration_evidence={
        "android": {
            "base": ROOT / "experiment_results/runtime_transition_20261020/task12_prefix/android-base-v2.parent-verified.json",
            "final": ROOT / "experiment_results/runtime_transition_20261020/task12_prefix/android-final-25_05_4-v3.json",
        },
        "arkts": {
            "base": ROOT / "experiment_results/runtime_transition_20261020/task12_rebuild/native-base-entry-v1/arkts_12_report_room_base.device-entry.json",
            "final": ROOT / "experiment_results/runtime_transition_20261020/task12_rebuild/native-final-device-v1/arkts_12_report_room_final.device.json",
        },
    },
    calibrator_files={
        "android": (
            ROOT / "state_tests/runtime/android/12_report_room/action_prefix/run.py",
            ROOT / "state_tests/runtime/android/12_report_room/action_prefix_final_25_05_4/run.py",
        ),
        "arkts": (
            ROOT / "scripts/runtime_semantics/Task12BaseDeviceEntry.cjs",
            ROOT / "scripts/runtime_semantics/Task12FinalDevice.cjs",
        ),
    },
)


def score(*, platform: str, source: Path, base_source: Path, final_source: Path,
          output: Path, compile_passed: bool | None = None, compile_command: str = "",
          evaluator: RuntimeEvaluator | None = None,
          application_compiler: ApplicationCompiler | None = None,
          application_compile_evidence: Path | None = None,
          device_serial: str | None = None, timeout: float = 3600,
          validate_public: bool = True, **testing) -> dict:
    if platform == "arkts" and evaluator is None:
        try:
            from .task12_merged_pipeline_v1 import score as actual_score
        except ImportError:
            try:
                from runtime_semantics.task12_merged_pipeline_v1 import score as actual_score
            except ImportError:
                from scripts.runtime_semantics.task12_merged_pipeline_v1 import score as actual_score
        return actual_score(platform=platform, source=source, base_source=base_source,
            final_source=final_source, output=output, compile_passed=compile_passed,
            compile_command=compile_command, application_compiler=application_compiler,
            application_compile_evidence=application_compile_evidence,
            device_serial=device_serial, timeout=timeout, validate_public=validate_public, **testing)
    actual_runtime = evaluator is None
    if application_compile_evidence is not None:
        if application_compiler is not None or compile_passed is not None:
            raise ValueError("Task12 compile receipt cannot be combined with another compile result")
        try:
            from .task12_application_evidence import reuse_compiler
        except ImportError:
            from task12_application_evidence import reuse_compiler
        application_compiler = reuse_compiler(application_compile_evidence)
    if evaluator is None:
        if platform == "android":
            try:
                from .task12_android_strict_runtime import evaluate as selected
            except ImportError:
                from task12_android_strict_runtime import evaluate as selected
        else:
            try:
                from .task12_arkts_strict_runtime import evaluate as selected
            except ImportError:
                from task12_arkts_strict_runtime import evaluate as selected
        evaluator = lambda **kwargs: selected(**kwargs, device_serial=device_serial)
    if application_compiler is None and compile_passed is None:
        try:
            from .task12_13_runtime_support import compile_candidate
        except ImportError:
            from task12_13_runtime_support import compile_candidate
        application_compiler = compile_candidate
    result = _score(spec=SPEC, platform=platform, source=source, base_source=base_source,
                  final_source=final_source, output=output, compile_passed=compile_passed,
                  compile_command=compile_command, evaluator=evaluator, timeout=timeout,
                  application_compiler=application_compiler, **testing)
    if actual_runtime and validate_public and result["calibration"].get("passed"):
        try:
            from .task12_13_report_validation import finalize
        except ImportError:
            from task12_13_report_validation import finalize
        result = finalize(result, output, json.loads(SPEC.contract.read_text()))
    return result


dispatch = score


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--platform", choices=("android", "arkts"), required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--base-source", type=Path, required=True)
    parser.add_argument("--final-source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--compile-command", default="")
    parser.add_argument("--application-compile-evidence", type=Path)
    parser.add_argument("--device-serial", default=os.environ.get("ARKTS_DEVICE_SERIAL", "127.0.0.1:5555"))
    args = parser.parse_args()
    result = score(platform=args.platform, source=args.source, base_source=args.base_source,
                   final_source=args.final_source, output=args.output,
                   compile_command=args.compile_command, device_serial=args.device_serial,
                   application_compile_evidence=args.application_compile_evidence)
    print(json.dumps({"output": str(args.output), "compile": result["compile"],
                      "semantic": result["semantic"], "publication": result["publication"]},
                     ensure_ascii=False))
    return 0 if result["publication"]["eligible"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
