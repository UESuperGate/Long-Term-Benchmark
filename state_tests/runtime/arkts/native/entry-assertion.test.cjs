'use strict';
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const test = require('node:test');
const assert = require('node:assert/strict');
const context = vm.createContext({});
vm.runInContext(fs.readFileSync(path.join(__dirname, 'entry-assertion.js'), 'utf8').replace(/^export /gm, ''), context);

// Synthetic unit data only. It is never emitted as native execution evidence.
function fixture() {
  const spec = { taskId: '14_join_room_by_address', caseId: 'initial', traceDigest: 'a'.repeat(64),
    given: { surface: 'start_chat', searchActive: false }, event: { name: 'select_join_by_address' }, invariants: ['unchanged existing actions'] };
  const policy = { id: 'unit', approval: 'approved', selectorCoverage: 'reviewed_complete',
    taskId: spec.taskId, caseId: spec.caseId, traceDigest: spec.traceDigest, eventName: spec.event.name,
    sourceSha256: 'b'.repeat(64), route: 'pages/Index', anchorId: 'search', anchorType: 'TextInput',
    entryIds: ['join', 'join_alias'], givenBindings: {
      surface: { kind: 'rendered_surface', value: 'start_chat' },
      searchActive: { kind: 'anchor_attributes', attributes: { text: '', focused: false }, value: false }
    } };
  const binding = { taskId: spec.taskId, role: 'base', sourceSha256: policy.sourceSha256, policySha256: 'c'.repeat(64) };
  const probes = policy.entryIds.map((id, index) => {
    const frame = time => ({ capturedAt: time, available: true, candidateRouteVerified: true,
      route: { path: 'pages/', name: 'Index', index: 2 }, viewport: { width: 1080, height: 2340 },
      anchor: { selector: { kind: 'arkui_id', value: 'search' }, present: true,
        node: { type: 'TextInput', bounds: '[60,400],[1020,500]', visible: true, text: '', focused: false } },
      target: { selector: { kind: 'arkui_id', value: id }, present: false, node: null } });
    return { schemaVersion: 1, kind: 'native_ui_entry_probe', backend: 'native_previewer_arkui',
      caseId: `${binding.taskId}:base:initial`, instanceId: 'instance', observationId: `instance_entry_${index}`,
      candidateRoute: policy.route, before: frame(100 + index * 10), after: frame(102 + index * 10),
      action: { api: 'sendEventByKey', selector: { kind: 'arkui_id', value: id }, action: 10, params: {},
        attempted: true, attemptedAt: 101 + index * 10, delivered: false }, prerequisiteChecks: [] };
  });
  const { assertion } = context.createEntryAssertion(spec, policy, binding, probes);
  return { spec, policy, binding, assertion };
}
const assess = f => context.assessEntryAssertion(f.assertion, f.spec, f.policy, f.binding);

test('reviewed entry failure does not require or invent later state/invariants', () => {
  const f = fixture();
  assert.equal(assess(f).status, 'fail');
  assert.equal(f.assertion.postState, null);
  assert.equal(f.assertion.transitionExecuted, false);
  assert.equal(f.assertion.invariants.evaluated, false);
});

for (const [name, mutate] of [
  ['pending review', f => { f.policy.approval = 'pending'; }],
  ['unreviewed selector alternatives', f => { f.policy.selectorCoverage = 'pending_review'; }],
  ['unestablished external given', f => { f.spec.given.serverResponse = 'success'; }],
  ['unobserved given value', f => { f.assertion.probes[0].before.anchor.node.text = 'searching'; }],
  ['changed source', f => { f.binding.sourceSha256 = 'd'.repeat(64); }],
  ['changed trace', f => { f.spec.traceDigest = 'e'.repeat(64); }],
  ['different case', f => { f.assertion.probes[0].caseId = 'other'; }],
  ['different instance', f => { f.assertion.probes[1].instanceId = 'other'; }],
  ['duplicate observation', f => { f.assertion.probes[1].observationId = f.assertion.probes[0].observationId; }],
  ['missing root', f => { f.assertion.probes[0].before.anchor.node = null; }],
  ['offscreen anchor', f => { f.assertion.probes[0].before.anchor.node.bounds = '[60,3000],[1020,3100]'; }],
  ['zero-area anchor', f => { f.assertion.probes[0].before.anchor.node.bounds = '[60,400],[60,500]'; }],
  ['harness route', f => { f.assertion.probes[0].before.route.path = 'test/'; }],
  ['missing action attempt', f => { f.assertion.probes[0].action.attempted = false; }],
  ['action exception', f => { f.assertion.probes[0].action.error = 'Unavailable'; }],
  ['accepted action', f => { f.assertion.probes[0].action.delivered = true; }],
  ['wrong action selector', f => { f.assertion.probes[0].action.selector.value = 'unrelated'; }],
  ['entry actually present', f => { f.assertion.probes[0].before.target.present = true; }],
  ['alternative not attempted', f => { f.assertion.probes.pop(); }],
  ['invalid time ordering', f => { f.assertion.probes[0].action.attemptedAt = 1; }],
  ['fabricated poststate', f => { f.assertion.postState = {}; }],
  ['fabricated invariant evaluation', f => { f.assertion.invariants.evaluated = true; }]
]) test(name + ' remains unscored', () => {
  const f = fixture(); mutate(f); assert.equal(assess(f).status, 'not_scored');
});

test('a previously consumed observation cannot score a second row', () => {
  const f = fixture();
  assert.equal(context.assessEntryAssertion(f.assertion, f.spec, f.policy, f.binding,
    [f.assertion.probes[0].observationId]).status, 'not_scored');
});
