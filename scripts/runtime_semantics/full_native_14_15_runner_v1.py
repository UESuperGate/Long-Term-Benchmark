"""OFFLINE by default: full-nine/full-ten native capture driver, no model.

Execution is explicit and needs a coordinator-released slot and its original
epoch deadline. One outer timer covers preparation, lock waits, every case,
raw admission, hashing, serialization and owned cleanup. No public registration
or readiness promotion is performed by this staging implementation.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time

from . import task14_full_native_packaging_v5 as t14
from . import task15_full_native_v7 as t15
from . import full_native_14_15_guard_v1 as guard
from . import task14_actual_routes_scorer_v4 as retained14
from . import task15_full_report_v4 as retained15
from . import task14_15_device_lease as lease
from . import task15_supervision_v4 as supervision
from .task15_deadline_v4 import OverallDeadline, child_local_deadline

core, artifacts = t14.core, t14.artifacts
ROOT = core.ROOT
PUBLIC_SHA = '6ceed2ee265a4eaeb59f13f4c8a4befbbc27f5c04cd2b9277cff0ab2f0a9d626'
PUBLIC_DEPS = {
    'withdrawn_owner_boundaries_v1.py': '16f259d2a6f737180a84775fe8447c5b66f0c9a3bf89f484d9cde73594a4954f',
    'withdrawn_sdk_boundaries_v1.py': 'ffeb9493a29b52218e86a8addbb5ea9fd283439622d08e96b23983229b65e54a'}
PROTOCOL = 'task14-15.full-native-review.v1'
MODULE = 'scripts.runtime_semantics.full_native_14_15_runner_v1'


def freeze(output):
    public = ROOT / 'scripts/run_runtime_transition_matrix.py'
    artifacts.require(core.sha256(public) == PUBLIC_SHA, 'Public changed: new freeze/review required, never repin old audit')
    for name, expected in PUBLIC_DEPS.items():
        artifacts.require(core.sha256(Path(__file__).with_name(name)) == expected, 'Public dependency changed: ' + name)
    sources = {item['path']: item for item in t14.implementation()['files']}
    for item in t15.previous.old.implementation()['files']:
        sources[item['path']] = item
    for name in ('task15_full_native_v7.py', 'task15_page_owner_packaging_v6.py',
                 'task15_page_owner_packaging_v6.cjs', 'task15_page_owner_v5.py',
                 'task15_full_report_v4.py', 'task15_page_owner_admission_v6.py'):
        path = Path(__file__).with_name(name)
        sources[str(path)] = {'path': str(path), 'bytes': path.stat().st_size, 'sha256': core.sha256(path)}
    for path in t15.owner.DIRECTORY.iterdir():
        if path.is_file():
            sources[str(path)] = {'path': str(path), 'bytes': path.stat().st_size, 'sha256': core.sha256(path)}
    records = []
    for item in sorted(sources.values(), key=lambda item: item['path']):
        original = Path(item['path'])
        artifacts.require(original.is_file() and not original.is_symlink() and core.sha256(original) == item['sha256'],
            'Source changed during freeze')
        relative = original.relative_to(ROOT)
        target = Path(output) / 'frozen-sources' / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(original.read_bytes())
        records.append({**item, 'snapshot': artifacts.artifact(target)})
    result = {'protocol': PROTOCOL, 'publicSha256': PUBLIC_SHA, 'publicDependencies': PUBLIC_DEPS,
        'files': records, 'ready': False, 'publicationEligible': False, 'sourceFreezeNotRuntimeEvidence': True}
    core.write(Path(output) / 'source-freeze.json', result)
    return artifacts.artifact(Path(output) / 'source-freeze.json')


def check_freeze(record):
    value = json.loads(artifacts.bound(record))
    for item in value['files']:
        path = Path(item['path'])
        artifacts.require(path.is_file() and not path.is_symlink() and path.stat().st_size == item['bytes'] and
            core.sha256(path) == item['sha256'] and artifacts.digest(path) ==
            hashlib.sha256(artifacts.bound(item['snapshot'])).hexdigest(), 'Frozen source changed')
    return value


def unavailable(task, source, reason, *, compile_passed=None, compile_command=''):
    contract = core.load(ROOT / 'benchmark_tasks' / task / 'transitions.json')
    rows = core.unavailable_rows(contract, reason)
    return {'schemaVersion': 4, 'taskId': task, 'platform': 'arkts', 'role': 'agent', 'target': str(source),
        'runtime': PROTOCOL, 'observationMode': 'runtime_state_transition',
        'compile': {'passed': compile_passed, 'command': compile_command, 'scope': 'separate application evidence supplied by parent'},
        'runtimeCompile': {'passed': None, 'status': 'not_scored', 'scope': 'evaluator packaging only'},
        'semantic': {'passed': 0, 'failed': 0, 'notScored': len(rows), 'total': len(rows), 'cases': rows},
        'publication': {'eligible': False, 'reason': reason},
        'diagnostics': {'modelCalled': False, 'hostFallbackUsed': False, 'originalModelMetricsChanged': False,
            'cleanup': {'status': 'not_started_or_unconfirmed'}}}


def prepare(*, task, source, output, deadline, device_serial='127.0.0.1:5555', case_ids=None):
    artifacts.require(task in (t14.TASK, t15.TASK), 'Only Task14/15 ArkTS')
    root = t14.snapshot.canonical_output(output)
    artifacts.require(not root.exists(), 'Never overwrite a previous plan/raw/model')
    remaining = core.remaining_deadline(deadline, 'Full-native offline prepare')
    artifacts.require(120 < remaining <= 3600, 'One remaining <=3600s preparation/cleanup budget')
    source = Path(source).resolve(strict=True)
    root.mkdir(parents=True)
    contract = core.load(ROOT / 'benchmark_tasks' / task / 'transitions.json')
    (root / 'canonical-contract.json').write_bytes((ROOT / 'benchmark_tasks' / task / 'transitions.json').read_bytes())
    selected = {item['caseId'] for item in contract['cases']} if case_ids is None else set(case_ids)
    artifacts.require(selected and selected <= {item['caseId'] for item in contract['cases']}, 'Unknown canonical cases')
    frozen = freeze(root)
    plans, errors = {}, {}
    if task == t14.TASK:
        plan = t14.prepare(source=source, output=root / 'task14-native', deadline=deadline, case_ids=selected)
        plans = {key: artifacts.artifact(root / 'task14-native/plan.json') for key in plan['selectedCases']}
    else:
        for case_id in sorted(selected):
            directory = root / 'native' / case_id
            try:
                directory.parent.mkdir(exist_ok=True)
                t15.prepare(source=source, case_id=case_id, output=directory, deadline=deadline, serial=device_serial)
                plans[case_id] = artifacts.artifact(directory / 'plan.json')
            except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
                errors[case_id] = repr(error)
    index = {'protocol': PROTOCOL, 'taskId': task, 'source': str(source), 'role': 'agent',
        'plans': plans, 'errors': errors, 'selectedCases': sorted(selected), 'freeze': frozen,
        'contract': artifacts.artifact(root / 'canonical-contract.json'),
        'deviceSerial': device_serial, 'deadlineEpochMs': int((time.time() + core.remaining_deadline(deadline, 'prepare seal')) * 1000),
        'preparedOnly': True, 'buildStarted': False, 'deviceStarted': False, 'modelCalled': False,
        'ready': False, 'hardwareAuthorization': 'No execution from preparation; released slot + explicit execute + original epoch required',
        'requirements': {'freeBytes': 8 * 1024**3, 'sharedHeavyFlock': '/tmp/long-term-benchmark-android-full-build.lock',
            'canonicalDeviceLeasePerCase': True, 'sameOriginalPageOwner': True, 'hashBeforeBinaryRemoval': True},
        'remainingGates': ['actual packaging and full native episodes', 'external reviewed full-layout/source/SDK-leaf profiles',
            'independent raw verification of each obligation', 'matched four controls', 'public narrow registration by parent']}
    core.write(root / 'full-native-index.json', index)
    check_freeze(frozen)
    return index


def verify_preparation(root):
    """Reconstruct offline file/contract/fixture identity, NEVER runtime proof."""
    root = Path(root)
    index = core.load(root / 'full-native-index.json')
    check_freeze(index['freeze'])
    contract = json.loads(artifacts.bound(index['contract']))
    specs = {item['caseId']: item for item in contract['cases']}
    artifacts.require(set(index['plans']) | set(index['errors']) == set(index['selectedCases']) and
        not set(index['plans']).intersection(index['errors']), 'Missing/duplicate preparation outcomes')
    verified = []
    for case_id, record in index['plans'].items():
        plan = json.loads(artifacts.bound(record))
        artifacts.require(plan['source'] == index['source'] and plan['role'] == 'agent', 'Unbound candidate/role')
        inputs = json.loads(artifacts.bound(plan['inputInventory']))
        digest = hashlib.sha256()
        names = [item['path'] for item in inputs['files']]
        artifacts.require(names == sorted(set(names)), 'Ambiguous source snapshot inventory')
        for item in inputs['files']:
            data = artifacts.bound(item['snapshot'])
            relative = Path(item['path'])
            artifacts.require(not relative.is_absolute() and '..' not in relative.parts and
                len(data) == item['bytes'] and hashlib.sha256(data).hexdigest() == item['sha256'], 'Source snapshot changed')
            name = item['path'].encode()
            digest.update(len(name).to_bytes(8, 'big')); digest.update(name)
            digest.update(len(data).to_bytes(8, 'big')); digest.update(data)
        artifacts.require(digest.hexdigest() == inputs['rootSha256'], 'Source snapshot closure digest differs')
        if index['taskId'] == t14.TASK:
            artifacts.require(plan['protocol'] == t14.PROTOCOL and case_id in plan['selectedCases'] and
                json.loads(artifacts.bound(plan['contract'])) == contract and plan['implementation'] == t14.implementation() and
                plan['packagedFixtures'] == t14.expected_fixtures(), 'Full-nine producer plan/fixture/contract differs')
            artifacts.bound(plan['builder'])
        else:
            artifacts.require(plan['canonicalCase'] == specs[case_id] and plan['caseId'] == case_id and
                plan.get('fullNativeProtocol') == t15.PROTOCOL, 'Own full-ten native canonical episode plan differs')
            guard.transport.identity(plan['evaluator'])
            for item in plan['derivedFiles']:
                artifacts.bound(item)
        verified.append(case_id)
    return {'verifiedPreparationOnly': True, 'preparedCases': verified, 'preparationErrors': index['errors'],
        'nativeRuntimeExecuted': False, 'sdkCompiled': False, 'ready': False,
        'publicValidatorSha256': PUBLIC_SHA, 'index': artifacts.artifact(root / 'full-native-index.json')}


def assemble(root, *, profile_key=None, compile_passed=None, compile_command=''):
    root = Path(root)
    index = core.load(root / 'full-native-index.json')
    check_freeze(index['freeze'])
    contract = json.loads(artifacts.bound(index['contract']))
    report = unavailable(index['taskId'], index['source'], 'Full native successor not publicly registered or calibrated',
        compile_passed=compile_passed, compile_command=compile_command)
    proposals, errors, bundles, compilations = {}, dict(index['errors']), {}, []
    for case_id, record in index['plans'].items():
        try:
            plan = json.loads(artifacts.bound(record))
            if index['taskId'] == t14.TASK:
                directory = root / 'task14-native'
                bundle = retained14._one_bundle(directory, case_id, plan)
                data, _, _ = guard.task14_envelope(bundle, contract)
            else:
                directory = Path(record['path']).parent
                bundle = retained15.native_bundle(directory)
                data = guard.transport.envelope(bundle, contract)
            bundles[case_id] = bundle
            compilations.append(data['build']['runtimeCompile'])
            proposals[case_id] = guard.admit(index['taskId'], bundle, contract, profile_key=profile_key)
        except (OSError, ValueError, KeyError, IndexError, StopIteration) as error:
            errors[case_id] = repr(error)
    # Private proposals are NOT scored formal rows before a separately reviewed
    # public route and four-control authority exist. Never forge public success.
    report['provenance'] = {'sourceFreeze': index['freeze'], 'sourceParameterizedPlans': index['plans'],
        'contract': index['contract'], 'rawBundles': bundles}
    report['diagnostics'].update(rawAdmissionErrors=errors, independentProposals=proposals,
        proposalCount=len(proposals), matchedFourControls=False, publicRegistered=False)
    if compilations:
        report['runtimeCompile'] = {'passed': len(compilations) == len(index['selectedCases']) and
            all(item.get('passed') is True for item in compilations), 'records': compilations,
            'scope': 'runtime evaluator packaging only; not full application compile'}
    from scripts.run_runtime_transition_matrix import validate_report
    validate_report(report, contract)
    report['diagnostics']['publicUnavailableReportValidated'] = True
    return report


def _command(argv, log, deadline):
    with Path(log).open('w') as stream:
        process = subprocess.Popen(argv, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT)
        # Commands remain within THIS owned session. The unreaped worker leader
        # lets the outer supervisor stop all descendants without PID reuse.
        try:
            process.wait(timeout=core.remaining_deadline(deadline, 'own native command'))
        except subprocess.TimeoutExpired:
            process.kill()
            raise TimeoutError('Own command exhausted original remaining budget')
    core.write(Path(log).with_suffix('.command.json'), {'command': argv, 'exit': process.returncode,
        'log': artifacts.artifact(log), 'ownedProcessGroup': os.getpgrp()})
    artifacts.require(process.returncode == 0, 'Native command failed; retain compiler/runtime log, NS only')


def _worker(request_path):
    request = core.load(Path(request_path))
    artifacts.require(os.getpid() == os.getpgrp(), 'Worker must own its new session')
    deadline = child_local_deadline(request['childBudget'])
    root = Path(request['output'])
    status = {'completed': False}
    try:
        index = core.load(root / 'full-native-index.json')
        check_freeze(index['freeze'])
        for case_id, record in index['plans'].items():
            with open('/tmp/long-term-benchmark-android-full-build.lock', 'a') as lock:
                while True:
                    try:
                        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                        break
                    except BlockingIOError:
                        time.sleep(min(.05, core.remaining_deadline(deadline, 'global heavy lock wait')))
                try:
                    core.require_build_space()
                    check_freeze(index['freeze'])
                    plan = json.loads(artifacts.bound(record))
                    if index['taskId'] == t14.TASK:
                        directory = root / 'task14-native/captures' / case_id
                        directory.mkdir(parents=True)
                        contract = json.loads(artifacts.bound(index['contract']))
                        subset = {**contract, 'cases': [row for row in contract['cases'] if row['caseId'] == case_id]}
                        core.write(directory / 'contract.json', subset)
                        with lease.task_scope(t14.TASK, deadline, device_serial=index['deviceSerial']):
                            lease.score_device(task_id=t14.TASK, source=Path(index['source']), output=directory / 'runtime.json',
                                deadline=deadline, contract_path=directory / 'contract.json', build_script=Path(plan['builder']['path']),
                                device_serial=index['deviceSerial'])
                    else:
                        # This generated versioned host owns the canonical lease
                        # around its entire one-case build/install/execute/cleanup.
                        directory = Path(record['path']).parent
                        _command(plan['command'], directory / 'host.log', deadline)
                finally:
                    fcntl.flock(lock, fcntl.LOCK_UN)
        status['completed'] = True
    except BaseException as error:
        status['error'] = repr(error)
    supervision.atomic_json(Path(request_path).parent / 'worker-finished.json', status)
    while time.monotonic() < deadline:
        time.sleep(min(.05, max(0, deadline - time.monotonic())))


def _cleanup(root, deadline):
    records = []
    root = Path(root)
    for path in sorted(root.rglob('*')):
        core.remaining_deadline(deadline, 'own hash/cleanup')
        if path.is_symlink():
            raise ValueError('Owned output unexpectedly contains a symlink; never traverse it')
        if path.is_file() and path.suffix.lower() in ('.hap', '.apk', '.abc', '.app', '.har', '.so'):
            record = artifacts.artifact(path)
            records.append(record)
            core.write(root / 'binary-cleanup-pending.json', {'files': records, 'complete': False})
            path.unlink()
            record['removed'] = True
    trees = []
    for name in ('build', 'certificates', 'preserved-work'):
        for directory in sorted(root.glob('native/*/native-e2e/' + name)):
            if not directory.is_dir():
                continue
            files = []
            for path in sorted(directory.rglob('*')):
                core.remaining_deadline(deadline, 'own intermediate/log retention')
                artifacts.require(not path.is_symlink(), 'Unexpected symlink in owned build tree')
                if path.is_file():
                    item = artifacts.artifact(path)
                    # Never retain certificate/private-key bytes. Keep unique
                    # compiler text and fixture/source diagnostics before delete.
                    if name != 'certificates' and path.suffix.lower() in ('.log', '.txt', '.json', '.ets', '.ts', '.js', '.cjs'):
                        target = root / 'retained-recovery-text' / path.relative_to(root)
                        target.parent.mkdir(parents=True, exist_ok=True)
                        target.write_bytes(path.read_bytes())
                        item['retainedText'] = artifacts.artifact(target)
                    files.append(item)
            trees.append({'path': str(directory), 'files': files, 'removed': False})
            core.write(root / 'intermediate-cleanup-pending.json', {'trees': trees, 'complete': False})
            shutil.rmtree(directory)
            trees[-1]['removed'] = True
    value = {'files': records, 'hashesRecordedBeforeRemoval': True, 'binariesRetained': False,
        'remoteCleanupInferred': False, 'intermediateTrees': trees,
        'uniqueCompilerLogsPreserved': True}
    core.write(root / 'outer-cleanup.json', value)
    return artifacts.artifact(root / 'outer-cleanup.json')


def evaluate(*, task, source, output, timeout=3600, original_deadline_epoch=None, execute=False,
             device_serial='127.0.0.1:5555', case_ids=None, profile_key=None,
             compile_passed=None, compile_command=''):
    artifacts.require(execute is True and original_deadline_epoch is not None,
        'No hardware by default: explicit released slot/original deadline required')
    artifacts.require(type(timeout) in (int, float) and math.isfinite(timeout) and 0 < timeout <= 3600,
        'One <=3600s budget')
    timeout = min(timeout, original_deadline_epoch - time.time())
    artifacts.require(timeout > 120, 'Original repair deadline expired; do not reset it')
    root = t14.snapshot.canonical_output(output)
    scope = root.with_name(root.name + '-supervision')
    artifacts.require(not root.exists() and not scope.exists(), 'No overwrites')
    process = None
    fallback = unavailable(task, source, 'End-to-end admission incomplete; not semantic failure',
        compile_passed=compile_passed, compile_command=compile_command)
    with OverallDeadline(timeout) as clock:
        scope.mkdir(parents=True)
        supervision.atomic_json(scope / 'revoked.json', {'state': 'revoked', 'publicationEligible': False})
        supervision.atomic_json(scope / 'fallback.json', fallback)
        supervision.atomic_json(scope / 'admission.json', {'state': 'pending', 'publicationEligible': False})
        try:
            prepare(task=task, source=source, output=root, deadline=clock.work_deadline,
                device_serial=device_serial, case_ids=case_ids)
            temporary = scope / 'work-tmp'
            temporary.mkdir()
            request = {'output': str(root), 'childBudget': clock.child_budget(reserve=min(180, timeout * .15))}
            supervision.atomic_json(scope / 'request.json', request)
            with (scope / 'worker.log').open('w') as stream:
                process = subprocess.Popen([sys.executable, '-B', '-m', MODULE, '--worker', str(scope / 'request.json')],
                    cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT, start_new_session=True,
                    env={**os.environ, 'TMPDIR': str(temporary)})
                while not (scope / 'worker-finished.json').is_file():
                    clock.check_work()
                    time.sleep(.02)
            stopped = supervision.stop_owned(process, clock.deadline)
            artifacts.require(stopped.get('leaderReaped') and stopped.get('groupGone'), 'Own process cleanup unconfirmed')
            cleanup = _cleanup(root, clock.work_deadline)
            temporary_cleanup = supervision._cleanup_temporary(root, scope)
            report = assemble(root, profile_key=profile_key, compile_passed=compile_passed, compile_command=compile_command)
            report['diagnostics']['cleanup'] = {'ownedProcess': stopped, 'local': cleanup, 'temporary': temporary_cleanup,
                'deviceStatus': 'only per-execution raw receipt, not local removal'}
            clock.check_work()
            supervision.atomic_json(root / 'report.json', report)
            seal = {'state': 'complete_diagnostic_only', 'publicationEligible': False,
                'report': artifacts.artifact(root / 'report.json'), 'sourceFreeze': core.load(root / 'full-native-index.json')['freeze'],
                'originalDeadlineEpoch': original_deadline_epoch, 'timeoutSeconds': timeout,
                'elapsedBeforeSealSeconds': time.monotonic() - clock.started,
                'includesHashingSerializationCleanup': True, 'crossProcessMonotonicTransported': False}
            clock.check_work()
            supervision.atomic_json(scope / 'admission.json', seal)
            clock.check_work()
            return report
        except BaseException:
            # Revoke before any cleanup; after the hard boundary only WNOHANG
            # and signals are allowed, never a new wait or cleanup budget.
            os.replace(scope / 'revoked.json', scope / 'admission.json')
            if root.exists():
                os.replace(scope / 'fallback.json', root / 'report.json')
            if process is not None:
                if clock.hard_expired:
                    supervision._signal_owned_group(process, signal.SIGKILL)
                    process.poll()
                else:
                    supervision.stop_owned(process, clock.deadline)
                    if root.exists():
                        _cleanup(root, clock.deadline)
                        supervision._cleanup_temporary(root, scope)
            raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--task', choices=(t14.TASK, t15.TASK))
    parser.add_argument('--source', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--case', action='append')
    parser.add_argument('--device-serial', default='127.0.0.1:5555')
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--original-deadline-epoch', type=float)
    parser.add_argument('--verify-preparation', type=Path, help='offline hash/closure verification only')
    parser.add_argument('--worker', type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker:
        _worker(args.worker)
        return
    if args.verify_preparation:
        print(json.dumps(verify_preparation(args.verify_preparation)))
        return
    parser.error('task/source/output required') if not (args.task and args.source and args.output) else None
    if args.execute:
        evaluate(task=args.task, source=args.source, output=args.output, execute=True,
            original_deadline_epoch=args.original_deadline_epoch, device_serial=args.device_serial, case_ids=args.case)
    else:
        value = prepare(task=args.task, source=args.source, output=args.output,
            deadline=time.monotonic() + 3600, device_serial=args.device_serial, case_ids=args.case)
        print(json.dumps({'preparedCases': len(value['plans']), 'errors': value['errors'],
            'ready': False, 'deviceStarted': False, 'modelCalled': False}))


if __name__ == '__main__':
    main()
