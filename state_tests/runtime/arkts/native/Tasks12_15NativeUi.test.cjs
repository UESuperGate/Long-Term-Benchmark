'use strict';

// Scaffold regressions only. These fake UiTest objects are never device evidence.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const test = require('node:test');
const ts = require('/Applications/DevEco-Studio.app/Contents/tools/hvigor/hvigor-ohos-plugin/node_modules/typescript');
const root = path.resolve(__dirname, '../../../..');
const canonical = task => JSON.parse(fs.readFileSync(path.join(root, 'migrations', task, 'canonical/transitions.json'))).cases;

class Selector {
  constructor(filters = {}) { this.filters = filters; }
  id(value) { return new Selector({ ...this.filters, id: value }); }
  text(value) { return new Selector({ ...this.filters, text: value }); }
  type(value) { return new Selector({ ...this.filters, type: value }); }
  inWindow(value) { return new Selector({ ...this.filters, bundle: value }); }
}

function component(values) {
  return { id: '', text: '', type: 'Text', enabled: true, checked: false, checkable: false, focused: false,
    bounds: { left: 0, top: 0, right: 20, bottom: 20 }, clicks: 0,
    async getId() { return this.id; }, async getText() { return this.text; },
    async isEnabled() { return this.enabled; }, async isCheckable() { return this.checkable; },
    async isChecked() { return this.checked; }, async isFocused() { return this.focused; },
    async getBounds() { return this.bounds; },
    async click() { this.clicks++; if (this.checkable) this.checked = !this.checked; },
    async inputText(value) { this.text = value; }, ...values };
}

function setup(nodes = [], args = {}, options = {}) {
  const logs = [], tests = [], launches = [], scopedQueries = [], waits = [];
  let uiImports = 0;
  const driver = {
    async findComponents(selector) {
      assert.equal(selector.filters.bundle, 'candidate.only');
      scopedQueries.push(selector.filters);
      if (options.onQuery) options.onQuery(selector);
      const matches = nodes.filter(node => !node.hidden && Object.entries(selector.filters).every(([key, value]) => key === 'bundle' || node[key] === value));
      return !matches.length && options.nullMatches ? null : matches;
    },
    async findComponent(selector) { return (await this.findComponents(selector))[0]; },
    async findWindow(filter) {
      assert.equal(filter.bundleName, 'candidate.only');
      return { getBounds: async () => ({ left: 0, top: 0, right: 200, bottom: 400 }) };
    },
    async delayMs(value) { waits.push(value); }
  };
  const imports = {
    '@ohos.UiTest': { Driver: { create: () => driver }, ON: new Selector() },
    '@ohos.inputMethod': { default: { getController: () => ({ hideTextInput: async () => {
      if (options.hideTextInput) await options.hideTextInput();
    } }) } },
    '@ohos/hypium': { describe: (_name, callback) => callback(), it: (_name, _flag, callback) => tests.push(callback),
      expect: value => ({ assertTrue: () => assert.equal(value, true), assertFalse: () => assert.equal(value, false) }) },
    '@ohos.app.ability.abilityDelegatorRegistry': { default: {
      getArguments: () => ({ bundleName: 'candidate.only', parameters: args }),
      getAbilityDelegator: () => ({ startAbility: async want => { launches.push(want); if (options.onLaunch) options.onLaunch(); } })
    } }
  };
  function load(name) {
    if (name === '@ohos.UiTest') uiImports++;
    if (imports[name]) return imports[name];
    const prefix = path.join(__dirname, name.replace('./', ''));
    const file = fs.existsSync(prefix + '.js') ? prefix + '.js' : prefix + '.ets';
    const code = ts.transpileModule(fs.readFileSync(file, 'utf8'), {
      compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 }, reportDiagnostics: true
    });
    assert.equal(code.diagnostics.length, 0);
    const context = { exports: {}, require: load, console: { info: value => logs.push(value) } };
    vm.runInNewContext(code.outputText, context, { filename: file });
    return imports[name] = context.exports;
  }
  const helper = load('./Tasks12_15NativeUi');
  helper.configureTasks12To15Selectors(imports['@ohos.UiTest'].ON);
  const suite = load('./Tasks12_15NativeUi.test');
  const observer = load('./Tasks12_15ReportPageObserver');
  const binding = load('./Tasks12_15NativeUi.binding');
  const nativeImports = [];
  if (options.Presenter) binding.configureTasks12ReportPageBinding(JSON.stringify({ bundleName: 'candidate.only', moduleName: 'entry',
    productionModuleUrl: '@bundle:candidate.only/entry/ets/features/ReportRoomFeature', presenterExport: 'ReportRoomPresenter' }), async url => {
      assert.equal(launches.length, 1, 'Original app import must follow startAbility');
      assert.ok(scopedQueries.some(query => query.id === 'report_room_reason'), 'Original page controls must be queried before import');
      nativeImports.push(url);
      return { ReportRoomPresenter: options.Presenter };
    });
  return { ui: new helper.Tasks12To15Ui(driver, 'candidate.only', 'fixture-session'), suite, observer, binding, nativeImports, logs, launches, scopedQueries, waits,
    uiImportCount: () => uiImports,
    async run() {
      suite.default();
      await tests[0]();
      const chunks = logs.filter(line => line.startsWith('ARKTS_12_15_UI_CHUNK ')).map(line => JSON.parse(line.slice('ARKTS_12_15_UI_CHUNK '.length)));
      assert.equal(chunks.length, chunks[0].chunks);
      assert.ok(chunks.every((chunk, index) => chunk.index === index));
      return JSON.parse(chunks.map(chunk => chunk.text).join(''));
    } };
}

test('actual action receipts and frames share one session, order and scoped window', async () => {
  const toggle = component({ id: 'report_room_leave_toggle', type: 'Toggle', checkable: true });
  const input = component({ id: 'report_room_reason', type: 'TextInput', text: 'original' });
  const f = setup([toggle, input, component({ id: 'submit_report_room', type: 'Button' })]);
  const before = await f.ui.capture('12_report_room', 'before_event');
  await f.ui.input([new Selector().id(input.id)], 'canonical event value');
  const after = await f.ui.capture('12_report_room', 'after_event');
  const action = f.ui.actionLog()[0];
  assert.equal(before.observed.reason, 'original');
  assert.equal(after.observed.reason, 'canonical event value');
  assert.equal(action.value, 'canonical event value');
  assert.equal(action.executed, true);
  assert.equal(action.sessionId, before.sessionId);
  assert.equal(action.sessionId, after.sessionId);
  assert.ok(before.sequence < action.sequence && action.sequence < after.sequence);
});

test('post-onRun suite uses static UiTest binding without dynamic namespace and handles null matches', async () => {
  const spec = canonical('12_report_room')[5];
  const f = setup([], { taskId: spec.taskId, caseSpec: JSON.stringify(spec) }, { nullMatches: true });
  assert.equal(f.uiImportCount(), 1);
  const source = fs.readFileSync(path.join(__dirname, 'Tasks12_15NativeUi.test.ets'), 'utf8');
  assert.match(source, /import \{ Driver, ON \} from '@ohos.UiTest'/);
  assert.doesNotMatch(source, /import\('@ohos.UiTest'\)/);
  const result = await f.run();
  assert.equal(f.uiImportCount(), 1);
  assert.equal(result.status, 'not_scored');
  assert.equal(result.prerequisite.rootConfirmed, false);
  assert.doesNotMatch(result.unsupported, /null|length/);
});

function originalReportTypes() {
  const file = path.join(root, 'final_dev_nodes/12_report_room_final_25_05_0/entry/src/main/ets/features/ReportRoomFeature.ets');
  const compiled = ts.transpileModule(fs.readFileSync(file, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 }
  });
  const context = { exports: {} };
  vm.runInNewContext(compiled.outputText, context, { filename: file });
  return context.exports;
}

function blankReasonFixture(options = {}) {
  const types = originalReportTypes();
  let presenter;
  const input = component({ id: 'report_room_reason', type: 'TextInput',
    async inputText(value) {
      presenter.updateReason(value);
      if (options.secondInstance) new types.ReportRoomPresenter(new types.ReportRoomService(new types.ReportRoomGateway())).updateReason('unrelated');
      refresh();
      if (options.keyboardOccludes) { leave.hidden = true; submit.hidden = true; }
      if (options.inputFailure) throw Object.assign(new Error('native input injection failed'), { code: 17000002 });
    } });
  const leave = component({ id: 'report_room_leave_toggle', type: 'Toggle', checkable: true,
    async click() {
      this.clicks++; presenter.toggleLeaveRoom(); refresh();
      if (options.toggleFailure) {
        input.hidden = true;
        throw Object.assign(new Error('native click receipt failed'), { code: 17000002 });
      }
    } });
  const submit = component({ id: 'submit_report_room', type: 'Button' });
  function refresh() {
    input.text = presenter.reason;
    leave.checked = presenter.leaveRoom;
    submit.enabled = options.wrongEnabled === true || presenter.canReport;
  }
  const spec = canonical('12_report_room')[5];
  const f = setup([component({ text: 'Community support' }), input, leave, submit],
    { taskId: spec.taskId, caseSpec: JSON.stringify(spec) }, {
      nullMatches: true, Presenter: options.noObserver ? undefined :
        (options.duplicateModule ? originalReportTypes().ReportRoomPresenter : types.ReportRoomPresenter),
      async hideTextInput() {
        if (options.hideFailure) throw new Error('input client detached');
        leave.hidden = false; submit.hidden = false;
      },
      onLaunch() {
        presenter = new types.ReportRoomPresenter(new types.ReportRoomService(new types.ReportRoomGateway()));
        refresh();
      }
    });
  return { ...f, presenter: () => presenter, input, leave, submit };
}

test('blank reason uses original getter on the UI-driven receiver and all canonical fields/invariant', async () => {
  const f = blankReasonFixture();
  const result = await f.run();
  assert.equal(result.status, 'passed');
  assert.equal(result.canonicalAssertion.evaluated, true);
  assert.equal(result.canonicalAssertion.samePresenterInstance, true);
  assert.deepEqual(f.nativeImports, ['@bundle:candidate.only/entry/ets/features/ReportRoomFeature']);
  assert.ok(result.givenChecks.every(check => check.passed));
  assert.ok(result.expectedChecks.every(check => check.passed));
  assert.equal(result.invariantChecks.length, 1);
  assert.equal(result.invariantChecks[0].passed, true);
  const frames = result.frames.filter(frame => frame.label.endsWith('_event'));
  assert.equal(frames.length, 2);
  assert.ok(frames.every(frame => frame.presenterEvidence.instanceId === 1));
  assert.ok(frames.every(frame => frame.presenterEvidence.reason === '   '));
  assert.ok(frames.every(frame => frame.presenterEvidence.binding.receiverObserved === true));
  assert.ok(frames.every(frame => frame.presenterEvidence.binding.importPhase === 'after_original_page_ready_before_fixture'));
  assert.equal(f.presenter().service.gateway.reportCalls, 0);
  assert.equal(f.presenter().service.gateway.leaveCalls, 0);
  assert.equal(f.submit.clicks, 0);
  assert.equal(f.observer.readTasks12ReportPage().available, false);
});

test('missing or multiple presenter receivers never turn rendered disabled UI into canonical pass', async () => {
  for (const options of [{ noObserver: true }, { secondInstance: true }, { duplicateModule: true }]) {
    const result = await blankReasonFixture(options).run();
    assert.equal(result.status, 'not_scored');
    assert.ok(result.canonicalAssertion.missingExpected.includes('canReport'));
    assert.equal(result.canonicalAssertion.samePresenterInstance, false);
  }
});

test('fixture selects leave before keyboard input and re-queries actual controls after OS dismissal', async () => {
  const result = await blankReasonFixture({ keyboardOccludes: true }).run();
  assert.equal(result.status, 'passed');
  assert.deepEqual(result.actions.map(action => action.kind), ['click', 'input', 'hide_input_method']);
  assert.ok(result.actions.every(action => action.executed));
  const bound = result.frames.find(frame => frame.label === 'original_page_observer_installed');
  assert.equal(bound.presenterEvidence.binding.importCompleted, true);
  assert.equal(bound.presenterEvidence.available, false, 'Binding alone cannot invent a receiver');
  const selected = result.frames.find(frame => frame.label === 'fixture_leave_selected');
  assert.equal(selected.observed.leaveRoom, true);
  assert.equal(selected.observed.reason, '');
  assert.equal(selected.presenterEvidence.available, true);
});

test('failed OS dismissal keeps receipt and cannot promote obscured controls to pass', async () => {
  const result = await blankReasonFixture({ keyboardOccludes: true, hideFailure: true }).run();
  assert.equal(result.status, 'not_scored');
  const hide = result.actions.find(action => action.kind === 'hide_input_method');
  assert.equal(hide.executed, false);
  assert.match(hide.error, /input client detached/);
  assert.ok(result.canonicalAssertion.missingExpected.includes('canReport'));
});

test('fixture failure preserves original error, stage and receiver even when diagnostic capture fails', async () => {
  const result = await blankReasonFixture({ toggleFailure: true }).run();
  assert.equal(result.status, 'not_scored');
  assert.equal(result.eventExecuted, false);
  assert.equal(result.failure.stage, 'fixture_leave_preference');
  assert.equal(result.failure.code, 17000002);
  assert.match(result.failure.stack, /native click receipt failed/);
  assert.match(result.failure.captureError, /Report form is not rendered/);
  assert.equal(result.failure.presenterEvidence.binding.importCompleted, true);
  assert.equal(result.failure.presenterEvidence.leaveRoom, true);
  assert.equal(result.failure.presenterEvidence.calls[0].method, 'toggleLeaveRoom');
});

test('input exception retains partial UI frame without claiming an event or canonical assertion', async () => {
  const result = await blankReasonFixture({ inputFailure: true }).run();
  assert.equal(result.status, 'not_scored');
  assert.equal(result.failure.stage, 'fixture_reason_input');
  assert.equal(result.failure.presenterEvidence.reason, '   ');
  assert.ok(result.frames.some(frame => frame.label === 'failure_diagnostic_only'));
  assert.equal(result.eventExecuted, false);
  assert.equal(result.canonicalAssertion.evaluated, false);
  assert.equal(result.actions.find(action => action.kind === 'input').executed, false);
});

test('postload original import is forbidden before actual window/form readiness and has no copy fallback', async () => {
  const f = setup();
  const types = originalReportTypes();
  // A configured test-copy class must never rescue a failed original import.
  f.observer.configureTasks12ReportPage(types.ReportRoomPresenter);
  const config = { bundleName: 'candidate.only', moduleName: 'entry',
    productionModuleUrl: '@bundle:candidate.only/entry/ets/features/ReportRoomFeature', presenterExport: 'ReportRoomPresenter' };
  let imports = 0;
  f.binding.configureTasks12ReportPageBinding(JSON.stringify(config), async () => {
    imports++;
    throw new Error('original module failed');
  });
  const ready = { bundleName: 'candidate.only', windowConfirmed: true, rootConfirmed: true, available: true,
    controls: [{ id: 'report_room_reason', present: true, visible: true }] };
  for (const mutation of [{ windowConfirmed: false }, { rootConfirmed: false }, { controls: [] }, { bundleName: 'other.app' }]) {
    await assert.rejects(() => f.binding.installTasks12ReportPageAfterReady(JSON.stringify({ ...ready, ...mutation })), /actual candidate window/);
  }
  assert.equal(imports, 0);
  await assert.rejects(() => f.binding.installTasks12ReportPageAfterReady(JSON.stringify(ready)), /original module failed/);
  assert.equal(imports, 1);
  assert.equal(f.observer.readTasks12ReportPage().available, false);
  assert.throws(() => f.binding.configureTasks12ReportPageBinding(JSON.stringify({ ...config,
    productionModuleUrl: '@bundle:candidate.only/entry_test/ets/features/ReportRoomFeature' })), /identity/);
});

test('wrong enabled control is a fully observed failure, not missing coverage', async () => {
  const f = blankReasonFixture({ wrongEnabled: true });
  await assert.rejects(() => f.run(), /false !== true/);
  const chunks = f.logs.filter(line => line.startsWith('ARKTS_12_15_UI_CHUNK '))
    .map(line => JSON.parse(line.slice('ARKTS_12_15_UI_CHUNK '.length)));
  const result = JSON.parse(chunks.map(chunk => chunk.text).join(''));
  assert.equal(result.status, 'failed');
  assert.equal(result.canonicalAssertion.evaluated, true);
  assert.equal(result.observed.canReport, false);
  assert.equal(result.observed.submitEnabled, true);
  assert.equal(result.invariantChecks[0].passed, true);
});

test('observer preserves receiver, arguments, Promise identity, throws and original descriptors', () => {
  const returned = Promise.resolve('original');
  const failure = new Error('original throw');
  class Probe {
    reason = ''; leaveRoom = false;
    updateReason(value) { assert.equal(this, receiver); this.reason = value; return returned; }
    toggleLeaveRoom() { throw failure; }
    get canReport() { return this.reason.length > 0; }
  }
  const receiver = new Probe();
  const original = Object.getOwnPropertyDescriptor(Probe.prototype, 'updateReason');
  const { observer } = setup();
  observer.configureTasks12ReportPage(Probe);
  const installed = observer.installTasks12ReportPageObserver();
  assert.strictEqual(receiver.updateReason('payload'), returned);
  assert.throws(() => receiver.toggleLeaveRoom(), error => error === failure);
  assert.equal(installed.read().calls[1].completed, false);
  installed.dispose();
  assert.deepEqual(Object.getOwnPropertyDescriptor(Probe.prototype, 'updateReason'), original);
});

test('ambiguous, missing, disabled or offscreen controls never receive a click', async () => {
  for (const nodes of [[], [component({ id: 'target', enabled: false })],
    [component({ id: 'target', bounds: { left: 500, top: 500, right: 550, bottom: 550 } })],
    [component({ id: 'target' }), component({ id: 'target' })]]) {
    const f = setup(nodes);
    await assert.rejects(() => f.ui.click([new Selector().id('target')]));
    assert.equal(f.ui.actionLog().length, 0);
    assert.ok(nodes.every(node => node.clicks === 0));
  }
});

test('immediate loading observation adds no automatic settling delay', async () => {
  const node = component({ id: 'confirm', type: 'Button' });
  const f = setup([node]);
  await f.ui.click([new Selector().id('confirm')], 0);
  assert.equal(node.clicks, 1);
  assert.equal(f.waits.length, 0);
  assert.equal(f.ui.actionLog()[0].settleMs, 0);
  assert.ok(f.ui.actionLog()[0].completedAt >= f.ui.actionLog()[0].attemptedAt);
  await assert.rejects(() => f.ui.click([new Selector().id('confirm')], -1));
  assert.equal(node.clicks, 1);
});

test('a wrong task case cannot launch or score the candidate', async () => {
  const spec = canonical('12_report_room')[1];
  const f = setup([], { taskId: '15_account_deactivation', caseSpec: JSON.stringify(spec) });
  const result = await f.run();
  assert.equal(f.launches.length, 0);
  assert.equal(result.status, 'not_scored');
  assert.equal(result.canonicalAssertion.identityMatches, false);
});

test('rendered task12 baseline root with absent report entry stays NS', async () => {
  const spec = canonical('12_report_room')[0];
  const f = setup([component({ text: 'Community support' }), component({ id: 'leave_room', type: 'Button' })],
    { taskId: '12_report_room', caseSpec: JSON.stringify(spec) });
  const result = await f.run();
  assert.equal(result.status, 'not_scored');
  assert.equal(result.prerequisite.status, 'absent');
  assert.equal(result.eventExecuted, false);
  assert.equal(result.canonicalAssertion.evaluated, false);
  assert.equal(f.launches.length, 1);
  assert.equal(result.actions.length, 0);
  assert.equal(result.traceDigest, spec.traceDigest);
});

test('reason UI fixture consumes given/event values and never invents canReport', async () => {
  const spec = structuredClone(canonical('12_report_room')[1]);
  spec.event.reason = 'unit-only event payload';
  spec.expected.reason = spec.event.reason;
  const f = setup([component({ text: 'Community support' }),
    component({ id: 'report_room_reason', type: 'TextInput' }),
    component({ id: 'report_room_leave_toggle', type: 'Toggle', checkable: true }),
    component({ id: 'submit_report_room', type: 'Button' })],
  { taskId: '12_report_room', caseSpec: JSON.stringify(spec) });
  const result = await f.run();
  assert.equal(result.observed.reason, spec.event.reason);
  assert.ok(result.givenChecks.every(check => check.passed));
  assert.equal(result.canonicalAssertion.eventEligible, true);
  assert.deepEqual(result.canonicalAssertion.missingExpected, ['canReport']);
  assert.equal(result.status, 'not_scored');
  assert.equal(result.invariantChecks[0].passed, true);
});

test('external givens, missing effects and cross-session frames cannot form a verdict', () => {
  const { suite } = setup();
  const spec = canonical('12_report_room')[6];
  const result = { status: 'failed', eventExecuted: true, sessionId: 'one', frames: [
    { label: 'before_event', sessionId: 'one', bundleName: 'candidate.only', sequence: 1, observed: { reason: 'Spam', leaveRoom: true } },
    { label: 'after_event', sessionId: 'two', bundleName: 'candidate.only', sequence: 3, observed: { reason: 'Spam', leaveRoom: true } }
  ], actions: [{ sessionId: 'one', sequence: 2, executed: true }], invariantChecks: [] };
  suite.finalizeNativeUiResult(result, spec);
  assert.equal(result.status, 'not_scored');
  assert.equal(result.canonicalAssertion.sameUiSession, false);
  assert.ok(result.canonicalAssertion.missingGivens.includes('reportResult'));
  assert.ok(result.canonicalAssertion.missingExpected.includes('reportCalls'));
});

test('a no-op open or setter cannot be relabeled as the canonical event', () => {
  const { suite } = setup();
  const spec = canonical('12_report_room')[1];
  const result = { status: 'failed', eventExecuted: true, sessionId: 'one', frames: [
    { label: 'before_event', sessionId: 'one', sequence: 1, observed: { reason: '', leaveRoom: false } },
    { label: 'after_event', sessionId: 'one', sequence: 2, observed: { reason: 'Spam', leaveRoom: false, canReport: true } }
  ], actions: [], invariantChecks: [{ description: spec.invariants[0], passed: true }] };
  suite.finalizeNativeUiResult(result, spec);
  assert.equal(result.status, 'not_scored');
  assert.equal(result.canonicalAssertion.eventEligible, false);
});

test('adapter root absence is diagnostic, never an automatic failed prerequisite', async () => {
  const { runCase } = require('../tasks12_15.cjs');
  const taskId = '12_report_room', caseSpec = canonical(taskId)[0];
  const result = await runCase({ taskId, caseSpec, load: async () => { throw new Error('No feature module'); },
    native: { ui: { observe: async (ids, anchor) => ({ available: true,
      snapshot: { candidateRouteVerified: true, route: 'pages/Index' }, anchor: { id: anchor },
      controls: ids.map(id => ({ id, present: false })) }) } } });
  assert.equal(result.prerequisiteChecks[0].passed, null);
  assert.equal(result.prerequisiteChecks[0].diagnosticOnly, true);
  assert.equal(result.prerequisiteChecks[0].canonicalEventExecuted, false);
  assert.equal(result.prerequisiteChecks[0].observed.caseId, caseSpec.caseId);
  assert.ok(result.unsupported);
  assert.equal(result.nativeUI.transitionObserved, false);
  assert.deepEqual(result.observed, {});
});
