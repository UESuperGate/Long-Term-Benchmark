const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { productionLoader, compareExpected, evaluateCase } = require('./arkts_runtime.cjs');

test('state changes come from executed production method, with source hash and call evidence', async () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'ltb-runtime-test-'));
  try {
    fs.writeFileSync(path.join(root, 'Counter.ets'), 'export class Counter { count: number = 0; add(): void { this.count += 2; } }');
    const adapter = { runCase: async ({ load, trace }) => {
      const { Counter } = load('Counter.ets');
      const subject = new Counter();
      trace('before', { count: subject.count });
      subject.add();
      trace('after', { count: subject.count });
      return { observed: { count: subject.count } };
    } };
    const spec = { caseId: 'counter', traceDigest: 'test', expected: { count: 2 }, invariants: [] };
    const passed = await evaluateCase('test', spec, root, adapter);
    assert.equal(passed.status, 'pass');
    assert.ok(passed.calls.some(call => call.method === 'add'));
    assert.equal(passed.productionSources[0].sha256.length, 64);
    fs.writeFileSync(path.join(root, 'Counter.ets'), 'export class Counter { count: number = 0; add(): void { this.count += 1; } }');
    const mutated = await evaluateCase('test', spec, root, adapter);
    assert.equal(mutated.status, 'fail');
    assert.equal(mutated.observed.count, 1);
    assert.notEqual(passed.productionSources[0].sha256, mutated.productionSources[0].sha256);
  } finally { fs.rmSync(root, { recursive: true }); }
});

test('missing observation is not a semantic failure and extra fields do not hide missing ones', () => {
  const result = compareExpected({ state: 'success', effects: ['persist'] }, { state: 'success', extra: true });
  assert.deepEqual(result.missing, ['effects']);
  assert.deepEqual(result.failures, []);
});

test('import escape and native services fail closed', () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'ltb-runtime-test-'));
  try {
    fs.mkdirSync(path.join(root, 'candidate'));
    fs.writeFileSync(path.join(root, 'Outside.ets'), 'export const value = 1;');
    const load = productionLoader(path.join(root, 'candidate'), [], []);
    assert.throws(() => load('../Outside.ets'), /escapes candidate/);
    const native = load('@ohos.data.preferences');
    assert.throws(() => native.default.getPreferences, /no runtime binding/);
  } finally { fs.rmSync(root, { recursive: true }); }
});

test('an adapter cannot claim pass by returning expected values without executing production', async () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'ltb-runtime-test-'));
  try {
    const spec = { caseId: 'fake', traceDigest: 'test', expected: { value: 1 }, invariants: [] };
    const row = await evaluateCase('test', spec, root, { runCase: async () => ({ observed: { value: 1 } }) });
    assert.equal(row.status, 'not_scored');
  } finally { fs.rmSync(root, { recursive: true }); }
});

test('readonly re-exports remain executable without changing export semantics', () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'ltb-runtime-test-'));
  try {
    fs.writeFileSync(path.join(root, 'Model.ets'), 'export class Model { value: number = 0; increment(): number { return ++this.value; } }');
    fs.writeFileSync(path.join(root, 'Index.ets'), "export { Model } from './Model';");
    const calls = [];
    const load = productionLoader(root, [], calls);
    const subject = new (load('Index.ets').Model)();
    assert.equal(subject.increment(), 1);
    assert.ok(calls.some(call => call.method === 'increment'));
  } finally { fs.rmSync(root, { recursive: true }); }
});
