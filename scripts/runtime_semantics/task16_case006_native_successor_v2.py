"""Test-only case006 scope successor; no original helper/raw/contract edits.

Not installed or admitted by this module. Materialized evaluator bytes and its
new derivation need reviewed packaging/producer binding before any device run.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.runtime_semantics import tasks16_17_page_ports_evidence as original

UI = ROOT / 'state_tests/runtime/arkts/native/Tasks16_17PagePortsUi.js'
SCOPE = ROOT / 'state_tests/runtime/arkts/native/Task16Case006CanonicalTraceV2.js'
OLD = '          const transitions = observer.read().managerTransitions;\n          const stateSequence = [transitions[0]?.from, ...transitions.map(value => value.to)];'
NEW = '          raw.canonicalManagerTrace = canonicalManagerTraceV2(observer.read(), raw.bootstrap);\n          const transitions = raw.canonicalManagerTrace.canonicalTransitions;\n          const stateSequence = [transitions[0]?.from, ...transitions.map(value => value.to)];'


def generate(output):
    output = Path(output).resolve()
    original.require(output.is_relative_to(ROOT / 'experiment_results') and not output.exists(), 'new audited successor output required')
    generated = compose_ui_text()
    output.mkdir(parents=True)
    target = output / 'Tasks16_17PagePortsUi.case006-v2.js'
    target.write_text(generated)
    legacy = output / 'legacy-before'
    legacy.mkdir()
    snapshots = []
    for path in (UI, Path(original.__file__)):
        retained = legacy / path.name
        retained.write_bytes(path.read_bytes())
        snapshots.append(dict(original=original.record(path), retained=original.record(retained)))
    value = dict(schemaVersion='task16.case006.test-only-successor.v2', originalUi=original.record(UI),
        originalValidator=original.record(original.__file__), scopeModule=original.record(SCOPE),
        generator=original.record(__file__), generatedUi=original.record(target), originalSnapshots=snapshots,
        changeScope='only case006 observed sequence derivation; same actual owners/SDK/UI operations unchanged',
        allOriginalWarmupLogsRetained=True, productionChanged=False, contractChanged=False,
        actualNativeExecuted=False, publicAdmissionChanged=False,
        packagingAndProducerIntegration='pending reviewed successor, not installed into existing fixture')
    (output / 'derivation.json').write_text(json.dumps(value, indent=2)+'\n')
    return value


def compose_ui_text():
    text = UI.read_text()
    original.require(text.count(OLD) == 1, 'exact existing case006 derivation no longer bound')
    return SCOPE.read_text() + '\n' + text.replace(OLD, NEW)


def derive_case006(case, raw):
    """Independent exact canonical manager selection; no raw mutation/projection."""
    original.require(case['key'] == 'handle_failure_recovers' and raw['taskId'] == '16_identity_reset' and
        all(raw.get(key) == case[key] for key in ('caseId', 'key', 'traceDigest')), 'wrong case006 scope')
    original.require(not raw.get('failure') and raw.get('eventExecuted'), 'actual transition incomplete')
    boot = original.bootstrap_facts(raw)
    before = original.frame(raw, 'before_event')
    after = original.frame(raw, 'after_event')
    stable_frame = original.frame(raw, 'after_failure_cleanup')
    current, stable = original.state(after), original.state(stable_frame)
    original.require(original.state(before)['handleState'] == 'loading' and before['sequence'] < stable_frame['sequence'] < after['sequence'],
        'canonical given/actual cleanup/retry order missing')
    for frame in raw['frames']:
        owner = original.state(frame)
        original.require(owner['managerId'] == current['managerId'] and owner['ownerId'] == boot['primaryOwnerId'] and
            frame['windowIdentity'].get('hostVerified') and frame['windowIdentity'].get('focused') and frame.get('inventory'),
            'canonical frame uses detached owner/unobserved UI')
    all_rows = after['owner']['managerTransitions']
    original.require(all(row['managerId'] in (boot['warmupManagerId'], current['managerId']) for row in all_rows), 'unknown manager in trace')
    selected = [row for row in all_rows if row['managerId'] == current['managerId']]
    original.require(selected and all(left['to'] == right['from'] for left, right in zip(selected, selected[1:])), 'canonical trace missing/discontinuous')
    expected_scope = dict(version='case006.actual-canonical-manager.v2', canonicalManagerId=current['managerId'],
        retiredWarmupManagerId=boot['warmupManagerId'], allTransitions=all_rows, canonicalTransitions=selected,
        retiredWarmupTransitions=[row for row in all_rows if row['managerId'] == boot['warmupManagerId']])
    original.require(raw.get('canonicalManagerTrace') == expected_scope, 'declared scope omits/rewrites native logs')
    sequence = [selected[0]['from']] + [row['to'] for row in selected]
    starts = original.calls(raw, 'start_identity_reset')
    observed = dict(failureObserved='failure' in sequence, stateSequence=sequence,
        stableHandleState=stable['handleState'], screen=stable['screen'], progressVisible=stable['progressVisible'],
        retryEnabled=any(item['enabled'] for item in original.ui(stable_frame, 'identity_reset_retry')),
        retryHandleState=current['handleState'])
    invariants = ['failure' in sequence and 'success' not in sequence,
        stable['handleState'] == 'uninitialized' and not stable['progressVisible'] and 'failure' in stable['cleanupHistory'],
        len(starts) == 2 and starts[-1]['delivered'] is False]
    original.require(raw['observed'] == observed and [row['description'] for row in raw['invariantChecks']] == case['invariants'] and
        [row['passed'] for row in raw['invariantChecks']] == invariants, 'original observation/invariant claims differ from scoped facts')
    return dict(observed=observed, invariantChecks=[dict(description=text, passed=value) for text, value in zip(case['invariants'], invariants)],
        canonicalManagerTrace=copy.deepcopy(expected_scope), allWarmupEvidenceRetained=True,
        actualNativeExecutedByThisFunction=False, publicAdmissionChanged=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    print(json.dumps(generate(parser.parse_args().output)))
