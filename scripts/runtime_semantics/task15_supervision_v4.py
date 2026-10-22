"""Task15-only end-to-end admission; no shared timers, source edits or devices at import.

The main-thread parent owns one timer and one new worker process group. Worker
clock values never cross process boundaries. Unsealed/late results are not
admissible, even if the worker wrote a locally successful report.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import signal
import shutil
import subprocess
import sys
import time
import traceback

from .task15_deadline_v4 import (OverallDeadline, WorkDeadlineExpired,
    HardDeadlineExpired, child_local_deadline)

WORKER_REGISTRY = None
WORKER_GROUP = None


class WorkerCommandExpired(BaseException):
    pass


def atomic_json(path, value):
    path = Path(path)
    temporary = path.with_name(path.name + '.pending')
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=True) + '\n')
    os.replace(temporary, path)


def _signal_owned_group(process, sig):
    # Only groups created here with start_new_session=True are ever signaled.
    if process.returncode is not None:
        return
    try:
        os.killpg(process.pid, sig)
    except ProcessLookupError:
        pass
    except PermissionError:
        # Darwin can return EPERM for a group containing only an unreaped
        # zombie. Do not infer success: stop_owned must still reap/check it.
        return False
    return True


def stop_owned(process, hard_deadline):
    """No unbounded communicate/wait, including after SIGKILL."""
    if process is None:
        return {'started': False, 'status': 'not_started'}
    if process.returncode is not None:
        return {'started': True, 'pid': process.pid, 'leaderReaped': True,
                'groupGone': False, 'status': 'already_reaped_no_further_group_signals'}
    # Do not reap the session leader until BOTH signals are sent: its reserved
    # PID prevents group-ID reuse while terminating owned descendants.
    _signal_owned_group(process, signal.SIGTERM)
    remaining = hard_deadline - time.monotonic()
    if remaining > 0:
        time.sleep(min(0.01, remaining))
    _signal_owned_group(process, signal.SIGKILL)
    remaining = hard_deadline - time.monotonic()
    if remaining > 0:
        try:
            process.wait(timeout=min(0.2, remaining))
        except subprocess.TimeoutExpired:
            pass
    try:
        os.killpg(process.pid, 0)
        group_gone = False
    except ProcessLookupError:
        group_gone = True
    except PermissionError:
        group_gone = False
    return {'started': True, 'pid': process.pid, 'ownedGroup': process.pid,
        'leaderReaped': process.returncode is not None, 'groupGone': group_gone,
        'boundedByOriginalHardDeadline': True, 'foreignProcessesSignaled': False}


def command(argv, *, log, deadline, lease_serial=None):
    """Inside a worker, all children stay in its owned session for outer revocation."""
    from . import task15_full_report_v4 as full
    remaining = full.core.remaining_deadline(deadline, 'own command')
    started = time.time()
    log = Path(log)
    in_worker = WORKER_GROUP is not None
    if in_worker and os.getpgrp() != WORKER_GROUP:
        raise ValueError('Worker process-group ownership changed')
    with log.open('w') as stream:
        process = subprocess.Popen(argv, cwd=full.ROOT, stdout=stream, stderr=subprocess.STDOUT,
                                   start_new_session=not in_worker)
        if in_worker:
            with Path(WORKER_REGISTRY).open('a') as registry:
                registry.write(json.dumps({'pid': process.pid, 'pgid': WORKER_GROUP}) + '\n')
        timed_out = False
        try:
            process.wait(timeout=remaining)
        except subprocess.TimeoutExpired:
            timed_out = True
            if in_worker:
                # Abort the whole worker. Its supervisor owns descendant termination.
                process.kill()
            else:
                stop_owned(process, deadline)
        value = {'command': argv, 'pid': process.pid, 'exit': process.poll(), 'timedOut': timed_out,
            'startedAtEpochMs': int(started * 1000), 'finishedAtEpochMs': int(time.time() * 1000),
            'processGroup': WORKER_GROUP if in_worker else process.pid,
            'monotonicClockScope': 'current Python process only'}
    value['log'] = full.raw.artifacts.artifact(log)
    full.core.write(log.with_suffix('.command.json'), value)
    if timed_out and in_worker:
        raise WorkerCommandExpired('Worker command timed out; outer group must stop')
    return value


def worker_main(request_path):
    from . import task15_full_report_v4 as full
    global WORKER_GROUP, WORKER_REGISTRY
    request = full.core.load(Path(request_path))
    if os.getpgrp() != os.getpid():
        raise ValueError('Worker must be a newly owned session leader')
    WORKER_GROUP = os.getpid()
    WORKER_REGISTRY = request['registry']
    deadline = child_local_deadline(request['childBudget'])
    remaining = deadline - time.monotonic()
    arguments = request['arguments']
    status = {'completed': False}
    try:
        if request['mode'] == 'candidate':
            full._evaluate_worker(output=Path(request['output']), timeout=remaining, deadline=deadline, **arguments)
        elif request['mode'] == 'controls':
            full._run_four_controls_worker(output=Path(request['output']), timeout=remaining, deadline=deadline,
                **{key: Path(value) if key.endswith('_source') else value for key, value in arguments.items()})
        elif request['mode'] == 'assemble':
            Path(request['output']).mkdir(parents=True)
            full.assemble(arguments['index'], output=Path(request['output']) / 'report.json')
        else:
            raise ValueError('Unknown private worker mode')
        status['completed'] = True
    except BaseException as error:
        status['error'] = repr(error)
        traceback.print_exc()
    atomic_json(Path(request_path).parent / 'worker-finished.json', status)
    # Hold the unreaped session leader until the parent kills its owned group.
    # This wait is bounded by the original child budget, not a fresh timer.
    while time.monotonic() < deadline:
        time.sleep(min(0.05, max(0, deadline - time.monotonic())))


def _timeout_report(arguments):
    from . import task15_full_report_v4 as full
    contract = full.core.load(full.native.CONTRACT)
    rows = full.core.unavailable_rows(contract, 'End-to-end scoring deadline/admission incomplete; not semantic failure')
    return {'schemaVersion': 4, 'taskId': full.TASK, 'platform': 'arkts', 'role': 'agent',
        'observationMode': 'runtime_state_transition', 'runtime': full.PROTOCOL,
        'compile': {'passed': arguments.get('compile_passed'), 'command': arguments.get('compile_command', ''),
            'evidence': arguments.get('compile_evidence'),
            'scope': 'separate application compile evidence preserved; not a new compile verdict'},
        'runtimeCompile': {'passed': None, 'status': 'not_scored', 'scope': 'unfinished evaluator admission'},
        'semantic': {'passed': 0, 'failed': 0, 'notScored': len(rows), 'total': len(rows), 'cases': rows},
        'diagnostics': {'adapter': 'incomplete', 'transport': 'incomplete', 'publicationEligible': False,
            'environmentFailureIsNotSemanticFailure': True, 'originalModelMetricsChanged': False,
            'cleanup': {'status': 'incomplete_or_not_started', 'completionNotAssumed': True}}}


def _remove_owned_dead_lease(serial, worker_pid, registry):
    if not serial or worker_pid is None:
        return {'status': 'not_started_or_serial_unknown'}
    lock = Path('/tmp') / ('ltb-arkts-device-' + hashlib.sha256(serial.encode()).hexdigest()[:16])
    owner_file = lock / 'owner.json'
    if not owner_file.is_file() or owner_file.is_symlink() or lock.is_symlink():
        return {'status': 'no_owned_lease_observed'}
    before = owner_file.read_bytes()
    owner = json.loads(before)
    children = set()
    if registry.is_file():
        for line in registry.read_text().splitlines():
            item = json.loads(line)
            if item['pgid'] == worker_pid:
                children.add(item['pid'])
    is_worker = owner.get('pid') == worker_pid and owner.get('taskId') == '15_account_deactivation'
    is_child = owner.get('pid') in children and owner.get('token') == 'task15-' + str(owner.get('pid'))
    if owner.get('serial') != serial or not (is_worker or is_child):
        return {'status': 'foreign_or_unproven_lease_untouched'}
    try:
        os.kill(owner['pid'], 0)
        return {'status': 'owner_still_alive_untouched'}
    except ProcessLookupError:
        if owner_file.read_bytes() != before:
            return {'status': 'ownership_changed_untouched'}
        owner_file.unlink()
        lock.rmdir()
        return {'status': 'proven_owned_dead_lease_removed', 'owner': owner}


def _cleanup_temporary(root, scope):
    """Hash only owned temporary trees, never follow cache symlinks."""
    from . import task15_full_report_v4 as full
    records = []
    for directory in (scope / 'work-tmp', root / 'sources'):
        if not directory.exists():
            continue
        for path in sorted(directory.rglob('*')):
            if path.is_symlink():
                records.append({'path': str(path), 'symlinkTarget': os.readlink(path), 'followed': False})
            elif path.is_file():
                record = full.raw.artifacts.artifact(path)
                if path.suffix in ('.log', '.txt'):
                    retained = scope / 'retained-recovery-text' / path.relative_to(directory.parent)
                    retained.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(path, retained)
                    record['retainedText'] = full.raw.artifacts.artifact(retained)
                records.append(record)
        # Receipt is durable before removal. Interruption never claims removal completed.
        atomic_json(scope / 'temporary-cleanup.pending.json', {'files': records, 'removed': False})
        shutil.rmtree(directory)
    value = {'files': records, 'removed': True, 'hashesRecordedBeforeRemoval': True,
             'scope': 'worker-private TMPDIR and this group source copies only', 'binariesRetained': False}
    atomic_json(scope / 'temporary-cleanup.json', value)
    return full.raw.artifacts.artifact(scope / 'temporary-cleanup.json')


def _finalize(mode, output, scope, clock, process_cleanup, temporary_cleanup):
    from . import task15_full_report_v4 as full
    from . import task15_full_report_verify_v4 as guard
    clock.check_work()
    group = full.core.load(output / 'four-controls.json') if mode == 'controls' else None
    if group is not None:
        full.raw.require(group['status'] == 'passed', 'Four-control worker not ready')
        paths = {pole: Path(reference['path']) for pole, reference in group['reports'].items()}
    else:
        paths = {'candidate': output / 'report.json'}
    files, receipts = [], {}
    for pole, path in paths.items():
        clock.check_work()
        full.raw.require(path.is_relative_to(output) and not path.is_symlink(), 'Escaping result path')
        report = full.core.load(path)
        report['diagnostics']['deadlineAdmissionPath'] = str(scope / 'admission.json')
        report['diagnostics']['endToEndDeadline'] = {
            'timeoutSeconds': clock.timeout, 'clockScope': 'supervisor process only',
            'includesPreparationWaitingHashingPublicVerificationSerializationAndCleanup': True}
        atomic_json(path, report)
        receipt = guard._verify_report_unsealed(path)
        atomic_json(path.with_suffix('.verified.json'), receipt)
        receipts[pole] = receipt
        files += [full.raw.artifacts.artifact(path), full.raw.artifacts.artifact(path.with_suffix('.verified.json'))]
    if group is not None:
        group['reports'] = {pole: full.raw.artifacts.artifact(path) for pole, path in paths.items()}
        group['verification'] = guard._verify_controls_unsealed(group['reports'],
            evaluator_sha=group['evaluator']['sha256'])
        group['workerElapsedSeconds'] = group.pop('elapsedSecondsOverall', None)
        group['overallTimeoutSeconds'] = clock.timeout
        group['elapsedSecondsBeforeGroupSerialization'] = time.monotonic() - clock.started
        atomic_json(output / 'four-controls.json', group)
        files.append(full.raw.artifacts.artifact(output / 'four-controls.json'))
    clock.check_work()
    seal = {'schemaVersion': 4, 'state': 'complete', 'output': str(output), 'mode': mode,
        'publicationEligible': all(value['publicationEligible'] for value in receipts.values()),
        'evaluatorSha256': full.implementation()['sha256'], 'files': files,
        'ownedProcessCleanup': process_cleanup, 'timeoutSeconds': clock.timeout,
        'temporaryCleanup': temporary_cleanup,
        'elapsedSecondsBeforeAdmissionCommit': time.monotonic() - clock.started,
        'completedAtEpochMs': int(time.time() * 1000),
        'allRawAndPublicVerificationBeforeSeal': True,
        'cleanupAndSerializationBeforeSeal': True, 'crossProcessMonotonicTransported': False,
        'postAtomicCommitDeadlineCheckRequired': True,
        'elapsedSampleExcludesOwnSealWriteButTimerCoversIt': True}
    atomic_json(scope / 'admission.json', seal)
    clock.check_work()
    return group if group is not None else full.core.load(output / 'report.json')


def verify_admission(path):
    from . import task15_full_report_v4 as full
    path = Path(path).resolve(strict=True)
    report = full.core.load(path)
    seal_path = full.native.canonical_output(Path(report['diagnostics']['deadlineAdmissionPath']))
    full.raw.require(seal_path.name == 'admission.json' and not seal_path.is_symlink(), 'Wrong deadline admission path')
    seal = full.core.load(seal_path)
    root = Path(seal['output'])
    full.raw.require(seal_path.parent == root.with_name(root.name + '-supervision') and path.is_relative_to(root),
                     'Admission belongs to a different isolated evaluation')
    full.raw.require(seal.get('state') == 'complete' and seal.get('allRawAndPublicVerificationBeforeSeal') is True and
        seal.get('cleanupAndSerializationBeforeSeal') is True and seal.get('crossProcessMonotonicTransported') is False,
        'End-to-end deadline admission absent/revoked/incomplete')
    full.raw.require(0 <= seal['elapsedSecondsBeforeAdmissionCommit'] < seal['timeoutSeconds'] <= 3600 and
        seal.get('postAtomicCommitDeadlineCheckRequired') is True and
        seal.get('elapsedSampleExcludesOwnSealWriteButTimerCoversIt') is True and
        seal['evaluatorSha256'] == full.implementation()['sha256'], 'Late/mixed deadline admission')
    full.raw.require(seal['ownedProcessCleanup'].get('leaderReaped') is True and
        seal['ownedProcessCleanup'].get('groupGone') is True, 'Owned processes not confirmed stopped')
    cleanup = seal['temporaryCleanup']
    full.raw.require(Path(cleanup['path']) == seal_path.parent / 'temporary-cleanup.json', 'Wrong cleanup manifest')
    full.raw.artifacts.bound(cleanup)
    full.raw.require(full.core.load(Path(cleanup['path'])).get('removed') is True, 'Temporary cleanup incomplete')
    matches = [item for item in seal['files'] if Path(item['path']) == path]
    full.raw.require(len(matches) == 1, 'Report not included in end-to-end admission')
    for record in seal['files']:
        full.raw.require(Path(record['path']).is_relative_to(root), 'Escaping admitted artifact')
        full.raw.artifacts.bound(record)
    return seal


def supervise(*, mode, output, timeout=3600, deadline=None, arguments=None):
    """One main-thread budget, including worker launch, verification, hashing and commit."""
    from . import task15_full_report_v4 as full
    arguments = arguments or {}
    if type(timeout) not in (float, int) or not math.isfinite(timeout) or not 0 < timeout <= 3600:
        raise ValueError('One 0 < timeout <= 3600 budget required')
    if deadline is not None:
        timeout = min(timeout, deadline - time.monotonic())
    process = None
    scope = None
    fallback = None
    fallback_filename = 'four-controls.json' if mode == 'controls' else 'report.json'
    result = None
    owns_scope = False
    clock = OverallDeadline(timeout)
    try:
        with clock:
            output = full.native.canonical_output(output)
            scope = output.with_name(output.name + '-supervision')
            full.raw.require(not output.exists() and not scope.exists(), 'Never overwrite an evaluation or admission')
            scope.mkdir(parents=True)
            owns_scope = True
            fallback = _timeout_report(arguments)
            if mode == 'controls':
                fallback = {'protocol': full.PROTOCOL, 'status': 'not_ready', 'reports': {},
                    'reason': 'End-to-end four-control deadline/admission incomplete',
                    'semanticReportsAdmitted': False, 'partialRawReportsPreserved': True,
                    'originalModelMetricsChanged': False, 'modelCalled': False}
            atomic_json(scope / 'deadline-report.json', fallback)
            atomic_json(scope / 'revoked.json', {'state': 'revoked', 'publicationEligible': False,
                'cleanup': 'not confirmed complete; inspect retained partial artifacts',
                'reason': 'end-to-end evaluation not admitted', 'timeoutSeconds': timeout})
            atomic_json(scope / 'admission.json', {'state': 'pending', 'publicationEligible': False})
            registry = scope / 'owned-processes.jsonl'
            registry.touch()
            request = {'mode': mode, 'output': str(output), 'arguments': arguments, 'registry': str(registry),
                'childBudget': clock.child_budget(reserve=min(120, timeout * 0.15))}
            atomic_json(scope / 'request.json', request)
            temporary = scope / 'work-tmp'
            temporary.mkdir()
            try:
                with (scope / 'worker.log').open('w') as log:
                    process = subprocess.Popen([sys.executable, '-B', '-m',
                        'scripts.runtime_semantics.task15_full_report_v4', '--worker', str(scope / 'request.json'),
                        '--output', str(output)], cwd=full.ROOT, stdout=log, stderr=subprocess.STDOUT,
                        env={**os.environ, 'TMPDIR': str(temporary)}, start_new_session=True)
                    # A child gets remaining seconds + epoch, never this process's monotonic reading.
                    child_limit = child_local_deadline(request['childBudget'])
                    finished = scope / 'worker-finished.json'
                    while not finished.exists():
                        left = child_limit - time.monotonic()
                        if left <= 0:
                            raise subprocess.TimeoutExpired(process.args, request['childBudget']['remainingSeconds'])
                        time.sleep(min(0.01, left))
                    worker_status = full.core.load(finished)
                stopped = stop_owned(process, clock.deadline)
                full.raw.require(worker_status.get('completed') is True and stopped['leaderReaped'] and stopped['groupGone'],
                                 'Worker failed or owned descendants not confirmed stopped')
                temporary_cleanup = _cleanup_temporary(output, scope)
                result = _finalize(mode, output, scope, clock, stopped, temporary_cleanup)
            except (WorkDeadlineExpired, WorkerCommandExpired, subprocess.TimeoutExpired, Exception) as error:
                # Revocation precedes any potentially slow cleanup. No semantic failure is invented.
                os.replace(scope / 'revoked.json', scope / 'admission.json')
                stopped = stop_owned(process, clock.deadline)
                cleanup = {'ownedProcesses': stopped, 'localFilesCleanupCompleted': False,
                    'deviceCleanupConfirmation': 'unknown_or_not_started; never inferred from file deletion'}
                try:
                    cleanup['lease'] = _remove_owned_dead_lease(arguments.get('device_serial'),
                        process.pid if process else None, registry)
                    if output.exists():
                        full._cleanup_orphans(output)
                    _cleanup_temporary(output, scope)
                    cleanup['localFilesCleanupCompleted'] = True
                except Exception as cleanup_error:
                    cleanup['error'] = repr(cleanup_error)
                if not output.exists():
                    output.mkdir(parents=True)
                if output.exists():
                    target = output / fallback_filename
                    if target.exists():
                        os.replace(target, target.with_name(target.stem + '.unadmitted.json'))
                    os.replace(scope / 'deadline-report.json', target)
                atomic_json(scope / 'failure.json', {'error': repr(error), 'cleanup': cleanup,
                    'elapsedSeconds': time.monotonic() - clock.started,
                    'publicationEligible': False, 'compileVerdictUnchanged': True})
                result = fallback
    except BaseException as error:
        # After the hard boundary: no hashes, waits, recursive cleanup or new timer.
        if process is not None:
            _signal_owned_group(process, signal.SIGKILL)
            process.poll()  # WNOHANG only; no fresh wait/cleanup budget after hard expiry.
        if owns_scope and (scope / 'revoked.json').exists():
            os.replace(scope / 'revoked.json', scope / 'admission.json')
        if owns_scope and (scope / 'deadline-report.json').exists() and output.exists():
            target = output / fallback_filename
            if target.exists():
                os.replace(target, target.with_name(target.stem + '.unadmitted.json'))
            os.replace(scope / 'deadline-report.json', target)
        result = fallback
        if not isinstance(error, (HardDeadlineExpired, WorkDeadlineExpired)):
            raise
    return result
