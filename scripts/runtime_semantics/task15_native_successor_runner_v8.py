"""Task15-only offline-default arbitrary-source entry. No central/readiness edits."""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import inspect
import json
import math
import os
from pathlib import Path
import subprocess
import shutil
import sys
import time

from . import task15_native_successor_v8 as producer
from . import task15_native_successor_guard_v8 as guard
from . import full_native_14_15_runner_v1 as old

ROOT, TASK, PROTOCOL = producer.ROOT, producer.TASK, producer.PROTOCOL
core, artifacts = producer.core, producer.transport.artifacts
MODULE = 'scripts.runtime_semantics.task15_native_successor_runner_v8'


def freeze(root):
    legacy = old.freeze(root)
    value = json.loads(artifacts.bound(legacy))
    (root / 'upstream-v1-source-freeze.json').write_bytes(Path(legacy['path']).read_bytes())
    paths = [Path(__file__), Path(producer.__file__), Path(guard.__file__),
        ROOT / 'scripts/runtime_semantics/task15_prefix_v4.py',
        ROOT / 'scripts/runtime_semantics/Task15BaseAllDevice.cjs'] + list(producer.DIRECTORY.iterdir())
    records = {item['path']: item for item in value['files']}
    for path in sorted(paths):
        if not path.is_file():
            continue
        target = root / 'frozen-sources' / path.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(path.read_bytes())
        records[str(path)] = {'path': str(path), 'bytes': path.stat().st_size, 'sha256': core.sha256(path),
            'snapshot': artifacts.artifact(target)}
    value.update(protocol=PROTOCOL, files=[records[key] for key in sorted(records)],
        upstreamFreeze=artifacts.artifact(root / 'upstream-v1-source-freeze.json'))
    core.write(root / 'source-freeze.json', value)
    return artifacts.artifact(root / 'source-freeze.json')


def prepare(*, task=TASK, source, output, deadline, device_serial='127.0.0.1:5555', case_ids=None):
    artifacts.require(task == TASK, 'Only Task15 ArkTS in this successor')
    root = producer.prior.transport.canonical_output(output)
    artifacts.require(not root.exists(), 'No old evidence/model/patch overwrite')
    source = Path(source).resolve(strict=True)
    artifacts.require(120 < core.remaining_deadline(deadline, 'V8 prepare') <= 3600, 'One remaining budget incl cleanup')
    root.mkdir(parents=True)
    frozen = freeze(root)
    (root / 'canonical-contract.json').write_bytes(producer.CONTRACT.read_bytes())
    (root / 'immutable-task-manifest.json').write_bytes((producer.CONTRACT.parent / 'task.json').read_bytes())
    contract = core.load(producer.CONTRACT)
    selected = set(producer.prior.CASES if case_ids is None else case_ids)
    artifacts.require(selected and selected <= producer.prior.CASES, 'Unknown canonical case')
    mode = producer.choose_probe(source)
    plans, errors = {}, {}
    if mode == 'reviewed_native_prefix':
        producer.prepare_prefix(source=source, output=root / 'prefix', deadline=deadline, serial=device_serial)
        plans['prefix'] = artifacts.artifact(root / 'prefix/plan.json')
    else:
        for case_id in sorted(selected):
            directory = root / 'native' / case_id
            directory.parent.mkdir(exist_ok=True)
            try:
                producer.prepare_feature(source=source, case_id=case_id, output=directory, deadline=deadline, serial=device_serial)
                plans[case_id] = artifacts.artifact(directory / 'plan.json')
            except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
                errors[case_id] = repr(error)
    index = {'protocol': PROTOCOL, 'taskId': TASK, 'source': str(source), 'role': 'agent', 'probe': mode,
        'sourceSha256BeforeExecution': core.directory_digest(source), 'plans': plans, 'errors': errors,
        'selectedCases': sorted(selected), 'freeze': frozen,
        'contract': artifacts.artifact(root / 'canonical-contract.json'),
        'immutableTaskManifest': artifacts.artifact(root / 'immutable-task-manifest.json'),
        'deviceSerial': device_serial, 'deadlineEpochMs': int((time.time()+core.remaining_deadline(deadline, 'V8 preparation seal'))*1000),
        'preparedOnly': True, 'deviceStarted': False, 'modelCalled': False, 'ready': False,
        'routeSelectionIsNotSemanticResult': True, 'arbitrarySourceNotMaterializedFromFinalOrPatch': True}
    core.write(root / 'full-native-index.json', index)
    old.check_freeze(frozen)
    return index


def command(argv, *, log, deadline, lease_serial=None):
    with Path(log).open('w') as stream:
        budget = core.remaining_deadline(deadline, 'V8 own command')
        process = subprocess.Popen(argv, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT,
            env={**os.environ, 'LTB_TASK15_V8_DEADLINE_EPOCH_MS': str(int((time.time()+budget)*1000))})
        try:
            process.wait(timeout=budget)
        except subprocess.TimeoutExpired:
            process.kill()
            raise TimeoutError('Owned command expired; outer supervisor stops owned session')
    result = {'command': argv, 'exit': process.returncode, 'timedOut': False,
        'ownedProcessGroup': os.getpgrp(), 'log': artifacts.artifact(log)}
    core.write(Path(log).with_suffix('.command.json'), result)
    return result


def verify_preparation(root):
    """Verify immutable own inputs/generated bytes. This is NOT native evidence."""
    root = Path(root)
    index = core.load(root / 'full-native-index.json')
    artifacts.require(index['protocol'] == PROTOCOL and index['role'] == 'agent' and index['preparedOnly'] is True,
        'Unknown successor/source role')
    old.check_freeze(index['freeze'])
    contract = json.loads(artifacts.bound(index['contract']))
    immutable = json.loads(artifacts.bound(index['immutableTaskManifest']))
    artifacts.require(immutable['taskId'] == TASK, 'Other immutable task')
    specs = {item['caseId']: item for item in contract['cases']}
    if index['probe'] == 'reviewed_native_prefix':
        artifacts.require(set(index['plans']) == {'prefix'} and not index['errors'], 'Incomplete prefix preparation')
    else:
        artifacts.require(set(index['plans']) | set(index['errors']) == set(index['selectedCases']) and
            not set(index['plans']).intersection(index['errors']), 'Missing/duplicate episode plan')
    verified = []
    for case_id, record in index['plans'].items():
        plan = json.loads(artifacts.bound(record))
        artifacts.require(plan['source'] == index['source'] and plan['role'] == 'agent', 'Different source/role')
        inputs = json.loads(artifacts.bound(plan['inputInventory']))
        digest = hashlib.sha256()
        names = [item['path'] for item in inputs['files']]
        artifacts.require(names == sorted(set(names)), 'Ambiguous source snapshot inventory')
        for item in inputs['files']:
            data = artifacts.bound(item['snapshot'])
            name = Path(item['path'])
            artifacts.require(not name.is_absolute() and '..' not in name.parts and len(data) == item['bytes'] and
                hashlib.sha256(data).hexdigest() == item['sha256'], 'Source snapshot changed')
            encoded = item['path'].encode()
            digest.update(len(encoded).to_bytes(8, 'big')); digest.update(encoded)
            digest.update(len(data).to_bytes(8, 'big')); digest.update(data)
        artifacts.require(digest.hexdigest() == inputs['rootSha256'], 'Input source closure mismatch')
        if case_id == 'prefix':
            artifacts.require(plan['protocol'] == PROTOCOL and json.loads(artifacts.bound(plan['contract'])) == contract and
                plan['candidateRootSha256'] == inputs['rootSha256'] and
                producer.prefix_closure.reviewed_source(TASK, inputs['rootSha256']), 'Unknown common reachable prefix')
            artifacts.bound(plan['driver'])
            verified.extend(index['selectedCases'])
        else:
            artifacts.require(plan['canonicalCase'] == specs[case_id] and plan['fullNativeProtocol'] == PROTOCOL,
                'Changed canonical/native case')
            guard.transport.identity(plan['evaluator'])
            for item in plan['derivedFiles']: artifacts.bound(item)
            scope = json.loads(artifacts.bound(plan['changedBodySourceLedger']))
            indexed = {item['path']: item for item in inputs['files']}
            for item in scope['records']:
                source = artifacts.bound(indexed[item['path']]['snapshot']).decode()
                span = item['sourceSpan']
                # TS offsets count UTF-16 code units, not Python code points.
                body = source.encode('utf-16-le')[span['start']*2:span['end']*2].decode('utf-16-le')
                artifacts.require(item['sourceSha256'] == indexed[item['path']]['sha256'] and
                    hashlib.sha256(body.encode()).hexdigest() == item['bodySha256'], 'Changed app bridge source span/body')
            artifacts.bound(plan['actualSourceBindings'])
            artifacts.require(json.loads(artifacts.bound(plan['immutableTaskManifest'])) == immutable, 'Different upstream refs')
            verified.append(case_id)
    return {'verifiedPreparationOnly': True, 'preparedCases': sorted(verified), 'probe': index['probe'],
        'preparationErrors': index['errors'], 'index': artifacts.artifact(root / 'full-native-index.json'),
        'nativeRuntimeExecuted': False, 'sdkCompiled': False, 'ready': False}


def _prefix_worker(plan_path):
    plan = core.load(Path(plan_path))
    artifacts.require(plan['protocol'] == PROTOCOL and plan['source'] and plan['role'] == 'agent', 'Wrong native prefix plan')
    epoch = min(plan['deadlineEpochMs'], int(os.environ['LTB_TASK15_V8_DEADLINE_EPOCH_MS']))
    remaining = (epoch-time.time()*1000)/1000
    artifacts.require(0 < remaining <= 3600, 'Original prefix work budget exhausted; no reset')
    output = Path(plan_path).parent
    rows, removed = producer.execute_prefix(source=Path(plan['source']), evidence=output,
        deadline=time.monotonic()+remaining, device_serial=plan['deviceSerial'])
    core.write(output / 'prefix-output.json', {'rows': rows, 'removedBinaries': removed,
        'contract': plan['contract'], 'sourceRootSha256': plan['candidateRootSha256'], 'finishedAtEpochMs': int(time.time()*1000)})


def _worker(request_path):
    request = core.load(Path(request_path))
    artifacts.require(os.getpid() == os.getpgrp(), 'Must own session')
    deadline = old.child_local_deadline(request['childBudget'])
    root = Path(request['output'])
    status = {'completed': False}
    try:
        index = core.load(root / 'full-native-index.json')
        old.check_freeze(index['freeze'])
        for _, record in index['plans'].items():
            with open('/tmp/long-term-benchmark-android-full-build.lock', 'a') as lock:
                while True:
                    try:
                        fcntl.flock(lock, fcntl.LOCK_EX|fcntl.LOCK_NB)
                        break
                    except BlockingIOError:
                        time.sleep(min(.05, core.remaining_deadline(deadline, 'shared heavy wait')))
                try:
                    core.require_build_space()
                    old.check_freeze(index['freeze'])
                    plan = json.loads(artifacts.bound(record))
                    directory = Path(record['path']).parent
                    result = command(plan['command'], log=directory / 'host.log', deadline=deadline)
                    artifacts.require(result['exit'] == 0, 'Real build/runtime failed: preserve log; NS, not semantic fail')
                finally:
                    fcntl.flock(lock, fcntl.LOCK_UN)
        status['completed'] = True
    except BaseException as error:
        status['error'] = repr(error)
    old.supervision.atomic_json(Path(request_path).parent / 'worker-finished.json', status)
    while time.monotonic() < deadline:
        time.sleep(min(.05, max(0, deadline-time.monotonic())))


def unavailable(task, source, reason, **kwargs):
    report = old.unavailable(task, source, reason, **kwargs)
    report['runtime'] = PROTOCOL
    return report


def cleanup(root, deadline):
    """Also remove the owned prefix app tree; retain its unique text logs first."""
    base = old._cleanup(root, deadline)
    value = json.loads(artifacts.bound(base))
    directory = Path(root) / 'prefix/base-application'
    if directory.is_dir():
        # Preserve all text evidence; only compiler intermediates are removed.
        for name in ('build', 'preserved-work', 'certificates'):
            for tree in sorted(directory.rglob(name)):
                if not tree.is_dir():
                    continue
                files = []
                for path in sorted(tree.rglob('*')):
                    core.remaining_deadline(deadline, 'own prefix hash/cleanup')
                    artifacts.require(not path.is_symlink(), 'Unknown symlink in own prefix intermediate tree')
                    if path.is_file():
                        item = artifacts.artifact(path)
                        if name != 'certificates' and path.suffix.lower() in ('.log', '.txt', '.json', '.ets', '.ts', '.js', '.cjs'):
                            retained = Path(root) / 'retained-recovery-text' / path.relative_to(root)
                            retained.parent.mkdir(parents=True, exist_ok=True)
                            retained.write_bytes(path.read_bytes())
                            item['retainedText'] = artifacts.artifact(retained)
                        files.append(item)
                entry = {'path': str(tree), 'files': files, 'removed': False}
                value['intermediateTrees'].append(entry)
                core.write(Path(root) / 'prefix-intermediate-cleanup-pending.json', value)
                shutil.rmtree(tree)
                entry['removed'] = True
    core.write(Path(root) / 'outer-cleanup.json', value)
    return artifacts.artifact(Path(root) / 'outer-cleanup.json')


def assemble(root, *, profile_key=None, compile_passed=None, compile_command=''):
    root = Path(root)
    index = core.load(root / 'full-native-index.json')
    old.check_freeze(index['freeze'])
    contract = json.loads(artifacts.bound(index['contract']))
    report = unavailable(TASK, index['source'], 'V8 actual four-control/public review incomplete',
        compile_passed=compile_passed, compile_command=compile_command)
    errors, proposals, bundles, compilations = dict(index['errors']), {}, {}, []
    if index['probe'] == 'reviewed_native_prefix':
        try:
            directory = root / 'prefix'
            raw = core.load(directory / 'base-device/report.json')
            build = core.load(directory / 'base-application/application-build.json')
            removed = core.load(directory / 'prefix-output.json')['removedBinaries']
            hap = build['hap']
            artifacts.require(any(item['sha256'] == hap['sha256'] and item['bytes'] == hap['bytes'] for item in removed) and
                not Path(hap['path']).exists(), 'Prefix HAP cleanup lacks matching hash/removal evidence')
            inputs = core.load(directory / 'input-inventory.json')
            report['provenance'] = {'candidateSource': index['source'], 'candidateRootSha256': inputs['rootSha256'],
                'productionSourceSnapshots': {item['path']: item['snapshot'] for item in inputs['files'] if item['path'].startswith('entry/src/main/')},
                'sourceFreeze': index['freeze'], 'immutableTaskManifest': index['immutableTaskManifest']}
            specs = {case['caseId']: case for case in contract['cases']}
            for row in raw['semantic']['cases']:
                if row['caseId'] in index['selectedCases']:
                    proposals[row['caseId']] = producer.prefix_admission.entry_row(row, specs[row['caseId']],
                        directory / 'base-device/report.json', build['sources'])
            report['semantic']['cases'] = [proposals.get(row['caseId'], row) for row in report['semantic']['cases']]
            report['runtimeCompile'] = {'passed': build['passed'], 'scope': 'original app prefix runtime HAP; separate benchmark application compile'}
        except (OSError, ValueError, KeyError, IndexError, StopIteration) as error:
            errors['prefix'] = repr(error)
    else:
        for case_id, record in index['plans'].items():
            try:
                directory = Path(record['path']).parent
                bundle = old.retained15.native_bundle(directory)
                data = guard.transport.envelope(bundle, contract)
                bundles[case_id] = bundle
                compilations.append(data['build']['runtimeCompile'])
                proposals[case_id] = guard.admit(bundle, contract, profile_key=profile_key)
            except (OSError, ValueError, KeyError, IndexError, StopIteration) as error:
                errors[case_id] = repr(error)
        report['provenance'] = {'candidateSource': index['source'], 'sourceFreeze': index['freeze'],
            'sourceParameterizedPlans': index['plans'], 'rawBundles': bundles, 'immutableTaskManifest': index['immutableTaskManifest']}
        if compilations:
            report['runtimeCompile'] = {'passed': len(compilations) == len(index['selectedCases']) and all(
                item.get('passed') is True for item in compilations), 'records': compilations, 'scope': 'evaluator HAP only'}
    for field, status in (('passed','pass'),('failed','fail'),('notScored','not_scored')):
        report['semantic'][field] = sum(row['status'] == status for row in report['semantic']['cases'])
    report['diagnostics'].update(probe=index['probe'], rawAdmissionErrors=errors, independentProposals=proposals,
        matchedFourControls=False, publicFeaturePolicyRegistered=False)
    from scripts.run_runtime_transition_matrix import validate_report
    validate_report(report, contract)
    report['diagnostics']['publicReportValidated'] = True
    return report


def evaluate(*, source, output, task=TASK, final_output=None, **kwargs):
    target = producer.prior.transport.canonical_output(final_output) if final_output is not None else None
    artifacts.require(target is None or not target.exists(), 'Do not overwrite a formal/model report')
    text = inspect.getsource(old.evaluate)
    text = producer.prior.transport.replace(text,
        "        supervision.atomic_json(scope / 'fallback.json', fallback)",
        "        supervision.atomic_json(scope / 'fallback.json', fallback)\n        if _final_output is not None: supervision.atomic_json(scope / 'formal-fallback.json', fallback)")
    text = producer.prior.transport.replace(text,
        "            supervision.atomic_json(root / 'report.json', report)",
        "            supervision.atomic_json(root / 'report.json', report)\n            if _final_output is not None: supervision.atomic_json(_final_output, report)")
    text = producer.prior.transport.replace(text,
        "                'includesHashingSerializationCleanup': True, 'crossProcessMonotonicTransported': False}",
        "                'includesHashingSerializationCleanup': True, 'crossProcessMonotonicTransported': False,\n                'formalOutput': artifacts.artifact(_final_output) if _final_output is not None else None}")
    text = producer.prior.transport.replace(text,
        "            os.replace(scope / 'revoked.json', scope / 'admission.json')",
        "            os.replace(scope / 'revoked.json', scope / 'admission.json')\n            if _final_output is not None: os.replace(scope / 'formal-fallback.json', _final_output)")
    namespace = {**old.evaluate.__globals__, 'MODULE': MODULE, 'prepare': prepare, 'assemble': assemble, '_cleanup': cleanup,
        'unavailable': unavailable, '_final_output': target}
    exec(compile(text, str(Path(__file__))+':same-reviewed-deadline-supervisor', 'exec'), namespace)
    return namespace['evaluate'](task=task, source=source, output=output, **kwargs)


def score(*, platform, source, base_source=None, final_source=None, output, compile_passed=None,
          compile_command='', timeout=3600, device_serial='127.0.0.1:5555', execute=False, original_deadline_epoch=None):
    artifacts.require(platform == 'arkts' and type(timeout) in (int,float) and math.isfinite(timeout) and 0 < timeout <= 3600,
        'Task15 ArkTS one 0<budget<=3600 only')
    output = producer.prior.transport.canonical_output(output)
    artifacts.require(not output.exists(), 'Do not overwrite a formal/model report')
    if not execute:
        report = unavailable(TASK, source, 'V8 staged only; no hardware authorization/public four-control readiness',
            compile_passed=compile_passed, compile_command=compile_command)
        from scripts.run_runtime_transition_matrix import validate_report
        validate_report(report, core.load(producer.CONTRACT))
        report['diagnostics'].update(publicReportValidated=True, hardwareExecuted=False, timeoutBudgetSeconds=timeout)
        old.supervision.atomic_json(output, report)
        return report
    artifacts.require(original_deadline_epoch is not None and math.isfinite(original_deadline_epoch), 'Original authorized epoch required')
    root = Path(output).with_name(Path(output).stem+'-v8-runtime')
    report = evaluate(source=source, output=root, timeout=timeout, device_serial=device_serial, execute=True,
        original_deadline_epoch=original_deadline_epoch, compile_passed=compile_passed, compile_command=compile_command,
        final_output=output)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--case', action='append')
    parser.add_argument('--device-serial', default='127.0.0.1:5555')
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--original-deadline-epoch', type=float)
    parser.add_argument('--verify-preparation', type=Path)
    parser.add_argument('--worker', type=Path, help=argparse.SUPPRESS)
    parser.add_argument('--prefix-worker', type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.verify_preparation:
        print(json.dumps(verify_preparation(args.verify_preparation)))
        return
    if args.worker:
        return _worker(args.worker)
    if args.prefix_worker:
        return _prefix_worker(args.prefix_worker)
    if not(args.source and args.output):
        parser.error('--source/--output required')
    if args.execute:
        value = evaluate(source=args.source, output=args.output, execute=True, original_deadline_epoch=args.original_deadline_epoch,
            device_serial=args.device_serial, case_ids=args.case)
    else:
        value = prepare(source=args.source, output=args.output, deadline=time.monotonic()+3600,
            device_serial=args.device_serial, case_ids=args.case)
    print(json.dumps({'probe': value.get('probe'), 'preparedCases': len(value.get('plans',{})),
        'errors': value.get('errors',{}), 'ready':False, 'modelCalled':False}))


if __name__ == '__main__':
    main()
