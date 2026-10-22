'use strict';

const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const test = require('node:test');

const source = fs.readFileSync(path.join(__dirname, 'native-platform.js'), 'utf8')
  .replace(/^import .*;\n/gm, '').replace(/^export /gm, '');

function fixture(nodes, route = { path: 'pages/', name: 'Index' }, delivered = false) {
  const created = [], removed = [];
  const ui = { getHostContext: () => ({ cacheDir: '/unit/cache' }),
    getRouter: () => ({ getState: () => route }), runScopedTask: callback => callback() };
  const context = vm.createContext({
    fileFs: { mkdirSync: directory => created.push(directory), rmdirSync: directory => removed.push(directory) },
    preferences: {}, router: {}, UIContext: { resolveUIContext: () => ui },
    getInspectorTree: () => ({ $type: 'root' }),
    getInspectorByKey: id => nodes[id] ? JSON.stringify(nodes[id]) : '',
    sendEventByKey: () => delivered, setTimeout
  });
  vm.runInContext(source, context);
  return { create: () => context.createNativeContext('unit', '/unit/sandbox', 'pages/Index'), created, removed };
}

const anchor = { $type: 'Button', $rect: '[1,1],[10,10]', $attrs: { id: 'anchor', visibility: 'Visibility.Visible' } };

test('an empty tree alone never establishes absence', async () => {
  const bridge = await fixture({}).create();
  const observation = bridge.ui.observe(['missing'], 'anchor');
  assert.equal(observation.available, false);
  assert.equal(observation.controls[0].present, null);
  assert.equal(observation.snapshot.completeTree, false);
  await bridge.dispose();
});

test('entry proof binds fresh observations and actual rejected action without claiming canonical failure', async () => {
  const bridge = await fixture({ anchor }).create();
  const proof = await bridge.ui.probeEntry('missing', 'anchor');
  const second = await bridge.ui.probeEntry('missing', 'anchor');
  assert.notEqual(proof.observationId, second.observationId);
  assert.equal(proof.caseId, 'unit');
  assert.equal(proof.action.attempted, true);
  assert.equal(proof.action.delivered, false);
  assert.equal(proof.selectorReachability, 'absent_action_rejected');
  assert.equal(proof.taskEntryReachable, null);
  assert.equal(proof.givenEstablished, null);
  assert.equal(proof.semanticVerdict, null);
  assert.equal(proof.prerequisiteChecks.find(check => check.id === 'positive_anchor_rendered').passed, true);
  assert.equal(proof.prerequisiteChecks.find(check => check.id === 'required_selector_present').observed, false);
  assert.ok(proof.prerequisiteChecks.every(check => check.evidence.every(ref => ref.observationId === proof.observationId)));
  await bridge.dispose();
});

test('accepted event or unrendered anchor cannot establish rejected absent entry', async () => {
  const accepted = await fixture({ anchor }, undefined, true).create();
  assert.equal((await accepted.ui.probeEntry('missing', 'anchor')).selectorReachability, 'unestablished');
  const blank = await fixture({ anchor: { ...anchor, $rect: '[0,0],[0,0]' } }).create();
  const proof = await blank.ui.probeEntry('missing', 'anchor');
  assert.equal(proof.action.attempted, false);
  assert.equal(proof.before.target.present, null);
  assert.equal(proof.selectorReachability, 'unestablished');
  assert.equal(proof.prerequisiteChecks.find(check => check.id === 'required_selector_present').passed, null);
  await accepted.dispose();
  await blank.dispose();
});

test('candidate route plus a rendered keyed anchor establishes keyed absence', async () => {
  const f = fixture({ anchor });
  const bridge = await f.create();
  const events = [];
  bridge.setObservationRecorder(event => events.push(event));
  const observation = bridge.ui.observe(['missing'], 'anchor');
  assert.equal(observation.available, true);
  assert.equal(observation.controls[0].present, false);
  assert.equal(events.length, 1);
  const next = await f.create();
  assert.notEqual(bridge.sandbox, next.sandbox);
  await bridge.dispose();
  await next.dispose();
  assert.deepEqual(f.created, f.removed);
});

test('a harness route or hidden anchor cannot establish candidate absence', async () => {
  const harness = await fixture({ anchor }, { path: 'harness/', name: 'Index' }).create();
  assert.equal(harness.ui.observe(['missing'], 'anchor').controls[0].present, null);
  const hidden = await fixture({ anchor: { ...anchor, $attrs: { ...anchor.$attrs, visibility: 'Visibility.Hidden' } } }).create();
  assert.equal(hidden.ui.observe(['missing'], 'anchor').controls[0].present, null);
  await harness.dispose();
  await hidden.dispose();
});
