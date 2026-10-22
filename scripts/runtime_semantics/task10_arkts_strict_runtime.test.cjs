'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const runtime = require('./task10_arkts_strict_runtime.cjs');

const root = path.resolve(__dirname, '../..');
const contract = JSON.parse(fs.readFileSync(path.join(root, 'benchmark_tasks/10_media_upload_quality/transitions.json')));

test('Task10 ArkTS normalization binds every exact canonical invariant', () => {
  for (const spec of contract.cases) {
    const row = runtime.normalizeRow({ caseId: spec.caseId, traceDigest: spec.traceDigest, status: 'pass',
      observed: spec.expected, checkpoints: [{ name: 'real-before' }, { name: 'real-after' }],
      invariantChecks: spec.invariants.map(description => ({ description, passed: true })) }, spec, 'agent');
    assert.equal(row.role, 'agent');
    assert.equal(row.transitionExecuted, true);
    assert.deepEqual(row.checkpoints.map(item => item.name), ['before:event', 'after:event']);
  }
});

test('Task10 ArkTS rejects expected-state and invariant mutations', () => {
  const spec = contract.cases[0];
  assert.throws(() => runtime.normalizeRow({ caseId: spec.caseId, traceDigest: spec.traceDigest, status: 'pass',
    observed: {}, checkpoints: [{ name: 'before' }, { name: 'after' }],
    invariantChecks: spec.invariants.map(description => ({ description, passed: true })) }, spec, 'agent'), /differs/);
});

test('Task10 ArkTS cleanup hashes then removes binaries', () => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'task10-arkts-cleanup-'));
  try {
    fs.writeFileSync(path.join(directory, 'candidate.hap'), 'hap');
    fs.mkdirSync(path.join(directory, 'build'));
    fs.writeFileSync(path.join(directory, 'build/evaluator.abc'), 'abc');
    const cleanup = runtime.cleanupArtifacts(directory);
    assert.equal(cleanup.binaryHashes.length, 2);
    assert.equal(cleanup.binaryArtifactsRetained, false);
    assert.equal(cleanup.temporaryBuildRemoved, true);
  } finally { fs.rmSync(directory, { recursive: true, force: true }); }
});

test('Task10 packaging cleanup preserves original build JSON until lossless host retention', () => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'task10-original-build-'));
  try {
    const artifacts = path.join(directory, 'application-artifacts');
    fs.mkdirSync(artifacts);
    const report = path.join(artifacts, 'device-build-report.json');
    const original = Buffer.from('{ "original": true }\n\n');
    fs.writeFileSync(report, original);
    fs.writeFileSync(path.join(artifacts, 'application.hap'), 'temporary hap');
    const cleanup = runtime.cleanupArtifacts(directory);
    assert.deepEqual(fs.readFileSync(report), original);
    assert.equal(cleanup.binaryHashes.length, 1);
    assert.equal(fs.existsSync(path.join(artifacts, 'application.hap')), false);
  } finally { fs.rmSync(directory, { recursive: true, force: true }); }
});

test('Task10 ArkTS derives both real device templates from explicit candidate parameters', () => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'task10-arkts-derived-'));
  try {
    for (const [name, role] of [['Task10BaseAllDevice.cjs', 'base'], ['Task10FinalAllDevice.cjs', 'agent']]) {
      const destination = path.join(directory, role + '.cjs');
      runtime.deriveDeviceScript(path.join(__dirname, name), destination, {
        bundleName: 'com.example.' + role,
        buildDir: path.join(directory, role + '-build'),
        buildReport: path.join(directory, role + '-build/report.json'),
        hap: path.join(directory, role + '-build/candidate.hap'),
        role,
      });
      const derived = fs.readFileSync(destination, 'utf8');
      assert.ok(derived.includes('const bundleName = ' + JSON.stringify('com.example.' + role) + ';'));
      assert.ok(derived.includes('role: ' + JSON.stringify(role) + ','));
      assert.ok(derived.includes(JSON.stringify(path.join(directory, role + '-build/report.json'))));
      assert.ok(derived.includes(JSON.stringify(path.join(directory, role + '-build/candidate.hap'))));
      assert.ok(derived.includes("process.env.LTB_DEVICE_LOCK_PREACQUIRED !== '1'"));
      assert.doesNotMatch(derived, /const root = path\.resolve\(__dirname/);
      if (role === 'agent') {
        for (const checkpoint of ['before_limit_request_failure', 'before_opening_estimates',
          'before_best_preset_selection']) assert.ok(derived.includes(checkpoint));
      }
    }
  } finally { fs.rmSync(directory, { recursive: true, force: true }); }
});

test('Task10 device waits retry transient dump and exact-node readiness errors', () => {
  for (const name of ['Task10BaseAllDevice.cjs', 'Task10FinalAllDevice.cjs']) {
    const source = fs.readFileSync(path.join(__dirname, name), 'utf8');
    assert.match(source, /catch \(error\) \{\s*lastError = error;/);
    assert.match(source, /last observation: \$\{lastError\.message\}/);
    assert.match(source, /requireOne\(nodes,/);
    assert.match(source, /await waitFor\(`input-\$\{id\}`/);
    assert.match(source, /focused === 'true'/);
    assert.match(source, /input-\$\{id\}-keyboard-dismissed/);
  }
});
