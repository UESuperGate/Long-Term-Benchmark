'use strict';

// Evaluator regressions only. Native persistence/UI are NOT executed here.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require(process.env.LTB_TYPESCRIPT ||
  '/Applications/DevEco-Studio.app/Contents/tools/hvigor/hvigor-ohos-plugin/node_modules/typescript');
const root = path.resolve(__dirname, '../../../..');

function compile(file, modules = {}) {
  const source = fs.readFileSync(file, 'utf8');
  const output = ts.transpileModule(source, { compilerOptions: {
    module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020
  } }).outputText;
  const module = { exports: {} };
  new vm.Script(`(function(exports,require,module){${output}\n})`).runInNewContext()(module.exports,
    name => { if (!modules[name]) throw new Error('Unbound SDK: ' + name); return modules[name]; }, module);
  return module.exports;
}

function fixture() {
  const api = compile(path.join(__dirname, 'Task17LoadingObserver.js'));
  const contexts = [], sdkPromises = [], writes = [];
  const context = { abilityInfo: { bundleName: 'test', moduleName: 'entry' },
    preferencesDir: '/native/haps/entry/preferences', area: 1,
    toJSON() { throw new Error('Original Context cannot be serialized'); } };
  const prefs = { getPreferences(actual, name) {
    contexts.push(actual);
    assert.equal(name, 'element_x_pinned_messages');
    const result = Promise.resolve({
      get() { return Promise.resolve('[{"eventId":"$a","sender":"sender","body":"body"}]'); },
      put(...args) { writes.push(args); return Promise.resolve(); }, flush() { return Promise.resolve(); }
    });
    sdkPromises.push(result); return result;
  } };
  const production = compile(path.join(root,
    'final_dev_nodes/17_pinned_messages_final_0_5_3/entry/src/main/ets/features/PinnedMessagesFeature.ets'),
  { '@ohos.data.preferences': { default: prefs } });
  return { api, production, prefs, context, contexts, sdkPromises, writes };
}

test('original production enters Loading without any held or replaced SDK Promise', async () => {
  const f = fixture(), P = f.production.PinnedMessagesListPresenter, R = f.production.PinnedMessagesRepository;
  const original = P.prototype.openPinnedMessages;
  let originalPromise;
  // Identity witness only; the original production body runs with unchanged args.
  P.prototype.openPinnedMessages = function(...args) { originalPromise = original.apply(this, args); return originalPromise; };
  const observer = f.api.observeTask17Loading(P, R, f.prefs, f.context);
  const p = new P(new R());
  assert.equal(JSON.parse(observer.snapshot()).presenterCount, 0);
  const result = p.openPinnedMessages(f.context);
  assert.equal(result, originalPromise);
  const immediate = JSON.parse(observer.snapshot());
  const returned = immediate.calls.find(c => c.method === 'openPinnedMessages' && c.phase === 'returned');
  assert.equal(returned.state.listState, 'loading');
  assert.equal(returned.promiseObservation, 'settlement_not_observed');
  assert.equal(returned.nativePromisePending, 'unproven', 'Promise.resolve SDK return does not prove pending I/O');
  assert.equal(immediate.currentPresenterState.listState, 'loading');
  assert.equal(immediate.singlePresenterCallChainObserved, true);
  assert.ok(immediate.calls.some(c => c.method === 'getPreferences' && c.phase === 'returned' && c.sameAbilityContext));
  assert.ok(f.contexts.every(context => context === f.context));
  await result;
  assert.equal(p.listState, 'filled');
  const finished = JSON.parse(observer.snapshot());
  assert.equal(finished.currentPresenterState.listState, 'filled');
  assert.ok(finished.calls.some(c => c.method === 'openPinnedMessages' && c.phase === 'fulfilled' && c.state.listState === 'filled'));
  assert.equal(returned.state.listState, 'loading', 'Saved observations remain immutable');
  assert.equal(f.writes.length, 0);
  assert.equal(finished.semanticVerdict, null);
  assert.equal(finished.renderedLoadingObserved, false);
  assert.equal(finished.navigationParentObserved, false);
  observer.dispose();
});

test('optional frame-registration hook sees original Loading and cannot change the returned Promise on failure', async () => {
  const f = fixture(), P = f.production.PinnedMessagesListPresenter, R = f.production.PinnedMessagesRepository;
  const original = P.prototype.openPinnedMessages;
  let originalPromise, observer, calls = 0;
  P.prototype.openPinnedMessages = function(...args) { return originalPromise = original.apply(this, args); };
  observer = f.api.observeTask17Loading(P, R, f.prefs, f.context, { onOpenReturned() {
    calls++;
    assert.equal(JSON.parse(observer.snapshot()).currentPresenterState.listState, 'loading');
    throw new Error('frame observer unavailable');
  } });
  const p = new P(new R()), returned = p.openPinnedMessages(f.context);
  assert.equal(returned, originalPromise);
  await returned;
  assert.equal(calls, 1); assert.equal(p.listState, 'filled');
  assert.ok(JSON.parse(observer.snapshot()).errors.some(e => e.includes('frame observer unavailable')));
  observer.dispose();
});

test('SDK Promise identity, receiver and original synchronous errors are unchanged', async () => {
  const f = fixture(), before = f.prefs.getPreferences;
  const observer = f.api.observeTask17Loading(f.production.PinnedMessagesListPresenter,
    f.production.PinnedMessagesRepository, f.prefs, f.context);
  const promise = f.prefs.getPreferences(f.context, 'element_x_pinned_messages');
  assert.equal(promise, f.sdkPromises[0]);
  await promise;
  observer.dispose();
  assert.equal(f.prefs.getPreferences, before);
  const error = new Error('original');
  const receiver = { getPreferences() { assert.equal(this, receiver); throw error; } };
  const observer2 = f.api.observeTask17Loading(undefined, undefined, receiver, f.context);
  assert.throws(() => receiver.getPreferences(f.context), actual => actual === error);
  observer2.dispose();
});

test('duplicate module exports give zero observed page calls, never inferred identity', async () => {
  const f = fixture(), other = fixture();
  const observer = f.api.observeTask17Loading(other.production.PinnedMessagesListPresenter,
    other.production.PinnedMessagesRepository, f.prefs, f.context);
  await new f.production.PinnedMessagesListPresenter(new f.production.PinnedMessagesRepository()).openPinnedMessages(f.context);
  const result = JSON.parse(observer.snapshot());
  assert.equal(result.presenterCount, 0);
  assert.equal(result.singlePresenterCallChainObserved, false);
  assert.equal(result.semanticVerdict, null);
  observer.dispose();
});

test('unobservable SDK descriptor is diagnostic; disposal never overwrites another observer', async () => {
  const f = fixture();
  Object.defineProperty(f.prefs, 'getPreferences', { configurable: false });
  const P = f.production.PinnedMessagesListPresenter, R = f.production.PinnedMessagesRepository;
  const original = P.prototype.openPinnedMessages;
  const observer = f.api.observeTask17Loading(P, R, f.prefs, f.context);
  await new P(new R()).openPinnedMessages(f.context);
  assert.equal(JSON.parse(observer.snapshot()).bindings.getPreferences.available, false);
  assert.equal(JSON.parse(observer.snapshot()).bindings.getPreferences.diagnostic.ownDescriptor.configurable, false);
  assert.equal(JSON.parse(observer.snapshot()).bindings.getPreferences.diagnostic.ownDescriptor.valueType, 'function');
  const external = function(...args) { return original.apply(this, args); };
  P.prototype.openPinnedMessages = external;
  observer.dispose();
  assert.equal(P.prototype.openPinnedMessages, external);
  const saved = observer.snapshot();
  await new P(new R()).openPinnedMessages(f.context);
  assert.equal(observer.snapshot(), saved);
});
