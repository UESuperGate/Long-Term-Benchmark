'use strict';
// Host boundary regressions only. These do not score page UI/runtime semantics.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('/Applications/DevEco-Studio.app/Contents/tools/hvigor/hvigor-ohos-plugin/node_modules/typescript');
const root = path.resolve(__dirname, '../../../..');
const drain = async () => { for (let i = 0; i < 40; i++) await Promise.resolve(); };
function deferred() {
  let resolve, reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}
function load(task) {
  const folder = path.join(root, 'final_dev_nodes', task, 'entry/src/main/ets/features');
  const cache = new Map(), writes = [];
  const preferences = { async getPreferences(context, store) {
    assert.ok(context);
    return { async put(key, raw) { writes.push({ store, key, rows: JSON.parse(raw) }); }, async flush() {} };
  } };
  function module(name) {
    const file = path.resolve(folder, name + (name.endsWith('.ets') ? '' : '.ets'));
    if (cache.has(file)) return cache.get(file).exports;
    const result = { exports: {} };
    cache.set(file, result);
    const compiled = ts.transpileModule(fs.readFileSync(file, 'utf8'), {
      compilerOptions: { target: ts.ScriptTarget.ES2020, module: ts.ModuleKind.CommonJS }
    }).outputText;
    new Function('exports', 'module', 'require', compiled)(result.exports, result, name => {
      if (name === '@ohos.data.preferences') return { default: preferences };
      if (name.startsWith('@ohos.')) return {};
      return module(name);
    });
    return result.exports;
  }
  return { module, writes };
}
function identity() {
  const api = load('16_identity_reset_final_0_5_1');
  const types = api.module('IdentityResetFeature'), services = api.module('IdentityResetServices');
  const starts = [], observers = new Set(), calls = [];
  const sdk = {
    async startIdentityReset() { const pending = deferred(); starts.push(pending); return pending.promise; },
    subscribeVerification(listener) { observers.add(listener); listener(false); return () => observers.delete(listener); }
  };
  function handle(kind = 'password') {
    const reset = deferred();
    const raw = { kind, url: 'https://identity.example/approval',
      resetPassword(password) { calls.push(['password', password]); return reset.promise; },
      resetOidc() { calls.push(['oidc']); return reset.promise; },
      async cancel() { calls.push(['cancel']); }, destroy() { calls.push(['destroy']); } };
    return { raw, reset };
  }
  services.IdentityResetSession.configure(sdk);
  const service = services.IdentityResetSession.createService();
  const manager = new types.IdentityResetFlowManager(service);
  const presenter = new types.IdentityResetPresenter(manager);
  return { ...api, types, services, service, manager, presenter, starts, calls, handle, observers,
    verified(value) { for (const listener of [...observers]) listener(value); } };
}

test('identity default service cannot manufacture success or verified state', async () => {
  const f = identity();
  f.services.IdentityResetSession.configure(undefined);
  await assert.rejects(f.services.IdentityResetSession.createService().startIdentityReset(), /unavailable/);
  assert.equal(f.presenter.sessionVerified, undefined);
  assert.equal(f.types.DemoIdentityResetService, undefined);
});

test('standalone identity page owner without service ends unavailable, never successful', async () => {
  const f = identity(); f.services.IdentityResetSession.configure(undefined);
  const service = f.services.IdentityResetSession.createService();
  const manager = new f.types.IdentityResetFlowManager(service);
  const presenter = new f.types.IdentityResetPresenter(manager);
  await presenter.confirmReset();
  assert.equal(presenter.screen, 'reset_root');
  assert.match(presenter.errorMessage, /SDK service unavailable/);
  assert.equal(presenter.progressVisible, false); assert.equal(presenter.completionCount, 0);
  assert.equal(manager.completionWatcherActive, false);
});

test('identity confirmation does not acquire SDK handle until actual confirm; concurrent loading reuses request', async () => {
  const f = identity();
  f.presenter.continue(); f.presenter.dismissConfirmation();
  assert.equal(f.starts.length, 0);
  const first = f.presenter.confirmReset(), second = f.presenter.confirmReset();
  assert.equal(f.starts.length, 1); assert.equal(f.manager.handleState, 'loading');
  const handle = f.handle(); f.starts[0].resolve(handle.raw);
  await Promise.all([first, second]);
  assert.equal(f.presenter.screen, 'reset_password');
  assert.equal(f.manager.currentHandle.sdkHandle, handle.raw);
});

test('identity handle failure cleans up and retry starts a second real request', async () => {
  const f = identity(), sequence = [];
  f.manager.subscribeHandleState(state => sequence.push(state));
  const first = f.presenter.confirmReset(); f.starts[0].resolve(undefined); await first;
  assert.deepEqual(sequence, ['uninitialized', 'loading', 'failure', 'uninitialized']);
  const retry = f.presenter.confirmReset();
  assert.equal(f.starts.length, 2); assert.equal(f.manager.handleState, 'loading');
  f.starts[1].resolve(f.handle().raw); await retry;
});

test('password empty guard, delegated error/edit, same SDK handle and held loading', async () => {
  const f = identity(), h = f.handle();
  const open = f.presenter.confirmReset(); f.starts[0].resolve(h.raw); await open;
  await f.presenter.submitPassword(); assert.equal(f.calls.length, 0);
  f.presenter.setPassword('not-a-magic-password');
  const pending = f.presenter.submitPassword();
  assert.deepEqual(f.calls, [['password', 'not-a-magic-password']]);
  assert.equal(f.presenter.resetAction, 'loading');
  h.reset.reject(new Error('external auth rejected')); await pending;
  assert.equal(f.presenter.resetAction, 'failure');
  f.presenter.setPassword('new password');
  assert.equal(f.presenter.resetAction, 'uninitialized'); assert.equal(f.presenter.errorMessage, '');
  assert.equal(f.manager.currentHandle.sdkHandle, h.raw);
});

test('password success waits for real subscribed verification callback and emits exactly once', async () => {
  const f = identity(), h = f.handle();
  const open = f.presenter.confirmReset(); f.starts[0].resolve(h.raw); await open;
  f.presenter.setPassword('any SDK-accepted password');
  const operation = f.presenter.submitPassword(); h.reset.resolve(); await operation;
  assert.equal(f.presenter.progressVisible, true); assert.equal(f.presenter.completionCount, 0);
  f.verified(true); f.verified(true);
  assert.equal(f.presenter.completionCount, 1); assert.equal(f.presenter.progressVisible, false);
  assert.equal(f.observers.size, 0);
});

test('OIDC delegates real URL/pending reset and cancellation destroys same raw handle once', async () => {
  const f = identity(), h = f.handle('oidc');
  const operation = f.presenter.confirmReset(); f.starts[0].resolve(h.raw); await drain();
  assert.equal(f.presenter.approvalUrl, h.raw.url);
  assert.deepEqual(f.calls, [['oidc']]); assert.equal(f.manager.resetJobActive, true);
  await f.presenter.oidcReturned(); await f.presenter.dispose();
  h.reset.resolve(); await operation; f.verified(true);
  assert.deepEqual(f.calls, [['oidc'], ['cancel'], ['destroy']]);
  assert.equal(f.manager.handleState, 'uninitialized'); assert.equal(f.presenter.completionCount, 0);
  assert.equal(f.observers.size, 0);
});

test('late identity acquisition after page destruction is cancelled/destroyed, never routed', async () => {
  const f = identity(), h = f.handle();
  const pending = f.presenter.confirmReset(); await f.presenter.dispose();
  f.starts[0].resolve(h.raw); await pending;
  assert.deepEqual(f.calls, [['cancel'], ['destroy']]);
  assert.equal(f.presenter.screen, 'reset_root'); assert.equal(f.manager.currentHandle, undefined);
});

function pinned() {
  const api = load('17_pinned_messages_final_0_5_3'), types = api.module('PinnedMessagesFeature');
  const opening = deferred(), itemObservers = new Set(), syncObservers = new Set(), calls = [];
  let permission = true, unpinFailure = false;
  const timeline = { subscribeItems(listener) { itemObservers.add(listener); return () => itemObservers.delete(listener); },
    async unpinEvent(id) { calls.push(['unpin', id]); if (unpinFailure) throw new Error('SDK denied'); return true; },
    close() { calls.push(['close']); } };
  const room = { roomId: '!room:test', pinnedEventsTimeline() { calls.push(['open']); return opening.promise; },
    async canPinUnpin() { calls.push(['permission', permission]); return permission; },
    subscribeSync(listener) { syncObservers.add(listener); return () => syncObservers.delete(listener); },
    async loadTimeline(id) { calls.push(['focus', id]); return [{ eventId: '$z', body: 'Parent', sender: 'Z' },
      { eventId: '$b', body: 'Beta', sender: 'B' }, { eventId: '$a', body: 'Alpha', sender: 'A' }]; } };
  types.PinnedMessagesSession.configureRoom(room);
  const presenter = types.PinnedMessagesSession.createPresenter();
  return { ...api, types, presenter, room, timeline, opening, calls, itemObservers, syncObservers,
    async emit(ids) { for (const listener of itemObservers) listener(ids.map(eventId => ({ eventId, body: eventId, sender: 'SDK' }))); await drain(); },
    async permissions(value) { permission = value; for (const listener of syncObservers) listener(); await drain(); },
    failUnpin() { unpinFailure = true; } };
}
async function opened(f, ids = ['$a', '$b']) {
  const pending = f.presenter.openPinnedMessages({});
  assert.equal(f.presenter.listState, 'loading'); f.opening.resolve(f.timeline); await drain();
  await f.emit(ids); await pending;
}

test('pinned default unavailable does not seed local success', async () => {
  const f = pinned(); f.types.PinnedMessagesSession.configureRoom(undefined);
  const presenter = f.types.PinnedMessagesSession.createPresenter(); await presenter.openPinnedMessages({});
  assert.equal(presenter.listState, 'failed'); assert.equal(f.writes.length, 0);
  await assert.rejects(presenter.parent.load(), /unavailable/);
});

test('pinned opening stays loading until actual external response/item flow, failure is not empty', async () => {
  const f = pinned(); const pending = f.presenter.openPinnedMessages({});
  await drain(); assert.equal(f.presenter.listState, 'loading');
  f.opening.reject(new Error('external SDK failure')); await pending;
  assert.equal(f.presenter.listState, 'failed'); assert.equal(f.presenter.retryEnabled, true);
  assert.equal(f.writes.length, 0);
});

test('pinned empty and ordered updates are successful external item flow, not magic default rows', async () => {
  const f = pinned(); await opened(f, []);
  assert.equal(f.presenter.listState, 'empty');
  await f.emit(['$b', '$a']); assert.equal(f.presenter.listState, 'filled');
  assert.deepEqual(f.presenter.pinnedMessages.map(item => item.eventId), ['$b', '$a']);
  assert.deepEqual(f.writes.at(-1).rows.map(item => item.eventId), ['$b', '$a']);
});

test('room permission sync controls same owner actions, never mutates pinned set', async () => {
  const f = pinned(); await opened(f);
  const writes = f.writes.length;
  assert.deepEqual(f.presenter.availableActions(), ['view_in_timeline', 'unpin']);
  await f.permissions(false); assert.deepEqual(f.presenter.availableActions(), ['view_in_timeline']);
  assert.equal(await f.presenter.unpin({}, '$a'), false);
  assert.equal(f.calls.filter(row => row[0] === 'unpin').length, 0);
  assert.equal(f.writes.length, writes);
});

test('unpin acknowledgement alone cannot filter list or write cache; SDK item flow is authoritative', async () => {
  const f = pinned(); await opened(f);
  const writes = f.writes.length;
  assert.equal(await f.presenter.unpin({}, '$a'), true);
  assert.deepEqual(f.calls.filter(row => row[0] === 'unpin'), [['unpin', '$a']]);
  assert.deepEqual(f.presenter.pinnedMessages.map(item => item.eventId), ['$a', '$b']);
  assert.equal(f.writes.length, writes);
  await f.emit(['$b']);
  assert.deepEqual(f.presenter.pinnedMessages.map(item => item.eventId), ['$b']);
  assert.deepEqual(f.writes.at(-1).rows.map(item => item.eventId), ['$b']);
});

test('unpin failure preserves list/cache and leaves original owner retryable', async () => {
  const f = pinned(); await opened(f); f.failUnpin(); const writes = f.writes.length;
  assert.equal(await f.presenter.unpin({}, '$a'), false);
  assert.deepEqual(f.presenter.pinnedMessages.map(item => item.eventId), ['$a', '$b']);
  assert.equal(f.writes.length, writes); assert.equal(f.presenter.retryEnabled, true);
  assert.ok(f.presenter.errorMessage.length > 0);
});

test('parent focus loads actual room items and locates event; label is not sufficient', async () => {
  const f = pinned(); await opened(f);
  await f.presenter.viewInTimeline('$a');
  assert.equal(f.presenter.parent.room, f.presenter.repository.room);
  assert.equal(f.presenter.parent.focusedIndex, 2);
  assert.equal(f.presenter.parent.items[2].eventId, '$a');
  assert.deepEqual(f.calls.filter(row => row[0] === 'focus'), [['focus', '$a']]);
  await assert.rejects(f.presenter.viewInTimeline('$absent'), /not returned/);
  assert.deepEqual(f.presenter.pinnedMessages.map(item => item.eventId), ['$a', '$b']);
});

test('pinned disposal closes subscriptions; later external items cannot change disposed owner', async () => {
  const f = pinned(); await opened(f); const writes = f.writes.length;
  f.presenter.dispose(); await f.emit(['$late']); await f.permissions(true);
  assert.equal(f.itemObservers.size, 0); assert.equal(f.syncObservers.size, 0);
  assert.deepEqual(f.presenter.pinnedMessages.map(item => item.eventId), ['$a', '$b']);
  assert.equal(f.writes.length, writes);
});

test('disposing room while first SDK items are held settles pending list load', async () => {
  const f = pinned();
  let settled = false;
  const pending = f.presenter.openPinnedMessages({}).then(() => { settled = true; });
  f.opening.resolve(f.timeline); await drain();
  assert.equal(f.itemObservers.size, 1); assert.equal(settled, false);
  f.presenter.dispose(); await drain();
  assert.equal(settled, true); await pending;
  assert.equal(f.itemObservers.size, 0); assert.equal(f.writes.length, 0);
  assert.equal(f.presenter.pinnedMessages.length, 0);
  assert.equal(f.calls.filter(row => row[0] === 'close').length, 1);
});

test('room-lifetime provider starts before collection and is reused on reopen', async () => {
  const f = pinned(); f.presenter.startRoom({});
  assert.equal(f.calls.filter(row => row[0] === 'open').length, 1);
  await opened(f);
  await f.presenter.openPinnedMessages({});
  assert.equal(f.calls.filter(row => row[0] === 'open').length, 1);
  assert.equal(f.presenter.provider.repository, f.presenter.repository);
  assert.deepEqual(f.presenter.pinnedMessages.map(item => item.eventId), ['$a', '$b']);
});

test('base restores identical pre-existing SDK delegate capability without collection UI/provider', async () => {
  const base = load('../17_pinned_messages_base_0_5_1');
  const services = base.module('MatrixRoomServices');
  const finalPath = path.join(root, 'final_dev_nodes/17_pinned_messages_final_0_5_3/entry/src/main/ets/features/MatrixRoomServices.ets');
  const basePath = path.join(root, '17_pinned_messages_base_0_5_1/entry/src/main/ets/features/MatrixRoomServices.ets');
  assert.equal(fs.readFileSync(basePath, 'utf8'), fs.readFileSync(finalPath, 'utf8'));
  assert.equal(services.PinnedEventsTimelineProvider, undefined);
  assert.equal(services.PinnedMessagesListPresenter, undefined);
  assert.equal(services.RoomSession.createService(), undefined);
  const calls = [], timeline = {};
  const sdk = { roomId: '!base:room',
    async pinnedEventsTimeline() { calls.push('pinned'); return timeline; },
    async canPinUnpin() { calls.push('permission'); return false; },
    subscribeSync(listener) { calls.push('sync'); listener(); return () => {}; },
    async loadTimeline(id) { calls.push(['focus', id]); return []; } };
  services.RoomSession.configureRoom(sdk);
  const service = services.RoomSession.createService();
  assert.equal(service.port, sdk); assert.equal(await service.pinnedEventsTimeline(), timeline);
  assert.equal(await service.canPinUnpin(), false);
  service.subscribeSync(() => {}); await service.loadTimeline('$target');
  assert.deepEqual(calls, ['pinned', 'permission', 'sync', ['focus', '$target']]);
});

test('SDK reset cancel failure still destroys raw handle', async () => {
  const f = identity(), h = f.handle();
  h.raw.cancel = async () => { throw new Error('External cancel failed'); };
  const open = f.presenter.confirmReset(); f.starts[0].resolve(h.raw); await open;
  await assert.rejects(f.presenter.dispose(), /External cancel failed/);
  assert.deepEqual(f.calls, [['destroy']]);
  assert.equal(f.manager.handleState, 'uninitialized'); assert.equal(f.observers.size, 0);
  assert.equal(f.presenter.screen, 'reset_root'); assert.equal(f.presenter.progressVisible, false);
});

test('ArkTS production feature modules do not declare constructor parameter properties', () => {
  for (const project of ['16_identity_reset_final_0_5_1', '17_pinned_messages_final_0_5_3']) {
    const folder = path.join(root, 'final_dev_nodes', project, 'entry/src/main/ets/features');
    for (const name of fs.readdirSync(folder).filter(name => name.endsWith('.ets'))) {
      const source = ts.createSourceFile(name, fs.readFileSync(path.join(folder, name), 'utf8'), ts.ScriptTarget.Latest, true);
      const visit = node => {
        if (ts.isConstructorDeclaration(node)) {
          for (const parameter of node.parameters) {
            assert.ok(!parameter.modifiers?.length, 'ArkTS constructor property: ' + name);
          }
        }
        ts.forEachChild(node, visit);
      };
      visit(source);
    }
  }
});

test('controlled external SDK cancel settles pending OIDC operation, not just bookkeeping flags', async () => {
  const file = path.join(__dirname, 'Tasks16_17SdkBoundary.js');
  const compiled = ts.transpileModule(fs.readFileSync(file, 'utf8'), {
    compilerOptions: { target: ts.ScriptTarget.ES2020, module: ts.ModuleKind.CommonJS }
  }).outputText;
  const module = { exports: {} };
  new Function('exports', 'module', compiled)(module.exports, module);
  const control = module.exports.createIdentitySdkControl();
  const acquired = control.port.startIdentityReset();
  control.deliverHandle(0, 'oidc');
  const handle = await acquired;
  const poll = handle.resetOidc();
  const rejected = assert.rejects(poll, /SDK operation cancelled/);
  await handle.cancel(); await rejected; handle.destroy();
  assert.equal(control.oidc[0].record.delivered, true);
  assert.equal(control.oidc[0].record.cancelled, true);
  assert.equal(control.calls.filter(call => call.kind === 'destroy_reset_handle').length, 1);
});
