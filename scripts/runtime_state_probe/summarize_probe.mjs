import { readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';

const root = process.argv[2];
if (!root) throw new Error('Evidence directory required');
const read = name => readFileSync(join(root, name), 'utf8');
const jsonl = name => read(name).trim().split(/\r?\n/).map(JSON.parse);
const events = rows => rows.flatMap(r => (r.data?.observedPropertiesInfo || []).map(p => ({ time: r.time, ...p })));
const candidateRows = jsonl('ark_candidate_state_trace.jsonl');
const candidate = events(candidateRows);
const base = events(jsonl('ark_base_state_trace.jsonl'));
const snapshots = jsonl('ark_candidate_deep_snapshot.jsonl');
const deepStatus = snapshots.find(r => r.direction === 'properties' && r.data.path === 'this.__clientSnapshot.wrappedValue_.[[Target]].currentUser.status.status');
const scalar = p => p.value?.value ?? p.value?.unserializableValue;
const deep = Object.fromEntries((deepStatus?.data.result?.result || []).map(p => [p.name, scalar(p)]));
const nodes = n => [n.attributes, ...(n.children || []).flatMap(nodes)].filter(Boolean);
const candidateUI = nodes(JSON.parse(read('ark_candidate_late_settings.layout.json')));
const baseUI = nodes(JSON.parse(read('ark_base_settings.layout.json')));
const before = read('android_qr_intro_state.tsv').split(/\r?\n/).map(s => s.split('\t'));
const after = read('android_qr_after_denial.tsv').split(/\r?\n/).map(s => s.split('\t'));
const field = (rows, suffix, value) => rows.some(r => r[0] === 'FIELD' && r[2].endsWith(suffix) && r[4] === value);
const has = (name, value) => candidate.some(p => p.propertyName === name && JSON.stringify(p.value) === JSON.stringify(value));
const check = (id, ok, evidence) => ({ id, result: ok ? 'OBSERVED' : 'NOT_OBSERVED', evidence });
const loading = candidate.find(p => p.propertyName === 'updateStatusAction' && p.value === 'loading');
const laterActions = candidate.filter(p => p.propertyName === 'updateStatusAction' && Date.parse(p.time) > Date.parse(loading?.time));
const checks = [
  check('android_permission_denial_state', field(before, '.permissionAlreadyDenied', 'false') && field(after, '.permissionAlreadyDenied', 'true'), ['android_qr_intro_state.tsv', 'android_qr_after_denial.tsv']),
  check('android_stale_and_new_states_coexist', field(after, '.permissionAlreadyDenied', 'false') && field(after, '.permissionAlreadyDenied', 'true'), ['android_qr_after_denial.tsv']),
  check('android_compose_write_events', read('android_state_watch.tsv').split(/\r?\n/).some(s => s.startsWith('WRITE\t')), ['android_state_watch.tsv']),
  check('ark_candidate_state_ui_dependency', candidate.some(p => p.propertyName === 'pickerState' && p.dependentElementIds?.propertyDependencies?.length > 0), ['ark_candidate_state_trace.jsonl']),
  check('ark_predefined_selection_partial_assertions', has('pickerState', 'predefined') && has('userStatusDraft', { emoji: '\uD83C\uDF34', text: 'Away' }) && has('pickerState', 'hidden') && has('updateStatusAction', 'loading'), ['ark_candidate_state_trace.jsonl']),
  check('ark_nested_status_payload', deep.text === 'Away' && deep.emoji === '\uD83C\uDF34', ['ark_candidate_deep_snapshot.jsonl']),
  check('ark_loading_clear_disabled', has('isUpdatingProfile', true) && candidateUI.some(n => n.text === 'Clear' && n.type === 'Button' && n.enabled === 'false'), ['ark_candidate_state_trace.jsonl', 'ark_candidate_late_settings.layout.json']),
  check('ark_base_same_state_protocol', base.some(p => p.propertyName === 'selectedTab' && p.value === 1 && p.dependentElementIds?.propertyDependencies?.some(d => d.elementTag === 'Tabs')), ['ark_base_state_trace.jsonl']),
  check('ark_base_settings_without_status_entry', baseUI.some(n => n.text === 'Alice') && baseUI.some(n => n.text === 'Privacy') && !baseUI.some(n => n.text === 'My status'), ['ark_base_settings.layout.json'])
];
const report = {
  scope: 'Runtime observation feasibility; NOT a benchmark testcase pass matrix',
  checks,
  candidateSaveObservation: {
    loadingAt: loading?.time,
    captureEndedAt: candidateRows.at(-1).time,
    subsequentObservedActions: laterActions.map(p => p.value),
    secondsObservedAfterLoading: (Date.parse(candidateRows.at(-1).time) - Date.parse(loading?.time)) / 1000,
    lateUIStillSaving: candidateUI.some(n => n.text === 'Saving status...'),
    interpretation: 'No completion observed during this ordinary UI route. Not a formal full save testcase execution.'
  },
  fullTestcasesExecuted: 0,
  warning: 'OBSERVED means evidence of a probe capability or partial assertion, not a functional testcase PASS. Heap snapshots may contain stale objects.'
};
writeFileSync(join(root, 'probe-summary.json'), JSON.stringify(report, null, 2) + '\n');
console.log(JSON.stringify(report, null, 2));
if (checks.some(c => c.result === 'NOT_OBSERVED')) process.exitCode = 1;
