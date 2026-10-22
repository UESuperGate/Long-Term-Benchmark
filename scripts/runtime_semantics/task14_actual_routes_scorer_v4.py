"""Versioned candidate-only Task14 native-route driver; central is not modified.

Default admission is fail closed. This version implements physical005/006/009
packaging/capture, not a new full nine-case score. Other rows are NS until their
own reviewed native/pure-domain-owner handlers and matched four controls exist.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

from . import task14_actual_routes_packaging_v4 as packaging
from . import task14_actual_routes_guard_v4 as guard
from . import task14_15_formal_core as core
from . import task14_15_arkts_artifacts as artifacts
from . import task14_15_device_lease as lease
from . import task15_supervision_v4 as supervision
from .task15_deadline_v4 import OverallDeadline, child_local_deadline, WorkDeadlineExpired, HardDeadlineExpired


def _fallback(source, compile_passed, compile_command, reason):
    contract = core.load(packaging.CONTRACT)
    rows = core.unavailable_rows(contract, reason)
    return {'schemaVersion': 4, 'taskId': packaging.TASK, 'platform': 'arkts', 'role': 'agent',
        'target': str(source), 'observationMode': 'runtime_state_transition', 'runtime': guard.PROTOCOL,
        'compile': {'passed': compile_passed, 'command': compile_command, 'scope': 'separate application build supplied by parent'},
        'runtimeCompile': {'passed': None, 'status': 'not_scored', 'scope': 'runtime evaluator packaging only'},
        'semantic': {'passed': 0, 'failed': 0, 'notScored': len(rows), 'total': len(rows), 'cases': rows},
        'publication': {'eligible': False, 'reason': reason},
        'diagnostics': {'modelCalled': False, 'oldDomainFallbackUsed': False,
            'cleanup': {'status': 'not_started_or_unconfirmed', 'binariesRetained': False}}}


def _one_bundle(root, case_id, plan):
    case_root = root / 'captures' / case_id
    report = core.load(case_root / 'runtime.json')
    retained = report['provenance']['strictEvidence']
    evidence = Path(retained['path'])
    manifest = core.load(Path(retained['manifest']))
    artifacts.require(core.sha256(Path(retained['manifest'])) == retained['manifestSha256'], 'Retention manifest changed')
    for item in manifest['files']:
        relative = Path(item['path'])
        artifacts.require(not relative.is_absolute() and '..' not in relative.parts, 'Escaping retained evidence')
        artifacts.bound({**item, 'path': str(evidence / relative)})
    matches = [item for item in report['provenance']['executions'] if item['caseId'] == case_id]
    artifacts.require(len(matches) == 1, 'No own native execution completed')
    execution = evidence / matches[0]['report']
    native_root = execution.parent
    build = evidence / case_id / 'device-build-report.json'
    return {key: artifacts.artifact(path) for key, path in {
        'plan': root / 'plan.json', 'inputs': Path(plan['inputInventory']['path']), 'build': build,
        'execution': execution, 'raw': native_root / 'native-result.json',
        'retention': Path(retained['manifest']), 'aaLog': native_root / 'aa-test.log'}.items()}


def _worker(request_file):
    request = core.load(Path(request_file))
    artifacts.require(os.getpid() == os.getpgrp(), 'Worker must own its new session')
    deadline = child_local_deadline(request['childBudget'])
    root = Path(request['output'])
    status = {'completed': False}
    try:
        plan = core.load(root / 'plan.json')
        # A child receives remaining seconds and an epoch cap, never a parent's
        # Python monotonic value. Its local deadline can only shorten the plan.
        artifacts.require(plan['deadlineEpochMs'] >= request['childBudget']['deadlineEpochMs'], 'Child budget extended plan')
        for case_id in plan['selectedCases']:
            core.require_build_space()
            core.remaining_deadline(deadline, 'Task14 isolated physical case')
            directory = root / 'captures' / case_id
            directory.mkdir(parents=True)
            contract = core.load(packaging.CONTRACT)
            subset = {**contract, 'cases': [row for row in contract['cases'] if row['caseId'] == case_id]}
            core.write(directory / 'contract.json', subset)
            # The canonical lease encloses the complete one-case build/install/
            # original application event/pull/uninstall scope; never foreign locks.
            with lease.task_scope(packaging.TASK, deadline, device_serial=request['deviceSerial']):
                report = lease.score_device(task_id=packaging.TASK, source=Path(plan['source']),
                    output=directory / 'runtime.json', deadline=deadline,
                    contract_path=directory / 'contract.json', build_script=Path(plan['builder']['path']),
                    device_serial=request['deviceSerial'])
            artifacts.require(report.get('runtimeCompile', {}).get('passed') is True,
                              'Runtime packaging incomplete; keep failure logs, not semantic FAIL')
        status['completed'] = True
    except BaseException as error:
        status['error'] = repr(error)
    supervision.atomic_json(Path(request_file).parent / 'worker-finished.json', status)
    # Parent retains the leader PID until it signals this owned process group.
    while time.monotonic() < deadline:
        time.sleep(min(0.05, max(0, deadline - time.monotonic())))


def assemble(root, *, compile_passed=None, compile_command='', profile_key=None):
    root = Path(root)
    plan = core.load(root / 'plan.json')
    contract = core.load(packaging.CONTRACT)
    report = _fallback(plan['source'], compile_passed, compile_command,
        'Full native nine-case/four-control default is not admitted; no host navigation fallback')
    admitted = {}
    errors = {}
    bundles = {}
    integrity = {}
    for case_id in plan['selectedCases']:
        try:
            bundle = _one_bundle(root, case_id, plan)
            bundles[case_id] = bundle
            guard.envelope(bundle, contract)
            integrity[case_id] = True
            admitted[case_id] = guard.admit(bundle, contract, profile_key=profile_key)
        except (OSError, ValueError, KeyError, StopIteration) as error:
            errors[case_id] = repr(error)
    report['semantic']['cases'] = [admitted.get(row['caseId'], row) for row in report['semantic']['cases']]
    for field, value in [('passed', 'pass'), ('failed', 'fail'), ('notScored', 'not_scored')]:
        report['semantic'][field] = sum(row['status'] == value for row in report['semantic']['cases'])
    compile_records = [core.load(root / 'captures' / case_id / 'runtime.json')['runtimeCompile']
        for case_id in plan['selectedCases'] if (root / 'captures' / case_id / 'runtime.json').is_file()]
    report['runtimeCompile'] = {'passed': bool(compile_records) and len(compile_records) == len(plan['selectedCases']) and
        all(item.get('passed') is True for item in compile_records), 'scope': 'selected physical route runtime packaging only',
        'records': compile_records, 'notFullApplicationCompile': True}
    report['provenance'] = {'candidateSource': plan['source'], 'candidateMode': 'standalone_directory',
        'archivedPatchApplied': False, 'candidateRootSha256': core.load(Path(plan['inputInventory']['path']))['rootSha256'],
        'routePlan': artifacts.artifact(root / 'plan.json'), 'routeBundles': bundles,
        'immutableTaskManifest': plan['immutableTaskManifest'], 'implementation': plan['implementation']}
    report['diagnostics'].update(rawAdmissionErrors=errors, oldRowsRelabeled=False,
        fullNineCaseReady=False, routeTransportIntegrity=integrity,
        profilesApproved=list(guard.REVIEWED_PROFILES), profileKey=profile_key)
    return report


def verify_capture(report_path):
    """Default read path rejects unsealed/late captures, even diagnostic ones."""
    report_path = Path(report_path).resolve(strict=True)
    report = json.loads(artifacts.bound(artifacts.artifact(report_path)))
    root = report_path.parent
    seal_path = root.with_name(root.name + '-supervision') / 'admission.json'
    seal = json.loads(artifacts.bound(artifacts.artifact(seal_path)))
    artifacts.require(seal.get('state') == 'complete_diagnostic_only' and seal.get('publicationEligible') is False and
        seal.get('report') == artifacts.artifact(report_path) and seal.get('evaluatorSha256') == packaging.implementation()['sha256'] and
        seal.get('includesHashingSerializationCleanup') is True and seal.get('crossProcessMonotonicTransported') is False and
        0 <= seal['elapsedBeforeSealSeconds'] < seal['timeoutSeconds'] <= 3600,
        'Capture is unsealed/revoked/late or evaluator version changed')
    expected = assemble(root, compile_passed=report['compile']['passed'], compile_command=report['compile']['command'],
                        profile_key=report['diagnostics']['profileKey'])
    artifacts.require(report['semantic'] == expected['semantic'] and report['provenance'] == expected['provenance'] and
        report['runtimeCompile'] == expected['runtimeCompile'] and report['publication']['eligible'] is False,
        'Independent raw guard does not reproduce capture report')
    return {'verifiedDiagnosticOnly': True, 'publicationEligible': False, 'semantic': {
        name: report['semantic'][name] for name in ('passed', 'failed', 'notScored')},
        'report': artifacts.artifact(report_path), 'seal': artifacts.artifact(seal_path)}


def evaluate(*, source, output, timeout=3600, device_serial=None, case_ids=None,
             compile_passed=None, compile_command='', profile_key=None, execute=False):
    artifacts.require(execute is True, 'No hardware by default; explicit release/execute required')
    process = None
    root = Path(output).absolute()
    scope = root.with_name(root.name + '-supervision')
    clock = OverallDeadline(timeout)
    owns = False
    report = _fallback(source, compile_passed, compile_command, 'End-to-end route admission incomplete; not semantic failure')
    try:
        with clock:
            artifacts.require(not root.exists() and not scope.exists(), 'Never overwrite raw or old model reports')
            root = packaging.snapshot.canonical_output(root)
            scope.mkdir(parents=True)
            owns = True
            supervision.atomic_json(scope / 'revoked.json', {'state': 'revoked', 'publicationEligible': False})
            supervision.atomic_json(scope / 'admission.json', {'state': 'pending', 'publicationEligible': False})
            supervision.atomic_json(scope / 'fallback.json', report)
            packaging.prepare(source=source, output=root, deadline=clock.work_deadline, case_ids=case_ids)
            temporary = scope / 'work-tmp'
            temporary.mkdir()
            request = {'output': str(root), 'deviceSerial': device_serial,
                'childBudget': clock.child_budget(reserve=min(120, timeout * 0.15))}
            supervision.atomic_json(scope / 'request.json', request)
            with (scope / 'worker.log').open('w') as stream:
                process = subprocess.Popen([sys.executable, '-B', '-m',
                    'scripts.runtime_semantics.task14_actual_routes_scorer_v4', '--worker', str(scope / 'request.json')],
                    cwd=packaging.ROOT, stdout=stream, stderr=subprocess.STDOUT, start_new_session=True,
                    env={**os.environ, 'TMPDIR': str(temporary)})
                deadline = child_local_deadline(request['childBudget'])
                while not (scope / 'worker-finished.json').exists():
                    clock.check_work()
                    left = deadline - time.monotonic()
                    if left <= 0:
                        raise TimeoutError('Route worker exceeded remaining child budget')
                    time.sleep(min(0.02, left))
            stopped = supervision.stop_owned(process, clock.deadline)
            artifacts.require(stopped.get('leaderReaped') is True and stopped.get('groupGone') is True,
                              'Owned worker/children not confirmed stopped')
            temporary_cleanup = supervision._cleanup_temporary(root, scope)
            report = assemble(root, compile_passed=compile_passed, compile_command=compile_command, profile_key=profile_key)
            report['diagnostics']['cleanup'] = {'ownedProcesses': stopped, 'temporary': temporary_cleanup,
                'binariesRetained': False, 'deviceConfirmation': 'per-execution raw cleanup; never inferred from local deletion'}
            clock.check_work()
            supervision.atomic_json(root / 'report.json', report)
            seal = {'state': 'complete_diagnostic_only', 'publicationEligible': False,
                'report': artifacts.artifact(root / 'report.json'), 'evaluatorSha256': packaging.implementation()['sha256'],
                'completedAtEpochMs': int(time.time() * 1000), 'timeoutSeconds': timeout,
                'elapsedBeforeSealSeconds': time.monotonic() - clock.started,
                'includesHashingSerializationCleanup': True, 'crossProcessMonotonicTransported': False}
            supervision.atomic_json(scope / 'admission.json', seal)
            clock.check_work()
    except BaseException as error:
        if process is not None:
            if clock.hard_expired:
                supervision._signal_owned_group(process, signal.SIGKILL)
                process.poll()
            else:
                supervision.stop_owned(process, clock.deadline)
        if owns:
            if (scope / 'revoked.json').exists():
                os.replace(scope / 'revoked.json', scope / 'admission.json')
            if (scope / 'fallback.json').exists() and root.exists():
                target = root / 'report.json'
                if target.exists():
                    os.replace(target, root / 'report.unadmitted.json')
                os.replace(scope / 'fallback.json', target)
        if not clock.hard_expired and owns:
            # Hash-owned temporary inputs before deletion. Device cleanup is
            # unknown on interruption, never synthesized as successful.
            try:
                supervision._cleanup_temporary(root, scope)
            except Exception:
                pass
        if not isinstance(error, (WorkDeadlineExpired, HardDeadlineExpired, Exception)):
            raise
        report = _fallback(source, compile_passed, compile_command, repr(error))
    return report


def score(*, platform, source, base_source, final_source, output, compile_passed,
          compile_command, timeout=3600, device_serial=None):
    """Drop-in candidate-only API, fail-closed until actual nine-case controls.

    Kept unregistered. It never revives the withdrawn mixed-tier default and
    never implicitly starts hardware before an explicit release.
    """
    artifacts.require(platform == 'arkts', 'This successor does not change Android scoring')
    clock = OverallDeadline(timeout)
    with clock:
        report = _fallback(Path(source).resolve(), compile_passed, compile_command,
            'Task14 actual-route default requires reviewed native profiles and matched complete four controls; not ready')
        report['diagnostics'].update(baseCalibrationSource=str(base_source), finalCalibrationSource=str(final_source),
            deviceSerial=device_serial, timeoutSeconds=timeout, hardwareStarted=False)
        output = packaging.snapshot.canonical_output(output)
        artifacts.require(not output.exists(), 'No original report overwrite')
        output.parent.mkdir(parents=True, exist_ok=True)
        supervision.atomic_json(output, report)
        clock.check_work()
        return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--case', action='append', choices=sorted(packaging.CASES))
    parser.add_argument('--prepare-only', action='store_true')
    parser.add_argument('--execute-capture', action='store_true')
    parser.add_argument('--timeout-seconds', type=float, default=3600)
    parser.add_argument('--device-serial')
    parser.add_argument('--worker', type=Path, help=argparse.SUPPRESS)
    parser.add_argument('--verify-capture', type=Path, help='offline independent default guard for a completed diagnostic capture')
    args = parser.parse_args()
    if args.worker:
        return _worker(args.worker)
    if args.verify_capture:
        print(json.dumps(verify_capture(args.verify_capture), indent=2))
        return
    artifacts.require(args.source and args.output, '--source and --output required')
    if args.prepare_only and not args.execute_capture:
        value = packaging.prepare(source=args.source, output=args.output,
            deadline=time.monotonic() + args.timeout_seconds, case_ids=args.case)
    elif args.execute_capture and not args.prepare_only:
        value = evaluate(source=args.source, output=args.output, timeout=args.timeout_seconds,
            device_serial=args.device_serial, case_ids=args.case, execute=True)
    else:
        parser.error('Choose offline --prepare-only or explicit release-gated --execute-capture')
    print(json.dumps({'output': str(args.output), 'ready': False,
        'deviceStarted': bool(args.execute_capture), 'semantic': value.get('semantic', {}).get('notScored')}))


if __name__ == '__main__':
    main()
