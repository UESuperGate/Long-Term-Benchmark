'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const runtime = require('./task11_arkts_strict_runtime.cjs');

const root = path.resolve(__dirname, '../..');
const contract = JSON.parse(fs.readFileSync(path.join(root, 'benchmark_tasks/11_room_upgrade_navigation/transitions.json')));
const snapshots = () => ['before:event', 'after:event'].map(label => ({ label,
  state: { state: { currentRoomId: '!actual:example.org' }, controls: { composer: { visible: true } },
    routeName: 'pages/Index', windowId: 42 } }));

test('Task11 ArkTS normalization covers all six canonical transitions', () => {
  for (const spec of contract.cases) {
    const row = runtime.normalizeRow({ caseId: spec.caseId, traceDigest: spec.traceDigest, role: 'agent', status: 'pass',
      observed: spec.expected, checkpoints: snapshots(),
      invariantChecks: spec.invariants.map(description => ({ description, passed: true })) }, spec, 'agent');
    assert.equal(row.transitionExecuted, true);
    assert.deepEqual(row.checkpoints.map(item => item.name), ['before:event', 'after:event']);
    assert.equal(row.checkpoints[0].state.production.currentRoomId, '!actual:example.org');
  }
});

test('Task11 ArkTS mutation checks fail closed', () => {
  const spec = contract.cases[0];
  assert.throws(() => runtime.normalizeRow({ caseId: spec.caseId, traceDigest: spec.traceDigest, role: 'agent',
    status: 'pass', observed: spec.expected, checkpoints: snapshots(),
    invariantChecks: spec.invariants.map(description => ({ description, passed: false })) }, spec, 'agent'),
  /does not satisfy/);
});

test('Task11 does not relabel warm-up or hash-only checkpoints as actual snapshots', () => {
  const spec = contract.cases[0];
  const row = { caseId: spec.caseId, traceDigest: spec.traceDigest, role: 'agent', status: 'pass',
    observed: spec.expected, invariantChecks: spec.invariants.map(description => ({ description, passed: true })) };
  assert.throws(() => runtime.normalizeRow({ ...row, checkpoints: [
    { label: 'prefix:original-page-ready', state: snapshots()[0].state }, snapshots()[1] ] }, spec, 'agent'), /actual canonical snapshot/);
  assert.throws(() => runtime.normalizeRow({ ...row, checkpoints: [
    { label: 'before:event', evidenceSha256: '0'.repeat(64) }, snapshots()[1] ] }, spec, 'agent'), /actual canonical snapshot/);
});

test('Task11 installer and runtime contain no bundle-suffix role inference', () => {
  const installer = fs.readFileSync(path.join(root, 'state_tests/runtime/arkts/native/task11_strict/Task11Strict.install.cjs'), 'utf8');
  assert.doesNotMatch(installer, /endsWith\(['"]\.(?:base|final)['"]\)/);
  assert.match(installer, /options\.role/);
  assert.match(installer, /options\.apiVariant/);
});

test('Task11 recognizes only the shared device-lock mkdir race', () => {
  assert.equal(runtime.lockRace("EEXIST: file already exists, mkdir '/tmp/ltb-arkts-device-abc123'"), true);
  assert.equal(runtime.lockRace('aa-test command failed'), false);
  assert.equal(runtime.lockRace('EEXIST: unrelated output directory'), false);
});

test('Task11 retries empty preflight transport only before test execution', () => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'task11-preflight-test-'));
  try {
    fs.writeFileSync(path.join(directory, 'device-execution.json'), JSON.stringify({
      status: 'incomplete', error: 'SyntaxError: Unexpected end of JSON input', rows: [],
      cleanup: { ownedAppUninstalled: true } }));
    fs.writeFileSync(path.join(directory, 'ui-preflight-tree.log'), '');
    assert.equal(runtime.retryablePreflight(directory), true);
    fs.writeFileSync(path.join(directory, 'aa-test.log'), 'test started');
    assert.equal(runtime.retryablePreflight(directory), false);
  } finally { fs.rmSync(directory, { recursive: true, force: true }); }
});

test('Task11 retains actual alias-expanded state snapshots and removes duplicate payload only', () => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'task11-snapshot-test-'));
  const spec = contract.cases[0];
  try {
    const points = snapshots().map(point => ({ ...point, state: {
      ...point.state, state: '[circular]', stateAfter: point.state.state } }));
    const row = runtime.normalizeRow({ caseId: spec.caseId, traceDigest: spec.traceDigest,
      role: 'agent', status: 'pass', observed: spec.expected, checkpoints: points,
      invariantChecks: spec.invariants.map(description => ({ description, passed: true })),
      calls: [{ duplicate: true }], evidence: { duplicate: true } }, spec, 'agent', directory);
    assert.equal(row.checkpoints[0].state.production.currentRoomId, '!actual:example.org');
    assert.equal(JSON.parse(fs.readFileSync(row.checkpoints[0].actualSnapshot.path)).state.stateAfter.currentRoomId,
      '!actual:example.org');
    assert.equal(row.calls, undefined);
    assert.equal(row.evidence, undefined);
    assert.equal(row.removedPayloads.calls.actualCheckpointsRetained, true);
  } finally { fs.rmSync(directory, { recursive: true, force: true }); }
});
