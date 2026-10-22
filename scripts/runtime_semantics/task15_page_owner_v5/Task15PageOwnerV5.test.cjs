'use strict';
// Synthetic component/driver fixtures, NOT native runtime or calibration proof.
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const assert = require('node:assert/strict');
const load = name => import('data:text/javascript;base64,' + Buffer.from(fs.readFileSync(path.join(__dirname, name))).toString('base64'));
const observerModule = load('Task15PageOwnerObserverV5.js');
const engineModule = load('Task15FreshActionsV2.js');
const contract = JSON.parse(fs.readFileSync(path.resolve(__dirname, '../../..', 'benchmark_tasks/15_account_deactivation/transitions.json')));

function classes() {
  let pending, getterCalls = 0, constructions = 0;
  class AccountClient {
    constructor() { this.requests = 0; }
    deactivateAccount() { this.requests++; return new Promise((resolve, reject) => { pending = { resolve, reject }; }); }
  }
  class AccountDeactivationPresenter {
    constructor(service) { constructions++; this.service = service; this.password = ''; this.eraseData = false; this.action = 'uninitialized'; }
    loadCapability() { return Promise.resolve(true); }
    submitEnabled() { getterCalls++; return this.password.length > 0 && this.action === 'uninitialized'; }
    setPassword(value) { this.password = value.replace(/\n/g, ''); }
    setEraseData(value) { this.eraseData = value; }
    async deactivateAccount(retry) {
      if (!retry && this.action !== 'confirming') { this.action = 'confirming'; return; }
      this.action = 'loading';
      try { await this.service.deactivateAccount(this.password, this.eraseData); this.action = 'success'; }
      catch (_) { this.action = 'failure'; }
    }
    closeDialogs() { this.action = 'uninitialized'; }
  }
  return { namespace: { AccountClient, AccountDeactivationPresenter },
    pending: () => pending, getters: () => getterCalls, constructions: () => constructions };
}

test('passive read never constructs receiver or calls getter/setter to discover defaults', async () => {
  const f = classes(), observe = (await observerModule).observeTask15OriginalPageOwnerV5;
  const observer = observe(f.namespace, {}, 'unit-episode');
  assert.equal(observer.read().available, false);
  assert.equal(f.constructions(), 0); assert.equal(f.getters(), 0);
  const presenter = new f.namespace.AccountDeactivationPresenter(new f.namespace.AccountClient());
  presenter.setPassword('secret');
  assert.equal(observer.read().available, false, 'A direct setter must not acquire a page owner');
  observer.dispose();
});

test('original lifecycle owns real receiver; read preserves Promise identity and before snapshots', async () => {
  const f = classes(), p = new f.namespace.AccountDeactivationPresenter(new f.namespace.AccountClient());
  const original = f.namespace.AccountDeactivationPresenter.prototype.loadCapability;
  const observer = (await observerModule).observeTask15OriginalPageOwnerV5(f.namespace, {}, 'unit-episode');
  class Index { aboutToAppear() { return p.loadCapability(); } }
  const call = new Index().aboutToAppear();
  const before = observer.read();
  assert.ok(before.available); assert.match(before.ownerCalls[0].stack, /Index.aboutToAppear/);
  assert.equal(before.state.password, ''); assert.equal(before.calls.length, 0);
  assert.equal(f.getters(), 0, 'read must not call canSubmit/submitEnabled');
  p.setPassword('secret\n');
  assert.equal(before.state.password, ''); assert.equal(observer.read().state.password, 'secret');
  assert.equal(await call, true);
  observer.dispose();
  assert.equal(f.namespace.AccountDeactivationPresenter.prototype.loadCapability, original);
});

test('service instrumentation returns exact original Promise without state/effect replacement', async () => {
  let resolve;
  const promise = new Promise(done => { resolve = done; });
  const f = classes();
  f.namespace.AccountClient.prototype.deactivateAccount = function() { return promise; };
  const observer = (await observerModule).observeTask15OriginalPageOwnerV5(f.namespace, {}, 'unit');
  const service = new f.namespace.AccountClient();
  assert.equal(service.deactivateAccount('secret', true), promise);
  resolve(); await promise; await Promise.resolve();
  assert.equal(observer.read().serviceCalls[0].settlement.status, 'fulfilled');
  observer.dispose();
});

async function episode(number, options = {}) {
  const f = classes(), p = new f.namespace.AccountDeactivationPresenter(new f.namespace.AccountClient());
  let active = false, keyboard = false, now = 100000;
  const bounds = { left: 10, top: 10, right: 90, bottom: 40 }, viewport = { left: 0, top: 0, right: 200, bottom: 200 };
  const binding = { entryId: 'entry', passwordId: 'password', eraseId: 'erase', submitId: 'submit',
    confirmText: 'Confirm', closeText: 'Close', ownerBinding: {}, productionModuleUrl: 'original/module' };
  class Index {
    async aboutToAppear() { await p.loadCapability(); this.refresh(); }
    refresh() { p.submitEnabled(); }
    submit() { p.deactivateAccount(false).then(() => this.refresh()); this.refresh(); }
  }
  const page = new Index();
  const query = value => ({ ...value, inWindow() { return this; }, text(textValue) { return query({ ...value, textValue }); } });
  const ON = { id: id => query({ id }), text: textValue => query({ textValue }), type: type => query({ type }) };
  const controlName = q => q.id || ({ Settings: 'settings', Notifications: 'notifications', Confirm: 'confirm', Close: 'close' })[q.textValue];
  const names = ['settings', 'notifications', 'entry', 'password', 'erase', 'submit', 'confirm', 'close'];
  const text = name => name === 'password' ? p.password : name;
  const enabled = name => name !== 'submit' || (!options.disabledSubmit && p.password.length > 0 && p.action === 'uninitialized');
  const node = name => ({
    getBounds: async () => bounds, getId: async () => name, getText: async () => text(name),
    isEnabled: async () => enabled(name), isCheckable: async () => name === 'erase', isChecked: async () => p.eraseData,
    async click() {
      if (name === 'entry') active = true;
      else if (name === 'erase') { p.setEraseData(!p.eraseData); page.refresh(); }
      else if (name === 'submit' || name === 'confirm') page.submit();
      else if (name === 'close') { p.closeDialogs(); page.refresh(); }
    },
    async inputText(value) { p.setPassword(value); page.refresh(); keyboard = true; }
  });
  const window = { bundleName: 'unit', focused: true, hostVerified: true, bounds: viewport, stageMainWindowId: 1, lastWindowId: 1 };
  const driver = { delayMs: async ms => { now += ms; await Promise.resolve(); }, pressBack: async () => { keyboard = false; },
    findComponents: async q => { const name = controlName(q); return names.includes(name) && (active || !['password', 'erase', 'submit', 'confirm', 'close'].includes(name)) ? [node(name)] : []; } };
  const inspector = { byKey: () => ({}), tree: () => ({ $type: 'Column', $children: names.map(name => ({
    $type: name === 'password' ? 'TextInput' : 'Button', $rect: '[10,10],[90,40]', $attrs: { id: name, text: text(name), enabled: enabled(name) } })) }),
    ime: async () => ({ visibilitySource: 'native_window_keyboard_avoid_area', keyboardVisible: keyboard }) };
  const launch = { start: async () => {}, reload: () => page.aboutToAppear(), check: async () => window, dispose: async () => {} };
  const integration = { prepare: async () => {}, evidence: () => ({ nonce: 'c'.repeat(32) }), cleanup: async () => ({ complete: true }),
    control: { status: async () => ({ deactivationCount: p.service.requests, loginCount: 1 }), waitHeld: async () => {},
      release: async (requestId, status) => {
        if (status === 200) f.pending().resolve();
        if (status === 503) f.pending().reject(Error('actual fixture response'));
        await Promise.resolve(); return { released: requestId, status };
      } } };
  const oldNow = Date.now; Date.now = () => now;
  try {
    const value = await (await engineModule).runTask15PageOwnerCaseV5({ spec: contract.cases[number - 1],
      driver, ON, launch, inspector, integration, binding, bundleName: 'unit', deadlineEpochMs: now + 3600000,
      importModule: async () => f.namespace, observePage: (await observerModule).observeTask15OriginalPageOwnerV5 });
    return { value, p, constructions: f.constructions() };
  } finally { Date.now = oldNow; }
}

test('five cases have own native event, receiver, before/after; no case005 projection', async () => {
  const sessions = new Set();
  for (const number of [2, 3, 4, 7, 10]) {
    const { value, constructions } = await episode(number);
    assert.equal(value.outcome, 'transition_observed', JSON.stringify(value.failure));
    assert.equal(value.caseId, contract.cases[number - 1].caseId);
    assert.equal(value.actions.filter(a => a.phase === 'event').length, 1);
    const before = value.frames.find(f => f.label === 'before_event'), after = value.frames.find(f => f.label === 'after_event');
    assert.equal(before.pageOwner.instanceId, after.pageOwner.instanceId);
    assert.equal(before.pageOwner.serviceId, after.pageOwner.serviceId);
    assert.equal(constructions, 1, 'Only fixture app itself constructs its original owner');
    sessions.add(value.sessionId);
  }
  assert.equal(sessions.size, 5);
});

test('002 performs only physical entry event and observes untouched defaults', async () => {
  const { value } = await episode(2);
  const after = value.frames.find(f => f.label === 'after_event');
  assert.equal(after.pageOwner.calls.length, 0);
  assert.equal(after.pageOwner.state.password, ''); assert.equal(after.pageOwner.state.eraseData, false);
  assert.equal(after.controls.find(c => c.name === 'submit').enabled, false);
});

test('003 injects literal newline physically and retains native disabled UI despite getter=true', async () => {
  const { value } = await episode(3, { disabledSubmit: true });
  const event = value.actions.find(a => a.phase === 'event');
  assert.deepEqual(event.driverArguments, ['secret\n']);
  const after = value.frames.find(f => f.label === 'after_event');
  assert.equal(after.pageOwner.state.password, 'secret');
  assert.equal(after.pageOwner.ownerCalls.at(-1).diagnosticGetterValue, true);
  assert.equal(after.controls.find(c => c.name === 'submit').enabled, false);
});

test('007 and010 execute their own external-success and actual physical Close events', async () => {
  const success = (await episode(7)).value;
  assert.equal(success.actions.find(a => a.phase === 'event').kind, 'https_response');
  assert.equal(success.frames.find(f => f.label === 'after_event').pageOwner.state.action, 'success');
  const close = (await episode(10)).value;
  assert.equal(close.actions.find(a => a.phase === 'event').target, 'close');
  assert.equal(close.frames.find(f => f.label === 'after_event').pageOwner.state.action, 'uninitialized');
});
