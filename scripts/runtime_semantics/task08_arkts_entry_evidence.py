"""Task08 native common-entry failures; never project unreachable post-state."""
import argparse
import ast
import copy
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
POLICY = 'task08.arkts.native-common-entry.v1'
HISTORY_ROOT = Path(__file__).with_name('task08_entry_history')


def require(value, message):
    if not value:
        raise ValueError('Task08 entry proof: ' + message)


def record(path):
    path = Path(path).resolve()
    data = path.read_bytes()
    return {'path': str(path), 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


def verify_implementation_receipt(item):
    """Verify the recorded implementation version, never substitute today's hash."""
    digest = item.get('sha256', '')
    require(len(digest) == 64 and all(character in '0123456789abcdef' for character in digest) and
            Path(item.get('path', '')).name == Path(__file__).name, 'invalid normalization implementation receipt')
    current = Path(__file__).resolve()
    resolved = current if record(current)['sha256'] == digest else HISTORY_ROOT / (digest + '.py')
    require(resolved.is_file(), 'recorded normalizer implementation has no immutable version archive')
    archived = record(resolved)
    require(archived['sha256'] == digest and archived['bytes'] == item.get('bytes'),
            'recorded normalizer implementation bytes changed')
    names = {'validate_raw', 'validate_nested', 'normalize', 'verify_normalized', 'apply'}

    def assertions(path):
        return {node.name: ast.dump(node, include_attributes=False) for node in ast.parse(path.read_text()).body
                if isinstance(node, ast.FunctionDef) and node.name in names}

    old, live = assertions(resolved), assertions(current)
    require(set(old) == set(live) == names and old == live,
            'historical normalizer assertions differ from the reviewed current semantics')
    return {'recorded': item, 'resolved': archived, 'historical': resolved != current,
            'assertionFunctionsIdentical': True}


def native_receipt(row):
    found = [item for item in row.get('evidence', []) if isinstance(item, dict) and
             item.get('taskId') == '08_threads' and item.get('entryFailure')]
    require(len(found) == 1, 'one native entry receipt required')
    return found[0]


def validate_raw(row, spec, build, nonce):
    require(row.get('status') == 'not_scored' and row.get('observed') == {} and
            row.get('invariantChecks') == [] and
            row.get('reason') == 'Adapter did not observe every canonical expectation and invariant',
            'raw result projected post-state, evaluated invariants or has another runtime error')
    raw = native_receipt(row)
    if raw.get('productionVariant') == 'timeline':
        validate_nested(row, raw, spec, build, nonce)
        return
    require((raw.get('caseId'), raw.get('traceDigest'), raw.get('role'), raw.get('bundleName')) ==
            (spec['caseId'], spec['traceDigest'], build['role'], build['bundleName']), 'native identity mismatch')
    require(raw.get('entryExecuted') is True and raw.get('prefixExecuted') is True and
            raw.get('eventExecuted') is False and not raw.get('failure'), 'real prefix incomplete')
    payload = 'task08-positive-control:' + spec['caseId']
    require(raw.get('entryFailure') == {'classification': 'required_feature_entry_missing',
            'requestedAction': 'open_thread', 'positiveControlBody': payload,
            'canonicalEventExecuted': False}, 'wrong entry assessment')
    require(raw.get('basePositiveControl') == {'roomRendered': True, 'roomSendCompleted': True,
            'requestedAction': 'open_thread', 'routeAvailable': False}, 'room positive control incomplete')
    window = raw.get('verifiedWindow', {})
    require(all(window.get(key) is True for key in ('focused', 'hostVerified')) and
            window.get('routeName') == 'pages/Index' and window.get('bundleName') == build['bundleName'],
            'wrong focused original application window')
    require(raw.get('launchEvidence', {}).get('created') is True and
            raw.get('launchEvidence', {}).get('destroyed') is True, 'native lifecycle incomplete')
    require(row.get('productionSources') == raw.get('productionSources') == build['nativeUIObserver']['sources'],
            'candidate production binding mismatch')
    bridge = row.get('nativeBridge', {})
    require(bridge.get('candidateUIVerified') is True and bridge.get('applicationContextAvailable') is True and
            bridge.get('capabilities', {}).get('execution', {}).get('nonce') == nonce, 'native session mismatch')
    frames = raw.get('frames', [])
    require([frame.get('label') for frame in frames] == ['before_event', 'after_event'], 'ordered prefix frames missing')
    for frame in frames:
        require(frame.get('windowIdentity') == window, 'positive control changed candidate window')
        controls = {item['name']: item for item in frame.get('controls', [])}
        require(controls.get('roomComposer', {}).get('visible') is True and
                controls.get('roomRoot', {}).get('present') is False, 'common room or absent entry unproven')
        inventory = frame.get('inventory')
        require(isinstance(inventory, list) and len(inventory) > 2, 'native UI inventory missing')
        require(not any(str(node.get('id', '')).startswith(('thread_', 'room_open_thread_')) or
                    ('Button' in str(node.get('type', '')) and 'thread' in str(node.get('text', '')).lower())
                    for node in inventory), 'another thread entry needs its own binding')
        require(frame.get('pageObserver', {}).get('available') is True and
                frame['pageObserver'].get('instanceCount') == 1, 'original receiver unavailable')
    before, after = [frame['pageObserver']['state'] for frame in frames]
    require(before['composerText'] == payload and after['composerText'] == '' and
            after['sendState'] == 'success' and after['gatewayLastBody'] == payload and
            after['events'] == before['events'] + [payload], 'original room send did not execute')
    require(any(node.get('text') == payload for node in frames[1]['inventory']), 'positive control did not render')
    require(any(action.get('kind') == 'click' and action.get('target') == 'roomSend' and
                action.get('executed') is True for action in raw.get('actions', [])) and
            all(action.get('executed') is True for action in raw.get('actions', [])), 'physical room send absent')
    require(any(call.get('owner') == 'RoomTimelineGateway' and call.get('method') == 'sendMessage' and
                call.get('args') == [payload] and call.get('completed') is True and call.get('result') is True
                for call in frames[1]['pageObserver'].get('calls', [])), 'native SDK boundary receipt absent')


def validate_nested(row, raw, spec, build, nonce):
    require(spec['key'] == 'restore_nested_context' and
            (raw.get('caseId'), raw.get('traceDigest'), raw.get('role'), raw.get('bundleName')) ==
            (spec['caseId'], spec['traceDigest'], build['role'], build['bundleName']), 'nested identity mismatch')
    require(raw.get('entryExecuted') is True and raw.get('prefixExecuted') is True and
            raw.get('eventExecuted') is False and not raw.get('failure'), 'nested prefix incomplete')
    require(raw.get('launchEvidence', {}).get('created') is True and
            raw.get('launchEvidence', {}).get('destroyed') is True, 'nested lifecycle incomplete')
    require(row.get('productionSources') == raw.get('productionSources') == build['nativeUIObserver']['sources'],
            'nested source binding mismatch')
    bridge = row.get('nativeBridge', {})
    require(bridge.get('candidateUIVerified') is True and bridge.get('applicationContextAvailable') is True and
            bridge.get('capabilities', {}).get('execution', {}).get('nonce') == nonce, 'nested native session mismatch')
    failure = raw['entryFailure']
    require(failure.get('classification') == 'required_nested_entry_unreachable' and
            failure.get('target') == 'thread_open_poll', 'wrong required nested entry')
    samples = failure.get('samples', [])
    require(len(samples) == 2, 'stable nested entry inventory missing')
    for sample in samples:
        window = sample.get('windowIdentity', {})
        require(window.get('bundleName') == build['bundleName'] and window.get('focused') is True and
                window.get('hostVerified') is True and window.get('routeName') == 'pages/Index', 'nested window mismatch')
        target = sample.get('target', {})
        require(target.get('id') == 'thread_open_poll' and target.get('present') in (None, False) and
                sample.get('pollTextCount') == 0, 'missing Poll control not established')
        inventory = sample.get('inventory', [])
        ids = {node.get('id') for node in inventory}
        require(len(inventory) > 2 and {'thread_composer', 'thread_open_location'} <= ids and
                'thread_open_poll' not in ids, 'native inventory/positive anchors incomplete')
        require(samples[0]['windowIdentity'].get('stageMainWindowId') == window.get('stageMainWindowId') and
                window.get('stageMainWindowId') is not None, 'nested probe changed original application instance')
    before = [frame['state']['thread'] for frame in raw.get('frames', []) if frame.get('label') == 'before_event']
    after = [frame['state']['thread'] for frame in raw.get('frames', []) if frame.get('label') == 'after_event']
    require(len(before) == len(after) == 2 and [state['surface'] for state in before] == ['attachment', 'location'] and
            all(state['surface'] == 'thread' for state in after), 'real preceding nested transitions incomplete')
    require(all(state['rootEvent']['id'] == '$root' and state['composerText'] == 'draft' and
                state['replyTargetId'] == '$reply' for state in before + after), 'native nested given/prefix changed')
    actions = raw.get('actions', [])
    require(all(action.get('executed') is True for action in actions) and
            [action['target'] for action in actions if action.get('kind') == 'click'][-4:] ==
            ['thread_open_attachment', 'attachment_discard', 'thread_open_location', 'location_discard'],
            'physical preceding nested navigation missing')


def normalize(row, spec, build, nonce, artifact):
    validate_raw(row, spec, build, nonce)
    result = copy.deepcopy(row)
    result.update(status='fail', observed=None, invariantChecks=[], transitionExecuted=False,
                  failureKind='semantic_missing_feature_entry',
                  unevaluatedInvariants=copy.deepcopy(spec['invariants']),
                  unobservedExpectedFields=list(spec['expected']), assertionFailures=[],
                  entryFailureEvidence={'policyId': POLICY, 'nativeResult': artifact},
                  reason='Required feature entry is unreachable after a real native positive-control prefix; later state is unknown.')
    return result


def verify_normalized(row, spec, build, nonce):
    evidence = row.get('entryFailureEvidence', {})
    require(evidence.get('policyId') == POLICY, 'unknown policy')
    artifact = evidence['nativeResult']
    require(record(artifact['path']) == artifact, 'raw native artifact changed')
    raw_row = json.loads(Path(artifact['path']).read_text())
    require(row == normalize(raw_row, spec, build, nonce, artifact), 'normalized early failure was modified')
    return raw_row


class EvidenceReader:
    """Resolve copied evidence without modifying any signed JSON or native row."""

    def __init__(self, report):
        self.mapping = {}
        self.original_root = None
        self.removed_binaries = []
        relocation = report.get('provenance', {}).get('strictEvidence', {}).get('relocations')
        if relocation:
            manifest = json.loads(self.read(relocation))
            require(manifest.get('taskId') == '08_threads' and manifest.get('schemaVersion') == 1,
                    'wrong relocation manifest')
            self.original_root = Path(manifest['originalRoot']).resolve()
            retained_root = Path(manifest['retainedRoot']).resolve()
            require(Path(relocation['path']).resolve().is_relative_to(retained_root), 'relocation root mismatch')
            destinations = set()
            for item in manifest['files']:
                original = Path(item['originalPath']).resolve()
                retained = item['retained']
                destination = Path(retained['path']).resolve()
                require(original.is_relative_to(self.original_root) and destination.is_relative_to(retained_root),
                        'relocation escapes its original or retained root')
                require(original not in self.mapping and destination not in destinations, 'duplicate relocation')
                require(original.relative_to(self.original_root) == destination.relative_to(retained_root),
                        'relocation changed relative artifact identity')
                self.mapping[original] = retained
                destinations.add(destination)
                self.read(retained)
            self.removed_binaries = manifest.get('removedBinaryArtifacts', [])
        strict = report.get('provenance', {}).get('strictEvidence')
        if strict:
            manifest = json.loads(self.read({'path': strict['manifest'], 'sha256': strict['manifestSha256']}))
            require(manifest.get('taskId') == '08_threads' and manifest.get('platform') == 'arkts' and
                    manifest.get('hapsRetained') is False, 'wrong retained evidence manifest')
            root = Path(strict['path']).resolve()
            for item in manifest['files']:
                path = (root / item['path']).resolve()
                require(path.is_relative_to(root), 'retained evidence manifest escapes its root')
                self.read({**item, 'path': str(path)})

    def read(self, item, code=False):
        original = Path(item.get('path') or item.get('file')).resolve()
        replacement = self.mapping.get(original)
        if code and any(original.is_relative_to(root) for root in
                        (ROOT / 'state_tests/runtime/arkts', ROOT / 'scripts/runtime_semantics')):
            require(replacement is None, 'reviewed evaluator source cannot be replaced by a relocation')
        if self.original_root and original.is_relative_to(self.original_root):
            require(replacement is not None, 'original artifact omitted from relocation manifest')
        actual = Path(replacement['path']).resolve() if replacement else original
        allowed = [ROOT / 'experiment_results', ROOT / 'eval_runs']
        if code:
            allowed += [ROOT / 'state_tests/runtime/arkts', ROOT / 'scripts/runtime_semantics',
                        ROOT / 'benchmark_tasks/08_threads']
        require(any(actual.is_relative_to(root.resolve()) for root in allowed), 'artifact outside retained evidence')
        data = actual.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        for expected in (item, replacement):
            if expected:
                require(expected.get('sha256', digest) == digest and expected.get('bytes', len(data)) == len(data),
                        'artifact hash or length changed')
        return data

    def json(self, item, code=False):
        return json.loads(self.read(item, code=code))

    def binary(self, item):
        path = Path(item['path']).resolve()
        if path.exists():
            self.read(item)
            return
        matches = [entry for entry in self.removed_binaries
                   if Path(entry['path']).resolve() == path and
                   all(entry.get(key) == item.get(key) for key in ('sha256', 'bytes'))]
        if matches:
            require(len(matches) == 1, 'ambiguous binary cleanup record')
            return
        cleanup = self.json({'path': str(path.parents[2] / 'binary-cleanup.json')})
        require(cleanup.get('hashesRecordedBeforeRemoval') is True and
                cleanup.get('binariesRetained') is False and cleanup.get('remaining') == [],
                'binary was removed without a complete cleanup receipt')
        matches = [entry for entry in cleanup['removed'] if Path(entry['path']).resolve() == path]
        require(len(matches) == 1 and all(matches[0][key] == item[key] for key in ('sha256', 'bytes')),
                'removed application/test binary differs from packaged artifact')


def _validate_report_evidence(report, contract):
    """Deep-check arbitrary source-bound runs; no patch or candidate-directory oracle."""
    require(report.get('taskId') == contract.get('taskId') == '08_threads' and
            report.get('platform') == 'arkts' and report.get('role') in ('base', 'final', 'agent'),
            'wrong report task/platform/role')
    reader = EvidenceReader(report)
    provenance = report.get('provenance', {})
    references = provenance.get('task08Runtime')
    if references:
        execution_record, build_record = references['execution'], references['build']
    else:
        entries = [row['entryFailureEvidence']['nativeResult'] for row in report['semantic']['cases']
                   if row.get('entryFailureEvidence')]
        require(bool(entries), 'explicit runtime references required for a report without entry failures')
        execution_record = {'path': str(Path(entries[0]['path']).parent / 'device-execution.json')}
        execution = reader.json(execution_record)
        build_record = execution['buildReport']
    execution = reader.json(execution_record)
    build = reader.json(build_record)
    require(reader.read(build_record) == reader.read(execution['buildReport']), 'execution/build binding differs')
    require(execution.get('taskId') == build.get('taskId') == '08_threads' and
            execution.get('role') == build.get('role') == report['role'], 'runtime role identity differs')
    require(execution.get('status') == 'transport_completed' and execution.get('transportCompleted') is True and
            execution.get('productionUnchanged') is True and execution.get('candidateAbsentBeforeInstall') is True and
            execution.get('cleanup', {}).get('ownedAppUninstalled') is True, 'transport/fresh install/cleanup incomplete')
    require(build.get('status') == 'built_not_executed' and build.get('caseCount') == len(contract['cases']) and
            build.get('caseId') is None and build.get('requiresFreshInstallPerCase') is True and
            all(build.get(key) is True for key in
                ('productionUnchanged', 'copiedProductionUnchanged', 'temporaryProjectRemoved')) and
            build.get('runtimeCompile', {}).get('passed') is True, 'runtime build isolation incomplete')
    if provenance.get('candidateSource'):
        require(Path(build['source']).resolve() == Path(provenance['candidateSource']).resolve(),
                'packaged source is not the supplied standalone candidate')
    strict = build['task08Strict']
    require(strict.get('role') == report['role'] and strict.get('caseSelection') == 'all' and
            strict.get('caseCount') == len(contract['cases']) and 1 <= strict.get('timeoutSeconds', 0) <= 3600,
            'runtime build used another case selection or budget')
    canonical = ROOT / 'benchmark_tasks/08_threads/transitions.json'
    require(strict['canonicalContract']['sha256'] == record(canonical)['sha256'] and
            json.loads(canonical.read_text()) == contract, 'runtime canonical contract changed')
    for name in ('wrapper', 'sharedBuilder', 'generatedBuilder', 'installer'):
        item = dict(strict[name])
        item['path'] = str((ROOT / item['path']).resolve())
        reader.read(item, code=True)
    observer = build['nativeUIObserver']
    require(observer.get('productionUnchanged') is True and observer.get('role') == report['role'] and
            observer.get('production') == build.get('production'), 'native production inventory differs')
    require(bool(observer.get('fixtures')), 'reviewed native fixtures missing')
    for fixture in observer['fixtures'] + [observer['installer']]:
        reader.read(fixture, code=True)
    sources = {item['path']: item['sha256'] for item in observer['sources']}
    production = {item['path']: item['sha256'] for item in build['production']}
    require(len(sources) >= 2 and all(production.get(path) == digest for path, digest in sources.items()),
            'observer is not bound to packaged production sources')
    source = Path(build['source'])
    if source.is_dir():
        actual = {path.relative_to(source).as_posix(): record(path)['sha256']
                  for path in (source / 'entry/src/main').rglob('*') if path.is_file()}
        require(actual == production, 'candidate production changed since packaging')
    for name in ('standaloneAppCompile', 'ohosTestCompile'):
        require(build.get(name, {}).get('passed') is True, 'application/test packaging did not succeed')
        reader.binary(build[name]['artifact'])
    require(len(build['commands']) == 2, 'application/test build command inventory incomplete')
    for target, command in zip(('default', 'ohosTest'), build['commands']):
        require(isinstance(command, list) and 'assembleHap' in command and 'module=entry@' + target in command,
                'application/test build command differs')
        log = reader.read({'path': str(Path(build_record['path']).parent / ('build-' + target + '.log'))})
        require(b'BUILD SUCCESSFUL' in log, 'native build success log missing')
    for command in execution['commands']:
        reader.read({'path': str(Path(execution_record['path']).parent / command['log']), 'sha256': command['sha256']})
    rows, native_rows, artifacts = report['semantic']['cases'], execution['rows'], execution['rowArtifacts']
    require(len(rows) == len(native_rows) == len(artifacts) == len(contract['cases']), 'canonical row inventory incomplete')
    require(rows == native_rows, 'public report rows differ from executed normalized rows')
    normalization = execution.get('entryNormalization')
    raw_execution = execution
    if normalization:
        require(normalization.get('policyId') == POLICY, 'unknown execution normalization policy')
        verify_implementation_receipt(normalization['implementation'])
        raw_execution = reader.json(normalization['rawExecution'])
        expected_raw = copy.deepcopy(execution)
        del expected_raw['entryNormalization']
        expected_raw['rows'] = raw_execution['rows']
        require(raw_execution == expected_raw, 'normalization changed transport metadata or other evidence')
    nonce = execution.get('executionNonce')
    require(isinstance(nonce, str) and len(nonce) == 32 and bool(execution.get('pid')), 'runtime nonce/pid missing')
    identities = {}
    paths = set()
    for index, (spec, row, artifact) in enumerate(zip(contract['cases'], rows, artifacts)):
        require((row.get('caseId'), row.get('traceDigest')) == (spec['caseId'], spec['traceDigest']) and
                row.get('taskId') == '08_threads' and row.get('role') == report['role'], 'canonical runtime identity differs')
        path = Path(artifact['local']).resolve()
        require(path not in paths and artifact.get('executionNonce') == nonce, 'native artifact reused or nonce differs')
        paths.add(path)
        native_record = {'path': str(path), 'sha256': artifact['sha256'], 'bytes': artifact['bytes']}
        raw_row = reader.json(native_record)
        require(raw_execution['rows'][index] == raw_row, 'raw execution row differs from pulled native bytes')
        if row.get('entryFailureEvidence'):
            evidence = row['entryFailureEvidence']
            require(normalization is not None and evidence.get('policyId') == POLICY and
                    evidence.get('nativeResult') == native_record, 'entry row is not bound to the actual native artifact')
            require(row == normalize(raw_row, spec, build, nonce, native_record),
                    'entry failure differs from independently evaluated runtime prefix')
        else:
            require(row == raw_row, 'scored row differs from pulled native bytes')
            receipts = [item for item in row.get('evidence', []) if isinstance(item, dict) and
                        item.get('taskId') == '08_threads' and item.get('caseId') == spec['caseId']]
            require(len(receipts) == 1, 'native page receipt missing or ambiguous')
            receipt = receipts[0]
            require((receipt.get('traceDigest'), receipt.get('role'), receipt.get('bundleName')) ==
                    (spec['traceDigest'], report['role'], build['bundleName']), 'native receipt identity differs')
            require(receipt.get('entryExecuted') is True and receipt.get('eventExecuted') is True and
                    not receipt.get('failure') and
                    receipt.get('productionSources') == observer['sources'] and
                    receipt.get('launchEvidence', {}).get('created') is True and
                    receipt.get('launchEvidence', {}).get('destroyed') is True, 'actual native transition incomplete')
            if receipt.get('productionVariant') == 'timeline':
                require(receipt.get('observed') == row.get('observed') and
                        receipt.get('invariantChecks') == row.get('invariantChecks'),
                        'original timeline state differs from scored observations')
            else:
                require(receipt.get('productionVariant') == 'final' and
                        receipt.get('finalPositiveControl') ==
                        {'threadOpened': True, 'rootVisible': True, 'replyVisible': True} and
                        receipt.get('uiAssertions') and all(value is True for value in receipt['uiAssertions'].values()) and
                        row.get('observationLevel') == 'openharmony_api23_original_application_ui_and_shared_production_domain' and
                        any(call.get('module') in sources and call.get('method') != 'constructor'
                            for call in row.get('calls', [])), 'original UI/shared-production domain binding incomplete')
            window = receipt.get('verifiedWindow', {})
            require(window.get('hostVerified') is True and window.get('focused') is True and
                    window.get('bundleName') == build['bundleName'] and window.get('routeName') == 'pages/Index',
                    'actual candidate window differs')
            require(receipt.get('actions') and all(action.get('executed') is True for action in receipt['actions']),
                    'native UI action was not executed')
        row_sources = row.get('productionSources', [])
        require({item['path']: item['sha256'] for item in row_sources} == sources and
                all(sources.get(item['path']) == item['sha256'] for item in row_sources) and
                row.get('nativeBridge', {}).get('candidateUIVerified') is True and
                row.get('nativeBridge', {}).get('applicationContextAvailable') is True and
                row.get('nativeBridge', {}).get('capabilities', {}).get('execution', {}).get('nonce') == nonce,
                'row production sources/session differ')
        identities[spec['caseId']] = (nonce, execution['pid'], str(path), artifact['sha256'])
    return identities


def validate_report_evidence(report, contract):
    try:
        return _validate_report_evidence(report, contract)
    except (KeyError, IndexError, TypeError, AttributeError) as error:
        raise ValueError('Task08 entry proof: malformed runtime provenance: ' + str(error)) from error


def validate_entry_failure(row, report, used_observation_ids, contract=None):
    require(contract is not None, 'canonical contract required')
    identities = validate_report_evidence(report, contract)
    require(row in report['semantic']['cases'] and row.get('entryFailureEvidence', {}).get('policyId') == POLICY,
            'entry row is not part of this runtime report')
    identity = identities[row['caseId']]
    require(identity not in used_observation_ids, 'runtime entry observation reused')
    used_observation_ids.add(identity)


def apply(build_path, execution_path):
    build, execution = [json.loads(Path(path).read_text()) for path in (build_path, execution_path)]
    require(execution.get('status') == 'transport_completed' and execution.get('transportCompleted') is True and
            execution.get('candidateAbsentBeforeInstall') is True and
            execution.get('cleanup', {}).get('ownedAppUninstalled') is True, 'transport/install/cleanup failed')
    contract = json.loads((ROOT / 'benchmark_tasks/08_threads/transitions.json').read_text())
    if not any(any(isinstance(item, dict) and item.get('entryFailure') for item in row.get('evidence', []))
               for row in execution['rows']):
        return
    specs = {spec['caseId']: spec for spec in contract['cases']}
    records = execution.get('rowArtifacts') or [execution.get('rowArtifact')]
    require(len(execution['rows']) == len(records) == build['caseCount'] and all(records), 'incomplete native artifact inventory')
    artifacts = {row['caseId']: item for row, item in zip(execution['rows'], records)}
    changed = False
    for index, row in enumerate(execution['rows']):
        if not any(isinstance(item, dict) and item.get('entryFailure') for item in row.get('evidence', [])):
            continue
        item = artifacts[row['caseId']]
        artifact = record(item['local'])
        require((artifact['sha256'], artifact['bytes']) == (item['sha256'], item['bytes']), 'native artifact changed')
        require(json.loads(Path(item['local']).read_text()) == row, 'row differs from native artifact')
        execution['rows'][index] = normalize(row, specs[row['caseId']], build, execution['executionNonce'], artifact)
        changed = True
    if changed:
        original = Path(execution_path).with_name('device-execution.raw.json')
        with original.open('x') as stream:
            stream.write(Path(execution_path).read_text())
        execution['entryNormalization'] = {'policyId': POLICY, 'implementation': record(__file__),
                                           'rawExecution': record(original)}
        Path(execution_path).write_text(json.dumps(execution, indent=2) + '\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', type=Path, required=True)
    parser.add_argument('--execution', type=Path, required=True)
    args = parser.parse_args()
    apply(args.build, args.execution)
