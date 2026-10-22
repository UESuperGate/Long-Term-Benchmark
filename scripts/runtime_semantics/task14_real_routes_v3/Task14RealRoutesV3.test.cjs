'use strict';
// Explicit unit-boundary session/production fixtures, NOT device evidence.
const fs = require('node:fs'), path = require('node:path'), test = require('node:test'), assert = require('node:assert/strict');
const dataModule = file => import('data:text/javascript;base64,' + Buffer.from(fs.readFileSync(file)).toString('base64'));
const source = fs.readFileSync(path.join(__dirname, 'Task14RealRoutesV3.suite.js'), 'utf8');
const contract = JSON.parse(fs.readFileSync(path.resolve(__dirname, '../../../benchmark_tasks/14_join_room_by_address/transitions.json')));

async function episode(number, options = {}) {
  const JoinObserver = (await dataModule(path.join(__dirname, 'Task14JoinOwnerV3.js'))).installTask14JoinOwnerV3;
  const acquire = (await dataModule(path.resolve(__dirname, '../../../state_tests/runtime/arkts/native/Task14RealFlowV2Frame.js'))).acquireTask14RealFlowFrame;
  const model = { surface: 'root', calls: [], sequence: 0, params: {}, actions: [], constructed: 0 };
  const record = (owner, method, args) => model.calls.push({ owner, method, args, phase: 'call', sequence: ++model.sequence });
  class SessionRoomAliasResolver { resolveRoomAlias() { throw Error('Unit original external directory not expected before connection'); } }
  class NativeNavigator {
    constructor() { this.openRoomCount = 0; this.addressFlowVisible = true; }
    openRoom(id, servers) {
      this.openRoomCount++;
      if (!options.intentOnly) {
        record('HarmonyRoutePort', 'replace', ['pages/Room', { roomId: id }]);
        model.surface = options.wrongRoute ? 'unknown' : 'room'; model.params = { roomId: id };
        if (!options.missingRoomLoad) record('RoomPresenter', 'load', [id]);
      }
    }
    back() { record('HarmonyRoutePort', 'returnToStart', []); model.surface = 'root'; this.addressFlowVisible = false; }
  }
  class JoinRoomByAddressPresenter {
    constructor() { model.constructed++; this.resolver = new SessionRoomAliasResolver(); this.navigator = new NativeNavigator();
      this.address = ''; this.addressState = 'unknown'; this.validationRequested = false; this.resolvedRoom = undefined; }
    async updateAddress(value) {
      this.address = value; this.addressState = 'resolving';
      this.resolvedRoom = await this.resolver.resolveRoomAlias(value);
      this.addressState = 'room_found';
      if (this.validationRequested) this.navigator.openRoom(this.resolvedRoom.roomId, this.resolvedRoom.servers);
    }
    continue() {
      if (this.addressState === 'room_found') this.navigator.openRoom(this.resolvedRoom.roomId, this.resolvedRoom.servers);
      else this.validationRequested = true;
    }
    dismiss() { this.navigator.back(); }
  }
  const p = new JoinRoomByAddressPresenter();
  const item = (name, present = true) => ({ present, visible: present, enabled: true, inspectorMatches: present ? 1 : 0,
    selector: { id: name }, text: name === 'input' ? p.address : '', clickable: true });
  const session = {
    async observeBracketed(label, selectors, read) {
      const route = model.surface === 'root' ? 'pages/Index' : model.surface === 'address' ? 'pages/JoinRoomByAddress' :
        model.surface === 'room' ? 'pages/Room' : 'pages/Unknown';
      const visible = model.surface === 'root' ? ['search', 'join', 'create', 'title'] :
        model.surface === 'address' ? ['input', 'continue', 'cancel'] : ['roomBack', 'roomId'];
      const tree = { $type: 'Column', $attrs: { id: model.surface }, $children: [] };
      return { label, routeName: route, routeParams: model.params, windowId: 1, tree,
        controls: Object.fromEntries(Object.keys(selectors).map(name => [name, item(name, visible.includes(name))])),
        bracketEnd: { routeName: route, windowId: 1, tree: structuredClone(tree) }, stateBefore: read(), stateAfter: read() };
    },
    async action(kind, control, value) {
      model.actions.push({ kind, target: control.selector.id, value });
      if (control.selector.id === 'join') model.surface = 'address';
      if (kind === 'input') p.updateAddress(value).catch(() => {});
      if (control.selector.id === 'continue') p.continue();
      if (control.selector.id === 'cancel') p.dismiss();
    },
    delay: async () => { for (let i = 0; i < 12; i++) await Promise.resolve(); },
    dismissKeyboard: async () => {}
  };
  const installProductionRouteObserver = ({ joinObserver }) => ({ checkpoint: () => model.sequence,
    calls: () => structuredClone(model.calls), dispose: () => joinObserver.dispose() });
  const run = new Function('installTask14JoinOwnerV3', 'installTask14RealFlowV2Observer', 'acquireTask14RealFlowFrame',
    source.replace(/^import .*;$/gm, '').replace(/export /g, '') + '\nreturn runTask14RealRoutesV3;')
    (JoinObserver, installProductionRouteObserver, acquire);
  const spec = contract.cases[number - 1];
  const result = await run(spec, { mode: 'after-page-ready', entryRoute: 'pages/Index', addressRoute: 'pages/JoinRoomByAddress',
    productionModuleUrl: 'join', chatFeatureModuleUrl: 'chat', chatRoutesModuleUrl: 'routes', chatRuntimeModuleUrl: 'runtime',
    resolverModuleUrl: 'resolver', deadlineEpochMs: Date.now() + 5000 }, session,
    async () => ({ JoinRoomByAddressPresenter, SessionRoomAliasResolver }));
  return { result, model };
}

test('005 uses actual native Room route+params and RoomPresenter load, not intent projection', async () => {
  const { result, model } = await episode(5);
  assert.equal(result.outcome, 'native_transition_observed_pending_independent_admission', result.failure);
  assert.equal(result.observed.dismissAddressFlow, true);
  assert.deepEqual(result.observed.openRoom, { roomIdOrAlias: '!team:example.org', serverNames: ['example.org'] });
  assert.ok(result.evidence.some(e => e.method === 'Task14.actualRouteOutcomeV3' && e.actualRoomPresenterLoads.length === 1));
  assert.equal(model.constructed, 1, 'Only fixture application constructs its real original owner');
});
test('006 physically continues pending own response then routes once without second lookup', async () => {
  const { result } = await episode(6);
  assert.equal(result.outcome, 'native_transition_observed_pending_independent_admission', result.failure);
  assert.deepEqual(result.observed, { validationRequested: true, dismissAddressFlow: true, navigationCount: 1 });
  assert.equal(result.invariantChecks[0].passed, true);
  assert.ok(result.frames.some(frame => frame.label === 'after:continue-before-resolution'));
});
test('009 actual Cancel yields native root and zero actual room routes/loads', async () => {
  const { result, model } = await episode(9);
  assert.equal(result.outcome, 'native_transition_observed_pending_independent_admission', result.failure);
  assert.deepEqual(result.observed, { addressFlowVisible: false, openRoomCount: 0 });
  assert.equal(result.invariantChecks[0].passed, true);
  assert.ok(model.actions.some(a => a.target === 'cancel'));
});
test('navigation intention without actual native route never invents openRoom success', async () => {
  const { result } = await episode(5, { intentOnly: true });
  assert.equal(result.outcome, 'native_transition_observed_pending_independent_admission', result.failure);
  assert.equal(result.observed.dismissAddressFlow, false);
  assert.equal(result.observed.openRoom, null);
});
test('unknown route or Room route missing actual production load remains unscored', async () => {
  for (const options of [{ wrongRoute: true }, { missingRoomLoad: true }]) {
    const { result } = await episode(5, options);
    assert.equal(result.outcome, 'not_scored');
    assert.equal(result.eventExecuted, false);
  }
});
