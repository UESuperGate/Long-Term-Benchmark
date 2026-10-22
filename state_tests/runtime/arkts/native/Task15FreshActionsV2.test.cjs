'use strict';
// These are protocol fixtures, never device observations or calibration reports.
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const assert = require('node:assert/strict');
const source = fs.readFileSync(path.join(__dirname, 'Task15FreshActionsV2.js'), 'utf8');
const engine = import('data:text/javascript;base64,' + Buffer.from(source).toString('base64'));
const contract = JSON.parse(fs.readFileSync(path.resolve(__dirname,
  '../../../../benchmark_tasks/15_account_deactivation/transitions.json')));

async function run(number, options = {}) {
  const oldNow = Date.now;
  let now = 100000, keyboard = false, form = false, disposed = false, cleaned = false;
  let state = { available: true, originalService: true, accountSessionActive: true, instanceCount: 1,
    instanceId: 1, serviceId: 2, password: '', eraseData: false, action: 'uninitialized',
    calls: [], serviceCalls: [], requestCount: 0 };
  const binding = { entryId: 'entry', submitId: 'submit', confirmationText: 'Confirm?', confirmText: 'Yes',
    loadingId: 'loading', productionModuleUrl: '@bundle:test/entry/ets/features/Feature' };
  const selection = attrs => ({ ...attrs, inWindow() { return this; }, text(value) { return selection({ ...attrs, textValue: value }); } });
  const ON = { id: id => selection({ id }), text: textValue => selection({ textValue }), type: type => selection({ type }) };
  const bounds = { left: 0, top: 0, right: 100, bottom: 100 };
  const kind = query => {
    if (query.id === 'entry') return 'entry';
    if (query.id === 'deactivation_password') return form ? 'password' : null;
    if (query.id === 'deactivation_erase_data' || query.type === 'Toggle') return form ? 'erase' : null;
    if (query.id === 'submit') return form && !options.missingSubmit ? 'submit' : null;
    if (query.textValue === 'Confirm?' || query.textValue === 'Yes') return state.action === 'confirming' ? 'confirm' : null;
    if (query.textValue === 'Retry') return state.action === 'failure' ? 'retry' : null;
    if (query.id === 'loading') return state.action === 'loading' ? 'loading' : null;
    if (query.textValue === 'Settings' || query.textValue === 'Notifications') return 'positive';
    return null;
  };
  const event = retry => {
    state.calls.push({ method: 'deactivateAccount', args: [retry], returned: true, instanceId: 1 });
    if (state.action === 'uninitialized' && !options.badConfirmation) state.action = 'confirming';
    else {
      state.action = options.badConfirmation ? 'failure' : 'loading';
      state.serviceCalls.push({ method: 'deactivateAccount', args: ['secret', true], returned: true, instanceId: 2 });
      state.requestCount++;
    }
  };
  const node = name => ({
    getBounds: async () => ({ left: 10, top: 10, right: 50, bottom: 50 }),
    getId: async () => name, getText: async () => name, isFocused: async () => false,
    isEnabled: async () => name !== 'submit' || !options.disabled,
    isCheckable: async () => name === 'erase', isChecked: async () => state.eraseData,
    async click() {
      if (name === 'entry') form = true;
      if (name === 'erase') { state.eraseData = !state.eraseData; state.calls.push({ method: 'setEraseData', args: [true], returned: true }); }
      if (name === 'submit' || name === 'confirm' || name === 'retry') event(name === 'retry');
    },
    async inputText(value) {
      state.password = value; keyboard = options.ime !== false;
      state.calls.push({ method: 'setPassword', args: [value], returned: true });
    }
  });
  const driver = { delayMs: async ms => { now += ms; }, pressBack: async () => {
    keyboard = false; if (options.backLeavesForm) form = false;
  }, findComponents: async query => {
    const name = kind(query); return name ? options.ambiguous ? [node(name), node(name)] : [node(name)] : [];
  } };
  const launch = { start: async () => {}, reload: async () => {}, dispose: async () => { disposed = true; },
    read: () => ({ disposed }), check: async () => ({ bundleName: 'test', bounds, hostVerified: true,
      focused: true, stageMainWindowId: 1, lastWindowId: 1 }) };
  const rect = () => ({ left: 0, top: 0, width: keyboard ? 100 : 0, height: keyboard ? 10 : 0 });
  const inspector = { byKey: () => ({}), tree: () => ({ $type: 'Root', $children: [
    { $type: 'TextInput', $attrs: { id: 'deactivation_password' }, $rect: '[10,10],[50,50]' }] }),
    ime: async () => ({ visibilitySource: 'native_window_keyboard_avoid_area', keyboardVisible: keyboard,
      keyboardAvoidArea: { topRect: rect(), bottomRect: rect(), leftRect: rect(), rightRect: rect() },
      nativeWindow: { id: 1 }, nativeWindowShowing: true,
      activeWindow: { bundleName: 'test', focused: true, bounds } }) };
  const nonce = 'a'.repeat(32);
  const integration = { prepare: async () => {}, evidence: () => ({ nonce, login: { providerLoginCount: 1 } }),
    cleanup: async () => { cleaned = true; return { certificate: { cleanupConfirmed: true } }; },
    control: { status: async () => ({ loginCount: 1, deactivationCount: state.requestCount }), waitHeld: async () => {},
      release: async (count, status) => {
        if (status === 503) state.action = 'failure';
        return { released: count, status };
      } } };
  Date.now = () => now;
  try {
    const spec = structuredClone(contract.cases[number - 1]);
    const value = await (await engine).runTask15FreshPhysicalCase({ spec, bundleName: 'test', driver, ON, launch,
      integration, inspector, binding, deadlineEpochMs: options.expired ? now - 1 : now + 3600000,
      importModule: async () => ({ AccountClient: function AccountClient() {} }),
      modalInput: async () => {}, observePage: () => ({ read: () => structuredClone(state), dispose: () => {} }) });
    return { value, state, cleaned, disposed };
  } finally { Date.now = oldNow; }
}

test('005 uses positive IME Back, observes stable disabled native action, never executes submit', async () => {
  const { value, state, cleaned, disposed } = await run(5, { disabled: true });
  assert.equal(value.outcome, 'blocked_required_physical_action', JSON.stringify(value.failure));
  assert.equal(value.eventExecuted, false);
  assert.equal(value.actions.filter(a => a.kind === 'system_back').length, 1);
  assert.ok(value.submitSamples.length >= 2);
  assert.ok(value.frames.at(-1).at - value.submitReadinessStartedAt >= 2000);
  assert.equal(state.requestCount, 0);
  assert.ok(!value.actions.some(a => a.target === 'submit'));
  assert.ok(cleaned && disposed);
});
test('005 without visible IME never sends Back', async () => {
  const { value } = await run(5, { disabled: true, ime: false });
  assert.equal(value.outcome, 'blocked_required_physical_action');
  assert.ok(!value.actions.some(a => a.kind === 'system_back'));
});
test('005 enabled physical event records actual wrong post-state, not expected-state readiness timeout', async () => {
  const { value } = await run(5, { badConfirmation: true });
  assert.equal(value.outcome, 'transition_observed', JSON.stringify(value.failure));
  assert.equal(value.eventExecuted, true);
  assert.equal(value.frames.at(-1).presenter.action, 'failure');
});
test('006 has its own confirming given, real confirm and physical modal routing', async () => {
  const { value } = await run(6);
  assert.equal(value.caseId, contract.cases[5].caseId);
  assert.equal(value.outcome, 'transition_observed');
  assert.equal(value.frames.find(f => f.label === 'before_event').presenter.action, 'confirming');
  assert.deepEqual(value.actions.filter(a => a.phase === 'event').map(a => a.target), ['confirm']);
  assert.ok(value.modalProbe);
  assert.ok(value.actions.some(a => a.kind === 'modal_physical_input' && a.phase === 'invariant'));
});
test('008 independently reaches loading before its own actual HTTP503 event', async () => {
  const { value } = await run(8);
  assert.equal(value.outcome, 'transition_observed');
  assert.equal(value.frames.find(f => f.label === 'before_event').presenter.action, 'loading');
  assert.deepEqual(value.actions.filter(a => a.phase === 'event').map(a => [a.kind, a.status]), [['https_response', 503]]);
});
test('009 independently reaches failure before physical Retry, not projected case005', async () => {
  const { value } = await run(9);
  assert.equal(value.outcome, 'transition_observed');
  const given = value.frames.find(f => f.label === 'before_event').presenter;
  assert.equal(given.action, 'failure'); assert.equal(given.requestCount, 1);
  assert.deepEqual(value.actions.filter(a => a.phase === 'event').map(a => a.target), ['retry']);
  assert.equal(value.frames.at(-1).presenter.requestCount, 2);
});
test('other cases never borrow blocked005 as their semantic result', async () => {
  for (const number of [3, 6, 8, 9]) {
    const { value } = await run(number, { disabled: true });
    assert.equal(value.outcome, 'not_scored');
    assert.equal(value.eventExecuted, false);
    assert.equal(value.blockedAction, undefined);
  }
});
test('missing/ambiguous selector, Back leaving form and deadline are unscored, with cleanup', async () => {
  for (const options of [{ missingSubmit: true }, { ambiguous: true }, { backLeavesForm: true }, { expired: true }]) {
    const result = await run(5, options);
    assert.equal(result.value.outcome, 'not_scored');
    assert.ok(result.cleaned && result.disposed);
    assert.equal(result.value.eventExecuted, false);
  }
});
