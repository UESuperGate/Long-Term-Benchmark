"""Task12 merged successor with parent-owned hard deadline and unreaped PID pins.

Unregistered/offline review only. The frozen v1 orchestrator is never executed.
The reviewed Task15 clock is reused read-only, as in controller v3.
"""

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tarfile
import time
import uuid

from . import task15_deadline_v4 as timer
from . import task12_arkts_merged_protocol_v4 as proof
from . import task12_arkts_merged_runtime_v4 as retained_owner
from . import task12_13_runtime_support as support

SCHEMA = 'task12.merged-supervisor.v1'
MODULE = 'scripts.runtime_semantics.task12_arkts_merged_runtime_v4'
NODE = '/Applications/DevEco-Studio.app/Contents/tools/node/bin/node'
PUBLIC_SHA = '25525fe1713d3194bbd8c2bf694800967b54fb4e5acf318e763dba82bfa4c7cc'
WITHDRAWN_SHA = '16f259d2a6f737180a84775fe8447c5b66f0c9a3bf89f484d9cde73594a4954f'
SDK_BOUNDARY_SHA = 'ffeb9493a29b52218e86a8addbb5ea9fd283439622d08e96b23983229b65e54a'
_RETAINED_CLAIMS = retained_owner._RETAINED_CLAIMS


class UnsafeOwnership(RuntimeError):
    pass


def atomic(path, value):
    path = Path(path)
    pending = path.with_name(path.name + '.pending')
    with pending.open('w') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')
    os.replace(pending, path)


def reap_nonblocking(process):
    # A pending alarm must not see waitpid-completed with returncode still None.
    previous = signal.pthread_sigmask(signal.SIG_BLOCK, [signal.SIGALRM])
    try:
        try:
            process.wait(timeout=0)
        except subprocess.TimeoutExpired:
            pass
    finally:
        signal.pthread_sigmask(signal.SIG_SETMASK, previous)


def wait_leader(process, deadline):
    while process.returncode is None:
        reap_nonblocking(process)
        if process.returncode is not None:
            return
        left = deadline - time.monotonic()
        if left <= 0:
            raise subprocess.TimeoutExpired(process.args, 0)
        time.sleep(min(.01, left))


def signal_unreaped(process):
    if process is None or process.returncode is not None:
        return False
    # No wait/poll/reap between either send: the unreaped leader pins the PGID.
    errors = []
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(process.pid, sig)
        except ProcessLookupError:
            pass
        except OSError as error:
            errors.append({'signal': int(sig), 'errno': error.errno, 'error': str(error)})
    return {'attempted': True, 'errors': errors}


def stop_group(process, deadline):
    if process is None:
        return {'started': False, 'leaderReaped': True, 'groupGone': True, 'unsafe': False}
    sent = signal_unreaped(process)
    if sent:
        try:
            wait_leader(process, deadline)
        except subprocess.TimeoutExpired:
            pass
    query_error = None
    try:
        os.killpg(process.pid, 0)  # A reaped numeric PGID is ONLY queried, never signaled.
        gone = False
    except ProcessLookupError:
        gone = True
    except OSError as error:
        gone = False
        query_error = {'errno': error.errno, 'error': str(error)}
    errors = sent['errors'] if sent else []
    return {'started': True, 'pid': process.pid, 'pgid': process.pid,
            'leaderReaped': process.returncode is not None, 'groupGone': gone,
            'signalsWhileUnreaped': bool(sent), 'signalErrors': errors, 'queryError': query_error,
            'unsafe': bool(errors or query_error or not gone or process.returncode is None)}


def _supervise(output, deadline, prepare, command, finalize, *, acquire=None, cleanup=None, release=None,
               report_path=None, precheck=None, failure_template=None, failure_update=None, commit_result=None):
    """One hard-timed envelope for preparation, work, raw validation and finalization."""
    left = deadline - time.monotonic()
    if not math.isfinite(left) or not 0 < left <= 3600:
        raise ValueError('Task12 requires 0 < original remaining deadline <= 3600')
    clock = timer.OverallDeadline(left)
    clock.deadline = min(clock.deadline, deadline)  # Never extend an existing caller budget.
    clock.work_deadline = clock.deadline - clock.reserve
    process = None
    claim = None
    entered = False
    result = None
    root = None
    revoked = None
    admission = None
    cleanup_attempted = False
    cleanup_value = None
    tracking = None

    def revoke():
        if revoked is not None and revoked.exists():
            os.replace(revoked, admission)

    def stop_or_retain():
        status = stop_group(process, clock.deadline)
        if tracking is not None:
            tracking['status'] = status
        if status['unsafe']:
            atomic(root / 'unsafe-process-ownership.json', {**status, 'inputsAndLeaseRetained': True,
                   'semanticFailureInferred': False, 'numericPgidAfterReapNotOwned': True})
            raise UnsafeOwnership('Process group is not safely owned after reap; retain inputs/lease')
        return status

    def clean_once():
        nonlocal cleanup_attempted, cleanup_value
        if cleanup_attempted:
            return cleanup_value if cleanup_value is not None else {'complete': False, 'reason': 'previous cleanup interrupted; never recursively retry'}
        cleanup_attempted = True
        cleanup_value = cleanup(root, clock) if cleanup else {'complete': True, 'nothingOwned': True}
        return cleanup_value

    def launch(argv, label, *, environment=None):
        nonlocal process, tracking
        clock.check_work()
        with (root / (label + '.log')).open('x') as log:
            process = subprocess.Popen(argv, cwd=proof.ROOT, stdout=log, stderr=subprocess.STDOUT,
                                       env=environment, start_new_session=True)
            tracking = {'pid': process.pid, 'label': label, 'command': argv, 'status': None}
            if isinstance(claim, dict):
                claim.setdefault('workers', []).append(tracking)
            atomic(root / (label + '.launch.json'), {'pid': process.pid, 'pgid': process.pid,
                   'command': argv, 'parentPid': os.getpid(), 'parentStarted': time.monotonic(),
                   'remainingSeconds': clock.work_deadline - time.monotonic()})
            wait_leader(process, clock.work_deadline)
        status = stop_or_retain()
        atomic(root / (label + '.process.json'), status)
        if process.returncode:
            raise RuntimeError('Owned worker exited ' + str(process.returncode) + ': ' + label)
        clock.check_work()
        return status

    try:
        with clock:
            entered = True
            root = Path(output).resolve()
            if precheck:
                precheck(root, clock)
            if root.exists():
                raise ValueError('Never overwrite a controller run')
            root.mkdir(parents=True)
            revoked = root / 'revocation-ready.json'
            admission = Path(report_path).resolve() if report_path else root / 'report.json'
            if admission.exists():
                raise ValueError('Never overwrite an existing scorable envelope')
            admission.parent.mkdir(parents=True, exist_ok=True)
            unavailable = {'schemaVersion': SCHEMA, 'state': 'revoked', 'status': 'not_scored',
                   'semantic': {'passed': 0, 'failed': 0, 'notScored': 10}, 'publicationEligible': False,
                   'reason': 'Original overall budget or complete source-bound proof not satisfied'}
            if failure_template:
                unavailable.update(failure_template(root, clock))
            atomic(revoked, unavailable)
            atomic(admission, {'schemaVersion': SCHEMA, 'state': 'pending', 'publicationEligible': False})
            try:
                request = prepare(root, clock)
                request['requestId'] = request.get('requestId', uuid.uuid4().hex)
                clock.check_work()
                if acquire:
                    claim = acquire(root, clock, request)
                request['childBudget'] = clock.child_budget(reserve=min(30, left * .1))
                atomic(root / 'request.json', request)
                launch(command(root / 'request.json'), 'worker',
                       environment={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})
                clock.check_work()
                result = finalize(root, request, clock, launch)
                clock.check_work()
                cleaned = clean_once()
                if cleaned.get('complete') is not True:
                    raise RuntimeError('Owned hash-cleanup incomplete')
                clock.check_work()
                released = release(claim, root, clock) if release else {'released': claim is None}
                if not released.get('released'):
                    raise RuntimeError('Owned resources retained; remote cleanup unconfirmed')
                claim = None
                clock.check_work()
                if commit_result:
                    result = commit_result(root, request, clock, result, cleaned, released)
                clock.check_work()
                envelope = {'schemaVersion': SCHEMA, 'state': 'complete', 'publicationEligible': False,
                            'diagnosticOnly': True, 'result': result, 'ownedCleanup': cleaned, 'resources': released,
                            'requestId': request['requestId'], 'allFinalizationInsideOriginalBudget': True,
                            'timeoutSeconds': left, 'elapsedSeconds': time.monotonic() - clock.started}
                atomic(root / 'completion.json', envelope)
                clock.check_work()
                atomic(admission, envelope)
                clock.check_work()
            except (timer.WorkDeadlineExpired, subprocess.TimeoutExpired, Exception) as error:
                revoke()  # FIRST action, before signaling, cleanup, hashing or another write.
                if isinstance(error, (UnsafeOwnership, timer.DeadlineOwnershipError)):
                    raise
                claim = claim or _RETAINED_CLAIMS.get(str(root))
                stopped = stop_or_retain()
                if failure_update:
                    revised = failure_update(root, clock)
                    if revised is not None:
                        assert revised['semantic']['passed'] == revised['semantic']['failed'] == 0 and revised['semantic']['notScored'] == 10
                        assert revised['publication']['eligible'] is False
                        atomic(admission, revised)
                cleaned = clean_once()
                released = release(claim, root, clock) if release else {'released': claim is None}
                atomic(root / 'failure.json', {'error': repr(error), 'ownedProcesses': stopped,
                       'cleanup': cleaned, 'resources': released, 'semanticFailureInferred': False})
                result = None
    except (timer.HardDeadlineExpired, timer.WorkDeadlineExpired, timer.DeadlineOwnershipError, UnsafeOwnership):
        if not entered:
            raise
        revoke()  # Atomic revocation precedes ALL post-hard best-effort process operations.
        if signal_unreaped(process):
            reap_nonblocking(process)
        # No restarted timer, waiting loop, recursive cleanup, hashing, or JSON write here.
        result = None
    return result
