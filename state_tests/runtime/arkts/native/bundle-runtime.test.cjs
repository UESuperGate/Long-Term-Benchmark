'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const test = require('node:test');

const source = fs.readFileSync(path.join(__dirname, 'bundle-runtime.js'), 'utf8')
  .replace('export async function runNativeCase', 'async function runNativeCase');

function loader(factories = {}, constants = {}, native = null) {
  const context = vm.createContext({
    factories, platformConstants: constants,
    metadata: Object.fromEntries(Object.keys(factories).map(file => [file, { path: file }])),
    snapshot: value => value, nativeFixture: native
  });
  vm.runInContext(source, context);
  vm.runInContext('activeNativeContext = nativeFixture', context);
  const calls = [], evidence = [];
  return { load: context.productionLoader('/project', evidence, calls), calls, evidence };
}

test('readonly re-exports load and execute their actual class', () => {
  const { load, calls } = loader({
    '/project/feature.ets': exports => {
      exports.Feature = class Feature { submit() { return 'actual-result'; } };
    },
    '/project/index.ets': (exports, require) => {
      const feature = require('./feature');
      Object.defineProperty(exports, 'Feature', { enumerable: true, get: () => feature.Feature });
    }
  });
  const exports = load('./index');
  assert.equal(new exports.Feature().submit(), 'actual-result');
  assert.equal(Object.getOwnPropertyDescriptor(exports, 'Feature').set, undefined);
  assert.ok(calls.some(call => call.method === 'constructor'));
  assert.ok(calls.some(call => call.method === 'submit'));
});

test('SDK constants do not grant notification service access', () => {
  const SlotType = Object.freeze({ SOCIAL_COMMUNICATION: 1, SERVICE_INFORMATION: 2 });
  const { load, calls } = loader({}, { '@ohos.notification': { SlotType } });
  const notification = load('@ohos.notification');
  assert.equal(notification.default.SlotType.SERVICE_INFORMATION, 2);
  assert.equal(notification.SlotType.SOCIAL_COMMUNICATION, 1);
  assert.equal(calls.length, 0);
  assert.throws(() => { notification.default.SlotType.SERVICE_INFORMATION = 99; }, TypeError);
  assert.throws(() => notification.default.addSlot, /no runtime binding/);
  assert.throws(() => notification.getSlot, /no runtime binding/);
  assert.throws(() => load('@ohos.unbound').default.SlotType, /no runtime binding/);
  assert.equal(calls.length, 3);
  assert.ok(calls.every(call => call.unavailableNativeService));
});

test('setter-backed exports remain instrumented and retain module cache identity', () => {
  let assignments = 0;
  const { load, calls, evidence } = loader({
    '/project/feature.ets': exports => {
      let value = class Feature { submit() { return 'actual-result'; } };
      Object.defineProperty(exports, 'Feature', {
        enumerable: true,
        get: () => value,
        set: replacement => { assignments++; value = replacement; }
      });
    }
  });
  const first = load('./feature');
  assert.strictEqual(load('./feature'), first);
  assert.equal(assignments, 1);
  assert.equal(evidence.length, 1);
  assert.equal(new first.Feature().submit(), 'actual-result');
  assert.equal(calls.filter(call => call.method === 'constructor').length, 1);
  assert.equal(calls.filter(call => call.method === 'submit').length, 1);
});

test('caught service errors still leave unavailable-service evidence', () => {
  const { load, calls } = loader({
    '/project/feature.ets': (exports, require) => {
      const notification = require('@ohos.notification').default;
      exports.Feature = class Feature {
        submit() {
          try { notification.addSlot(2); }
          catch { return 'caught'; }
          return 'unexpected-service-result';
        }
      };
    }
  });
  assert.equal(new (load('./feature').Feature)().submit(), 'caught');
  assert.deepEqual(calls.filter(call => call.unavailableNativeService).map(call => ({ ...call })), [
    { module: '@ohos.notification', method: 'addSlot', unavailableNativeService: true }
  ]);
});

test('native module forwarding preserves identity and records missing operations', () => {
  const target = { value: 7, readSync() { return this.value; } };
  const native = { modules: { '@ohos.file.fs': { default: target } }, capabilities: { context: { available: true } } };
  const { load, calls } = loader({}, {}, native);
  const file = load('@ohos.file.fs').default;
  assert.equal(file.readSync(), 7);
  assert.equal(file.readSync, file.readSync);
  assert.equal(calls[0].nativeService, true);
  assert.strictEqual(native.productionCalls, calls);
  assert.throws(() => file.copyFileSync, /Native API unavailable/);
  assert.equal(calls[1].unavailableNativeService, true);
});

test('await native modules and defaults tolerates absent then without service evidence', async () => {
  const native = { modules: {
    '@ohos.file.fs': { default: { value: 7 } },
    '@ohos.data.preferences': { default: {} }
  }, capabilities: { context: { available: false } } };
  const { load, calls } = loader({}, {}, native);
  for (const request of Object.keys(native.modules)) {
    const module = load(request);
    assert.strictEqual(await module, module);
    assert.strictEqual(await module.default, module.default);
  }
  assert.equal(calls.length, 0);
  assert.throws(() => load('@ohos.file.fs').default.copyFile, /Native API unavailable/);
  assert.throws(() => load('@ohos.data.preferences').default.getPreferences, /Native API unavailable/);
  assert.equal(calls.length, 2);
  assert.ok(calls.every(call => call.unavailableNativeService));
});

test('await unbound modules does not grant any native service access', async () => {
  const { load, calls } = loader();
  const module = load('@ohos.unbound');
  assert.strictEqual(await module, module);
  assert.strictEqual(await module.default, module.default);
  assert.equal(calls.length, 0);
  assert.throws(() => module.default.realOperation, /no runtime binding/);
  assert.equal(calls.length, 1);
  assert.equal(calls[0].unavailableNativeService, true);
});

test('real native then is retained with native receiver and fulfillment or rejection', async () => {
  const failure = new Error('actual then rejection');
  const target = { value: 42, fail: false, then(resolve, reject) {
    if (this.fail) reject(failure);
    else resolve(this.value);
  } };
  const native = { modules: { '@ohos.example': { default: target } }, capabilities: { context: { available: true } } };
  const { load, calls } = loader({}, {}, native);
  const module = load('@ohos.example');
  assert.equal(await module, 42);
  assert.equal(await module.default, 42);
  target.fail = true;
  await assert.rejects(async () => await module, error => error === failure);
  assert.equal(calls.length, 3);
  assert.ok(calls.every(call => call.nativeService && call.method === 'then'));
});

test('non-callable existing then values are preserved', async () => {
  const native = { modules: { '@ohos.example': { default: { then: 7 } } }, capabilities: { context: { available: true } } };
  const { load, calls } = loader({}, {}, native);
  const module = load('@ohos.example');
  assert.equal(module.then, 7);
  assert.strictEqual(await module, module);
  assert.equal(calls.length, 0);
});

test('factory getContext forwards actual case context and fails closed without one', () => {
  const context = { filesDir: '/unit/actual/context' };
  const factory = (exports, require, module, getContext) => { exports.context = getContext(); };
  const native = { modules: {}, context, capabilities: { context: { available: true } } };
  const bound = loader({ '/project/feature.ets': factory }, {}, native);
  assert.strictEqual(bound.load('./feature').context, context);
  assert.ok(bound.calls.some(call => call.method === 'getContext' && call.nativeService));
  const missing = loader({ '/project/feature.ets': factory });
  assert.throws(() => missing.load('./feature'), /Actual native application context unavailable/);
  assert.ok(missing.calls.some(call => call.method === 'getContext' && call.unavailableNativeService));
});
