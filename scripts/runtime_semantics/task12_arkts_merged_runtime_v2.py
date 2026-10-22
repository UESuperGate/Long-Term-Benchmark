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
from . import task12_arkts_merged_protocol_v1 as proof
from . import task12_13_runtime_support as support

SCHEMA = 'task12.merged-controller.v2'
MODULE = 'scripts.runtime_semantics.task12_arkts_merged_runtime_v2'
NODE = '/Applications/DevEco-Studio.app/Contents/tools/node/bin/node'
PUBLIC_SHA = '6ceed2ee265a4eaeb59f13f4c8a4befbbc27f5c04cd2b9277cff0ab2f0a9d626'
WITHDRAWN_SHA = '16f259d2a6f737180a84775fe8447c5b66f0c9a3bf89f484d9cde73594a4954f'
SDK_BOUNDARY_SHA = 'ffeb9493a29b52218e86a8addbb5ea9fd283439622d08e96b23983229b65e54a'
_RETAINED_CLAIMS = {}


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
               report_path=None, precheck=None):
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
        nonlocal cleanup_attempted
        if cleanup_attempted:
            return {'complete': False, 'reason': 'previous cleanup interrupted; never recursively retry'}
        cleanup_attempted = True
        return cleanup(root, clock) if cleanup else {'complete': True, 'nothingOwned': True}

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
            atomic(revoked, {'schemaVersion': SCHEMA, 'state': 'revoked', 'status': 'not_scored',
                   'semantic': {'passed': 0, 'failed': 0, 'notScored': 10}, 'publicationEligible': False,
                   'reason': 'Original overall budget or complete source-bound proof not satisfied'})
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
                envelope = {'schemaVersion': SCHEMA, 'state': 'complete', 'publicationEligible': False,
                            'diagnosticOnly': True, 'result': result, 'ownedCleanup': cleaned, 'resources': released,
                            'requestId': request['requestId'], 'allFinalizationInsideOriginalBudget': True,
                            'timeoutSeconds': left, 'elapsedSeconds': time.monotonic() - clock.started}
                atomic(admission, envelope)
                clock.check_work()
            except (timer.WorkDeadlineExpired, subprocess.TimeoutExpired, Exception) as error:
                revoke()  # FIRST action, before signaling, cleanup, hashing or another write.
                if isinstance(error, (UnsafeOwnership, timer.DeadlineOwnershipError)):
                    raise
                claim = claim or _RETAINED_CLAIMS.get(str(root))
                stopped = stop_or_retain()
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


def implementation(deadline):
    records = proof.producer_records(deadline)
    records.extend(proof.file_record(path, deadline) for path in (Path(__file__), Path(timer.__file__),
                   proof.ROOT / 'scripts/run_runtime_transition_matrix.py',
                   proof.ROOT / 'scripts/runtime_semantics/withdrawn_owner_boundaries_v1.py',
                   proof.ROOT / 'scripts/runtime_semantics/withdrawn_sdk_boundaries_v1.py'))
    by_path = {item['path']: item for item in records}
    if by_path[str(proof.ROOT / 'scripts/run_runtime_transition_matrix.py')]['sha256'] != PUBLIC_SHA or \
            by_path[str(proof.ROOT / 'scripts/runtime_semantics/withdrawn_owner_boundaries_v1.py')]['sha256'] != WITHDRAWN_SHA or \
            by_path[str(proof.ROOT / 'scripts/runtime_semantics/withdrawn_sdk_boundaries_v1.py')]['sha256'] != SDK_BOUNDARY_SHA:
        raise ValueError('Reviewed public boundary version differs; no implicit adoption')
    return records


def lease_path(serial):
    return Path('/tmp') / ('ltb-arkts-device-' + hashlib.sha256(serial.encode()).hexdigest()[:16])


def _acquire(root, clock, request):
    # Canonical full-build lock wait is part of the same armed timer.
    lock = support.android_full_build_lock(clock.work_deadline)
    lock.__enter__()
    claim = {'buildLock': lock, 'lease': None, 'pid': os.getpid(), 'root': str(root),
             'requestId': request['requestId'], 'source': request['source'], 'serial': request['serial'], 'workers': []}
    _RETAINED_CLAIMS[str(root)] = claim
    try:
        path = lease_path(request['serial'])
        while True:
            clock.check_work()
            try:
                # Only this tiny mkdir/claim transaction masks SIGALRM.
                previous = signal.pthread_sigmask(signal.SIG_BLOCK, [signal.SIGALRM])
                try:
                    path.mkdir()
                    stat = path.stat()
                    claim['lease'] = {'path': str(path), 'inode': stat.st_ino, 'ctimeNs': stat.st_ctime_ns}
                    atomic(root / 'lease-claim.json', claim['lease'])
                finally:
                    signal.pthread_sigmask(signal.SIG_SETMASK, previous)
                break
            except FileExistsError:
                time.sleep(min(.1, max(.000001, clock.work_deadline - time.monotonic())))
        return claim
    except BaseException:
        if claim['lease'] is None:
            lock.__exit__(None, None, None)
            _RETAINED_CLAIMS.pop(str(root), None)
        raise


def _release(claim, root, clock):
    if claim is None:
        return {'released': True, 'acquired': False}
    if claim['pid'] != os.getpid() or claim['root'] != str(root) or _RETAINED_CLAIMS.get(str(root)) is not claim:
        return {'released': False, 'reason': 'foreign resource claim untouched'}
    proof.check(clock.deadline)  # Cleanup reserve is part of the original timer, not new work time.
    workers = claim.get('workers', [])
    if not workers or any(not item.get('status') or item['status'].get('unsafe') or
                          item['status'].get('leaderReaped') is not True or item['status'].get('groupGone') is not True
                          for item in workers):
        return {'released': False, 'reason': 'owned worker quiescence unproven'}
    request_path = root / 'request.json'
    request = proof.load(request_path)
    if request['requestId'] != claim['requestId'] or request['source'] != claim['source'] or request['serial'] != claim['serial']:
        return {'released': False, 'reason': 'resource request/source ownership differs'}
    current = proof.file_record(Path(__file__), clock.deadline)
    if current not in request['implementation']:
        return {'released': False, 'reason': 'actual native-start marker ordering implementation unbound'}
    expected_command = [sys.executable, '-B', '-m', MODULE, '--worker', str(request_path)]
    actual_workers = [item for item in workers if item['label'] == 'worker']
    if len(actual_workers) != 1 or actual_workers[0]['command'] != expected_command:
        return {'released': False, 'reason': 'exact source worker launch unproven'}
    marker = root / 'native-started.json'
    raw_path = root / 'native/runtime.native.json'
    if not marker.exists():
        # Verified producer order is marker-commit BEFORE native subprocess dispatch.
        # Absence is used only with exact source/worker ownership and group quiescence.
        remote = {'status': 'not_applicable_never_started', 'nativeExecutionStarted': False,
                  'ownedAppUninstalled': 'not_applicable', 'reverseRemoved': 'not_applicable'}
    else:
        try:
            started = proof.load(marker)
            if started['pid'] != actual_workers[0]['pid'] or started['requestId'] != claim['requestId'] or \
                    started['source'] != claim['source'] or started['request'] != proof.file_record(request_path, clock.deadline) or \
                    started['command'] != [NODE, str(proof.RUNNER), str(root / 'native-config.json')]:
                raise ValueError('Native-start marker identity differs')
        except Exception as error:
            return {'released': False, 'remoteCleanup': 'unknown', 'reason': repr(error), 'leaseRetained': True}
        if not raw_path.exists():
            return {'released': False, 'remoteCleanup': 'unknown', 'nativeExecutionStarted': True, 'leaseRetained': True}
        remote = proof.load(raw_path).get('diagnostics', {}).get('cleanup', {})
        if not all(remote.get(k) is True for k in ('ownedAppUninstalled', 'reverseRemoved', 'remoteFilesRemoved')):
            return {'released': False, 'remoteCleanup': 'unknown_or_failed', 'leaseRetained': True}
    item = claim['lease']
    path = Path(item['path'])
    if path != lease_path(claim['serial']):
        return {'released': False, 'reason': 'resource lease path differs'}
    if not path.is_dir() or path.is_symlink():
        return {'released': False, 'reason': 'owned lease missing/changed'}
    stat = path.stat()
    if stat.st_ino != item['inode'] or stat.st_ctime_ns != item['ctimeNs'] or list(path.iterdir()):
        return {'released': False, 'reason': 'foreign/replaced lease untouched'}
    path.rmdir()
    claim['buildLock'].__exit__(None, None, None)
    _RETAINED_CLAIMS.pop(str(root), None)
    return {'released': True, 'remoteCleanup': remote}


def evaluate(*, task, platform, source, role, output, deadline, serial='127.0.0.1:5555', coordinator_release=False):
    if coordinator_release is not True:
        raise ValueError('Explicit coordinator resource release required; no hardware/build started')
    def precheck(root, clock):
        candidate = Path(source).resolve()
        if candidate == root or candidate in root.parents:
            raise ValueError('Private evaluator output must be outside candidate source')
        if Path(output).exists():
            raise ValueError('Never overwrite existing output')

    def prepare(root, clock):
        if task.task_id != '12_report_room' or platform != 'arkts' or role not in ('base', 'final', 'agent'):
            raise ValueError('Task12 ArkTS only')
        candidate = Path(source).resolve()
        if candidate == root or candidate in root.parents:
            raise ValueError('Private evaluator output must be outside candidate source')
        if proof.file_record(proof.CONTRACT, clock.work_deadline)['sha256'] != proof.CONTRACT_SHA:
            raise ValueError('Canonical contract differs')
        if shutil.disk_usage(root).free < 8 * 1024**3:
            raise RuntimeError('Storage protection: below 8 GiB')
        before = proof.inventory(candidate, clock.work_deadline)
        # Tiny original inputs survive binary/temp cleanup for bytewise review.
        archive = root / 'source-input.tar.gz'
        with tarfile.open(archive, 'w:gz') as stream:
            for item in before['files']:
                clock.check_work()
                path = candidate / item['path']
                if proof.file_record(path, clock.work_deadline)['sha256'] != item['sha256']:
                    raise ValueError('Source changed during input archive preparation')
                stream.add(path, arcname=item['path'], recursive=False)
        if proof.inventory(candidate, clock.work_deadline) != before:
            raise ValueError('Source changed while freezing exact input archive')
        (root / 'owned-temporary').mkdir()
        return {'source': str(candidate), 'role': role, 'serial': serial, 'inventory': before,
                'implementation': implementation(clock.work_deadline), 'output': str(root),
                'sourceInputArchive': proof.file_record(archive, clock.work_deadline),
                'publicRegistered': False, 'historicalRuntimeUsed': False}

    def finalize(root, request, clock, launch):
        if implementation(clock.work_deadline) != request['implementation'] or \
                proof.inventory(Path(request['source']), clock.work_deadline) != request['inventory']:
            raise ValueError('Producer/source changed during actual execution')
        config = proof.load(root / 'native-config.json')
        raw = proof.load(root / 'native/runtime.native.json')
        proof.validate_envelope(raw, source=Path(request['source']), source_inventory=request['inventory'],
                                build_path=root / 'application-build/application-build.json',
                                config_path=root / 'native-config.json', deadline=clock.work_deadline)
        launch([NODE, '-e', proof.NODE_VERIFY, str(proof.FACTS), str(root / 'native/runtime.native.json'),
                str(proof.CONTRACT), config['bundle'], str(root / 'native')], 'independent-validation')
        checked = proof.load(root / 'independent-validation.log')
        if checked.get('validated') is not True:
            raise ValueError('Full native independent recomputation incomplete')
        return {'role': role, 'source': request['source'], 'semantic': raw['semantic'],
                'raw': proof.file_record(root / 'native/runtime.native.json', clock.work_deadline),
                'runtimeCompile': {'passed': True, 'scope': 'runtime HAP, not standalone compile metric'},
                'publicAdmitted': False, 'publicationEligible': False}

    def cleanup(root, clock):
        from .task12_arkts_merged_runtime_v1 import cleanup as hash_cleanup
        return hash_cleanup(root, clock.deadline)  # Pure cleanup only; never v1.evaluate/run.

    root = Path(output).with_suffix('.merged-v2-evidence')
    return _supervise(root, deadline, prepare, lambda request: [sys.executable, '-B', '-m', MODULE,
                      '--worker', str(request)], finalize, acquire=_acquire, cleanup=cleanup, release=_release,
                      report_path=output, precheck=precheck)


def worker(request_path):
    """All children inherit this owned group; no nested start_new_session escape."""
    from .task12_arkts_merged_build_v1 import build_application
    request = proof.load(request_path)
    deadline = timer.child_local_deadline(request['childBudget'])
    root, source = Path(request['output']), Path(request['source'])
    build = build_application(source=source, output=root / 'application-build', temporary=root / 'owned-temporary', deadline=deadline)
    code = "const fs=require('fs'),J=require(process.argv[1]);process.stdout.write(JSON.stringify(J.parse(fs.readFileSync(process.argv[2],'utf8')).app));"
    with (root / 'identity.json').open('x') as stream:
        subprocess.run([NODE, '-e', code, str(proof.JSON5), str(source / 'AppScope/app.json5')], stdout=stream,
                       stderr=subprocess.STDOUT, timeout=max(.000001, deadline - time.monotonic()), check=True)
    bundle = proof.load(root / 'identity.json')['bundleName']
    if not isinstance(bundle, str) or not bundle or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.' for c in bundle):
        raise ValueError('Unknown app identity')
    support.wait_hdc_connected(serial=request['serial'], deadline=deadline, log=root / 'hdc-readiness.log')
    config = {'source': str(source), 'bundle': bundle, 'hap': build['hap']['path'],
              'buildReport': str(root / 'application-build/application-build.json'), 'contract': str(proof.CONTRACT),
              'hdc': str(Path.home() / 'Library/OpenHarmony/Sdk/23/toolchains/hdc'), 'serial': request['serial'],
              'port': 18743, 'output': str(root / 'native'), 'remainingSeconds': deadline - time.monotonic()}
    proof.write(root / 'native-config.json', config)
    atomic(root / 'native-started.json', {'pid': os.getpid(), 'requestId': request['requestId'], 'source': str(source),
           'request': proof.file_record(request_path, deadline),
           'command': [NODE, str(proof.RUNNER), str(root / 'native-config.json')]})
    with (root / 'native.log').open('x') as stream:
        subprocess.run([NODE, str(proof.RUNNER), str(root / 'native-config.json')], stdout=stream, stderr=subprocess.STDOUT,
                       timeout=max(.000001, deadline - time.monotonic()), check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--worker', type=Path)
    parser.add_argument('--source', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--timeout', type=float, default=3600)
    parser.add_argument('--role', choices=('base', 'final', 'agent'), default='agent')
    parser.add_argument('--device-serial', default='127.0.0.1:5555')
    parser.add_argument('--execute-after-coordinator-release', action='store_true')
    args = parser.parse_args()
    if args.worker:
        worker(args.worker)
        return
    if not args.execute_after_coordinator_release or args.source is None or args.output is None or \
            not math.isfinite(args.timeout) or not 0 < args.timeout <= 3600:
        parser.error('Explicit resource release, source/output, finite 0 < timeout <= 3600 required')
    from types import SimpleNamespace
    result = evaluate(task=SimpleNamespace(task_id='12_report_room'), platform='arkts', source=args.source,
                      role=args.role, output=args.output, deadline=time.monotonic() + args.timeout,
                      serial=args.device_serial, coordinator_release=True)
    print(json.dumps({'completed': result is not None, 'publicationReady': False}))


if __name__ == '__main__':
    main()
