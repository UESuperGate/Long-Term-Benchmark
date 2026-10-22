'use strict';

const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const vm = require('node:vm');
const { execFileSync } = require('node:child_process');
const { productionLoader, evaluateCase } = require('../../../scripts/runtime_semantics/arkts_runtime.cjs');
const { archivedBase } = require('../../../scripts/runtime_semantics/archived_arkts_base.cjs');
const adapter = require('./tasks08_11.cjs');
const root = path.resolve(__dirname, '../../..');
const tasks = ['08_threads', '09_spaces_lifecycle', '10_media_upload_quality', '11_room_upgrade_navigation'];
const json = file => JSON.parse(fs.readFileSync(path.join(root, file), 'utf8'));
const manifest = id => json(`benchmark_tasks/${id}/task.json`);
const cases = id => json(`benchmark_tasks/${id}/transitions.json`).cases;
const observerFile = path.join(__dirname, 'native/Tasks08_11RoomObserver.js');
const observerSource = fs.readFileSync(observerFile, 'utf8');
const installRoomObserver = vm.runInNewContext(observerSource.replaceAll('export function', 'function') + '\ninstallRoomObserver;');
const clone = value => JSON.parse(JSON.stringify(value));

function reconstruct(t, taskId) {
  const project = fs.mkdtempSync(path.join(os.tmpdir(), 'Tasks08_11-agent-'));
  t.after(() => fs.rmSync(project, { recursive: true, force: true }));
  const original = archivedBase(taskId)?.source || path.join(root, manifest(taskId).arkts.basePath);
  fs.cpSync(path.join(original, 'entry/src/main/ets/features'),
    path.join(project, 'entry/src/main/ets/features'), { recursive: true });
  const patch = path.join(root, 'experiment_results/new_tasks_opencode_minimax_m3_20261015_semantic_repair/provenance/patches', `arkts_${taskId}.patch`);
  execFileSync('git', ['init', '-q', project]);
  execFileSync('git', ['apply', '--include=entry/src/main/ets/features/*', patch], { cwd: project });
  return project;
}

test('08-11 host calibration runs base/final before archived-agent, preserving IDs and unsupported boundaries', async t => {
  for (const role of ['base', 'final', 'agent']) {
    for (const taskId of tasks) {
      const project = role === 'agent' ? reconstruct(t, taskId) : path.join(root, manifest(taskId).arkts[role + 'Path']);
      const counts = { pass: 0, fail: 0, not_scored: 0 };
      for (const caseSpec of cases(taskId)) {
        const row = await evaluateCase(taskId, caseSpec, project, adapter);
        assert.equal(row.caseId, caseSpec.caseId);
        assert.equal(row.traceDigest, caseSpec.traceDigest);
        assert.ok(row.productionSources.length, caseSpec.caseId);
        assert.ok(row.calls.length, caseSpec.caseId);
        assert.ok(row.checkpoints.some(item => item.label === 'before:event'), caseSpec.caseId);
        assert.ok(row.checkpoints.some(item => item.label === 'after:event'), caseSpec.caseId);
        if (role === 'base' && taskId === '08_threads') {
          assert.equal(row.status, 'fail', 'Reachable room entry plus missing thread route is a semantic failure: ' + caseSpec.caseId);
          assert.equal(row.missingObservations.length, 0, caseSpec.caseId);
          assert.ok(row.invariantChecks.every(check => check.passed === false), caseSpec.caseId);
          assert.ok(row.checkpoints.some(item => item.label === 'task08:common-room-positive-control'), caseSpec.caseId);
        } else if (role === 'base') {
          assert.equal(row.status, 'not_scored', 'A missing feature API cannot establish the canonical given: ' + caseSpec.caseId);
        }
        if (role === 'final' && ['08_threads', '09_spaces_lifecycle', '10_media_upload_quality'].includes(taskId))
          assert.equal(row.status, 'pass', row.reason || JSON.stringify(row.assertionFailures));
        if (row.status === 'not_scored') assert.ok(row.reason);
        counts[row.status]++;
      }
      t.diagnostic(`${taskId} ${role}: ${JSON.stringify(counts)} (host production-domain only)`);
    }
  }
});

test('task08 base fails only after the real room positive control completes', async t => {
  const taskId = '08_threads';
  const original = path.join(root, manifest(taskId).arkts.basePath);
  const spec = cases(taskId)[0];
  const control = await evaluateCase(taskId, spec, original, adapter);
  assert.equal(control.status, 'fail');
  assert.ok(control.calls.some(call => call.class === 'RoomTimelinePresenter' && call.method === 'sendMessage'));

  const mutated = fs.mkdtempSync(path.join(os.tmpdir(), 'task08-base-positive-control-mutation-'));
  t.after(() => fs.rmSync(mutated, { recursive: true, force: true }));
  fs.cpSync(path.join(original, 'entry'), path.join(mutated, 'entry'), { recursive: true });
  const feature = path.join(mutated, 'entry/src/main/ets/features/RoomTimelineFeature.ets');
  fs.writeFileSync(feature, fs.readFileSync(feature, 'utf8').replace(
    'this.lastBody = body;\n    return true;',
    'return false;'));
  const row = await evaluateCase(taskId, spec, mutated, adapter);
  assert.equal(row.status, 'not_scored');
  assert.match(row.reason, /positive-control transition did not complete/);
});

test('task08 final semantic mutations are detected by the shared evaluator', async t => {
  const taskId = '08_threads';
  const original = path.join(root, manifest(taskId).arkts.finalPath);
  const mutations = [
    ['open_thread', 'this.surface = ThreadSurface.Thread;', 'this.surface = ThreadSurface.Room;'],
    ['reply_remote_event',
      'const succeeded = this.gateway.sendMessage(body, this.threadRootId, this.replyTargetId);',
      "const succeeded = this.gateway.sendMessage(body, this.threadRootId, '');"],
    ['back_isolates_room', "this.threadRootId = '';", "this.threadRootId = '$root';"],
  ];
  for (const [key, before, after] of mutations) {
    const project = fs.mkdtempSync(path.join(os.tmpdir(), `task08-final-${key}-mutation-`));
    t.after(() => fs.rmSync(project, { recursive: true, force: true }));
    fs.cpSync(path.join(original, 'entry'), path.join(project, 'entry'), { recursive: true });
    const feature = path.join(project, 'entry/src/main/ets/features/ThreadFeature.ets');
    const source = fs.readFileSync(feature, 'utf8');
    assert.ok(source.includes(before), key);
    fs.writeFileSync(feature, source.replace(before, after));
    const row = await evaluateCase(taskId, cases(taskId).find(item => item.key === key), project, adapter);
    assert.equal(row.status, 'fail', `${key}: ${row.reason || JSON.stringify(row.assertionFailures)}`);
  }
});

test('read-only native observer retains original returns, room metadata, history, and restores descriptors', async () => {
  const taskId = '11_room_upgrade_navigation';
  const load = productionLoader(path.join(root, manifest(taskId).arkts.finalPath), [], []);
  const m = load('entry/src/main/ets/features/RoomUpgradeFeature.ets');
  const descriptor = Object.getOwnPropertyDescriptor(m.RoomUpgradePresenter.prototype, 'openPredecessorRoom');
  const observer = installRoomObserver(m.RoomUpgradePresenter);
  try {
    assert.equal(observer.read().available, false);
    const gateway = new m.RoomNavigationGateway();
    const p = new m.RoomUpgradePresenter(gateway);
    p.selectReplacementRoom();
    const before = clone(observer.read());
    assert.equal(before.currentRoomId, '!new:example.org');
    assert.equal(p.openPredecessorRoom(), undefined);
    const after = clone(observer.read());
    assert.equal(after.instanceId, before.instanceId);
    assert.equal(after.currentRoomId, '!old:example.org');
    assert.equal(after.navigationCount - before.navigationCount, 1);
    assert.deepEqual(after.rooms.find(room => room.roomId === '!new:example.org').predecessorRoom,
      { roomId: '!old:example.org', lastEventId: '$last:example.org' });
    assert.deepEqual(after.rooms.find(room => room.roomId === '!new:example.org'), before.rooms.find(room => room.roomId === '!new:example.org'));
    const callCount = after.calls.length;
    assert.equal(observer.read().calls.length, callCount, 'Reading observations must not manufacture candidate calls');
    p.selectReplacementRoom();
    const count = gateway.navigationCount;
    p.openPredecessorRoom();
    p.openPredecessorRoom();
    assert.equal(gateway.navigationCount - count, 1, 'Domain diagnostic only, not physical double-tap proof');
  } finally { observer.dispose(); }
  assert.deepEqual(Object.getOwnPropertyDescriptor(m.RoomUpgradePresenter.prototype, 'openPredecessorRoom'), descriptor);
});

test('room observer binds unchanged legacy and alternative store APIs without inventing upgrade metadata', async t => {
  const taskId = '11_room_upgrade_navigation';
  for (const project of [path.join(root, manifest(taskId).arkts.basePath), reconstruct(t, taskId)]) {
    const m = productionLoader(project, [], [])('entry/src/main/ets/features/RoomFeature.ets');
    const observer = installRoomObserver(m.RoomPresenter);
    try {
      const gateway = new m.RoomGateway();
      const p = new m.RoomPresenter(gateway, m.RoomStore && new m.RoomStore());
      if (m.RoomStore) {
        p.observeRoomInfo('!new:example.org', 'New');
        p.applyPredecessorMetadata('!new:example.org', { roomId: '!old:example.org', lastEventId: '$last:example.org' });
        p.store.selectRoom('!new:example.org');
        p.currentRoom();
        assert.equal(observer.read().rooms[0].predecessorRoom.lastEventId, '$last:example.org');
      } else {
        p.openRoom();
        const observed = clone(observer.read());
        assert.equal(observed.currentRoomId, '!old:example.org');
        assert.equal(observed.rooms[0].successorRoom, null);
        assert.equal(observed.rooms[0].predecessorRoom, null);
        assert.equal(observed.navigationState, undefined);
      }
    } finally { observer.dispose(); }
  }
});

test('native transport returning true without a production callback stays unscored', async () => {
  const taskId = '11_room_upgrade_navigation';
  const project = path.join(root, manifest(taskId).arkts.finalPath);
  const load = productionLoader(project, [], []);
  const m = load('entry/src/main/ets/features/RoomUpgradeFeature.ets');
  const observer = installRoomObserver(m.RoomUpgradePresenter);
  try {
    const p = new m.RoomUpgradePresenter(new m.RoomNavigationGateway());
    p.selectOldRoom();
    // Transport-only UNIT stub. It never executes a UI callback and must never
    // produce a scored canonical result or be published as native UI evidence.
    const ui = {
      observe(ids) {
        return { available: true, snapshot: { tree: { width: 1080, height: 2340 } },
          controls: ids.map(id => ({ id, present: ['current_room_id', 'open_successor_room'].includes(id),
            node: { $rect: '[0,0],[100,100]', $attrs: { content: p.currentRoom.roomId,
              visibility: 'Visibility.Visible', opacity: 1, enabled: true } } })) };
      },
      sendEvent() { return true; }
    };
    const caseSpec = cases(taskId).find(item => item.key === 'open_successor');
    const result = await adapter.runCase({ taskId, project, caseSpec, load, native: { ui, roomUpgrade: observer } });
    assert.match(result.unsupported, /transport accepted.*callback did not execute/);
    assert.equal(p.gateway.navigationCount, 0);
    assert.equal(p.currentRoom.roomId, '!old:example.org');
    assert.equal(result.invariantChecks.length, 0);
    assert.equal(result.unsupportedInvariants.length, caseSpec.invariants.length);
    const tombstone = cases(taskId).find(item => item.key === 'tombstone_is_read_only');
    const unboundInput = await adapter.runCase({ taskId, project, caseSpec: tombstone, load,
      native: { ui, roomUpgrade: observer } });
    assert.match(unboundInput.unsupported, /composerEnabled input is not independently bound/);
    assert.equal(unboundInput.invariantChecks.length, 0);
  } finally { observer.dispose(); }
});
