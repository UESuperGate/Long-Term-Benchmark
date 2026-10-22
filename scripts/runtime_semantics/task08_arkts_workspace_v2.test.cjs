'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const crypto = require('node:crypto');
const helper = require('./task08_arkts_workspace_v2.cjs');

async function unit(action) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'task08-workspace-unit-'));
  const old = process.env.LTB_TASK08_INTERMEDIATE_AUDIT_DIR;
  process.env.LTB_TASK08_INTERMEDIATE_AUDIT_DIR = root;
  try { await action(root); }
  finally {
    if (old === undefined) delete process.env.LTB_TASK08_INTERMEDIATE_AUDIT_DIR;
    else process.env.LTB_TASK08_INTERMEDIATE_AUDIT_DIR = old;
    fs.rmSync(root, { recursive: true, force: true });
  }
}

test('hash-before-removal covers tiny generated HAP/ABC intermediate bytes', async () => unit(async root => {
  const bytes = Buffer.from('synthetic-binary-unit');
  const work = await helper.withTemporaryWorkspace(async work => {
    fs.writeFileSync(path.join(work, 'entry.hap'), bytes);
    fs.writeFileSync(path.join(work, 'ets.abc'), bytes);
    return work;
  });
  const report = JSON.parse(fs.readFileSync(path.join(root, fs.readdirSync(root)[0])));
  assert.equal(report.removedWorkspace, true); assert.equal(fs.existsSync(work), false);
  assert.equal(report.removed.length, 2);
  assert.equal(report.hashesRecordedBeforeRemoval, true);
  for (const r of report.removed) {
    assert.equal(r.bytes, bytes.length);
    assert.equal(r.sha256, crypto.createHash('sha256').update(bytes).digest('hex'));
  }
}));

test('failed action still preserves intermediate hashes and removes only its workspace', async () => unit(async root => {
  let work;
  await assert.rejects(helper.withTemporaryWorkspace(async directory => {
    work = directory; fs.writeFileSync(path.join(work, 'failed.class'), 'unit');
    throw new Error('simulated compiler failure');
  }), /simulated compiler failure/);
  const report = JSON.parse(fs.readFileSync(path.join(root, fs.readdirSync(root)[0])));
  assert.equal(report.removed.length, 1); assert.equal(report.removedWorkspace, true);
  assert.equal(fs.existsSync(work), false);
}));

test('dependency symlink is recorded but never followed or removed outside owned work', async () => unit(async root => {
  const outside = path.join(root, 'dependency.jar'); fs.writeFileSync(outside, 'do-not-touch');
  await helper.withTemporaryWorkspace(async work => fs.symlinkSync(outside, path.join(work, 'dependency.jar')));
  const file = fs.readdirSync(root).find(name => name.endsWith('.json'));
  const report = JSON.parse(fs.readFileSync(path.join(root, file)));
  assert.equal(report.removed.length, 0); assert.equal(report.symlinks.length, 1);
  assert.equal(report.symlinks[0].followed, false);
  assert.equal(fs.readFileSync(outside, 'utf8'), 'do-not-touch');
}));

test('missing audit destination fails before creating unrecorded temporary inputs', async () => {
  const old = process.env.LTB_TASK08_INTERMEDIATE_AUDIT_DIR;
  delete process.env.LTB_TASK08_INTERMEDIATE_AUDIT_DIR;
  try {
    await assert.rejects(helper.withTemporaryWorkspace(async () => assert.fail('must not execute')), /Explicit owned/);
  } finally {
    if (old !== undefined) process.env.LTB_TASK08_INTERMEDIATE_AUDIT_DIR = old;
  }
});
