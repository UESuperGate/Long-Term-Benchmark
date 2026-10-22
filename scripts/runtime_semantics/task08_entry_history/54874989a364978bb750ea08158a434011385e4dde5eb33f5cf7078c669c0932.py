"""Task08 native common-entry failures; never project unreachable post-state."""
import argparse
import copy
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
POLICY = 'task08.arkts.native-common-entry.v1'


def require(value, message):
    if not value:
        raise ValueError('Task08 entry proof: ' + message)


def record(path):
    path = Path(path).resolve()
    data = path.read_bytes()
    return {'path': str(path), 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


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
