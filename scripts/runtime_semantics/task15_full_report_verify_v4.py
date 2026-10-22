"""Default independent admission for the complete Task15 report, including NS.

No override flag disables raw, contract, source, episode, cleanup or public
validation. A missing/ineligible raw episode yields only that case's NS, never
a semantic failure. Source closure selects bindings, not verdicts.
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import re

from . import task15_full_report_v4 as full
from . import task15_fresh_admission_v2 as native
from . import task14_15_arkts_entry_evidence as entry
from . import task14_15_formal_core as core
from . import task15_native_transition_v4 as transition

require = native.require
read = native.read


def counts(rows):
    return {'passed': sum(row['status'] == 'pass' for row in rows),
        'failed': sum(row['status'] == 'fail' for row in rows),
        'notScored': sum(row['status'] == 'not_scored' for row in rows), 'total': len(rows)}


def _contract(index, contract):
    require(index.get('protocol') == full.PROTOCOL and contract == read(index['contract']) and
            contract.get('taskId') == full.TASK and len(contract['cases']) == 10,
            'Wrong full-report protocol/canonical contract')
    require({spec['caseId'] for spec in contract['cases']} == full.HOST_CASES | full.native.NATIVE_CASES and
            not full.HOST_CASES.intersection(full.native.NATIVE_CASES), 'Exact ten-case pole partition required')
    require(index['evaluator'] == full.implementation(), 'Full evaluator source version changed')
    manifest = read(index['taskManifest'])
    require(manifest.get('taskId') == full.TASK and all(re.fullmatch('[0-9a-f]{40}',
        manifest['android'][key]) for key in ('baseCommit', 'finalCommit')), 'Immutable upstream commit identities missing')
    native.identity(index['evaluator'])
    inventory = read(index['inputInventory'])
    sources = [{key: item[key] for key in ('path', 'bytes', 'sha256')} for item in inventory['files']
               if item['path'].startswith('entry/src/main/')]
    native._input_closure(inventory, {'production': sources})
    require(inventory['source'] == index['source'], 'Full source inventory belongs to another candidate')
    require(0 < index['budgetSeconds'] <= 3600 and
            index['deadlineEpochMs'] - index['startedAtEpochMs'] <= index['budgetSeconds'] * 1000 + 10,
            'Whole scorer budget reset/extended')
    if index.get('finishedAtEpochMs') is not None:
        require(index['startedAtEpochMs'] <= index['finishedAtEpochMs'] <= index['deadlineEpochMs'],
                'Whole scoring/cleanup exceeded its deadline')
    public_path = full.ROOT / 'scripts/run_runtime_transition_matrix.py'
    public_record = index['publicValidator']
    require(public_record['path'] == str(public_path) and
        public_record['snapshot']['sha256'] == public_record['sha256'], 'Original public source pin changed')
    native.artifacts.bound(public_record['snapshot'])
    require(set(index['host']) <= full.HOST_CASES and set(index['native']) <= full.native.NATIVE_CASES,
            'Unknown/incorrect pole case binding')
    return inventory


def _obligations(spec):
    return {key: copy.deepcopy(spec[key]) for key in ('given', 'event', 'expected', 'invariants')}


def _row(spec, *, observed, checks, checkpoints, sources, runtime, raw_evidence, episode_id):
    require({item['description'] for item in checks} == set(spec['invariants']) and
            len(checks) == len(spec['invariants']) and all(type(item.get('passed')) is bool for item in checks),
            'Missing/extra/fabricated original invariant obligation')
    passed = core._contains(observed, spec['expected']) and all(item['passed'] for item in checks)
    return {'caseId': spec['caseId'], 'key': spec['key'], 'traceDigest': spec['traceDigest'],
        'status': 'pass' if passed else 'fail', 'observed': observed, 'invariantChecks': checks,
        'checkpoints': copy.deepcopy(checkpoints), 'productionSources': sources, 'runtime': runtime,
        'canonicalObligations': _obligations(spec), 'rawEpisode': raw_evidence, 'episodeId': episode_id,
        'transitionExecuted': True}


def host_row(bundle, index, spec):
    plan, raw, command = (read(bundle[key]) for key in ('plan', 'raw', 'command'))
    require(plan['protocol'] == full.PROTOCOL and plan['canonicalCase'] == spec and
            read(plan['contract']) == read(index['contract']) and plan['evaluator'] == index['evaluator'] and
            plan['inputInventory'] == index['inputInventory'] and plan['source'] == index['source'],
            'Host plan not bound to this case/full source/implementation')
    require(raw.get('protocol') == full.HOST_PROTOCOL and raw.get('canonicalCase') == spec and
            raw.get('source') == index['source'] and raw.get('evaluatorSha256') == index['evaluator']['sha256'] and
            raw.get('caseId') == spec['caseId'] and raw.get('traceDigest') == spec['traceDigest'] and
            raw.get('outcome') == 'transition_observed' and raw.get('error') is None,
            'Host error or projected/old episode: NOT_SCORED')
    require(raw['role'] == 'agent' and raw['taskId'] == full.TASK and
            re.fullmatch('[0-9a-f]{32}', raw['executionNonce']) and
            raw['episodeId'] == raw['executionNonce'] + ':' + spec['caseId'], 'Unbound host episode identity')
    require(command['command'] == plan['command'] == [full.NODE, str(full.HOST), '--plan', bundle['plan']['path']] and
            command['exit'] == 0 and command['timedOut'] is False and
            index['startedAtEpochMs'] <= raw['startedAt'] <= raw['finishedAt'] <= index['deadlineEpochMs'] and
            raw['deadlineEpochMs'] <= index['deadlineEpochMs'] + 10 and
            command['startedAtEpochMs'] <= raw['startedAt'] <= command['finishedAtEpochMs'] and
            raw['finishedAt'] <= command['finishedAtEpochMs'] + 10, 'Host command/whole deadline did not complete')
    lines = native.artifacts.bound(command['log']).decode().splitlines()
    require(any(raw['episodeId'] in line for line in lines), 'Command log not bound to actual fresh episode')
    require(raw.get('cleanup') == {'externalPendingReleased': True, 'productionFieldsAssignedByEvaluator': False,
        'vmEpisodeDiscardedAtProcessExit': True, 'noDeviceOrBuildStarted': True}, 'Host external cleanup incomplete')
    inventory = read(index['inputInventory'])
    known = {item['path']: item for item in inventory['files']}
    sources = raw['productionSources']
    require(sources and len({item['path'] for item in sources}) == len(sources) and all(
        known.get(item['path'], {}).get('sha256') == item['sha256'] for item in sources), 'Host execution source mismatch')
    sources = [{key: known[item['path']][key] for key in ('path', 'bytes', 'sha256')} for item in sources]
    binding = raw['apiBinding']
    require(known[binding['path']]['sha256'] == binding['sha256'] and
            binding['class'] == 'AccountDeactivationPresenter', 'Unbound production API')
    calls, actions, frames = raw['calls'], raw['actions'], raw['frames']
    require(not any(call.get('unavailableNativeService') for call in calls), 'Host OS/transport call unavailable')
    constructors = [call for call in calls if call.get('class') == binding['class'] and call['method'] == 'constructor']
    require(len(constructors) == 1 and constructors[0]['module'] == binding['path'], 'Not one own production receiver')
    require(len({item['sequence'] for item in frames + actions}) == len(frames + actions) and
            all(item.get('episodeId') == raw['episodeId'] for item in frames + actions), 'Host episode reused')
    afters = [frame for frame in frames if frame['label'] == 'after_event']
    require(len(afters) == 1, 'No own host after-event observation')
    after = afters[0]
    events = [action for action in actions if action['phase'] == 'event']
    require(events and all(action['executed'] is True and action['sequence'] < after['sequence'] for action in events),
            'Actual host event missing')
    for action in actions:
        if action['kind'] not in ('production_method', 'production_constructor'):
            continue
        require(0 <= action['callStart'] < action['callEnd'] <= len(calls), 'No real production invocation span')
        name = 'constructor' if action['kind'] == 'production_constructor' else action['method']
        require(any(call.get('module') == binding['path'] and call.get('class') == binding['class'] and
            call.get('method') == name and (name == 'constructor' or call['args'] == action['args'])
            for call in calls[action['callStart']:action['callEnd']]), 'Receipt lacks actual production call')
    state = after['state']
    if spec['key'] == 'default_form_blocks_submit':
        require(raw['givenMode'] == 'constructor_defaults_no_setter_repair' and
            not any(action['method'] in ('setPassword', 'setEraseData') for action in actions) and
            [(action['kind'], action['method']) for action in events] ==
                ([('production_constructor', 'AccountDeactivationPresenter')] +
                 ([('production_method', 'openForm')] if binding['shape'] == 'clientCallback' else [])),
            'Default form was repaired by a fixture or had no real production creation/open event')
        before = next(frame for frame in frames if frame['label'] == 'constructor_defaults')
        observed = {key: state[key] for key in ('password', 'eraseData', 'submitEnabled')}
        passed = state['requestCount'] == 0 and not raw['externalRequests']
    else:
        require(raw['givenMode'] == 'observed_before_event' and len(events) == 1, 'No one own canonical event')
        befores = [frame for frame in frames if frame['label'] == 'before_event']
        require(len(befores) == 1, 'No canonical host given observation')
        before = befores[0]
        require(before['sequence'] < events[0]['sequence'] < after['sequence'] and
                before['receiverId'] == after['receiverId'] and core._contains(before['state'], spec['given']),
                'Canonical given/same receiver not actually established')
        event = events[0]
        if event['kind'] == 'production_method':
            require(before['callCount'] <= event['callStart'] < event['callEnd'] <= after['callCount'],
                    'Event receipt borrowed an invocation outside own before/after boundary')
        key = spec['key']
        if key == 'password_enables_submit':
            require((event['kind'], event['method'], event['args']) ==
                    ('production_method', 'setPassword', [spec['event']['value']]), 'Pasted input was not the original newline event')
            observed = {name: state[name] for name in ('password', 'submitEnabled')}
            passed = isinstance(state['password'], str) and '\n' not in state['password'] and '\r' not in state['password']
        elif key == 'erase_data_option':
            require((event['kind'], event['method'], event['args']) ==
                    ('production_method', 'setEraseData', [spec['event']['value']]), 'Wrong erase-data event')
            observed = {'eraseData': state['eraseData']}
            passed = state['password'] == before['state']['password']
        elif key == 'success_completes':
            require((event['kind'], event['method'], event['args']) ==
                    ('external_response', 'deactivation_response', [1, 'fulfilled']) and
                    len(raw['externalRequests']) >= 1 and raw['externalRequests'][0]['settlement'] == 'fulfilled',
                    'No actual external response to a pending production request')
            observed = {name: state[name] for name in ('action', 'requestCount')}
            passed = state['requestCount'] == before['state']['requestCount'] == 1
        elif key == 'close_dialog_resets_action':
            require((event['kind'], event['method'], event['args']) == ('production_method', 'closeDialogs', []),
                    'Wrong close-dialog event')
            observed = {name: state[name] for name in ('action', 'password', 'eraseData')}
            passed = state['requestCount'] == before['state']['requestCount']
        else:
            raise ValueError('Native case cannot be substituted by a host episode')
    require(type(passed) is bool, 'Invariant was not actually observed')
    checks = [{'description': spec['invariants'][0], 'passed': passed,
               'observed': {'before': before['state'], 'after': state, 'eventReceipts': events}}]
    return _row(spec, observed=observed, checks=checks, checkpoints=[before, after], sources=sources,
        runtime='host_transpiled_current_production_presenter', raw_evidence=bundle, episode_id=raw['episodeId'])


def _native_row(bundle, index, spec):
    data = native.envelope(bundle, read(index['contract']))
    require(data['plan'].get('reportProtocol') == full.PROTOCOL and data['plan']['evaluator'] == index['evaluator'] and
        data['inputs']['rootSha256'] == read(index['inputInventory'])['rootSha256'] and
        data['plan']['source'] == index['source'] and data['spec'] == spec and
        data['plan']['deadlineEpochMs'] <= index['deadlineEpochMs'] + 10, 'Mixed native full-producer/source/case/deadline')
    value = data['native']
    run = read(bundle['run'])
    command_file = Path(data['plan']['command'][1])
    host_record = native.artifacts.artifact(command_file)
    require(any((Path(item['path']) if Path(item['path']).is_absolute() else full.ROOT / item['path']) == command_file and
        item['sha256'] == host_record['sha256'] for item in run.get('scriptHashes', [])),
        'Actual executed native host version not bound')
    if value['outcome'] == 'blocked_required_physical_action':
        review = native.inspect_blocked_prefix(data)
        from scripts import run_runtime_transition_matrix as public
        require(full.POLICY in public.SOURCE_BOUND_ENTRY_POLICIES, 'Blocked005 pending public hook review/registration')
        require(index.get('controls') is not None, 'Blocked005 requires four complete fresh controls')
        verify_controls(index['controls'], evaluator_sha=index['evaluator']['sha256'])
        return {'caseId': spec['caseId'], 'key': spec['key'], 'traceDigest': spec['traceDigest'], 'status': 'fail',
            'observed': None, 'invariantChecks': [], 'transitionExecuted': False,
            'unevaluatedExpected': copy.deepcopy(spec['expected']), 'unevaluatedInvariants': copy.deepcopy(spec['invariants']),
            'canonicalObligations': _obligations(spec), 'actionEligibilityReview': review,
            'productionSources': data['build']['production'], 'checkpoints': copy.deepcopy(value['frames']),
            'entryFailureEvidence': {'policyId': full.POLICY, 'bundle': bundle, 'controls': index['controls']},
            'runtime': 'openharmony_api23_device_https_arkui', 'episodeId': value['sessionId'], 'rawEpisode': bundle}
    # Every non-default native case establishes its own physical form prefix.
    value_frames = [frame for frame in value['frames'] if frame['label'] == 'before_event']
    require(len(value_frames) == 1, 'No own native given frame')
    before = value_frames[0]
    if spec['caseId'] != 'ad_state_001_capability_gates_entry':
        p = before['presenter']
        binding = data['build']['nativeUIObserver']['binding']
        require(p['binding']['presenterSourcePath'] == binding['presenterSourcePath'] and
            p['binding']['productionModuleUrl'] == binding['productionModuleUrl'] and
            p['binding']['importCompleted'] is True and
            p['binding']['importPhase'] == 'after_original_page_ready_before_fixture',
            'Native observer not bound to the actual original production page')
        for kind, target in (('click', 'entry'), ('input', 'password'), ('click', 'erase')):
            require(any(item['kind'] == kind and item['target'] == target and item['executed'] is True and
                item['sessionId'] == value['sessionId'] and item['sequence'] < before['sequence']
                for item in value['actions']), 'Own physical form setup missing')
        for method, argument in (('setPassword', 'secret'), ('setEraseData', True)):
            require(any(item.get('method') == method and item.get('args') == [argument] and
                item.get('instanceId') == p['instanceId'] and item.get('returned') is True
                for item in p['calls']), 'No own original production setter evidence')
    if spec['caseId'] == 'ad_state_001_capability_gates_entry':
        cap = read(index['capability'])
        implementation = Path(__file__).with_name('task15_capability_v4.py')
        require(cap.get('freshProtocol') == full.PROTOCOL and cap.get('runtimeImplementation') == {
            'path': str(implementation), 'sha256': core.sha256(implementation)},
            'Capability came from an old/unbound evaluator version')
    observed = transition.inspect_transition(data, capability=index.get('capability'))
    frames = [frame for frame in value['frames'] if frame['label'] in ('before_event', 'after_event')]
    require(len(frames) == 2 and frames[0]['sequence'] < frames[1]['sequence'], 'Own native before/after frames required')
    sources = [{key: item[key] for key in ('path', 'bytes', 'sha256')} for item in data['inputs']['files']
               if item['path'] in {item['path'] for item in data['build']['production']}]
    return _row(spec, observed=observed['observed'], checks=observed['invariantChecks'], checkpoints=frames,
        sources=sources, runtime='openharmony_api23_device_https_arkui', raw_evidence=bundle, episode_id=value['sessionId'])


def _prefix_row(reference, index, spec, inventory):
    report = read(reference)
    prefix_module = Path(__file__).with_name('task15_prefix_v4.py')
    require(report.get('freshProtocol') == full.PROTOCOL and report.get('runtimeImplementation') == {
        'path': str(prefix_module), 'sha256': core.sha256(prefix_module)}, 'Old/unbound prefix producer version')
    command = read(report['outerCommand'])
    runner = native.artifacts.bound(report['provenance']['runner']).decode()
    require('Whole base probe deadline exhausted' in runner and command['exit'] == 0 and command['timedOut'] is False,
            'Prefix runtime did not execute the bounded current producer')
    require(entry.closure.reviewed_source(full.TASK, inventory['rootSha256']),
            'Unknown source cannot be classified by missing selectors')
    require(report['provenance']['source'] == index['source'] and report.get('status') == 'passed',
            'Prefix source/transport incomplete')
    rows = [row for row in report['semantic']['cases'] if row['caseId'] == spec['caseId']]
    require(len(rows) == 1 and rows[0]['traceDigest'] == spec['traceDigest'], 'No own canonical prefix episode')
    actual = rows[0]
    entry.check_raw(actual, report, full.TASK)
    build = read(report['compile']['build'])
    require(build['passed'] is True and build['productionUnchanged'] is True and
        build['copiedProductionUnchanged'] is True and build['temporaryProjectRemoved'] is True,
        'Base packaging/environment failure is not semantic failure')
    native._input_closure(inventory, {'production': build['sources']})
    proof = entry.closure.check_prefix(actual, report, full.TASK, build['sources'],
                                      candidate_root_sha256=inventory['rootSha256'])
    return {'caseId': spec['caseId'], 'key': spec['key'], 'traceDigest': spec['traceDigest'], 'status': 'fail',
        'failureKind': 'semantic_missing_feature_entry', 'failPhase': 'entry', 'transitionExecuted': False,
        'observed': None, 'invariantChecks': [], 'unevaluatedExpected': copy.deepcopy(spec['expected']),
        'unevaluatedInvariants': copy.deepcopy(spec['invariants']), 'canonicalObligations': _obligations(spec),
        'checkpoints': copy.deepcopy(actual['checkpoints']), 'productionSources': build['sources'],
        'runtime': 'openharmony_api23_device_missing_entry',
        'entryFailureEvidence': {'policyId': entry.POLICY_ID, 'report': reference, 'nativeLayoutClosure': proof,
            'rawRowSha256': native.artifacts.row_digest(actual),
            'observationIds': [f"{entry.POLICY_ID}:{reference['sha256']}:{spec['caseId']}"]},
        'episodeId': 'prefix:' + reference['sha256'] + ':' + spec['caseId']}


def derive_rows(index, contract):
    inventory = _contract(index, contract)
    rows, executed, episodes = [], {}, set()
    sizes = {item['path']: item for item in inventory['files']}
    for spec in contract['cases']:
        try:
            if index.get('prefix'):
                row = _prefix_row(index['prefix'], index, spec, inventory)
            elif spec['caseId'] in full.HOST_CASES:
                row = host_row(index['host'][spec['caseId']], index, spec)
            else:
                row = _native_row(index['native'][spec['caseId']], index, spec)
            require(row['episodeId'] not in episodes, 'Same episode reused for multiple canonical cases')
            episodes.add(row['episodeId'])
            for item in row['productionSources']:
                require(item['sha256'] == sizes[item['path']]['sha256'], 'Executed source differs from whole input')
                executed[item['path']] = {key: sizes[item['path']][key] for key in ('path', 'bytes', 'sha256')}
        except (ValueError, KeyError, IndexError, StopIteration, OSError) as error:
            row = {**core.unavailable_rows({'cases': [spec]}, f'{type(error).__name__}: {error}')[0],
                'canonicalObligations': _obligations(spec)}
        rows.append(row)
    return rows, [executed[path] for path in sorted(executed)]


def packaging_complete(index):
    try:
        if index.get('prefix'):
            report = read(index['prefix']); build = read(report['compile']['build'])
            return build.get('passed') is True and build.get('temporaryProjectRemoved') is True
        require(set(index['native']) == full.native.NATIVE_CASES and index['capability'], 'Packaging incomplete')
        for bundle in index['native'].values():
            build = read(bundle['build'])
            require(build.get('runtimeCompile', {}).get('passed') is True, 'Native packaging failed')
        capability = read(index['capability'])
        return capability.get('build', {}).get('runtimeCompile', {}).get('passed') is True
    except (ValueError, KeyError, OSError):
        return False


def _verify_value_unsealed(report, contract):
    from scripts import run_runtime_transition_matrix as public
    require((report.get('taskId'), report.get('platform'), report.get('role'), report.get('observationMode')) ==
        (full.TASK, 'arkts', 'agent', 'runtime_state_transition'), 'Not a full standalone agent report')
    provenance = report['provenance']
    index = read(provenance['fullTask15']['index'])
    rows, sources = derive_rows(index, contract)
    require(report['semantic'] == {**counts(rows), 'cases': rows}, 'Report row/count differs from independent own-episode admission')
    inventory = read(index['inputInventory'])
    require(provenance['candidateMode'] == 'standalone_directory' and provenance['archivedPatchApplied'] is False and
        provenance['candidateSource'] == index['source'] and provenance['candidateRootSha256'] == inventory['rootSha256'] and
        provenance['productionSources'] == sources and
        provenance['fullTask15']['evaluatorSha256'] == index['evaluator']['sha256'], 'Report source/full evaluator binding differs')
    require(provenance['fullTask15']['protocol'] == full.PROTOCOL and
            provenance['fullTask15']['controlLabel'] == index.get('controlLabel'), 'Full-report protocol/label differs')
    for source in sources:
        record = provenance['productionSourceSnapshots'][source['path']]
        data = native.artifacts.bound(record)
        require(record['sha256'] == source['sha256'] and len(data) == source['bytes'], 'Actual production snapshot differs')
    require(report['compile'] == index['applicationCompile'] and
            report['runtimeCompile']['passed'] is packaging_complete(index), 'App compile/runtimeCompile conflated')
    require(report['runtimeCompile'].get('status') == ('passed' if packaging_complete(index) else 'not_scored'),
            'Runtime packaging status differs from actual evidence')
    if report['compile']['passed'] is True:
        proof = read(report['compile']['evidence'])
        require(proof.get('passed') is True and proof.get('candidateRootSha256') == inventory['rootSha256'],
                'Application compile has no independent source-bound full-build proof')
    retained = provenance['retainedEvidence']
    root = Path(retained['path'])
    require(str(root) == index['evidenceRoot'], 'Wrong retained evidence root')
    retained_records = {}
    for item in retained['files']:
        relative = Path(item['path'])
        require(not relative.is_absolute() and '..' not in relative.parts, 'Escaping retained evidence path')
        record = {**item, 'path': str(root / relative)}
        native.artifacts.bound(record)
        require(record['path'] not in retained_records, 'Duplicate retained evidence record')
        retained_records[record['path']] = record
    def bind_retained(value):
        if isinstance(value, dict):
            if {'path', 'bytes', 'sha256'} <= value.keys() and Path(value['path']).is_absolute() and Path(value['path']).is_relative_to(root):
                require(retained_records.get(value['path']) == {key: value[key] for key in ('path', 'bytes', 'sha256')},
                        'Referenced raw/production evidence missing from retained manifest')
            for child in value.values():
                bind_retained(child)
        elif isinstance(value, list):
            for child in value:
                bind_retained(child)
    bind_retained(index)
    bind_retained(provenance['productionSourceSnapshots'])
    core.validate_cleanup(report)
    require(report['diagnostics']['adapter'] == ('ready' if counts(rows)['notScored'] == 0 else 'incomplete'),
            'Incomplete runtime incorrectly declared ready')
    public.validate_report(report, contract)
    return {'passed': True, 'publicValidatorPassed': True, 'independentDefaultGuardPassed': True,
        'counts': counts(rows), 'evaluatorSha256': index['evaluator']['sha256'],
        'publicationEligible': counts(rows)['notScored'] == 0 and packaging_complete(index),
        'originalModelMetricsChanged': False,
        'publicValidatorAtExecution': copy.deepcopy(index['publicValidator']),
        'publicValidatorAtRevalidation': {'path': str(full.ROOT / 'scripts/run_runtime_transition_matrix.py'),
            'sha256': core.sha256(full.ROOT / 'scripts/run_runtime_transition_matrix.py')},
        'publicSourceChangedSinceExecution': index['publicValidator']['sha256'] !=
            core.sha256(full.ROOT / 'scripts/run_runtime_transition_matrix.py')}


def _verify_report_unsealed(path):
    report = core.load(Path(path))
    index = read(report['provenance']['fullTask15']['index'])
    return {**_verify_value_unsealed(report, read(index['contract'])), 'report': native.artifacts.artifact(path)}


def _verify_controls_unsealed(controls, *, evaluator_sha):
    require(set(controls) == {'base', 'final', 'base_copy_agent', 'final_copy_agent'}, 'Four fresh controls required')
    roots, source_paths, evidence_roots, episode_ids = {}, set(), set(), set()
    for pole, reference in controls.items():
        report = read(reference)
        index = read(report['provenance']['fullTask15']['index'])
        require(index.get('controls') is None and not any(
            row.get('entryFailureEvidence', {}).get('policyId') == full.POLICY for row in report['semantic']['cases']),
            'Calibration controls cannot recursively depend on blocked-candidate admission')
        result = _verify_value_unsealed(report, read(index['contract']))
        require(result['publicationEligible'] and index['evaluator']['sha256'] == evaluator_sha,
                'Old/mixed/NS controls cannot calibrate candidate005')
        expected = 'fail' if pole in ('base', 'base_copy_agent') else 'pass'
        require(all(row['status'] == expected for row in report['semantic']['cases']), 'Four-control polarity failed')
        require(index['source'] not in source_paths and index['evidenceRoot'] not in evidence_roots,
                'Controls need distinct source copies and evidence roots')
        source_paths.add(index['source']); evidence_roots.add(index['evidenceRoot'])
        for row in report['semantic']['cases']:
            require(row['episodeId'] not in episode_ids, 'Episode reused across controls')
            episode_ids.add(row['episodeId'])
        roots[pole] = report['provenance']['candidateRootSha256']
    manifest = core.load(full.ROOT / 'benchmark_tasks' / full.TASK / 'task.json')['arkts']
    require(roots['base'] == roots['base_copy_agent'] == core.directory_digest(full.ROOT / manifest['basePath']) and
        roots['final'] == roots['final_copy_agent'] == core.directory_digest(full.ROOT / manifest['finalPath']) and
        roots['base'] != roots['final'], 'Controls are not exact approved base/final byte copies')
    return {'passed': True, 'publicAndIndependentRevalidationPassed': True, 'reports': controls}


def verify_report(path):
    from .task15_supervision_v4 import verify_admission
    # Fail closed before expensive raw verification if end-to-end finalization was revoked.
    admission = verify_admission(path)
    return {**_verify_report_unsealed(path), 'endToEndDeadlineAdmission': admission}


def verify_value(report, contract):
    """Public value API is sealed too; assembly uses the explicit private guard."""
    from .task15_supervision_v4 import verify_admission
    seal = core.load(Path(report['diagnostics']['deadlineAdmissionPath']))
    matches = []
    for reference in seal.get('files', []):
        path = Path(reference['path'])
        if path.name == 'report.json' and read(reference) == report:
            matches.append(path)
    require(len(matches) == 1, 'Unsealed/mixed value cannot bypass end-to-end admission')
    admission = verify_admission(matches[0])
    return {**_verify_value_unsealed(report, contract), 'endToEndDeadlineAdmission': admission}


def verify_controls(controls, *, evaluator_sha):
    from .task15_supervision_v4 import verify_admission
    seals = []
    for reference in controls.values():
        seal = verify_admission(Path(reference['path']))
        require(seal['mode'] == 'controls', 'Separate candidate deadlines cannot masquerade as one control budget')
        seals.append(seal)
    require(len(seals) == 4 and all(seal == seals[0] for seal in seals), 'Four controls require one outer admission')
    group = core.load(Path(seals[0]['output']) / 'four-controls.json')
    require(group['reports'] == controls and group['status'] == 'passed', 'Control references differ from admitted group')
    return _verify_controls_unsealed(controls, evaluator_sha=evaluator_sha)


def validate_entry_failure(row, report, used_observation_ids, contract=None):
    """Small parent integration hook. No registration is performed by this module."""
    require(contract is not None and report['taskId'] == full.TASK and report['platform'] == 'arkts' and
        report['role'] == 'agent' and row['entryFailureEvidence']['policyId'] == full.POLICY, 'Wrong blocked-entry identity')
    index = read(report['provenance']['fullTask15']['index'])
    spec = native.spec_for(contract, row['caseId'])
    actual = _native_row(row['entryFailureEvidence']['bundle'], index, spec)
    require(actual == row, 'Invented blocked post-state/invariant or changed physical evidence')
    token = row['episodeId']
    require(token not in used_observation_ids, 'Reused blocked action evidence')
    used_observation_ids.add(token)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('report', type=Path)
    args = parser.parse_args()
    print(json.dumps(verify_report(args.report), indent=2))
