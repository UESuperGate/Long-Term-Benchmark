#!/usr/bin/env python3
"""Unpromoted Task08 fresh base/final controls: one <=3600s owned outer deadline."""
import argparse
import copy
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.runtime_semantics import task15_deadline_v4 as timer
from scripts.runtime_semantics import tasks16_17_native_controller_v3 as owned
from scripts.runtime_semantics import task08_arkts_supervised_verifier_v1 as verifier
from scripts.runtime_semantics import task08_arkts_focus_build_v2 as builder

SCHEMA = 'task08.arkts.fresh-controls.supervisor.v1.unpromoted'
NODE = '/Applications/DevEco-Studio.app/Contents/tools/node/bin/node'
BINARY = {'.hap', '.har', '.app', '.apk', '.abc', '.so', '.class', '.jar', '.aar', '.dex'}


def atomic(path, value):
    temporary = path.with_name(path.name + '.pending')
    temporary.write_text(json.dumps(value, indent=2) + '\n')
    os.replace(temporary, path)


def record(path, hard_deadline=None):
    h, size = hashlib.sha256(), 0
    with path.open('rb') as stream:
        while True:
            if hard_deadline is not None and time.monotonic() >= hard_deadline:
                raise timer.HardDeadlineExpired('No late hashing')
            chunk = stream.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            h.update(chunk)
    return {'path': str(path), 'bytes': size, 'sha256': h.hexdigest()}


def process_closure_gate():
    native = ROOT / 'scripts/runtime_semantics/arkts_native_device.cjs'
    source = native.read_text()
    if not all(token in source for token in ("'--no-daemon', '--no-parallel'", 'spawnSync(command[0], command.slice(1)',
        "const { withTemporaryWorkspace } = require('./arkts_native_smoke.cjs');")) or 'detached:' in source:
        raise ValueError('Unreviewed SDK builder launch/session configuration')
    paths = [native, ROOT / 'scripts/runtime_semantics/task08_arkts_strict_build.cjs',
             ROOT / 'scripts/runtime_semantics/task08_arkts_strict_execute.cjs',
             ROOT / 'scripts/runtime_semantics/task13_arkts_revision5_execute.cjs',
             ROOT / 'scripts/runtime_semantics/arkts_device_execute.cjs',
             ROOT / 'state_tests/runtime/arkts/native/Tasks16_18ProviderHost.cjs',
             Path(timer.__file__), Path(owned.__file__), Path(builder.__file__), Path(verifier.__file__), Path(__file__)]
    return {'files': [record(p) for p in paths], 'hvigorNoDaemonAndNoParallel': True,
            'smokeDetachedMainNotInvoked': True, 'workspaceReplacedByPrivateHashBeforeDeleteHelper': True,
            'scope': 'source-level process-launch audit, not a new SDK runtime execution'}


def unavailable(application_compile):
    return {'schema': SCHEMA, 'publicPromotion': False,
            'poles': {role: {'compile': copy.deepcopy(application_compile.get(role)),
                            'applicationCompileOrigin': 'explicit_agent_runner_standalone_build_parameter_only',
                            'runtimeCompile': {'passed': None, 'status': 'unavailable'},
                            'semantic': {'pass': 0, 'fail': 0, 'not_scored': 9}} for role in ('base', 'final')}}


def revoke(output):
    pending = output / 'revocation-ready.json'
    if pending.exists():
        os.replace(pending, output / 'admission.json')


def cleanup(output, clock):
    records = []
    for directory, dirs, files in os.walk(output, followlinks=False):
        if time.monotonic() >= clock.deadline:
            raise timer.HardDeadlineExpired('No late cleanup traversal')
        for name in dirs + files:
            if (Path(directory) / name).is_symlink():
                raise ValueError('Cleanup refuses symlink; retain inputs')
        for name in files:
            path = Path(directory) / name
            if path.suffix.lower() in BINARY:
                records.append(record(path, clock.deadline))
    atomic(output / 'binary-cleanup.json', {'hashesRecordedBeforeRemoval': True, 'removed': records,
                                           'binariesRetained': True, 'remaining': [r['path'] for r in records]})
    for r in records:
        if time.monotonic() >= clock.deadline:
            raise timer.HardDeadlineExpired('No late binary deletion')
        Path(r['path']).unlink()
    work = output / 'owned-work'
    work_records = []
    if work.exists():
        for directory, _, files in os.walk(work, followlinks=False):
            for name in files:
                work_records.append(record(Path(directory) / name, clock.deadline))
        atomic(output / 'work-cleanup-hashes.json', {'files': work_records, 'removed': False})
        if time.monotonic() >= clock.deadline:
            raise timer.HardDeadlineExpired('No late recursive deletion')
        shutil.rmtree(work)
    result = {'hashesRecordedBeforeRemoval': True, 'removed': records, 'binariesRetained': False,
              'remaining': [], 'ownedTemporaryWorkRemoved': not work.exists(),
              'remoteCleanupInferredFromLocalCleanup': False}
    atomic(output / 'binary-cleanup.json', result)
    return result


def supervise(output, timeout, prepare, worker_command, finalize, application_compile=None, cleanup_fn=cleanup):
    """Pinned unreaped worker owns its group until result marker or hard revocation."""
    app = application_compile if application_compile is not None else {}
    result = unavailable(app)
    output = Path(output).resolve()
    clock = timer.OverallDeadline(timeout)
    process, entered = None, False
    try:
        with clock:
            entered = True
            if output.exists():
                raise ValueError('Fresh output required')
            output.mkdir(parents=True)
            atomic(output / 'revocation-ready.json', {'state': 'revoked', 'publicPromotion': False, 'schema': SCHEMA})
            atomic(output / 'admission.json', {'state': 'pending', 'publicPromotion': False})
            try:
                request = prepare(output, clock)
                clock.check_work()
                request['childBudget'] = clock.child_budget()
                atomic(output / 'request.json', request)
                (output / 'owned-work/tmp').mkdir(parents=True)
                environment = dict(os.environ, TMPDIR=str(output / 'owned-work/tmp'))
                environment.pop('LTB_DEVICE_LOCK_PREACQUIRED', None)
                with (output / 'worker.log').open('x') as log:
                    mask = signal.pthread_sigmask(signal.SIG_BLOCK, [signal.SIGALRM])
                    try:
                        process = subprocess.Popen(worker_command(output / 'request.json'), cwd=ROOT,
                            stdout=log, stderr=subprocess.STDOUT, env=environment, start_new_session=True)
                    finally:
                        signal.pthread_sigmask(signal.SIG_SETMASK, mask)
                    atomic(output / 'worker-launch.json', {'pid': process.pid, 'pgid': process.pid, 'childrenInheritPgid': True})
                    while not (output / 'worker-finished.json').exists():
                        clock.check_work()
                        time.sleep(min(0.01, max(0.000001, clock.work_deadline - time.monotonic())))
                stopped = owned.stop_or_retain(process, clock.work_deadline, output)
                if not stopped['leaderReaped'] or not stopped['groupGone']:
                    raise ValueError('Owned descendants not proven stopped')
                clock.check_work()
                result = finalize(output, request, clock)
                clock.check_work()
                cleaned = cleanup_fn(output, clock)
                clock.check_work()
                result['supervision'] = dict(clock.diagnostic(), process=stopped, cleanup=cleaned)
                atomic(output / 'report.json', result)
                atomic(output / 'admission.json', {'state': 'complete_diagnostic_only', 'publicPromotion': False,
                                                   'allFinalizationInsideOverallBudget': True})
                clock.check_work()
            except (timer.WorkDeadlineExpired, Exception) as error:
                revoke(output)
                if isinstance(error, (timer.DeadlineOwnershipError, owned.UnsafeReapedGroupError)):
                    raise
                stopped = owned.stop_or_retain(process, clock.deadline, output)
                try:
                    cleaned = cleanup_fn(output, clock)
                except Exception as cleanup_error:
                    cleaned = {'removed': False, 'inputsRetained': True, 'error': repr(cleanup_error)}
                result = unavailable(app)
                atomic(output / 'failure.json', {'error': repr(error), 'process': stopped, 'cleanup': cleaned,
                    'canonicalLeaseMayRequireOwnedRecovery': True, 'deviceUninstallNotInferred': True,
                    'semanticFailureInferred': False})
                atomic(output / 'report.json', result)
    except (timer.HardDeadlineExpired, timer.WorkDeadlineExpired, timer.DeadlineOwnershipError, owned.UnsafeReapedGroupError):
        if not entered:
            raise
        revoke(output)  # First action; no late report, hashing, traversal or blocking reap.
        if owned.signal_unreaped(process):
            owned.reap_nonblocking(process)
        result = unavailable(app)
    return result


def run(plan, output, timeout=3600, coordinator_release=False):
    if coordinator_release is not True:
        raise ValueError('Explicit coordinator release required; no runtime work started')
    app = {}
    def prepare(root, clock):
        clock.check_work()
        value = json.loads(Path(plan).read_text()) if isinstance(plan, (str, Path)) else copy.deepcopy(plan)
        app.update(copy.deepcopy(value.get('applicationCompile', {})))
        if set(value.get('sources', {})) != {'base', 'final'} or not isinstance(value.get('serial'), str) or not value['serial']:
            raise ValueError('Explicit standalone base/final sources and serial required; no filename/role inference')
        for source in value['sources'].values():
            clock.check_work()
            if not (Path(source) / 'entry/src/main').is_dir():
                raise ValueError('Missing explicit standalone source')
        if shutil.disk_usage(ROOT).free < 8 * 1024**3:
            raise OSError('8 GiB guard; no SDK/build/device work')
        closure = process_closure_gate()
        template = builder.derive(root / 'fresh-evaluator-v2')
        return {'schema': SCHEMA, 'sources': {k: str(Path(v).resolve()) for k, v in value['sources'].items()},
                'serial': value['serial'], 'applicationCompile': app, 'overallTimeoutSeconds': timeout,
                'freshEvaluator': template, 'processClosure': closure}
    def finalize(root, request, clock):
        for item in request['processClosure']['files']:
            clock.check_work()
            if record(Path(item['path'])) != item:
                raise ValueError('Runtime/shared implementation changed during owned execution')
        worker = json.loads((root / 'worker-finished.json').read_text())
        if not worker['completed']:
            raise ValueError('Build/device/environment failure: ' + worker.get('error', 'unknown'))
        clock.check_work()
        proof = verifier.verify(root, worker['commands'])
        result = unavailable(app)
        result['strictControlVerification'] = proof
        for role in ('base', 'final'):
            build = json.loads((root / role / 'build/device-build-report.json').read_text())
            result['poles'][role]['runtimeCompile'] = build['runtimeCompile']
            result['poles'][role]['diagnosticSemantic'] = proof[role]
            result['poles'][role]['standaloneBuildFromEvaluatorNotBenchmarkCompile'] = build['standaloneAppCompile']
        return result
    return supervise(output, timeout, prepare,
        lambda request: [sys.executable, '-B', str(Path(__file__)), '--worker-request', str(request)],
        finalize, application_compile=app)


def worker(request_path):
    request_path = Path(request_path)
    output = request_path.parent
    request = json.loads(request_path.read_text())
    deadline = timer.child_local_deadline(request['childBudget'])
    commands, completed, error = [], False, None
    try:
        for role in ('base', 'final'):
            for stage in ('build', 'execute'):
                remaining = math.floor(deadline - time.monotonic())
                if remaining < 1:
                    raise TimeoutError('No original overall budget remains')
                if stage == 'build':
                    if shutil.disk_usage(ROOT).free < 8 * 1024**3:
                        raise OSError('8 GiB guard before build')
                    args = [NODE, request['freshEvaluator']['buildEntrypoint'], '--source', request['sources'][role],
                            '--role', role, '--case', 'all', '--output-dir', str(output / role / 'build')]
                else:
                    args = [NODE, request['freshEvaluator']['executeEntrypoint'],
                            str(output / role / 'build/device-build-report.json'), request['serial'], str(output / role / 'execute')]
                args += ['--timeout-seconds', str(remaining)]
                with (output / (role + '-' + stage + '.log')).open('x') as log:
                    # No new session: all stage descendants belong to the pinned root worker.
                    child = subprocess.run(args, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
                                           timeout=max(0.001, deadline - time.monotonic()), check=False,
                                           env={**os.environ, 'LTB_TASK08_INTERMEDIATE_AUDIT_DIR': str(output / role / 'build')})
                commands.append({'role': role, 'stage': stage, 'command': args, 'timeoutSeconds': remaining,
                                 'exitCode': child.returncode, 'completedMonotonic': time.monotonic()})
                atomic(output / 'command-receipts.json', commands)
                if child.returncode != 0:
                    raise RuntimeError(role + ' ' + stage + ' failed; semantics unavailable')
        completed = True
    except Exception as exc:
        error = repr(exc)
    atomic(output / 'worker-finished.json', {'completed': completed, 'commands': commands, 'error': error})
    # Never exit/reap leader before the parent has signaled the complete group.
    while True:
        time.sleep(60)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--worker-request', type=Path)
    parser.add_argument('--plan', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--timeout', type=float, default=3600)
    parser.add_argument('--coordinator-release', action='store_true')
    args = parser.parse_args()
    if args.worker_request:
        worker(args.worker_request)
    else:
        if not args.plan or not args.output:
            parser.error('Explicit plan and fresh output required')
        result = run(args.plan, args.output, args.timeout, args.coordinator_release)
        print(json.dumps(result, indent=2))
