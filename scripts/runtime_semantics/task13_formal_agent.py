#!/usr/bin/env python3
"""Task13 revision-5 strict formal agent-result scorer entrypoint."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import time
import uuid

try:
    from .task12_13_formal_core import ApplicationCompiler, ROOT, RuntimeEvaluator, TaskSpec, score as _score
    from . import task12_13_formal_core as core
    from .task13_overall_deadline import OverallDeadline, WorkDeadlineExpired, HardDeadlineExpired, DeadlineOwnershipError
except ImportError:
    from task12_13_formal_core import ApplicationCompiler, ROOT, RuntimeEvaluator, TaskSpec, score as _score
    import task12_13_formal_core as core
    from task13_overall_deadline import OverallDeadline, WorkDeadlineExpired, HardDeadlineExpired, DeadlineOwnershipError


REVISION5_SHA256 = "c038fddc0beba7933076cef4f63a8d156ccf914628cb39c3b5eec708c7035e90"


SPEC = TaskSpec(
    task_id="13_user_verification",
    case_count=10,
    contract=ROOT / "benchmark_tasks/13_user_verification/transitions.json",
    audited_contract=ROOT / "experiment_results/runtime_transition_20261020/contract_audit/revision_5_task13/after/transitions.json",
    expected_contract_sha256=REVISION5_SHA256,
    calibration_evidence={
        "android": {
            "base": ROOT / "experiment_results/runtime_transition_20261020/task13_android/revision_5_runtime/calibrated_v2/base.runtime_calibrated.json",
            "final": ROOT / "experiment_results/runtime_transition_20261020/task13_android/revision_5_runtime/calibrated_v2/final.runtime_calibrated.json",
        },
        "arkts": {
            "base": ROOT / "experiment_results/runtime_transition_20261020/task13_page_owner_port_v1/controls-v4/base/runtime.json",
            "final": ROOT / "experiment_results/runtime_transition_20261020/task13_page_owner_port_v1/controls-v4/final/runtime.json",
        },
    },
    calibrator_files={
        "android": (
            ROOT / "state_tests/runtime/android/13_user_verification/revision5_base/run.py",
            ROOT / "state_tests/runtime/android/13_user_verification/revision5_final/run.py",
            ROOT / "scripts/assemble_task13_revision5_runtime.py",
        ),
        "arkts": (
            ROOT / "scripts/runtime_semantics/task13_arkts_revision5_build.cjs",
            ROOT / "scripts/runtime_semantics/task13_arkts_revision5_execute.cjs",
            ROOT / "state_tests/runtime/arkts/native/Task13Revision5NativeUi.install.cjs",
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
    budget = OverallDeadline(timeout)
    state = {'result': None, 'compile': {'passed': compile_passed,
             'status': 'passed' if compile_passed is True else 'failed' if compile_passed is False else 'not_run',
             'scope': 'standalone_candidate_application_build', 'command': compile_command},
             'revocationNonce': uuid.uuid4().hex, 'revokedOutputs': [], 'revocationAttempts': []}
    # This fallback exists before any timer can interrupt contract parsing.
    state['failure'] = {'schemaVersion': 2, 'taskId': SPEC.task_id, 'platform': platform, 'role': 'agent',
                        'target': str(source), 'observationMode': 'runtime_state_transition',
                        'compile': state['compile'], 'runtimeCompile': {'passed': None, 'status': 'not_run'},
                        'semantic': {'total': SPEC.case_count, 'passed': 0, 'failed': 0,
                                     'notScored': SPEC.case_count, 'cases': []},
                        'calibration': {'passed': False}, 'publication': {'eligible': False},
                        'diagnostics': {'adapter': 'failed', 'revokedOutputs': state['revokedOutputs'],
                                        'revocationAttempts': state['revocationAttempts']}}
    try:
        with budget:
            try:
                state['failure']['semantic']['cases'] = core._not_scored(core.load(SPEC.contract), 'Task13 overall deadline exhausted')
                result = _score_with_owned_deadline(
                    platform=platform, source=source, base_source=base_source, final_source=final_source,
                    output=output, compile_passed=compile_passed, compile_command=compile_command,
                    evaluator=evaluator, application_compiler=application_compiler,
                    application_compile_evidence=application_compile_evidence,
                    device_serial=device_serial, timeout=timeout, validate_public=validate_public,
                    _budget=budget, _state=state, **testing)
                budget.check_work()
                result.setdefault('diagnostics', {})['task13OverallDeadline'] = budget.diagnostic()
                core.write(output, result)
                return result
            except WorkDeadlineExpired as error:
                # Rename first: no potentially slow copy/hash/write can leave success live.
                _revoke_provisional(output, state)
                result = _deadline_result(state, budget, str(error))
                core.write(output, result)
                cleanup = core.cleanup_artifacts(output.resolve().with_suffix('.strict-evidence'))
                result['diagnostics']['deadlineCleanup'] = cleanup
                if state['revokedOutputs']:
                    result['diagnostics']['preDeadlineOutput'] = core.file_record(Path(state['revokedOutputs'][0]))
                result['diagnostics']['task13OverallDeadline'] = budget.diagnostic()
                core.write(output, result)
                return result
    except (HardDeadlineExpired, WorkDeadlineExpired, DeadlineOwnershipError) as error:
        if isinstance(error, DeadlineOwnershipError) and not budget.entered:
            raise
        # Outside the context: catches hard interruption anywhere in the soft suite
        # or __exit__. Only atomic revocation and prebuilt in-memory NS are allowed.
        _revoke_provisional(output, state)
        result = _deadline_result(state, budget, str(error))
        result['diagnostics']['deadlineCleanupIncomplete'] = True
        result['diagnostics']['outputNotWrittenAfterHardStop'] = budget.hard_expired
        result['diagnostics']['outputRevokedWithoutFurtherIO'] = True
        return result


def _revoke_provisional(output, state):
    retained = output.with_name(output.name + '.revoked-' + state['revocationNonce'] +
                                '-' + str(len(state['revokedOutputs'])) + '.raw')
    state['revocationAttempts'].append(str(retained))
    try:
        os.replace(output, retained)
    except FileNotFoundError:
        return
    state['revokedOutputs'].append(str(retained))


def _deadline_result(state, budget, reason):
    # No I/O, serialization or deepcopy: this also runs after the hard stop.
    result = state['failure']
    result['compile'] = state['compile']
    diagnostics = result['diagnostics']
    diagnostics['preDeadlineCalibration'] = state['result'].get('calibration') if state['result'] else None
    diagnostics['task13OverallDeadline'] = budget.diagnostic()
    diagnostics['adapter'] = 'failed'
    result['publication'] = {'eligible': False, 'reason': reason}
    return result


def _score_with_owned_deadline(*, platform, source, base_source, final_source, output,
          compile_passed, compile_command, evaluator, application_compiler,
          application_compile_evidence, device_serial, timeout, validate_public,
          _budget, _state, **testing):
    actual_runtime = evaluator is None
    if application_compile_evidence is not None:
        if application_compiler is not None or compile_passed is not None:
            raise ValueError("Task13 compile receipt cannot be combined with another compile result")
        try:
            from .task13_application_evidence import reuse_compiler
        except ImportError:
            from task13_application_evidence import reuse_compiler
        application_compiler = reuse_compiler(application_compile_evidence)
    if evaluator is None:
        if platform == "android":
            try:
                from .task13_android_strict_runtime import evaluate as selected
            except ImportError:
                from task13_android_strict_runtime import evaluate as selected
        else:
            try:
                from .task13_arkts_strict_runtime import evaluate as selected
            except ImportError:
                from task13_arkts_strict_runtime import evaluate as selected
        evaluator = lambda **kwargs: selected(**kwargs, device_serial=device_serial)
    if application_compiler is None and compile_passed is None:
        try:
            from .task12_13_runtime_support import compile_candidate
        except ImportError:
            from task12_13_runtime_support import compile_candidate
        application_compiler = compile_candidate
    if application_compiler is not None:
        selected_compiler = application_compiler
        def tracked_compiler(**kwargs):
            _state['compile'] = {'passed': None, 'status': 'not_scored',
                                 'scope': 'standalone_candidate_application_build',
                                 'classification': 'overall_deadline', 'command': compile_command,
                                 'reason': 'Application compiler started; no completed result returned before deadline'}
            value = selected_compiler(**kwargs)
            if isinstance(value, dict):
                _state['compile'] = dict(value)
            return value
        application_compiler = tracked_compiler
    if 'monotonic' not in testing:
        # Anchor the shared core's first clock read at wrapper entry, not after imports.
        first_read = True
        def anchored_clock():
            nonlocal first_read
            if first_read:
                first_read = False
                return _budget.started
            return time.monotonic()
        testing['monotonic'] = anchored_clock
    _budget.check_work()
    result = _score(spec=SPEC, platform=platform, source=source, base_source=base_source,
                  final_source=final_source, output=output, compile_passed=compile_passed,
                  compile_command=compile_command, evaluator=evaluator, timeout=timeout,
                  application_compiler=application_compiler, **testing)
    _state['result'] = result
    _state['compile'] = dict(result.get('compile', _state['compile']))
    _budget.check_work()
    if actual_runtime and validate_public and result["calibration"].get("passed"):
        try:
            from .task12_13_report_validation import finalize
        except ImportError:
            from task12_13_report_validation import finalize
        result = finalize(result, output, json.loads(SPEC.contract.read_text()))
        _state['result'] = result
        _budget.check_work()
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
