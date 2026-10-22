'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const crypto = require('node:crypto');
const { archivedBase, verifySnapshot } = require('./archived_arkts_base.cjs');
const sha = value => crypto.createHash('sha256').update(value).digest('hex');

function fixture(fn) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'ltb-archived-base-test-'));
  try {
    const task = 'task';
    const directory = 'before';
    const source = path.join(root, directory, 'project');
    fs.mkdirSync(source, { recursive: true });
    fs.writeFileSync(path.join(source, 'source.ets'), 'original');
    const manifest = { stage: 'before', taskId: task, role: 'base', production: [
      { path: 'before/project/source.ets', bytes: 8, sha256: sha('original') }
    ] };
    const manifestFile = path.join(root, directory, 'manifest.json');
    fs.writeFileSync(manifestFile, JSON.stringify(manifest));
    const patch = path.join(root, 'experiment_results/new_tasks_opencode_minimax_m3_20261015_semantic_repair/provenance/patches/arkts_task.patch');
    fs.mkdirSync(path.dirname(patch), { recursive: true });
    fs.writeFileSync(patch, 'original patch');
    const policy = { directory, manifestSha256: sha(fs.readFileSync(manifestFile)), patchSha256: sha('original patch') };
    fn({ root, task, source, manifest, manifestFile, patch, policy });
  } finally { fs.rmSync(root, { recursive: true, force: true }); }
}

test('actual repaired task11 selects the exact original archived base', () => {
  const result = archivedBase('11_room_upgrade_navigation');
  assert.match(result.source, /task11_base_repair\/before\/project$/);
  assert.equal(result.purpose, 'original_archived_candidate_replay_not_repaired_base_agent');
});
test('unrepaired tasks do not receive an unrelated snapshot', () => assert.equal(archivedBase('14_join_room_by_address'), null));
test('valid snapshot accepted', () => fixture(f => assert.equal(verifySnapshot(f.root, f.task, f.policy).source, f.source)));
test('modified production rejected', () => fixture(f => {
  fs.writeFileSync(path.join(f.source, 'source.ets'), 'repaired');
  assert.throws(() => verifySnapshot(f.root, f.task, f.policy), /source changed/);
}));
test('modified patch rejected', () => fixture(f => {
  fs.writeFileSync(f.patch, 'new patch');
  assert.throws(() => verifySnapshot(f.root, f.task, f.policy), /patch changed/);
}));
test('modified manifest rejected', () => fixture(f => {
  fs.appendFileSync(f.manifestFile, ' ');
  assert.throws(() => verifySnapshot(f.root, f.task, f.policy), /manifest changed/);
}));
test('extra unmanifested file rejected', () => fixture(f => {
  fs.writeFileSync(path.join(f.source, 'added.ets'), 'later repair');
  assert.throws(() => verifySnapshot(f.root, f.task, f.policy), /Unmanifested/);
}));
test('symlink rejected even with same bytes', () => fixture(f => {
  fs.renameSync(path.join(f.source, 'source.ets'), path.join(f.root, 'real.ets'));
  fs.symlinkSync(path.join(f.root, 'real.ets'), path.join(f.source, 'source.ets'));
  assert.throws(() => verifySnapshot(f.root, f.task, f.policy), /not regular/);
}));
test('wrong task rejected', () => fixture(f => assert.throws(() => verifySnapshot(f.root, 'wrong', f.policy), /identity/)));
test('path escape rejected', () => fixture(f => {
  f.manifest.production[0].path = '../outside.ets';
  fs.writeFileSync(f.manifestFile, JSON.stringify(f.manifest));
  f.policy.manifestSha256 = sha(fs.readFileSync(f.manifestFile));
  assert.throws(() => verifySnapshot(f.root, f.task, f.policy), /archived source path/);
}));
