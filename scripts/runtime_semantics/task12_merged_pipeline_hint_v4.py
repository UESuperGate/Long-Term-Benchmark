"""Unregistered prospective four-pole factory and candidate-only source scorer.

No historical receipt adoption, model call, nested evaluator/session or ready flag.
Public policy registration/review remains coordinator-owned.
"""

import argparse
import json
import math
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time
import traceback
import uuid

from . import task12_arkts_merged_runtime_v4 as owner
from . import task12_arkts_merged_protocol_hint_v4 as proof
from . import task12_arkts_merged_build_v2 as builder
from . import task12_merged_inputs_v1 as inputs
from . import task12_merged_toolchain_v1 as tools
from . import task15_deadline_v4 as timer
from . import task12_merged_supervisor_v1 as supervisor

MODULE = 'scripts.runtime_semantics.task12_merged_pipeline_hint_v4'
POLICY = 'arkts.task12.merged-source-bound.hint-profile-v4'
RECEIPT = 'task12.merged-reviewed-controls.hint-profile-v4'
LABELS = ('base', 'final', 'negative', 'positive')
EXPECTED = {'base': (0, 10, 0), 'final': (10, 0, 0), 'negative': (0, 10, 0), 'positive': (10, 0, 0)}
BASE_SHA = 'dcdfee285d5cd027b43abe78850350113ff7258a0eb0f3acf0d12ebd37f663c9'
FINAL_SHA = 'aad374ecce30168ede22c209f5a4fef111ac4d510bbb8b3c8b1ad457008d7183'


def require(value, reason):
    if not value:
        raise ValueError('Task12 merged pipeline: ' + reason)


def records(deadline):
    paths = [Path(__file__), Path(inputs.__file__), Path(tools.__file__), Path(owner.__file__), Path(timer.__file__), Path(supervisor.__file__),
             Path(tools.validate_versions.__code__.co_filename),
             Path(__file__).with_name('task12_arkts_merged_reader_v2.py'),
             Path(__file__).with_name('task12_arkts_merged_reader_v1.py'),
             proof.ROOT / 'scripts/run_runtime_transition_matrix.py',
             proof.ROOT / 'scripts/run_task_runtime_tests.py',
             Path(__file__).with_name('task12_arkts_runtime_admission.py'),
             Path(__file__).with_name('task12_formal_agent.py'),
             Path(__file__).with_name('task12_formal_agent_hint_v4.py'),
             proof.ROOT / 'scripts/replay_task12_archived_agent_hint_v4.py',
             Path(__file__).with_name('withdrawn_owner_boundaries_v1.py'),
             Path(__file__).with_name('withdrawn_sdk_boundaries_v1.py')]
    values = proof.producer_records(deadline) + [proof.file_record(p, deadline) for p in paths]
    return sorted({item['path']: item for item in values}.values(), key=lambda item: item['path'])


def budget(deadline):
    seconds = deadline - time.monotonic()
    require(0 < seconds <= 3600, 'one original remaining budget exhausted')
    return {'remainingSeconds': seconds, 'deadlineEpochMs': int((time.time() + seconds) * 1000)}


def make_phase(root, source, label, role, deadline):
    phase = root / 'phases' / label
    phase.mkdir(parents=True, exist_ok=False)
    target = root / 'owned-sources' / uuid.uuid4().hex
    proof.write(phase / 'prepared.json', {'source': str(target), 'phase': str(phase)})
    before = inputs.inventory(source, deadline)
    copied = inputs.copy(source, target, before, deadline)
    manifest = {'original': before, 'executed': copied,
                'bytes': proof.inventory(target, deadline),
                'archive': inputs.archive(target, phase / 'source-input.tar.gz', copied, deadline)}
    proof.write(phase / 'inputs.json', manifest)
    return {'label': label, 'role': role, 'source': str(target), 'originalSource': str(Path(source).resolve()),
            'output': str(phase), 'inputManifest': proof.file_record(phase / 'inputs.json', deadline)}


def private_ref(record, candidate, deadline):
    require(isinstance(record, dict) and set(record) == {'path', 'bytes', 'sha256'} and
            type(record['bytes']) is int and 0 < record['bytes'] <= 32 * 1024 * 1024,
            'exact bounded private receipt record required')
    declared = Path(record['path'])
    require(declared.is_absolute() and not declared.is_symlink() and
            all(not parent.is_symlink() for parent in declared.parents), 'receipt path must not alias a symlink')
    path = declared.resolve()
    require(any(path.is_relative_to(proof.ROOT / directory) for directory in ('experiment_results', 'eval_runs')) and
            not path.is_relative_to(Path(candidate).resolve()), 'receipt is not private evaluator evidence')
    require(proof.file_record(path, deadline) == record, 'private receipt bytes/SHA differ')
    envelope = proof.load(path)
    require(type(envelope.get('timeoutSeconds')) in (float, int) and type(envelope.get('elapsedSeconds')) in (float, int) and
            0 < envelope['elapsedSeconds'] <= envelope['timeoutSeconds'] <= 3600,
            'calibration exceeded its one explicit independent budget')
    require(envelope.get('state') == 'complete' and envelope.get('allFinalizationInsideOriginalBudget') is True and
            envelope.get('ownedCleanup', {}).get('complete') is True and
            envelope.get('resources', {}).get('released') is True,
            'partial/revoked/unclean calibration cannot be reused')
    receipt = envelope.get('result', {})
    require(receipt.get('protocol') == RECEIPT and receipt.get('freshControlExecutions') is True and
            receipt.get('controlsReused') is False and receipt.get('modelCalled') is False and
            receipt.get('implementation') == records(deadline), 'receipt schema/policy/source revision differs')
    require(receipt.get('contract') == proof.file_record(proof.CONTRACT, deadline), 'receipt contract changed')
    require(set(receipt.get('reports', {})) == set(LABELS), 'four controls missing; no implicit fresh fallback')
    origin = path.with_suffix('.merged-pipeline-evidence')
    require(envelope.get('schemaVersion') == supervisor.SCHEMA, 'not the new owned calibration supervisor')
    finalized = proof.load(proof.checked(receipt['parentFinalization'], deadline))
    require(Path(receipt['parentFinalization']['path']) == origin / 'parent-finalized.json' and
            finalized['requestId'] == envelope['requestId'] and finalized['resources'] == envelope['resources'] and
            0 < finalized['elapsedSeconds'] <= finalized['timeoutSeconds'] <= 3600 and
            proof.load(proof.checked(finalized['cleanup'], deadline)) == envelope['ownedCleanup'] and
            finalized['publicAssessment'] == receipt['publicAssessment'], 'original within-budget finalization/cleanup unbound')
    q = proof.load(origin / 'request.json')
    require(q['mode'] == 'calibration' and q['requestId'] == envelope['requestId'] and
            q['implementation'] == receipt['implementation'] and q['immutableSources'] == receipt['immutableSources'] and
            len(q['phases']) == 4 and [item['label'] for item in q['phases']] == list(LABELS),
            'receipt not bound to the original fresh four-pole request')
    launched = proof.load(origin / 'worker.launch.json')
    status = proof.load(origin / 'worker.process.json')
    require(launched['command'] == [sys.executable, '-B', '-m', MODULE, '--worker', str(origin / 'request.json')] and
            status.get('leaderReaped') is True and status.get('groupGone') is True and status.get('unsafe') is False,
            'original factory worker execution/quiescence missing')
    assessed = proof.load(proof.checked(receipt['publicAssessment'], deadline))
    require(assessed.get('validated') is True and len(assessed['results']) == 4 and
            all(item.get('publicPassed') is True for item in assessed['results']), 'original full public proof missing')
    for phase, actual in zip(q['phases'], assessed['results']):
        label = phase['label']
        report = proof.load(proof.checked(receipt['reports'][label], deadline))
        require(actual['report'] == receipt['reports'][label] and
                tuple(actual['counts'][k] for k in ('passed', 'failed', 'notScored')) == EXPECTED[label] and
                report['role'] == (label if label in ('base', 'final') else 'agent') and
                envelope['ownedCleanup']['sources'][label]['complete'] is True and
                all(envelope['resources']['remoteCleanup'][label].get(k) is True for k in
                    ('ownedAppUninstalled', 'reverseRemoved', 'remoteFilesRemoved')),
                'original control/public/remote-cleanup receipt incomplete')
    return receipt


def receipt_record(path, deadline):
    path = Path(path)
    require(path.is_absolute() and not path.is_symlink() and all(not p.is_symlink() for p in path.parents),
            'parent receipt path is a symlink/alias')
    with inputs.regular(path) as stream:
        require(0 < os.fstat(stream.fileno()).st_size <= 16 * 1024 * 1024, 'private receipt outside bounded size')
        value = inputs.digest_stream(stream, deadline)
    require(0 < value['bytes'] <= 16 * 1024 * 1024, 'private receipt grew beyond bounded size')
    return {'path': str(path.resolve()), **value}


def acquire(root, clock, request):
    return owner._acquire(root, clock, request)


def release(claim, root, clock):
    if claim is None:
        return {'released': True, 'acquired': False}
    if claim['pid'] != os.getpid() or claim['root'] != str(root) or owner._RETAINED_CLAIMS.get(str(root)) is not claim:
        return {'released': False, 'reason': 'foreign claim untouched'}
    proof.check(clock.deadline)
    q = proof.load(root / 'request.json')
    workers = claim['workers']
    actual = [item for item in workers if item['label'] == 'worker']
    if len(actual) != 1 or actual[0]['command'] != [sys.executable, '-B', '-m', MODULE, '--worker', str(root / 'request.json')] or \
            q['requestId'] != claim['requestId'] or q['source'] != claim['source'] or q['serial'] != claim['serial'] or \
            proof.file_record(Path(__file__), clock.deadline) not in q['implementation'] or \
            any(not item.get('status') or item['status'].get('leaderReaped') is not True or
                item['status'].get('groupGone') is not True or item['status'].get('unsafe') for item in workers):
        return {'released': False, 'reason': 'owned worker/source quiescence unproven'}
    remote = {}
    for item in q['phases']:
        phase = Path(item['output'])
        marker = phase / 'native-started.json'
        if not marker.exists():
            remote[item['label']] = {'status': 'not_applicable_never_started', 'ownedAppUninstalled': 'not_applicable'}
            continue
        try:
            started = proof.load(marker)
            require(started['pid'] == actual[0]['pid'] and started['source'] == item['source'] and
                    started['request'] == proof.file_record(phase / 'phase-request.json', clock.deadline) and
                    started['requestId'] == q['requestId'] and
                    started['command'] == [str(tools.NODE), str(proof.RUNNER), str(phase / 'native-config.json')],
                    'native-start marker differs')
            cleanup = proof.load(phase / 'native/runtime.native.json')['diagnostics']['cleanup']
            require(all(cleanup.get(k) is True for k in ('ownedAppUninstalled', 'reverseRemoved', 'remoteFilesRemoved')),
                    'started native remote cleanup unknown')
            remote[item['label']] = cleanup
        except Exception as error:
            return {'released': False, 'remoteCleanup': 'unknown', 'reason': repr(error), 'leaseRetained': True}
    lease = claim['lease']
    path = Path(lease['path'])
    if path != owner.lease_path(claim['serial']) or not path.is_dir() or path.is_symlink():
        return {'released': False, 'reason': 'canonical lease missing/changed'}
    stat = path.stat()
    if stat.st_ino != lease['inode'] or stat.st_ctime_ns != lease['ctimeNs'] or list(path.iterdir()):
        return {'released': False, 'reason': 'foreign/replaced lease untouched'}
    path.rmdir()
    claim['buildLock'].__exit__(None, None, None)
    owner._RETAINED_CLAIMS.pop(str(root), None)
    return {'released': True, 'remoteCleanup': remote}


def run_phase(item, request, deadline):
    phase, source = Path(item['output']), Path(item['source'])
    manifest = proof.load(proof.checked(item['inputManifest'], deadline))
    require(inputs.inventory(source, deadline) == manifest['executed'], 'source input bytes/type/mode changed')
    phase_request = {**item, 'requestId': request['requestId'], 'serial': request['serial'], 'budget': budget(deadline)}
    proof.write(phase / 'phase-request.json', phase_request)
    (phase / 'owned-temporary').mkdir()
    started = time.monotonic()
    build = builder.build_application(source=source, output=phase / 'application-build',
                                      temporary=phase / 'owned-temporary', deadline=deadline)
    code = "const fs=require('fs'),J=require(process.argv[1]);process.stdout.write(JSON.stringify(J.parse(fs.readFileSync(process.argv[2],'utf8')).app));"
    with (phase / 'identity.json').open('x') as stream:
        subprocess.run([str(tools.NODE), '-e', code, str(proof.JSON5), str(source / 'AppScope/app.json5')],
                       stdout=stream, stderr=subprocess.STDOUT, timeout=max(.001, deadline - time.monotonic()), check=True)
    bundle = proof.load(phase / 'identity.json')['bundleName']
    require(isinstance(bundle, str) and bundle and all(c in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.' for c in bundle),
            'unknown application identity')
    # Read-only readiness has no nested session or lock; the parent owns both resources.
    owner.support.wait_hdc_connected(serial=request['serial'], deadline=deadline, log=phase / 'hdc-readiness.log')
    config = {'source': str(source), 'bundle': bundle, 'hap': build['hap']['path'],
              'buildReport': str(phase / 'application-build/application-build.json'), 'contract': str(proof.CONTRACT),
              'hdc': str(tools.HDC), 'serial': request['serial'], 'port': 18743,
              'output': str(phase / 'native'), 'remainingSeconds': deadline - time.monotonic()}
    proof.write(phase / 'native-config.json', config)
    owner.atomic(phase / 'native-started.json', {'pid': os.getpid(), 'source': str(source), 'requestId': request['requestId'],
                 'request': proof.file_record(phase / 'phase-request.json', deadline),
                 'command': [str(tools.NODE), str(proof.RUNNER), str(phase / 'native-config.json')]})
    with (phase / 'native.log').open('x') as stream:
        subprocess.run([str(tools.NODE), str(proof.RUNNER), str(phase / 'native-config.json')], stdout=stream,
                       stderr=subprocess.STDOUT, timeout=max(.001, deadline - time.monotonic()), check=True)
    require(inputs.inventory(source, deadline) == manifest['executed'], 'source mode/type/bytes changed during runtime')
    result = {'workerPid': os.getpid(), 'startedLocal': started, 'finishedLocal': time.monotonic(),
              'inputManifest': item['inputManifest'], 'label': item['label'], 'source': str(source)}
    proof.write(phase / 'execution.json', result)
    return proof.file_record(phase / 'execution.json', deadline)


def production_sources(manifest, deadline):
    """Expose compiled production inputs, not report-supplied source claims."""
    executed = manifest['executed']
    inputs.verify_archive(manifest['archive'], executed, deadline)
    source = Path(executed['source'])
    require(source.is_absolute() and '..' not in source.parts and
            manifest['bytes']['source'] == str(source), 'production source root differs')
    byte_files = manifest['bytes']['files']
    by_path = {item['path']: item for item in byte_files}
    require(len(by_path) == len(byte_files), 'duplicate byte-inventory source')
    sources = []
    for item in executed['entries']:
        proof.check(deadline)
        if item['type'] != 'file':
            continue
        relative = Path(item['path'])
        require(not relative.is_absolute() and '..' not in relative.parts and
                str(relative) == item['path'], 'unsafe production source path')
        if relative.parts[:3] != ('entry', 'src', 'main'):
            continue
        record = {key: item[key] for key in ('path', 'bytes', 'sha256')}
        require(type(record['bytes']) is int and record['bytes'] >= 0 and
                isinstance(record['sha256'], str) and len(record['sha256']) == 64 and
                all(c in '0123456789abcdef' for c in record['sha256']) and
                by_path.get(item['path']) == record, 'production source bytes/hash differ')
        sources.append({**record, 'path': str(source / relative)})
    require(sources, 'no archived entry/src/main production inputs')
    return sorted(sources, key=lambda item: item['path'])


def validate_production_sources(report, manifest, deadline):
    expected = production_sources(manifest, deadline)
    require(report['provenance'].get('productionSources') == expected,
            'report production provenance differs from archived compiled inputs')
    for row in report['semantic']['cases']:
        proof.check(deadline)
        require('productionSources' not in row or row['productionSources'] == expected,
                'row production provenance overrides actual compiled inputs')
    return expected


def verify_artifacts(report, contract, deadline):
    require(report['taskId'] == contract['taskId'] == '12_report_room' and report['platform'] == 'arkts' and
            report['observationMode'] == 'runtime_state_transition', 'wrong Task12 native report')
    evidence = report['provenance']['runtimeEvidence']
    require(evidence['policyId'] == POLICY and evidence['implementation'] == records(deadline), 'unreviewed producer revision')
    raw = proof.load(proof.checked(evidence['raw'], deadline))
    phase = Path(evidence['raw']['path']).parent.parent
    request_path = phase.parent.parent / 'request.json'
    require(evidence.get('executionRequest') == proof.file_record(request_path, deadline), 'actual outer request unbound')
    request = proof.load(request_path)
    bound_phase = [item for item in request['phases'] if item['output'] == str(phase)]
    require(len(bound_phase) == 1 and request['implementation'] == evidence['implementation'] and
            request['requestId'] == evidence.get('requestId') and bound_phase[0]['role'] == report['role'] and
            bound_phase[0]['inputManifest'] == evidence['inputManifest'] and
            bound_phase[0]['originalSource'] == report['provenance']['candidateSource'], 'actual phase/source/role metadata unbound')
    manifest = proof.load(proof.checked(evidence['inputManifest'], deadline))
    validate_production_sources(report, manifest, deadline)
    require(raw['nativeProtocol'] == proof.PROTOCOL and raw['semantic'] == report['semantic'] and
            raw['source'] == manifest['executed']['source'] == report['provenance']['executedSource'],
            'raw/source/semantic report binding differs')
    if request['mode'] == 'calibration':
        require([item['label'] for item in request['phases']] == list(LABELS) and
                report.get('publication', {}).get('eligible') is False, 'control diagnostics cannot claim model publication')
        immutable = request['immutableSources']['base' if bound_phase[0]['label'] in ('base', 'negative') else 'final']
        require(manifest['original'] == immutable and manifest['executed']['entries'] == immutable['entries'],
                'fresh control source mapping differs')
    else:
        require(request['mode'] == 'candidate' and len(request['phases']) == 1 and
                evidence.get('reviewedControlReceipt') == request['controlReceipt'], 'candidate lacks exact private calibration binding')
    for key, path in (('runner', proof.RUNNER), ('facts', proof.FACTS), ('contract', proof.CONTRACT),
                      ('config', phase / 'native-config.json')):
        require(raw['provenance'][key] == proof.file_record(path, deadline), 'native provenance differs: ' + key)
    require(proof.file_record(proof.CONTRACT, deadline)['sha256'] == proof.CONTRACT_SHA and
            proof.load(proof.CONTRACT) == contract, 'canonical contract changed')
    build = proof.load(proof.checked(raw['compile']['build'], deadline))
    require(build['source'] == raw['source'] and build.get('productionInputModesUnchanged') is True and
            build['sourceInputs'] == manifest['executed'] and all(build.get(k) is True for k in
            ('passed', 'productionUnchanged', 'copiedProductionUnchanged', 'temporaryProjectRemoved')),
            'actual compiled source bytes/type/mode continuity missing')
    config = proof.load(phase / 'native-config.json')
    require(raw['compile']['hap'] == build['hap'] and config['hap'] == build['hap']['path'] and
            config['source'] == raw['source'] and config['bundle'] == raw['bundle'] and
            config['serial'] == request['serial'] and config['hdc'] == str(tools.HDC) and
            config['port'] == raw['executionConfig']['port'] and
            build['effectiveEnvironment']['JAVA_HOME'] == str(tools.JAVA_HOME) and
            build['command'][0] == str(tools.NODE) and build['effectiveProduct']['runtimeOS'] == 'OpenHarmony' and
            build['effectiveProduct']['compileSdkVersion'] == 23, 'actual app/binary/config/toolchain differs')
    if Path(build['hap']['path']).exists():
        proof.checked(build['hap'], deadline)
        proof.validate_envelope(raw, source=Path(raw['source']), source_inventory=manifest['bytes'],
                build_path=Path(raw['compile']['build']['path']), config_path=phase / 'native-config.json', deadline=deadline)
    else:
        from .task12_arkts_merged_reader_v2 import binary_free_history
        binary_free_history(phase, raw, build, config, deadline)
    if Path(raw['source']).exists():
        require(inputs.inventory(raw['source'], deadline) == manifest['executed'], 'current executed source changed')
    else:
        removed = proof.load(proof.checked(evidence['sourceCleanup'], deadline))
        require(removed.get('complete') is True and removed.get('root') == raw['source'], 'deleted input lacks actual cleanup receipt')
        source_files = {str(Path(raw['source']) / item['path']): item for item in manifest['executed']['entries'] if item['type'] == 'file'}
        seen = set()
        with proof.checked(removed['hashLedger'], deadline).open() as stream:
            for line in stream:
                proof.check(deadline)
                item = json.loads(line)
                require(item['path'] in source_files and item['path'] not in seen and
                        all(item[key] == source_files[item['path']][key] for key in ('bytes', 'sha256')),
                        'deleted source journal bytes/path differ')
                if 'retained' in item:
                    proof.checked(item['retained'], deadline)
                seen.add(item['path'])
        require(seen == set(source_files) and removed['filesRemoved'] == len(seen), 'deleted source journal incomplete')
    result = subprocess.run([str(tools.NODE), '-e', proof.NODE_VERIFY, str(proof.FACTS), evidence['raw']['path'],
            str(proof.CONTRACT), raw['bundle'], str(phase / 'native')], capture_output=True, text=True,
            timeout=max(.001, deadline - time.monotonic()), check=True)
    checked = json.loads(result.stdout)
    require(checked.get('validated') is True and checked['counts']['notScored'] == 0, 'full raw/invariant recomputation incomplete')
    return checked


def validate_report_evidence(report, contract, deadline=None):
    # The parent-isolated validator receives one remaining budget and owns the hard cap.
    # A standalone call must also supply an explicit budget, never a new default 120s.
    selected = deadline if deadline is not None else _VALIDATION_DEADLINE
    if selected is None:
        # Independent public recheck only. A foreign enclosing timer is rejected,
        # never overridden or silently extended by this fresh verification budget.
        with timer.OverallDeadline(120) as clock:
            return validate_report_evidence(report, contract, deadline=clock.work_deadline)
    evidence = report['provenance']['runtimeEvidence']
    request = proof.load(proof.checked(evidence['executionRequest'], selected))
    if request['mode'] == 'calibration':
        context = verify_calibration_context(report, contract, selected)
        label = next(item['label'] for item in request['phases'] if item['source'] == report['provenance']['executedSource'])
        return context['assessments'][label]
    return verify_candidate_context(report, contract, selected)['candidate']


def validate_entry_failure(row, report, used_observation_ids, contract=None):
    matching = [item for item in report['semantic']['cases'] if item['caseId'] == row['caseId']]
    require(len(matching) == 1 and matching[0] == row, 'entry row differs from actual report/raw row')
    checked = validate_report_evidence(report, contract)
    actual = [item for item in checked['cases'] if item['caseId'] == row['caseId']]
    require(len(actual) == 1 and actual[0]['status'] == row['status'] == 'fail', 'common entry failure not independently observed')
    identities = {row['caseRunId'] + ':' + str(point['sequence']) for point in row['checkpoints']}
    require(identities and not identities.intersection(used_observation_ids), 'common entry observations reused')
    used_observation_ids.update(identities)


_VALIDATION_DEADLINE = None


def active_validation_deadline():
    """Public adapter hook: this is already child-local, never a parent absolute."""
    require(_VALIDATION_DEADLINE is not None, 'no enclosing pipeline validation lifetime')
    proof.check(_VALIDATION_DEADLINE)
    return _VALIDATION_DEADLINE


def validate_worker(path):
    global _VALIDATION_DEADLINE
    q = proof.load(path)
    deadline = timer.child_local_deadline(q['budget'])
    _VALIDATION_DEADLINE = deadline
    # Running as -m has a different module name; public routing must find this same context.
    sys.modules.setdefault(MODULE, sys.modules[__name__])
    from scripts.run_runtime_transition_matrix import validate_report
    result = []
    for record in q['reports']:
        proof.check(deadline)
        report = proof.load(proof.checked(record, deadline))
        checked = verify_artifacts(report, proof.load(proof.CONTRACT), deadline)
        validate_report(report, proof.load(proof.CONTRACT))  # No bypass when the new route is not registered.
        result.append({'report': record, 'counts': checked['counts'], 'publicPassed': True,
                       'caseRunIds': [row['caseRunId'] for row in report['semantic']['cases']],
                       'nativeNonce': proof.load(proof.checked(report['provenance']['runtimeEvidence']['raw'], deadline))['nativeNonce']})
    proof.write(Path(q['output']), {'validated': True, 'results': result})


def make_report(item, request, deadline):
    phase = Path(item['output'])
    raw_path = phase / 'native/runtime.native.json'
    raw = proof.load(raw_path)
    manifest = proof.load(proof.checked(item['inputManifest'], deadline))
    return {'taskId': '12_report_room', 'platform': 'arkts', 'role': item['role'],
            'observationMode': 'runtime_state_transition', 'semantic': raw['semantic'],
            'provenance': {'candidateSource': item['originalSource'], 'executedSource': item['source'],
                'productionSources': production_sources(manifest, deadline),
                'runtimeEvidence': {'policyId': POLICY, 'raw': proof.file_record(raw_path, deadline),
                    'inputManifest': item['inputManifest'], 'implementation': request['implementation'],
                    'executionRequest': proof.file_record(phase.parent.parent / 'request.json', deadline),
                    'executionResult': proof.file_record(phase.parent.parent / 'worker-result.json', deadline),
                    'executionWorker': proof.file_record(phase.parent.parent / 'worker.launch.json', deadline),
                    'workerQuiescence': proof.file_record(phase.parent.parent / 'worker.process.json', deadline),
                    'requestId': request['requestId'],
                    **({'reviewedControlReceipt': request['controlReceipt']} if request['mode'] == 'candidate' else {}),
                    'sourceCleanup': None}}, 'diagnostics': {'runtimeCompile': {'passed': True,
                        'scope': 'production runtime HAP; not benchmark standalone compile'}},
            'publication': {'eligible': False, 'reason': 'Await complete prospective public four-control review'}}


def execution_window(report, deadline):
    evidence = report['provenance']['runtimeEvidence']
    request = proof.load(proof.checked(evidence['executionRequest'], deadline))
    root = Path(request['output'])
    require(Path(evidence['executionRequest']['path']) == root / 'request.json' and
            request['implementation'] == records(deadline), 'actual factory request/policy changed')
    result = proof.load(proof.checked(evidence['executionResult'], deadline))
    launched = proof.load(proof.checked(evidence['executionWorker'], deadline))
    status = proof.load(proof.checked(evidence['workerQuiescence'], deadline))
    require(Path(evidence['executionResult']['path']) == root / 'worker-result.json' and
            Path(evidence['executionWorker']['path']) == root / 'worker.launch.json' and
            Path(evidence['workerQuiescence']['path']) == root / 'worker.process.json' and
            launched['command'] == [sys.executable, '-B', '-m', MODULE, '--worker', str(root / 'request.json')] and
            status.get('pid') == launched['pid'] == result['workerPid'] and status.get('leaderReaped') is True and
            status.get('groupGone') is True and status.get('unsafe') is False, 'actual single worker source/quiescence differs')
    before, after = tools.compare(result['toolchainBefore'], result['toolchainAfter'], deadline)
    require(before['workerPid'] == after['workerPid'] == launched['pid'] and
            len(result['phases']) == len(request['phases']), 'toolchain capture was not inside actual same worker')
    previous = before['finishedLocal']
    for item, record in zip(request['phases'], result['phases']):
        phase = Path(item['output'])
        require(phase.parent == root / 'phases' and Path(record['path']) == phase / 'execution.json', 'phase escapes original root')
        actual = proof.load(proof.checked(record, deadline))
        require(actual['workerPid'] == before['workerPid'] and actual['source'] == item['source'] and
                actual['inputManifest'] == item['inputManifest'] and actual['label'] == item['label'] and
                previous <= actual['startedLocal'] < actual['finishedLocal'] <= after['startedLocal'],
                'prospective phase clocks/source do not lie in one real worker capture window')
        marker = proof.load(phase / 'native-started.json')
        require(marker['pid'] == before['workerPid'] and marker['requestId'] == request['requestId'] and
                marker['source'] == item['source'] and marker['request'] == proof.file_record(phase / 'phase-request.json', deadline) and
                marker['command'] == [str(tools.NODE), str(proof.RUNNER), str(phase / 'native-config.json')],
                'actual native dispatch/source binding differs')
        previous = actual['finishedLocal']
    return request, result, before, after


def verify_calibration_context(report, contract, deadline):
    """Four complete debug controls, no recursive public calls and no receipt cycle."""
    request, result, before, after = execution_window(report, deadline)
    require(request['mode'] == 'calibration' and [item['label'] for item in request['phases']] == list(LABELS),
            'not one original four-pole calibration request')
    for label, source, sha in (('base', request['base'], BASE_SHA), ('final', request['final'], FINAL_SHA)):
        require(proof.inventory(Path(source), deadline)['sha256'] == sha and
                inputs.inventory(source, deadline) == request['immutableSources'][label],
                'current immutable bytes/type/mode inputs differ')
    assessments, reports, identities, nonces, sources = {}, {}, set(), set(), set()
    for item in request['phases']:
        label = item['label']
        path = Path(item['output']) / 'report.json'
        current = proof.load(path)
        require(current['role'] == (label if label in ('base', 'final') else 'agent') and
                current['provenance']['runtimeEvidence']['executionRequest'] == report['provenance']['runtimeEvidence']['executionRequest'],
                'four-control role/request metadata differs')
        checked = verify_artifacts(current, contract, deadline)
        require(tuple(checked['counts'][key] for key in ('passed', 'failed', 'notScored')) == EXPECTED[label],
                'actual four-control polarity differs')
        raw = proof.load(proof.checked(current['provenance']['runtimeEvidence']['raw'], deadline))
        ids = {row['caseRunId'] for row in raw['semantic']['cases']}
        require(len(ids) == 10 and not identities.intersection(ids) and raw['nativeNonce'] not in nonces and
                raw['source'] not in sources, 'four-control observations/source/nonce reused')
        identities.update(ids); nonces.add(raw['nativeNonce']); sources.add(raw['source'])
        assessments[label] = checked
        reports[label] = proof.file_record(path, deadline)
    require(len(identities) == 40 and len(nonces) == 4 and len(sources) == 4, 'four fresh independent poles required')
    require(any(proof.load(Path(record['path'])) == report for record in reports.values()), 'caller report is not an exact control member')
    return {'validated': True, 'kind': 'four_actual_debug_controls_not_a_model_receipt',
            'reports': reports, 'assessments': assessments, 'caseRunIds': sorted(identities),
            'nativeNonces': sorted(nonces), 'executionRequest': report['provenance']['runtimeEvidence']['executionRequest'],
            'executionResult': report['provenance']['runtimeEvidence']['executionResult'],
            'contract': proof.file_record(proof.CONTRACT, deadline), 'implementation': records(deadline),
            'toolchainBefore': result['toolchainBefore'], 'toolchainAfter': result['toolchainAfter']}


def verify_candidate_context(report, contract, deadline):
    checked = verify_artifacts(report, contract, deadline)
    request, result, before, after = execution_window(report, deadline)
    require(request['mode'] == 'candidate' and len(request['phases']) == 1, 'not an independent actual candidate request')
    evidence = report['provenance']['runtimeEvidence']
    receipt = private_ref(evidence['reviewedControlReceipt'], report['provenance']['candidateSource'], deadline)
    controls = verify_receipt(receipt, Path(request['base']), Path(request['final']), Path(request['output']), deadline)
    require(before['files'] == after['files'] == controls['toolchain']['files'] and
            before['versions'] == after['versions'] == controls['toolchain']['versions'] and
            before['scope'] == after['scope'] == controls['toolchain']['scope'], 'candidate actual toolchain differs from controls')
    raw = proof.load(proof.checked(evidence['raw'], deadline))
    require(not controls['ids'].intersection(row['caseRunId'] for row in raw['semantic']['cases']) and
            raw['nativeNonce'] not in controls['nonces'], 'candidate reuses control observations')
    if report.get('publication', {}).get('eligible') is True:
        finalized = proof.load(proof.checked(evidence['parentFinalization'], deadline))
        require(Path(evidence['parentFinalization']['path']) == Path(request['output']) / 'parent-finalized.json' and
                finalized['requestId'] == request['requestId'] and finalized['resources'].get('released') is True and
                0 < finalized['elapsedSeconds'] <= finalized['timeoutSeconds'] <= 3600 and
                proof.load(proof.checked(finalized['cleanup'], deadline)).get('complete') is True,
                'publishable candidate lacks actual within-budget resource/cleanup finalization')
    return {'validated': True, 'counts': checked['counts'], 'controlsReused': True, 'freshControlExecutions': False,
            'candidate': checked, 'controlReceipt': evidence['reviewedControlReceipt']}


def verify_receipt(receipt, base, final, root, deadline):
    require(receipt['implementation'] == records(deadline), 'calibration implementation differs')
    for label, source, expected in (('base', base, BASE_SHA), ('final', final, FINAL_SHA)):
        require(proof.inventory(source, deadline)['sha256'] == expected and
                inputs.inventory(source, deadline) == receipt['immutableSources'][label], 'immutable input bytes/type/mode changed')
    result, sources, ids, nonces = {}, set(), set(), set()
    validation = []
    first_report = proof.load(proof.checked(receipt['reports']['base'], deadline))
    context = verify_calibration_context(first_report, proof.load(proof.CONTRACT), deadline)
    require(context['reports'] == receipt['reports'] and context['toolchainBefore'] == receipt['toolchainBefore'] and
            context['toolchainAfter'] == receipt['toolchainAfter'], 'receipt reparented controls/toolchain into a different batch')
    for label in LABELS:
        report = proof.load(proof.checked(receipt['reports'][label], deadline))
        manifest = proof.load(proof.checked(report['provenance']['runtimeEvidence']['inputManifest'], deadline))
        expected_source = receipt['immutableSources']['base' if label in ('base', 'negative') else 'final']
        require(manifest['original'] == expected_source and manifest['executed']['entries'] == expected_source['entries'],
                'control inputs do not match their immutable source bytes/type/modes')
        checked = context['assessments'][label]
        counts = tuple(checked['counts'][k] for k in ('passed', 'failed', 'notScored'))
        require(counts == EXPECTED[label], 'reviewed control polarity incomplete')
        source = report['provenance']['executedSource']
        raw = proof.load(proof.checked(report['provenance']['runtimeEvidence']['raw'], deadline))
        current_ids = {row['caseRunId'] for row in raw['semantic']['cases']}
        require(source not in sources and len(current_ids) == 10 and not current_ids.intersection(ids) and
                raw['nativeNonce'] not in nonces, 'control source/raw identity reused')
        sources.add(source); ids.update(current_ids); nonces.add(raw['nativeNonce'])
        result[label] = list(counts)
        validation.append(receipt['reports'][label])
    before, after = tools.compare(receipt['toolchainBefore'], receipt['toolchainAfter'], deadline)
    require(len(ids) == 40 and len(nonces) == 4, 'forty independent cases required')
    return {'reports': validation, 'ids': ids, 'nonces': nonces, 'toolchain': before, 'counts': result}


def worker(path):
    q = proof.load(path)
    deadline = timer.child_local_deadline(q['childBudget'])
    require(os.getpid() == os.getpgrp() == os.getsid(0), 'one owned worker session required')
    root = Path(q['output'])
    if q['mode'] == 'candidate':
        receipt = private_ref(q['controlReceipt'], q['candidate'], deadline)
        checked = verify_receipt(receipt, Path(q['base']), Path(q['final']), root, deadline)
        # Re-admit every retained control through the current public route, not old approval flags.
        global _VALIDATION_DEADLINE
        _VALIDATION_DEADLINE = deadline
        sys.modules.setdefault(MODULE, sys.modules[__name__])
        from scripts.run_runtime_transition_matrix import validate_report
        for record in checked['reports']:
            validate_report(proof.load(proof.checked(record, deadline)), proof.load(proof.CONTRACT))
    first = tools.capture(root / 'toolchain-before', q['serial'], deadline)
    if q['mode'] == 'candidate':
        current = proof.load(proof.checked(first, deadline))
        require(current['versions'] == checked['toolchain']['versions'] and current['files'] == checked['toolchain']['files'] and
                current['scope'] == checked['toolchain']['scope'], 'current actual toolchain differs from controls')
    phases = []
    for item in q['phases']:
        proof.check(deadline)
        require(shutil.disk_usage(root).free >= 8 * 1024**3, 'storage protection below 8 GiB')
        if q['mode'] == 'candidate' and q['compilePassed'] is None:
            # A genuine separate standalone application compile, not runtimeCompile credit.
            target = Path(item['output'])
            (target / 'standalone-temporary').mkdir()
            try:
                built = builder.build_application(source=Path(item['source']), output=target / 'standalone-build',
                            temporary=target / 'standalone-temporary', deadline=deadline)
            except Exception:
                path = target / 'standalone-build/application-build.json'
                metric = {'passed': None, 'status': 'not_scored', 'scope': 'standalone_candidate_application_build'}
                if path.exists():
                    failure = proof.load(path)
                    log = target / 'standalone-build/application-build.log'
                    text = log.read_text() if log.exists() else ''
                    # Only explicit actual ArkTS compiler diagnostics earn compile-fail credit.
                    environmental = any(word in text.lower() for word in ('no space left', 'permission denied',
                        'connection reset', 'tls handshake', 'timed out', 'sdk location not found'))
                    failed = failure.get('exitCode') == 1 and 'ArkTS:ERROR' in text and not environmental
                    metric.update(passed=False if failed else None, status='failed' if failed else 'not_scored',
                                  build=proof.file_record(path, deadline))
                proof.write(target / 'compile-metric.json', metric)
                raise
            proof.write(target / 'compile-metric.json', {'passed': built['passed'], 'status': 'passed',
                        'scope': 'standalone_candidate_application_build', 'build': proof.file_record(target / 'standalone-build/application-build.json', deadline)})
        phases.append(run_phase(item, q, deadline))
    last = tools.capture(root / 'toolchain-after', q['serial'], deadline)
    tools.compare(first, last, deadline)
    proof.write(root / 'worker-result.json', {'workerPid': os.getpid(), 'phases': phases,
                'toolchainBefore': first, 'toolchainAfter': last})


def worker_entry(path):
    """Never let a failed leader reap while its compiler/native descendants run."""
    try:
        worker(path)
        q = proof.load(path)
        require(not builder.compiler_group_members(timer.child_local_deadline(q['childBudget'])),
                'owned descendants remain at worker boundary')
    except BaseException:
        traceback.print_exc()
        # This is the CURRENT live process/session leader, not a previously reaped PID.
        # A signal failure propagates; it cannot turn unknown cleanup into success.
        if os.getpid() == os.getpgrp() == os.getsid(0):
            try:
                q = proof.load(path)
                members = builder.compiler_group_members(timer.child_local_deadline(q['childBudget']))
            except BaseException:
                members = ['unknown']
            if members:
                os.killpg(os.getpid(), signal.SIGKILL)
        raise


def cleanup(root, clock):
    from .task12_arkts_merged_runtime_v1 import cleanup as hash_cleanup
    # Staged before public validation, so reports can bind real cleanup hashes.
    # A started-but-interrupted sweep is NEVER recursively retried.
    receipt = root / 'staged-cleanup.json'
    marker = root / 'cleanup-started.json'
    if receipt.exists():
        return proof.load(receipt)
    if marker.exists():
        return {'complete': False, 'reason': 'previous owned cleanup interrupted; no recursive retry'}
    proof.write(marker, {'root': str(root), 'pid': os.getpid()})
    phases, sources = {}, {}
    complete = True
    phase_root = root / 'phases'
    for phase in sorted(phase_root.iterdir()) if phase_root.exists() else []:
        proof.check(clock.deadline)
        prepared = proof.load(phase / 'prepared.json')
        require(prepared['phase'] == str(phase), 'unowned phase cleanup')
        label = phase.name
        # Includes both standalone and runtime HAPs; untouched JSON/log/archive stay retained.
        phases[label] = hash_cleanup(phase, clock.deadline)
        complete = complete and phases[label].get('complete') is True
        for prefix in ('owned-temporary', 'standalone-temporary'):
            directory = phase / prefix
            if directory.exists():
                for residual in list(directory.iterdir()):
                    swept = builder.remove_owned_tree(residual, phase / ('deferred-' + prefix + '-' + residual.name), clock.deadline)
                    complete = complete and swept.get('complete') is True
                directory.rmdir()
        source = Path(prepared['source'])
        require(source.parent == root / 'owned-sources' and len(source.name) == 32 and
                all(c in '0123456789abcdef' for c in source.name), 'unowned source cleanup')
        if source.exists():
            audit = root / 'source-cleanup' / label
            sources[label] = builder.remove_owned_tree(source, audit, clock.deadline)
            complete = complete and sources[label].get('complete') is True
    result = {'complete': complete, 'localOnly': True, 'phases': phases, 'sources': sources}
    proof.write(receipt, result)
    return result


def execute(*, mode, base_source, final_source, output, deadline, serial, source=None,
            compile_passed=None, compile_command='', control_receipt=None, coordinator_release=False, fallback_holder=None):
    require(coordinator_release is True, 'explicit hardware release required; no work started')
    require(mode in ('calibration', 'candidate'), 'unknown pipeline mode')
    root = Path(output).with_suffix('.merged-pipeline-evidence')
    fallback_holder = fallback_holder if fallback_holder is not None else {}

    def failure_template(actual, clock):
        contract = proof.load(proof.CONTRACT)
        result = {'schemaVersion': supervisor.SCHEMA, 'state': 'revoked', 'status': 'not_scored',
            'taskId': '12_report_room', 'platform': 'arkts', 'role': 'agent',
            'observationMode': 'runtime_state_transition',
            'compile': {'passed': compile_passed, 'command': compile_command,
                        'status': 'passed' if compile_passed is True else 'failed' if compile_passed is False else 'not_scored',
                        'scope': 'caller_provided_standalone_compile' if compile_passed is not None else 'standalone_not_completed'},
            'semantic': {'total': 10, 'passed': 0, 'failed': 0, 'notScored': 10,
                'cases': [dict(caseId=case['caseId'], key=case['key'], traceDigest=case['traceDigest'],
                    status='not_scored', observed=None, invariantChecks=[], transitionExecuted=False,
                    reason='Complete current source-bound calibration/candidate proof unavailable') for case in contract['cases']]},
            'calibration': {'passed': False}, 'publication': {'eligible': False}, 'publicationEligible': False,
            'diagnostics': {'auditRoot': str(actual), 'missingReceiptNeverTriggersFreshControls': True}}
        fallback_holder['report'] = result
        return result

    def failure_update(actual, clock):
        result = fallback_holder.get('report')
        if result is None:
            return None
        metric = actual / 'phases/candidate/compile-metric.json'
        if compile_passed is None and metric.exists():
            proof.check(clock.deadline)
            result['compile'] = proof.load(metric)
        return result

    def precheck(actual, clock):
        for value in (base_source, final_source, source):
            if value is not None:
                path = Path(value).resolve()
                require(actual != path and path not in actual.parents, 'private evidence inside production source')
        require(not Path(output).exists(), 'never overwrite a previous output')

    def prepare(actual, clock):
        require(proof.file_record(proof.CONTRACT, clock.work_deadline)['sha256'] == proof.CONTRACT_SHA, 'canonical contract changed')
        private = control_receipt
        if mode == 'candidate':
            if isinstance(private, (Path, str)):
                private = receipt_record(private, clock.work_deadline)
            private_ref(private, source, clock.work_deadline)  # Fail before hardware with no fresh fallback.
        require(shutil.disk_usage(actual).free >= 8 * 1024**3, 'storage protection below 8 GiB')
        immutable = {}
        for label, path, sha in (('base', base_source, BASE_SHA), ('final', final_source, FINAL_SHA)):
            require(proof.inventory(Path(path), clock.work_deadline)['sha256'] == sha, 'immutable source inventory differs')
            immutable[label] = inputs.inventory(path, clock.work_deadline)
        phases = ([make_phase(actual, base_source if label in ('base', 'negative') else final_source,
                    label, label if label in ('base', 'final') else 'agent', clock.work_deadline) for label in LABELS]
                  if mode == 'calibration' else [make_phase(actual, source, 'candidate', 'agent', clock.work_deadline)])
        return {'source': str(Path(base_source).resolve()), 'mode': mode, 'serial': serial, 'phases': phases,
                'base': str(Path(base_source).resolve()), 'final': str(Path(final_source).resolve()),
                'candidate': str(Path(source).resolve()) if source is not None else None,
                'output': str(actual), 'immutableSources': immutable, 'implementation': records(clock.work_deadline),
                'controlReceipt': private, 'compilePassed': compile_passed, 'compileCommand': compile_command}

    def finalize(actual, q, clock, launch):
        require(records(clock.work_deadline) == q['implementation'], 'execution/policy changed during prospective run')
        for label, path in (('base', base_source), ('final', final_source)):
            require(inputs.inventory(path, clock.work_deadline) == q['immutableSources'][label], 'immutable source changed during execution')
        result = proof.load(actual / 'worker-result.json')
        require(len(result['phases']) == len(q['phases']), 'worker did not execute every prospective phase')
        before, after = tools.compare(result['toolchainBefore'], result['toolchainAfter'], clock.work_deadline)
        for item in q['phases']:
            manifest = proof.load(proof.checked(item['inputManifest'], clock.work_deadline))
            require(inputs.inventory(item['source'], clock.work_deadline) == manifest['executed'] and
                    inputs.inventory(item['originalSource'], clock.work_deadline) == manifest['original'],
                    'source bytes/type/mode changed before hash-cleanup')
        require(cleanup(actual, clock).get('complete') is True, 'actual source/binary hash-cleanup incomplete')
        previous = before['finishedLocal']
        reports = {}
        for item, execution in zip(q['phases'], result['phases']):
            observed = proof.load(proof.checked(execution, clock.work_deadline))
            require(observed['workerPid'] == before['workerPid'] == after['workerPid'] and
                    previous <= observed['startedLocal'] < observed['finishedLocal'] <= after['startedLocal'] and
                    observed['source'] == item['source'] and observed['inputManifest'] == item['inputManifest'],
                    'four phases do not lie in one real before/after worker interval')
            previous = observed['finishedLocal']
            report = make_report(item, q, clock.work_deadline)
            # Future binary-free rechecks use this exact owned-source cleanup receipt.
            report['provenance']['runtimeEvidence']['sourceCleanup'] = proof.file_record(
                    actual / 'source-cleanup' / item['label'] / 'cleanup.json', clock.work_deadline)
            report_path = Path(item['output']) / 'report.json'
            proof.write(report_path, report)
            reports[item['label']] = proof.file_record(report_path, clock.work_deadline)
        require(len(reports) == len(q['phases']) == len(result['phases']), 'missing prospective phase')
        validation = actual / 'public-validation.json'
        proof.write(validation, {'reports': list(reports.values()), 'budget': clock.child_budget(reserve=5),
                                'output': str(actual / 'public-assessment.json')})
        launch([sys.executable, '-B', '-m', MODULE, '--validate', str(validation)], 'public-validation')
        assessed = proof.load(actual / 'public-assessment.json')['results']
        ids, nonces = set(), set()
        for item, evidence in zip(q['phases'], assessed):
            require(evidence['publicPassed'] is True and evidence['report'] == reports[item['label']], 'public proof differs')
            current = set(evidence['caseRunIds'])
            require(len(current) == 10 and not current.intersection(ids) and evidence['nativeNonce'] not in nonces,
                    'prospective runtime reused a case/nonce')
            ids.update(current); nonces.add(evidence['nativeNonce'])
            if mode == 'calibration':
                require(tuple(evidence['counts'][k] for k in ('passed', 'failed', 'notScored')) == EXPECTED[item['label']],
                        'fresh four-control polarity incomplete')
        if mode == 'candidate':
            receipt = private_ref(q['controlReceipt'], source, clock.work_deadline)
            reused = verify_receipt(receipt, Path(base_source), Path(final_source), actual, clock.work_deadline)
            require(not ids.intersection(reused['ids']) and not nonces.intersection(reused['nonces']), 'candidate reused control observations')
            passed = compile_passed
            metric = {'passed': passed, 'status': 'passed' if passed is True else 'failed' if passed is False else 'not_scored',
                      'command': compile_command, 'scope': 'caller_provided_standalone_compile'}
            if passed is None:
                metric = proof.load(Path(q['phases'][0]['output']) / 'compile-metric.json')
            report = proof.load(Path(reports['candidate']['path']))
            report.update(protocol='task12.merged-candidate-only.v1', reports=reports, controlsReused=True,
                    freshControlExecutions=False, compile=metric, calibration={'passed': True, 'controlsReused': True},
                    publicAssessment=proof.file_record(actual / 'public-assessment.json', clock.work_deadline))
            report['provenance']['runtimeEvidence']['reviewedControlReceipt'] = q['controlReceipt']
            report['publication'] = {'eligible': metric.get('passed') is True, 'publicValidated': True}
            return report
        require(len(ids) == 40 and len(nonces) == 4, 'fresh forty-case proof missing')
        return {'protocol': RECEIPT, 'freshControlExecutions': True, 'controlsReused': False, 'modelCalled': False,
                'reports': reports, 'immutableSources': q['immutableSources'], 'implementation': q['implementation'],
                'contract': proof.file_record(proof.CONTRACT, clock.work_deadline),
                'toolchainBefore': result['toolchainBefore'], 'toolchainAfter': result['toolchainAfter'],
                'publicAssessment': proof.file_record(actual / 'public-assessment.json', clock.work_deadline),
                'uniqueCaseCount': len(ids), 'uniqueNativeNonceCount': len(nonces), 'publicationEligible': False}

    def commit_result(actual, q, clock, result, cleaned, released):
        path = actual / 'parent-finalized.json'
        proof.write(path, {'requestId': q['requestId'], 'parentPid': os.getpid(),
                    'timeoutSeconds': clock.timeout, 'elapsedSeconds': time.monotonic() - clock.started,
                    'clockDomain': 'one_parent_process_local_monotonic',
                    'cleanup': proof.file_record(actual / 'staged-cleanup.json', clock.work_deadline),
                    'resources': released, 'publicAssessment': result['publicAssessment']})
        record = proof.file_record(path, clock.work_deadline)
        if mode == 'candidate':
            result['provenance']['runtimeEvidence']['parentFinalization'] = record
        else:
            result['parentFinalization'] = record
        return result

    return supervisor._supervise(root, deadline, prepare, lambda path: [sys.executable, '-B', '-m', MODULE, '--worker', str(path)],
            finalize, acquire=acquire, cleanup=cleanup, release=release, report_path=output, precheck=precheck,
            failure_template=failure_template if mode == 'candidate' else None,
            failure_update=failure_update if mode == 'candidate' else None, commit_result=commit_result)


def calibrate_controls(*, base_source, final_source, output, timeout=3600, serial='127.0.0.1:5555', coordinator_release=False):
    require(type(timeout) in (int, float) and math.isfinite(timeout) and 0 < timeout <= 3600, 'invalid independent pre-agent budget')
    return execute(mode='calibration', base_source=base_source, final_source=final_source, output=output,
                   deadline=time.monotonic() + timeout, serial=serial, coordinator_release=coordinator_release)


def score(*, platform, source, base_source, final_source, output, timeout=3600, compile_passed=None,
          compile_command='', device_serial='127.0.0.1:5555', control_receipt=None, coordinator_release=True,
          application_compiler=None, application_compile_evidence=None, validate_public=True, **unsupported):
    require(platform == 'arkts' and type(timeout) in (int, float) and math.isfinite(timeout) and 0 < timeout <= 3600,
            'Task12 ArkTS original remaining budget required')
    require(application_compiler is None and application_compile_evidence is None and validate_public is True and not unsupported,
            'only parent compile_passed/command or genuine standalone compiler; public validation cannot be bypassed')
    fallback = {}
    result = execute(mode='candidate', base_source=base_source, final_source=final_source, source=source,
            output=output, deadline=time.monotonic() + timeout, serial=device_serial or '127.0.0.1:5555', compile_passed=compile_passed,
            compile_command=compile_command, control_receipt=control_receipt, coordinator_release=coordinator_release,
            fallback_holder=fallback)
    return result if result is not None else fallback.get('report')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--worker', type=Path)
    parser.add_argument('--validate', type=Path)
    parser.add_argument('--base-source', type=Path)
    parser.add_argument('--final-source', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--timeout', type=float, default=3600)
    parser.add_argument('--device-serial', default='127.0.0.1:5555')
    parser.add_argument('--execute-after-coordinator-release', action='store_true')
    args = parser.parse_args()
    if args.worker:
        worker_entry(args.worker)
    elif args.validate:
        validate_worker(args.validate)
    else:
        require(args.base_source is not None and args.final_source is not None and args.output is not None,
                'explicit pre-agent calibration sources/output required')
        calibrate_controls(base_source=args.base_source, final_source=args.final_source, output=args.output,
            timeout=args.timeout, serial=args.device_serial, coordinator_release=args.execute_after_coordinator_release)


if __name__ == '__main__':
    main()
