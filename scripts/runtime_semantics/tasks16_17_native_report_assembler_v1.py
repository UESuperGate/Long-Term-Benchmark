"""Versioned native-only diagnostic assembler; never promotes public admission.

The generic loader's original NS rows remain immutable. Calls below are exact
native observer records, not reconstructed JavaScript-loader invocations.
"""
import argparse
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tarfile
import time

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.runtime_semantics import tasks16_17_page_ports_evidence as native
from scripts.runtime_semantics import tasks16_17_arkts_entry_binding_v2 as acquisition
from scripts.runtime_semantics import tasks16_17_arkts_entry_binding_v3 as prefix

SCHEMA = 'tasks16_17.native-report-assembler.v1'
TASKS = ('16_identity_reset', '17_pinned_messages')
SOURCE_FREEZE_SHA256 = 'b38329d42a4bdfa7490fac49871091a3d0596186916d49c8d6d3df7c73747910'
SDK_KINDS = {
    '16_identity_reset': {'subscribe_verification', 'unsubscribe_verification', 'start_identity_reset',
        'external_response', 'external_rejection', 'cancel_reset_handle', 'destroy_reset_handle',
        'verification_status', 'reset_password', 'reset_oidc'},
    '17_pinned_messages': {'subscribe_timeline_items', 'unpin_event', 'close_timeline', 'open_pinned_timeline',
        'can_pin_unpin', 'room_timeline', 'room_sync_permission', 'external_open_result', 'sdk_timeline_items'},
}


def require(condition, message):
    if not condition:
        raise ValueError('Native assembler unavailable: ' + message)


def record(path):
    return native.record(path)


def remaining(deadline):
    value = deadline - time.monotonic()
    if value <= 0:
        raise TimeoutError('Native assembly overall budget exhausted')
    return value


def audit_path(path):
    path = Path(path).resolve()
    require(path.is_relative_to(ROOT / 'experiment_results'), 'path outside experiment audit root')
    return path


def write_json(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')


def inventory(source, deadline):
    """Post-hoc source check only; never labels this a prospective capture."""
    source = Path(source).resolve()
    require(source.is_dir(), 'explicit source directory missing')
    rows = []
    for parent, directories, files in os.walk(source, followlinks=False):
        for name in list(directories):
            path = Path(parent) / name
            if name in acquisition.EXCLUDED or path.relative_to(source).parts[0] == '_benchmark_inputs':
                directories.remove(name)
            else:
                require(not path.is_symlink(), 'unknown enclosing source directory symlink')
        for name in files:
            remaining(deadline)
            path = Path(parent) / name
            relative = path.relative_to(source).as_posix()
            if relative == 'opencode.json' or name == '.git':
                continue
            require(not path.is_symlink() and not name.startswith('.env') and name not in
                    ('local.properties', '.npmrc', '.netrc', 'key.properties'), 'unknown/private source input')
            item = record(path)
            item['path'] = relative
            rows.append(item)
    require(rows, 'empty source closure')
    return acquisition.ordered(rows)


def evaluator_records():
    return [record(path) for path in (Path(__file__), Path(native.__file__), Path(acquisition.__file__),
                                     Path(prefix.__file__), prefix.REFERENCE)]


def generate_policy(freeze, groups, output, timeout=120):
    """Explicit reviewer source groups; no role labels, filename or ref inference."""
    deadline = time.monotonic() + timeout
    freeze = audit_path(freeze)
    require(record(freeze)['sha256'] == SOURCE_FREEZE_SHA256, 'unknown pre-runtime reviewed source freeze')
    frozen = json.loads(freeze.read_text())
    require(frozen['allLightweightTestsPassed'] and frozen['sources'], 'incomplete reviewed freeze')
    variants = []
    for task_id, source in groups:
        require(task_id in TASKS, 'wrong task')
        source = Path(source).resolve()
        reviewed = acquisition.ordered([dict(path=str(Path(item['path']).relative_to(source)), bytes=item['bytes'], sha256=item['sha256'])
            for item in frozen['sources'] if Path(item['path']).is_relative_to(source)])
        require(reviewed and inventory(source, deadline) == reviewed, 'unknown/changed/extra source inputs at policy generation')
        variants.append(dict(taskId=task_id, reviewedGroupRoot=str(source), completeInputs=reviewed,
            inputDigest=hashlib.sha256(json.dumps(reviewed, sort_keys=True).encode()).hexdigest()))
    require(variants and len({(row['taskId'], row['inputDigest']) for row in variants}) == len(variants), 'empty/duplicate reviewed variants')
    value = dict(schemaVersion=SCHEMA + '.policy', reviewedSourceFreeze=record(freeze), variants=variants,
        evaluators=evaluator_records(), canonicalContracts={task: record(ROOT / 'benchmark_tasks' / task / 'transitions.json') for task in TASKS},
        reviewStatus='technical-proposal-awaiting-main-review', humanApprovalClaimed=False, publicAdmissionChanged=False)
    output = audit_path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    write_json(output, value)
    return record(output)


def load_policy(path, expected_sha256):
    path = audit_path(path)
    require(isinstance(expected_sha256, str) and len(expected_sha256) == 64 and record(path)['sha256'] == expected_sha256,
            'reviewed policy digest missing or changed')
    policy = json.loads(path.read_text())
    require(policy.get('schemaVersion') == SCHEMA + '.policy' and policy.get('variants'), 'unknown policy schema')
    require(policy.get('evaluators') == evaluator_records(), 'assembler/current reviewed evaluator bytes changed')
    frozen = policy['reviewedSourceFreeze']
    require(record(audit_path(frozen['path'])) == frozen and frozen['sha256'] == SOURCE_FREEZE_SHA256, 'unreviewed source freeze')
    frozen_rows = json.loads(Path(frozen['path']).read_text())['sources']
    # Policy cannot introduce an input hash absent from the reviewed full freeze.
    for variant in policy['variants']:
        require(variant['taskId'] in TASKS and variant['completeInputs'], 'invalid reviewed variant')
        group = Path(variant['reviewedGroupRoot']).resolve()
        complete = acquisition.ordered([dict(path=str(Path(item['path']).relative_to(group)), bytes=item['bytes'], sha256=item['sha256'])
            for item in frozen_rows if Path(item['path']).is_relative_to(group)])
        require(complete and complete == variant['completeInputs'], 'policy introduced partial/unknown source closure')
    for task in TASKS:
        require(policy['canonicalContracts'][task] == record(ROOT / 'benchmark_tasks' / task / 'transitions.json'), 'canonical contract changed')
    return policy


def validate_native_calls(case, raw, compiled):
    """Check actual recorded receivers/stacks; return originals without synthetic calls."""
    require(raw.get('productionSources') == compiled, 'native source provenance differs from actual compiled source')
    require(raw.get('frames') and raw.get('eventExecuted') and not raw.get('failure'), 'actual native proof missing')
    if raw.get('integrationTier') == 'actual_page_physical_prefix':
        return dict(ownerCalls=[], externalSdkCalls=[], managerInvocations=[], managerTransitions=[])
    before, after = native.frame(raw, 'before_event'), native.frame(raw, 'after_event')
    if case['key'] != 'cancel_cleans_up':
        for key in ('ownerId', 'sdkPortId') + (('managerId', 'serviceId') if raw['taskId'] == TASKS[0]
                                             else ('repositoryId', 'providerId', 'parentTimelineId', 'roomServiceId')):
            require(before['owner']['current'].get(key) is not None and
                    before['owner']['current'][key] == after['owner']['current'].get(key), 'primary owner identity changed: ' + key)
    latest = max(raw['frames'], key=lambda row: row['sequence'])['owner']
    owners = {row['ownerId']: row for row in latest['owners']}
    require(len(owners) == latest['ownerCount'], 'incomplete owner inventory')
    original_calls = latest.get('calls')
    require(original_calls and len({row['invocationId'] for row in original_calls}) == len(original_calls), 'missing/duplicate actual native invocations')
    production_paths = {item['path'] for item in compiled}
    primary_ui = False
    for call in original_calls:
        actor = call.get('before', {})
        require(actor.get('ownerId') in owners, 'unknown native call owner')
        for key in ('managerId', 'serviceId', 'repositoryId', 'providerId', 'parentTimelineId', 'roomServiceId', 'sdkPortId'):
            if key in actor:
                require(actor[key] == owners[actor['ownerId']].get(key), 'detached native receiver: ' + key)
        require(call.get('stack') and call.get('originalMethodId') and call.get('publicMethodId'), 'original native method/stack proof missing')
        for name in ('afterReturn', 'afterSettlement'):
            if name in call:
                require(call[name]['ownerId'] == actor['ownerId'], 'native invocation changed receiver')
        primary_ui |= (call.get('scope') != 'bootstrap_ui' and actor['ownerId'] != raw['bootstrap']['warmupOwnerId'] and
                       any(path + ':' in call['stack'] for path in production_paths if path.endswith('/pages/Index.ets')))
    require(primary_ui, 'no actual original page callback reaches canonical owner')
    sdk_calls = raw.get('externalSdk')
    require(isinstance(sdk_calls, list) and all(row.get('kind') in SDK_KINDS[raw['taskId']] for row in sdk_calls), 'unknown/missing SDK call proof')
    require([row.get('sequence') for row in sdk_calls] == list(range(1, len(sdk_calls) + 1)), 'SDK log missing/reordered')
    return dict(ownerCalls=copy.deepcopy(original_calls), externalSdkCalls=copy.deepcopy(sdk_calls),
                managerInvocations=copy.deepcopy(latest.get('managerInvocations', [])),
                managerTransitions=copy.deepcopy(latest.get('managerTransitions', [])))


def verify_assembled(report_path, policy_sha256):
    """Revalidate retained native facts/archives after candidate/build cleanup."""
    report_path = audit_path(report_path)
    report = json.loads(report_path.read_text())
    require(report.get('schemaVersion') == SCHEMA and report.get('platform') == 'arkts' and report.get('taskId') in TASKS,
            'unknown assembled report')
    provenance = report['provenance']
    policy_ref = provenance['reviewedPolicy']
    require(record(audit_path(policy_ref['path'])) == policy_ref, 'reviewed policy record differs')
    policy = load_policy(policy_ref['path'], policy_sha256)
    require(provenance['assembler'] == record(__file__) and provenance['evaluatorSources'] == evaluator_records(),
            'report is not bound to current reviewed assembler/evaluators')
    require(provenance.get('assemblerEvaluatorSnapshots') and len(provenance['assemblerEvaluatorSnapshots']) == len(evaluator_records()),
            'assembler evaluator snapshots missing')
    for snapshot, current in zip(provenance['assemblerEvaluatorSnapshots'], evaluator_records()):
        retained = audit_path(snapshot['snapshot']['path'])
        require(snapshot['current'] == current and retained.is_relative_to(report_path.parent / 'evaluator-sources') and
                record(retained) == snapshot['snapshot'] and snapshot['snapshot']['sha256'] == current['sha256'],
                'retained assembler evaluator bytes differ')
    task_id = report['taskId']
    contract_path = ROOT / 'benchmark_tasks' / task_id / 'transitions.json'
    require(provenance['canonicalContract'] == record(contract_path), 'report canonical contract differs')
    contract = json.loads(contract_path.read_text())
    specs = {row['caseId']: row for row in contract['cases']}
    for key in ('sourceInventory', 'sourceArchive', 'fullRawLedger'):
        item = provenance[key]
        path = audit_path(item['path'])
        require(path.parent == report_path.parent and record(path) == item, 'retained assembled artifact missing/changed: ' + key)
    inventory_record = json.loads(Path(provenance['sourceInventory']['path']).read_text())
    inputs = inventory_record['files']
    require(inventory_record.get('phase') == 'posthoc_assembly_only' and inventory_record['source'] == report['source'],
            'post-hoc check relabeled prospective or source differs')
    require(sum(row['taskId'] == task_id and row['completeInputs'] == inputs for row in policy['variants']) == 1,
            'retained source has unknown complete inputs')
    with tarfile.open(provenance['sourceArchive']['path'], 'r:gz') as archive:
        members = archive.getmembers()
        require(all(item.isfile() for item in members) and len(members) == len(inputs) and
                sorted(item.name for item in members) == sorted(item['path'] for item in inputs), 'retained source archive incomplete/extra')
        for item in inputs:
            data = archive.extractfile(item['path']).read()
            require(len(data) == item['bytes'] and hashlib.sha256(data).hexdigest() == item['sha256'], 'retained source archive bytes differ')
    ledger = json.loads(Path(provenance['fullRawLedger']['path']).read_text())
    require(ledger.get('schemaVersion') == SCHEMA + '.raw-ledger' and ledger.get('cases'), 'full raw ledger absent')
    rows = report['semantic']['cases']
    require([row['caseId'] for row in rows] == list(specs) and all(row['traceDigest'] == specs[row['caseId']]['traceDigest'] for row in rows),
            'report lost/changed canonical cases or digests')
    scored = {row['caseId']: row for row in rows if row['status'] in ('pass', 'fail')}
    require(len({entry['caseId'] for entry in ledger['cases']}) == len(ledger['cases']) and
            set(scored) == {entry['caseId'] for entry in ledger['cases']}, 'scored cases differ from unique native receipts')
    for entry in ledger['cases']:
        require(entry['taskId'] == task_id, 'ledger task scope differs')
        root = audit_path(entry['originalReceipt']['path']).parent
        require(entry['originalReceipt'] == record(root / 'receipt.json') and
                entry['originalManifest'] == record(root / 'evidence-manifest.json'), 'original native receipt/manifest differs')
        manifest = json.loads((root / 'evidence-manifest.json').read_text())
        require(entry['files'] == manifest['files'] + [dict(**record(root / 'evidence-manifest.json'), relativePath='evidence-manifest.json')],
                'full raw ledger omitted/added original evidence')
        proof = native.verify_probe(root, specs[entry['caseId']], inputs)
        require(entry['independentlyDerived'] == proof, 'recorded independent facts changed')
        receipt = json.loads((root / 'receipt.json').read_text())
        binding = native.checked(receipt['inputBinding'])
        build = native.checked(binding['build'])
        raw_path = Path(receipt['execution']['path']).parent / 'native-result.json'
        require(entry['nativeRaw'] == record(raw_path), 'original native raw changed')
        outer = json.loads(raw_path.read_text())
        matches = [(index, value['nativePagePorts']) for index, value in enumerate(outer['evidence']) if 'nativePagePorts' in value]
        require(len(matches) == 1, 'missing native raw proof')
        index, raw = matches[0]
        actual_calls = validate_native_calls(specs[entry['caseId']], raw, build['production'])
        row = scored[entry['caseId']]
        require(all(row[key] == proof[key] for key in ('status', 'observed', 'invariantChecks')), 'assembled facts/status differ from native runtime')
        require(row['integrationTier'] == proof['integrationTier'] and row['liveMatrixSdkOrServerVerified'] is False,
                'native integration tier overstated')
        require(row['calls'] == actual_calls['ownerCalls'] and all(row[key] == actual_calls[key] for key in
                    ('externalSdkCalls', 'managerInvocations', 'managerTransitions')), 'native passthrough calls rewritten')
        require(row['productionSources'] == build['production'] and row['compiledInputBinding'] == receipt['inputBinding'] and
                entry['actualCompiledBuild'] == binding['build'] and entry['inputBinding'] == receipt['inputBinding'],
                'assembled compiled source/seal differs')
        require(row['nativeActions'] == raw['actions'] and row['checkpoints'] == [dict(label=frame['label'], state=frame) for frame in raw['frames']],
                'actual native actions/checkpoints changed')
        pointer = '/evidence/' + str(index) + '/nativePagePorts'
        require(row['nativeRawEvidence'] == dict(artifact=entry['nativeRaw'], jsonPointer=pointer) and entry['rawPointer'] == pointer and
                row['originalGenericLoaderStatus'] == entry['originalOuterStatus'] == outer['status'] and
                entry['originalOuterReason'] == outer.get('reason'), 'original loader NS lineage changed')
    require(all(row['status'] in ('pass', 'fail', 'not_scored') for row in rows), 'unknown case status')
    for row in rows:
        if row['status'] == 'not_scored':
            require(row['observed'] is None and row['invariantChecks'] == row['checkpoints'] == row['calls'] == row['productionSources'] == [],
                    'unexecuted case was projected')
    expected_counts = dict(passed=sum(row['status'] == 'pass' for row in rows), failed=sum(row['status'] == 'fail' for row in rows),
                           notScored=sum(row['status'] == 'not_scored' for row in rows), total=len(rows))
    require(report['counts'] == expected_counts and report['diagnostics']['benchmarkMetricsAvailable'] is False and
            report['diagnostics']['publicAdmissionChanged'] is False and report['diagnostics']['liveMatrixSdkOrServerVerified'] is False,
            'counts/availability not diagnostic-only')
    retained_manifest = json.loads((report_path.parent / 'evidence-manifest.json').read_text())
    actual_retained = [record(path) for path in sorted(report_path.parent.rglob('*'))
                       if path.is_file() and path != report_path.parent / 'evidence-manifest.json']
    require(retained_manifest['files'] == actual_retained, 'assembled final evidence manifest missing/extra/changed file')
    return dict(schemaVersion=SCHEMA + '.revalidation', report=record(report_path), counts=expected_counts,
                rawLedger=provenance['fullRawLedger'], currentEvaluators=evaluator_records(),
                nativeFactsAndCallsRevalidated=True, rawUnchanged=True, publicAdmissionChanged=False,
                modelBuildOrDeviceStarted=False)


def assemble(task_id, source, roots, output, policy_path, policy_sha256, timeout=120):
    started = time.monotonic()
    require(task_id in TASKS and 0 < timeout <= 3600, 'task or overall deadline invalid')
    deadline = started + timeout
    source = Path(source).resolve()
    output = audit_path(output)
    require(not output.exists() and not output.is_relative_to(source), 'output must be new and outside candidate source')
    policy = load_policy(policy_path, policy_sha256)
    inputs = inventory(source, deadline)
    variants = [row for row in policy['variants'] if row['taskId'] == task_id and row['completeInputs'] == inputs]
    require(len(variants) == 1, 'unknown/changed/extra complete source input')
    contract_path = ROOT / 'benchmark_tasks' / task_id / 'transitions.json'
    contract = json.loads(contract_path.read_text())
    specs = {row['caseId']: row for row in contract['cases']}
    require(roots and len(set(map(str, roots))) == len(roots), 'empty/duplicate receipt roots')
    selected, ledger = {}, []
    for root in roots:
        remaining(deadline)
        root = audit_path(root)
        receipt_path = root / 'receipt.json'
        receipt = json.loads(receipt_path.read_text())
        require(receipt.get('taskId') == task_id and receipt.get('caseId') in specs, 'wrong task/case receipt')
        case = specs[receipt['caseId']]
        require(case['caseId'] not in selected, 'duplicate case attempts require explicit separate reports')
        proof = native.verify_probe(root, case, inputs)
        binding = native.checked(receipt['inputBinding'])
        build = native.checked(binding['build'])
        execution = native.checked(receipt['execution'])
        raw_path = Path(receipt['execution']['path']).parent / 'native-result.json'
        raw_ref = record(raw_path)
        outer = json.loads(raw_path.read_text())
        matches = [(index, value['nativePagePorts']) for index, value in enumerate(outer['evidence']) if 'nativePagePorts' in value]
        require(len(matches) == 1, 'actual native page proof missing/ambiguous')
        index, raw = matches[0]
        require(raw.get('taskId') == task_id, 'native task scope differs')
        calls = validate_native_calls(case, raw, build['production'])
        manifest_path = root / 'evidence-manifest.json'
        manifest = json.loads(manifest_path.read_text())
        all_raw = manifest['files'] + [dict(**record(manifest_path), relativePath='evidence-manifest.json')]
        require(all(record(audit_path(item['path'])) == {key: item[key] for key in ('path', 'bytes', 'sha256')} for item in all_raw), 'original full raw ledger changed')
        entry = dict(taskId=task_id, caseId=case['caseId'], originalReceipt=record(receipt_path),
            originalManifest=record(manifest_path), files=all_raw, nativeRaw=raw_ref,
            originalOuterStatus=outer['status'], originalOuterReason=outer.get('reason'),
            inputBinding=receipt['inputBinding'], actualCompiledBuild=binding['build'],
            independentlyDerived=proof, rawPointer='/evidence/' + str(index) + '/nativePagePorts')
        ledger.append(entry)
        row = dict(caseId=case['caseId'], key=case['key'], traceDigest=case['traceDigest'], status=proof['status'],
            observed=proof['observed'], invariantChecks=proof['invariantChecks'],
            checkpoints=[dict(label=frame['label'], state=frame) for frame in raw['frames']],
            productionSources=copy.deepcopy(build['production']), calls=calls.pop('ownerCalls'), **calls,
            nativeActions=copy.deepcopy(raw['actions']),
            nativeRawEvidence=dict(artifact=raw_ref, jsonPointer=entry['rawPointer']),
            compiledInputBinding=receipt['inputBinding'], integrationTier=proof['integrationTier'],
            observationLevel=('native_original_page_physical_prefix_diagnostic' if proof['integrationTier'] == 'actual_page_physical_prefix'
                              else 'native_original_page_controlled_external_sdk_diagnostic'),
            liveMatrixSdkOrServerVerified=False, originalGenericLoaderStatus=outer['status'])
        if proof['integrationTier'] == 'actual_page_physical_prefix':
            row.update(semanticFailureKind=proof['semanticFailureKind'], unevaluatedInvariants=case['invariants'],
                       nativeEntryDiagnostic=proof)
        selected[case['caseId']] = row
    remaining(deadline)
    require(inventory(source, deadline) == inputs, 'source changed during assembly')
    output.mkdir(parents=True, exist_ok=False)
    evaluator_snapshots = []
    for index, current in enumerate(evaluator_records()):
        retained = output / 'evaluator-sources' / str(index) / Path(current['path']).name
        retained.parent.mkdir(parents=True)
        with retained.open('xb') as stream:
            stream.write(Path(current['path']).read_bytes())
        require(record(retained)['sha256'] == current['sha256'], 'evaluator changed while retaining snapshot')
        evaluator_snapshots.append(dict(current=current, snapshot=record(retained)))
    write_json(output / 'source-inventory.json', dict(source=str(source), phase='posthoc_assembly_only', files=inputs))
    with tarfile.open(output / 'source-inputs.tar.gz', 'w:gz') as archive:
        for item in inputs:
            remaining(deadline)
            data = (source / item['path']).read_bytes()
            require(len(data) == item['bytes'] and hashlib.sha256(data).hexdigest() == item['sha256'], 'source changed while archiving')
            member = tarfile.TarInfo(item['path'])
            member.size = len(data)
            archive.addfile(member, io.BytesIO(data))
    write_json(output / 'full-raw-ledger.json', dict(schemaVersion=SCHEMA + '.raw-ledger', cases=ledger,
        originalRawRetainedInPlace=True, genericLoaderRowsRewritten=False))
    rows = [selected.get(case['caseId'], dict(caseId=case['caseId'], key=case['key'], traceDigest=case['traceDigest'],
        status='not_scored', observed=None, invariantChecks=[], checkpoints=[], productionSources=[], calls=[],
        reason='No completed independently verified native receipt supplied')) for case in contract['cases']]
    result = dict(schemaVersion=SCHEMA, taskId=task_id, platform='arkts', observationMode='runtime_state_transition',
        semantic=dict(cases=rows), source=str(source), integrationTiers=sorted({row['integrationTier'] for row in selected.values()}),
        provenance=dict(assembler=record(__file__), evaluatorSources=evaluator_records(), assemblerEvaluatorSnapshots=evaluator_snapshots,
            canonicalContract=record(contract_path), reviewedPolicy=record(policy_path),
            sourceInventory=record(output / 'source-inventory.json'), sourceArchive=record(output / 'source-inputs.tar.gz'),
            sourceRelation='requested source is byte-identical to verified actual compiled inputs; no new execution at requested path',
            fullRawLedger=record(output / 'full-raw-ledger.json')),
        counts=dict(passed=sum(row['status'] == 'pass' for row in rows), failed=sum(row['status'] == 'fail' for row in rows),
                    notScored=sum(row['status'] == 'not_scored' for row in rows), total=len(rows)),
        diagnostics=dict(publicAdmissionChanged=False, benchmarkMetricsAvailable=False, fullCalibrationAvailable=False,
            rawUnchanged=True, liveMatrixSdkOrServerVerified=False, noGenericLoaderInvocationsFabricated=True),
        overallElapsedSeconds=round(time.monotonic() - started, 3), overallDeadlineSeconds=timeout)
    # This proposal intentionally remains subject to main's existing fail-closed policy.
    from scripts.run_runtime_transition_matrix import validate_report
    try:
        validate_report(result, contract)
        validation = dict(status='accepted_by_current_public_validator', admissionPolicyChanged=False)
    except ValueError as error:
        validation = dict(status='rejected_by_current_public_validator', reason=str(error), admissionPolicyChanged=False)
    write_json(output / 'public-validation.json', validation)
    write_json(output / 'report.json', result)
    for entry in ledger:
        require(all(record(item['path']) == {key: item[key] for key in ('path', 'bytes', 'sha256')} for item in entry['files']),
                'raw changed during assembly')
    write_json(output / 'evidence-manifest.json', dict(files=[record(path) for path in sorted(output.rglob('*')) if path.is_file()],
        binaryBuildArtifactsCreated=False, modelOrDeviceStarted=False, originalRawUnchanged=True))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    generate = commands.add_parser('policy')
    generate.add_argument('--freeze', type=Path, required=True)
    generate.add_argument('--group', nargs=2, action='append', metavar=('TASK_ID', 'SOURCE'), required=True)
    generate.add_argument('--output', type=Path, required=True)
    run = commands.add_parser('assemble')
    run.add_argument('--task-id', choices=TASKS, required=True)
    run.add_argument('--source', type=Path, required=True)
    run.add_argument('--receipt-root', type=Path, action='append', required=True)
    run.add_argument('--policy', type=Path, required=True)
    run.add_argument('--policy-sha256', required=True)
    run.add_argument('--output', type=Path, required=True)
    run.add_argument('--timeout', type=float, default=120)
    verify = commands.add_parser('verify')
    verify.add_argument('--report', type=Path, required=True)
    verify.add_argument('--policy-sha256', required=True)
    args = parser.parse_args()
    if args.command == 'policy':
        print(json.dumps(generate_policy(args.freeze, args.group, args.output)))
    elif args.command == 'verify':
        print(json.dumps(verify_assembled(args.report, args.policy_sha256)))
    else:
        report = assemble(args.task_id, args.source, args.receipt_root, args.output, args.policy, args.policy_sha256, args.timeout)
        print(json.dumps(dict(taskId=args.task_id, counts=report['counts'], output=str(args.output), publicAdmissionChanged=False)))


if __name__ == '__main__':
    main()
