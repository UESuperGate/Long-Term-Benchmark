'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const retention = require('./task11_arkts_evidence_retention.cjs');
const runtime = require('./task11_arkts_strict_runtime.cjs');

test('native not_scored bytes survive normalization failure and temporary-tree deletion', () => {
  const work = fs.mkdtempSync(path.join(os.tmpdir(), 'task11-native-retention-'));
  try {
    const source = path.join(work, 'temporary'), retained = path.join(work, 'retained');
    fs.mkdirSync(source);
    const raw = Buffer.from('{"caseId":"case","status":"not_scored","unsupported":"actual binding failure"}\n');
    fs.writeFileSync(path.join(source, 'native-result.json'), raw);
    fs.writeFileSync(path.join(source, 'device-execution.json'), Buffer.from('actual execution bytes\r\n'));
    fs.writeFileSync(path.join(source, 'build-command.log'), 'actual failed log\n');
    fs.writeFileSync(path.join(source, 'device-build-report.json'), '{"actual":"build"}\n');
    const manifest = retention.retainTree(source, retained);
    assert.throws(() => runtime.normalizeRow(JSON.parse(raw), { caseId: 'case' }, 'agent'), /identity\/verdict mismatch/);
    const data = JSON.parse(fs.readFileSync(manifest.path));
    fs.rmSync(source, { recursive: true });
    assert.equal(data.files.length, 4);
    const native = data.files.find(item => item.relativePath === 'native-result.json');
    assert.deepEqual(retention.restoredBytes(native), raw);
    assert.equal(JSON.parse(retention.restoredBytes(native)).status, 'not_scored');
    const restored = path.join(work, 'restored');
    assert.equal(retention.restore(manifest.path, restored).restoredFiles, 4);
    assert.deepEqual(fs.readFileSync(path.join(restored, 'native-result.json')), raw);
    assert.throws(() => retention.restore(manifest.path, restored), /overwrite/);
  } finally { fs.rmSync(work, { recursive: true, force: true }); }
});

test('gzip and original byte binding corruptions reject restoration', () => {
  const work = fs.mkdtempSync(path.join(os.tmpdir(), 'task11-retention-integrity-'));
  try {
    const source = path.join(work, 'source'); fs.mkdirSync(source);
    fs.writeFileSync(path.join(source, 'raw.json'), 'exact native bytes\n');
    const receipt = retention.retainTree(source, path.join(work, 'archive'));
    const item = JSON.parse(fs.readFileSync(receipt.path)).files[0];
    assert.throws(() => retention.restoredBytes({ ...item, original: { ...item.original, sha256: '0'.repeat(64) } }), /differs/);
    fs.appendFileSync(item.gzip.path, 'corrupt');
    assert.throws(() => retention.restoredBytes(item), /binding changed/);
  } finally { fs.rmSync(work, { recursive: true, force: true }); }
});

test('retention keeps versions, skips binaries only after hashing, and never stores inside temporary root', () => {
  const work = fs.mkdtempSync(path.join(os.tmpdir(), 'task11-retention-versions-'));
  try {
    const source = path.join(work, 'source'); fs.mkdirSync(source);
    const raw = path.join(source, 'raw.log');
    fs.writeFileSync(raw, 'first'); fs.writeFileSync(path.join(source, 'app.hap'), 'binary');
    const destination = path.join(work, 'archive');
    retention.retainTree(source, destination);
    fs.writeFileSync(raw, 'second');
    const manifest = JSON.parse(fs.readFileSync(retention.retainTree(source, destination).path));
    assert.equal(manifest.files.length, 2);
    assert.deepEqual(manifest.files.map(item => retention.restoredBytes(item).toString()), ['first', 'second']);
    assert.equal(manifest.binaryHashes.length, 1);
    assert.equal(manifest.binaryHashes[0].bytes, 6);
    assert.throws(() => retention.retainTree(source, path.join(source, 'bad')), /outside temporary/);
  } finally { fs.rmSync(work, { recursive: true, force: true }); }
});
