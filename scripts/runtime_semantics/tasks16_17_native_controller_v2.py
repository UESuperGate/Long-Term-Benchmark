"""Scheduled calibration-only controller. Importing it starts no work.

One parent-owned POSIX clock covers the entire task/pole, including finalization.
The Task15-v4 clock is reused read-only, not its evaluator/admission policy.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.runtime_semantics import task15_deadline_v4 as timer
from scripts.runtime_semantics import tasks16_17_native_report_assembler_v2 as assembly

SCHEMA = 'tasks16_17.native-controller.v2'
NODE = '/Applications/DevEco-Studio.app/Contents/tools/node/bin/node'
PRODUCER_MODULE = 'scripts.runtime_semantics.tasks16_17_native_episode_producer_v2'
POLES = ('base', 'final', 'random_base_copy', 'random_final_copy')


def atomic(path, value):
    path = Path(path)
    temporary = path.with_name(path.name + '.pending')
    with temporary.open('w') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')
    os.replace(temporary, path)


def implementation():
    return [assembly.record(path) for path in (Path(__file__), Path(timer.__file__),
        ROOT / 'scripts/runtime_semantics/tasks16_17_native_episode_producer_v2.py',
        ROOT / 'scripts/runtime_semantics/arkts_native_device.cjs',
        ROOT / 'scripts/runtime_semantics/arkts_native_smoke.cjs',
        ROOT / 'scripts/runtime_semantics/arkts_device_execute.cjs',
        ROOT / 'scripts/runtime_semantics/task16_arkts_revision5_build.cjs',
        ROOT / 'scripts/runtime_semantics/task17_arkts_strict_build.cjs',
        ROOT / 'state_tests/runtime/arkts/native/Tasks16_17PagePorts.install.cjs')] + assembly.evaluator_records()


def stop_group(process, hard_deadline):
    if process is None:
        return dict(started=False, leaderReaped=True, groupGone=True)
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(process.pid, sig)
        except ProcessLookupError:
            pass
        left = hard_deadline - time.monotonic()
        if process.poll() is None and left > 0:
            try:
                process.wait(timeout=min(0.04, left))
            except subprocess.TimeoutExpired:
                pass
    try:
        os.killpg(process.pid, 0)
        gone = False
    except ProcessLookupError:
        gone = True
    return dict(started=True, pid=process.pid, pgid=process.pid, leaderReaped=process.poll() is not None,
                groupGone=gone, foreignProcessesSignaled=False)


def lease_path(serial):
    return Path('/tmp') / ('ltb-arkts-device-' + hashlib.sha256(serial.encode()).hexdigest()[:16])


def acquire_lease(serial, clock, token, claim_file=None):
    path = lease_path(serial)
    legacy = Path(os.environ.get('TMPDIR', '/tmp')) / path.name
    while True:
        clock.check_work()
        if path.exists() or legacy.exists():
            time.sleep(min(0.1, max(0.000001, clock.work_deadline-time.monotonic())))
            continue
        # A very short critical section prevents an owned empty lock on SIGALRM.
        old_mask = signal.pthread_sigmask(signal.SIG_BLOCK, [signal.SIGALRM])
        try:
            try:
                path.mkdir()
            except FileExistsError:
                continue
            owner = dict(pid=os.getpid(), serial=serial, token=token, controller=SCHEMA)
            atomic(path / 'owner.json', owner)
            claim = dict(path=str(path), owner=owner, ownerRecord=assembly.record(path / 'owner.json'),
                         inode=path.stat().st_ino, device=path.stat().st_dev)
            if claim_file is not None:
                atomic(claim_file, claim)
        finally:
            signal.pthread_sigmask(signal.SIG_SETMASK, old_mask)
        return claim


def release_lease(claim):
    if claim is None:
        return dict(released=True, acquired=False)
    path = Path(claim['path'])
    if claim['owner'].get('pid') != os.getpid() or claim['owner'].get('controller') != SCHEMA:
        return dict(released=False, reason='foreign controller ownership untouched')
    if not path.exists():
        return dict(released=False, reason='owned lease disappeared; ownership not assumed')
    same = (not path.is_symlink() and path.stat().st_ino == claim['inode'] and path.stat().st_dev == claim['device'] and
            list(path.iterdir()) == [path / 'owner.json'] and assembly.record(path / 'owner.json') == claim['ownerRecord'])
    if not same:
        return dict(released=False, reason='foreign/changed lease untouched')
    (path / 'owner.json').unlink()
    path.rmdir()
    return dict(released=True, acquired=True, owner=claim['owner'])


def cleanup_work(output, deadline):
    work = output / 'owned-work'
    records = []
    if work.exists():
        for path in sorted(work.rglob('*')):
            assembly.remaining(deadline)
            if path.is_symlink():
                records.append(dict(path=str(path), symlinkTarget=os.readlink(path), followed=False))
            elif path.is_file():
                records.append(assembly.record(path))
        atomic(output / 'work-cleanup.pending.json', dict(files=records, removed=False))
        shutil.rmtree(work)
    value = dict(files=records, removed=not work.exists(), hashesRecordedBeforeRemoval=True,
                 dependenciesOutsideOwnedWorkUntouched=True)
    atomic(output / 'work-cleanup.json', value)
    return value


def safe_device_cleanup_observed(output):
    # Never infer uninstall merely from a dead worker/process or empty rows.
    for marker in output.glob('cases/*/native-execution.started.json'):
        execution = marker.parent / 'execution/device-execution.json'
        if not execution.exists() or not json.loads(execution.read_text()).get('cleanup', {}).get('ownedAppUninstalled'):
            return False
    return True


def _supervise(output, timeout, prepare, worker_command, finalize, *, acquire=None, cleanup=None):
    """Private process protocol also exercised by real short offline test children."""
    clock = timer.OverallDeadline(timeout)
    output = Path(output).resolve()
    process = None
    claim = None
    result = None
    entered = False
    started_epoch = int(time.time()*1000)
    try:
        with clock:
            entered = True
            assembly.require(not output.exists(), 'never overwrite a controller run')
            output.mkdir(parents=True)
            atomic(output / 'revocation-ready.json', dict(state='revoked', schemaVersion=SCHEMA,
                publicationEligible=False, reason='end-to-end task/pole not completed within owned budget'))
            atomic(output / 'controller-admission.json', dict(state='pending', publicationEligible=False))
            try:
                request = prepare(output, clock)
                request['startedAtEpochMs'] = started_epoch
                clock.check_work()
                if acquire:
                    claim = acquire(clock, request)
                    request['lease'] = claim
                request['childBudget'] = clock.child_budget(reserve=min(60, timeout * 0.15))
                atomic(output / 'request.json', request)
                (output / 'owned-work/tmp').mkdir(parents=True)
                with (output / 'worker.log').open('w') as stream:
                    argv = worker_command(output / 'request.json')
                    process = subprocess.Popen(argv, cwd=ROOT, stdout=stream,
                        stderr=subprocess.STDOUT, env={**os.environ, 'TMPDIR': str(output / 'owned-work/tmp')}, start_new_session=True)
                    atomic(output / 'worker-launch.json', dict(command=argv, pid=process.pid, pgid=process.pid,
                        request=assembly.record(output / 'request.json'), startedAtEpochMs=int(time.time()*1000)))
                    # Remaining seconds + epoch cross processes, never a monotonic timestamp.
                    wait = timer.child_local_deadline(request['childBudget']) - time.monotonic()
                    process.wait(timeout=max(0.000001, wait))
                stopped = stop_group(process, clock.deadline)
                assembly.require(process.returncode == 0 and stopped['leaderReaped'] and stopped['groupGone'], 'owned worker/descendants not complete')
                clock.check_work()
                result = finalize(output, request, clock)
                clock.check_work()
                cleaned = (cleanup or cleanup_work)(output, clock.deadline)
                assembly.require(cleaned.get('removed'), 'owned temporary cleanup not complete')
                assembly.require(safe_device_cleanup_observed(output), 'actual app uninstall not confirmed; retain owned lease')
                released = release_lease(claim)
                assembly.require(released['released'], 'lease release not confirmed')
                claim = None
                clock.check_work()
                files = [assembly.record(path) for path in sorted(output.rglob('*')) if path.is_file() and
                         path.name not in ('controller-admission.json', 'revocation-ready.json')]
                clock.check_work()
                atomic(output / 'controller-admission.json', dict(schemaVersion=SCHEMA, state='complete',
                    publicationEligible=False, diagnosticOnly=True, files=files, requestId=request['requestId'],
                    implementation=implementation(), timeoutSeconds=timeout,
                    elapsedBeforeCommitSeconds=time.monotonic()-clock.started,
                    startedAtEpochMs=request['startedAtEpochMs'], deadlineEpochMs=request['deadlineEpochMs'],
                    completedAtEpochMs=int(time.time()*1000), ownedProcesses=stopped,
                    temporaryCleanup=cleaned, leaseReleased=released, allFinalizationInsideOriginalBudget=True))
                clock.check_work()
            except (timer.WorkDeadlineExpired, subprocess.TimeoutExpired, Exception) as error:
                # FIRST failure action; clock remains armed through cleanup below.
                if (output / 'revocation-ready.json').exists():
                    os.replace(output / 'revocation-ready.json', output / 'controller-admission.json')
                if isinstance(error, timer.DeadlineOwnershipError):
                    # Never run potentially blocking cleanup without our timer.
                    # Foreign handler/timer ownership must remain untouched.
                    raise
                if claim is None and (output / 'lease-claim.json').exists():
                    claim = json.loads((output / 'lease-claim.json').read_text())
                stopped = stop_group(process, clock.deadline)
                cleaned = (cleanup or cleanup_work)(output, clock.deadline)
                release = release_lease(claim) if safe_device_cleanup_observed(output) else dict(released=False, reason='app cleanup unproven; owned lease retained')
                atomic(output / 'failure.json', dict(error=repr(error), ownedProcesses=stopped, cleanup=cleaned,
                    lease=release, elapsedSeconds=time.monotonic()-clock.started, semanticFailureInferred=False))
                result = None
    except (timer.HardDeadlineExpired, timer.WorkDeadlineExpired, timer.DeadlineOwnershipError):
        if not entered:
            raise
        if process is not None:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        # No restarted timeout, recursive cleanup or hashing after the hard cap.
        if entered and (output / 'revocation-ready.json').exists():
            os.replace(output / 'revocation-ready.json', output / 'controller-admission.json')
        result = None
    return result


def verify_case_producers(output, request):
    from scripts.runtime_semantics import tasks16_17_native_episode_producer_v2 as producer
    completed = json.loads((output / 'worker-result.json').read_text())
    launch = json.loads((output / 'worker-launch.json').read_text())
    assembly.require(launch['command'] == [sys.executable, '-B', '-m', PRODUCER_MODULE, '--request', str(output / 'request.json')] and
        launch['pid'] == launch['pgid'] == completed['pid'] and launch['request'] == assembly.record(output / 'request.json'),
        'actual producer subprocess launch not bound')
    assembly.require(completed['requestId'] == request['requestId'] and completed['producer'] == assembly.record(producer.__file__), 'actual producer missing/changed')
    assembly.require(completed['caseIds'] == request['caseIds'], 'producer omitted/reordered canonical cases')
    assembly.require(completed['deadlineEpochMs'] == request['childBudget']['deadlineEpochMs'] and
        completed['finishedAtEpochMs'] <= completed['deadlineEpochMs'], 'producer finished outside original remaining budget')
    cleaned = json.loads((output / 'pole-source-cleanup.json').read_text())
    assembly.require(cleaned['source'] == completed['candidateSource'] and cleaned['files'] == request['inputs'] and
        cleaned['removed'] and not Path(cleaned['source']).exists(), 'actual per-pole source cleanup not proved')
    nonces, hashes = set(), set()
    for case_id in request['caseIds']:
        receipt = json.loads((output / 'cases' / case_id / 'receipt.json').read_text())
        proof = receipt['actualProducer']
        assembly.require(receipt['candidateRemoved'] and receipt['poleSourceCleanup'] == assembly.record(output / 'pole-source-cleanup.json'),
                         'case missing actual shared per-pole source cleanup binding')
        assembly.require(proof['implementation'] == assembly.record(producer.__file__) and proof['requestId'] == request['requestId'] and
            proof['candidateSource'] == completed['candidateSource'] and proof['caseId'] == case_id and
            proof['deadlineEpochMs'] == request['childBudget']['deadlineEpochMs'] and proof['pid'] == completed['pid'] and
            proof['processGroup'] == completed['pid'], 'case actual producer/source/deadline differs')
        execution = json.loads(Path(receipt['execution']['path']).read_text())
        nonce = execution['executionNonce']
        raw_hash = assembly.record(Path(receipt['execution']['path']).parent / 'native-result.json')['sha256']
        assembly.require(nonce not in nonces and raw_hash not in hashes, 'case reused an actual nonce/raw')
        nonces.add(nonce); hashes.add(raw_hash)
        for phase in ('build', 'native-execution'):
            command = json.loads((output / 'cases' / case_id / (phase + '.command.json')).read_text())
            case_root = output / 'cases' / case_id
            expected_command = ([NODE, str(ROOT/'scripts/runtime_semantics/tasks16_17_arkts_page_ports_build_v2.cjs'),
                '--source', completed['candidateSource'], '--task', request['taskId'], '--case', case_id,
                '--output-dir', str(case_root/'build')] if phase == 'build' else
                [NODE, str(ROOT/'scripts/runtime_semantics/arkts_device_execute.cjs'), str(case_root/'build/device-build-report.json'),
                 request['serial'], str(case_root/'execution')])
            assembly.require(command['producerPid'] == completed['pid'] and command['pgid'] == completed['pid'] and
                command['command'] == expected_command and
                command['exitCode'] == 0 and command['deadlineEpochMs'] == request['childBudget']['deadlineEpochMs'] and
                request['startedAtEpochMs'] <= command['startedAtEpochMs'] <= command['finishedAtEpochMs'] <= command['deadlineEpochMs'] and
                assembly.record(command['log']['path']) == command['log'], 'actual producer command/log/budget proof differs')
    return completed


def run_pole(*, task_id, pole, source, output, policy, policy_sha256, timeout=3600, serial='127.0.0.1:5555', coordinator_release=False):
    assembly.require(coordinator_release is True, 'explicit coordinator release required; no native work started')
    assembly.require(task_id in assembly.TASKS and pole in POLES, 'wrong task/pole')
    output = assembly.audit_path(output)
    source = Path(source).resolve()

    def prepare(root, clock):
        reviewed = assembly.load_policy(policy, policy_sha256)
        inputs = assembly.inventory(source, clock.work_deadline)
        assembly.require(sum(row['taskId'] == task_id and row['completeInputs'] == inputs for row in reviewed['variants']) == 1,
                         'calibration-only reviewed inputs missing; NOT arbitrary-candidate formal ready')
        assembly.require(shutil.disk_usage(root).free >= 8*1024**3, '8 GiB storage floor')
        contract = ROOT / 'benchmark_tasks' / task_id / 'transitions.json'
        return dict(schemaVersion=SCHEMA, requestId=uuid.uuid4().hex, taskId=task_id, pole=pole,
            source=str(source), inputs=inputs, caseIds=[row['caseId'] for row in json.loads(contract.read_text())['cases']],
            canonicalContract=assembly.record(contract), serial=serial, policy=assembly.record(policy), policySha256=policy_sha256,
            implementation=implementation(), startedAtEpochMs=int(time.time()*1000),
            deadlineEpochMs=int((time.time()+clock.deadline-time.monotonic())*1000), calibrationOnly=True,
            futureArbitraryCandidateFormalReady=False, publicAdmissionChanged=False)

    def finalize(root, request, clock):
        completed = verify_case_producers(root, request)
        # The producer has already hash-removed its per-pole copy. The explicit
        # caller source must still be byte-identical to those actual build inputs.
        report = assembly.assemble(task_id, source,
            [root / 'cases' / case_id for case_id in request['caseIds']], root / 'assembled',
            Path(request['policy']['path']), policy_sha256, min(3600, clock.work_deadline-time.monotonic()))
        checked = assembly.verify_assembled(root / 'assembled/report.json', policy_sha256)
        atomic(root / 'native-revalidation.json', checked)
        public = json.loads((root / 'assembled/public-validation.json').read_text())
        assembly.require(public['status'] == 'rejected_by_current_public_validator', 'public policy changed; review new version before continuing')
        atomic(root / 'controller-result.json', dict(taskId=task_id, pole=pole, counts=report['counts'],
            nativeReport=assembly.record(root / 'assembled/report.json'), publicValidation=public,
            calibrationOnly=True, futureArbitraryCandidateFormalReady=False, publicAdmissionChanged=False))
        return report

    return _supervise(output, timeout, prepare,
        lambda request: [sys.executable, '-B', '-m', PRODUCER_MODULE, '--request', str(request)], finalize,
        acquire=lambda clock, request: acquire_lease(serial, clock, request['requestId'], output / 'lease-claim.json'))


def run_all_controls(*, sources, output, policy, policy_sha256, timeout_per_pole=3600,
                     serial='127.0.0.1:5555', full_queue_release=False):
    """Explicit future serial eight-pole executor; never starts on import/default."""
    assembly.require(full_queue_release is True, 'explicit whole four-control queue release required')
    assembly.require(set(sources) == set(assembly.TASKS) and all(set(value) == {'base','final'} for value in sources.values()),
                     'explicit base/final sources for BOTH tasks required')
    # Validate before filesystem changes, including NaN/bool/oversized budgets.
    timer.OverallDeadline(timeout_per_pole)
    output = assembly.audit_path(output)
    assembly.require(not output.exists(), 'new four-control output required')
    output.mkdir(parents=True)
    index = dict(schemaVersion=SCHEMA+'.four-controls', controls=[], publicAdmissionChanged=False,
        calibrationOnly=True, futureArbitraryCandidateFormalReady=False, complete=False)
    atomic(output/'controls.json',index)
    for task_id in assembly.TASKS:
        for pole in POLES:
            source_key = 'base' if pole in ('base','random_base_copy') else 'final'
            directory = output/task_id/pole
            result = run_pole(task_id=task_id,pole=pole,source=Path(sources[task_id][source_key]),output=directory,
                policy=policy,policy_sha256=policy_sha256,timeout=timeout_per_pole,serial=serial,coordinator_release=True)
            index['controls'].append(dict(taskId=task_id,pole=pole,output=str(directory),completedDiagnostic=result is not None,
                admission=assembly.record(directory/'controller-admission.json')))
            atomic(output/'controls.json',index)
            if result is None:
                return index  # No automatic environment rerun or old-log overwrite.
    # Each task/pole was sealed under its OWN original <=3600 budget. Cohort
    # comparison is a separate offline audit, never an untimed scoring phase.
    index['allPoleDiagnosticsComplete']=True
    index['offlineCohortAuditPending']=True
    atomic(output/'controls.json',index)
    return index


def verify_controller(output):
    output = assembly.audit_path(output)
    seal = json.loads((output / 'controller-admission.json').read_text())
    assembly.require(seal.get('state') == 'complete', 'controller admission pending/revoked; do not consume scores')
    assembly.require(seal['implementation'] == implementation() and seal['diagnosticOnly'] and not seal['publicationEligible'], 'unreviewed controller/tier')
    assembly.require(0 <= seal['elapsedBeforeCommitSeconds'] < seal['timeoutSeconds'] <= 3600 and
        seal['startedAtEpochMs'] <= seal['completedAtEpochMs'] <= seal['deadlineEpochMs'] and
        0 < seal['deadlineEpochMs']-seal['startedAtEpochMs'] <= seal['timeoutSeconds']*1000+10 and
        seal['ownedProcesses']['leaderReaped'] and seal['ownedProcesses']['groupGone'] and
        seal['temporaryCleanup']['removed'] and seal['leaseReleased']['released'], 'whole task/pole deadline or cleanup incomplete')
    for item in seal['files']:
        path = Path(item['path']).resolve()
        assembly.require(path.is_relative_to(output) and assembly.record(path) == item, 'sealed evidence bytes changed')
    assembly.require(seal['files'] == [assembly.record(path) for path in sorted(output.rglob('*')) if path.is_file() and
        path.name not in ('controller-admission.json', 'revocation-ready.json')], 'controller final ledger incomplete/extra')
    request = json.loads((output / 'request.json').read_text())
    assembly.require(request.get('requestId') == seal['requestId'] and request.get('implementation') == implementation(), 'wrong producer request')
    assembly.require(0 < request['childBudget']['remainingSeconds'] <= seal['timeoutSeconds'] and
        request['childBudget']['deadlineEpochMs'] <= seal['deadlineEpochMs'], 'per-case deadline was extended/reset')
    verify_case_producers(output, request)
    facts = assembly.verify_assembled(output / 'assembled/report.json', request['policySha256'])
    return dict(controllerAdmission=assembly.record(output / 'controller-admission.json'), nativeFacts=facts,
                calibrationOnly=True, futureArbitraryCandidateFormalReady=False, publicAdmissionChanged=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--task-id', choices=assembly.TASKS, required=True)
    parser.add_argument('--pole', choices=POLES, required=True)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--policy', type=Path, required=True)
    parser.add_argument('--policy-sha256', required=True)
    parser.add_argument('--timeout', type=float, default=3600)
    parser.add_argument('--serial', default='127.0.0.1:5555')
    parser.add_argument('--coordinator-release', action='store_true')
    args = parser.parse_args()
    result = run_pole(task_id=args.task_id, pole=args.pole, source=args.source, output=args.output,
        policy=args.policy, policy_sha256=args.policy_sha256, timeout=args.timeout, serial=args.serial,
        coordinator_release=args.coordinator_release)
    print(json.dumps(dict(completedDiagnostic=result is not None, publicAdmissionChanged=False)))
