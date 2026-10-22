'use strict';
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const test = require('node:test');
const assert = require('node:assert/strict');

function acquisitionFunctions() {
  const context = { Map, Promise };
  vm.createContext(context);
  vm.runInContext(fs.readFileSync(path.join(__dirname, 'Task09Repository.js'), 'utf8').replace(/^export /gm, ''), context);
  return context;
}

const readiness = () => acquisitionFunctions().waitTask09EligibleControl;

test('read-only control acquisition waits for actual render eligibility', async () => {
  const target = { present: true, visible: true, enabled: true };
  let reads = 0;
  const delays = [], observations = [];
  const actual = await readiness()(async () => ++reads < 3 ? { present: false } : target,
    async milliseconds => delays.push(milliseconds), (...args) => observations.push(args));
  assert.equal(actual, target);
  assert.equal(reads, 3);
  assert.deepEqual(delays, [50, 50]);
  assert.equal(observations.length, 2);
});

test('absent, disabled or visibility-unobserved controls are never forced eligible', async () => {
  for (const target of [{ present: false }, { present: true, visible: true, enabled: false },
    { present: true, enabled: true }]) {
    let reads = 0;
    const before = JSON.stringify(target);
    await assert.rejects(readiness()(async () => { reads++; return target; }, async () => {}, () => {}),
      /did not become eligible before physical dispatch/);
    assert.equal(reads, 20);
    assert.equal(JSON.stringify(target), before);
  }
});

test('control acquisition failures propagate without an action or success substitution', async () => {
  let reads = 0;
  await assert.rejects(readiness()(async () => { reads++; throw new Error('native query unavailable'); },
    async () => {}, () => {}), /native query unavailable/);
  assert.equal(reads, 1);
});

test('only read-only WidgetNoCandidates acquisition errors are retried', async () => {
  let reads = 0;
  const target = { present: true, visible: true, enabled: true };
  const actual = await readiness()(async () => {
    if (++reads === 1) throw new Error('WidgetNoCandidates');
    return target;
  }, async () => {}, () => {});
  assert.equal(reads, 2);
  assert.equal(actual, target);
});

test('physical actions retry only the exact pre-dispatch target-change exception', async () => {
  for (const message of ['Original UI action target changed', 'handler failed after delivery']) {
    let attempted = 0, delivered = 0;
    const action = acquisitionFunctions().clickTask09OriginalControl;
    const call = action(async () => ({ present: true, visible: true, enabled: true }), {
      delay: async () => {}, action: async () => {
        if (++attempted === 1) throw new Error(message);
        delivered++;
      }
    }, () => {});
    if (message === 'Original UI action target changed') {
      await call;
      assert.equal(attempted, 2);
      assert.equal(delivered, 1);
    } else {
      await assert.rejects(call, /handler failed after delivery/);
      assert.equal(attempted, 1);
      assert.equal(delivered, 0);
    }
  }
});

test('base checkpoint retains the actual visible placeholder, not an earlier unknown-visibility read', async () => {
  // Synthetic transport only: this tests acquisition ordering, not benchmark semantics.
  const helpers = acquisitionFunctions();
  const state = { available: true, surface: 'chats' };
  const context = { Map, Promise, waitTask09EligibleControl: helpers.waitTask09EligibleControl,
    clickTask09OriginalControl: helpers.clickTask09OriginalControl,
    installTask09Input: () => ({ read: () => ({ ...state }), dispose() {} }) };
  vm.createContext(context);
  const source = fs.readFileSync(path.join(__dirname, 'Task09Suite.js'), 'utf8');
  vm.runInContext(source.replace(/^import .*;\n/gm, '').replace(/^export /gm, ''), context);
  const actions = [], traces = [];
  let afterReads = 0;
  const session = {
    async reloadOriginalPage() {}, async delay() {},
    async action(_kind, target) {
      actions.push(target.id);
      state.surface = target.id === 'home_chats_tab' ? 'chats' : 'spaces';
    },
    async observe(label, selectors) {
      const controls = {};
      if (label === 'after:event') afterReads++;
      for (const [name, choices] of Object.entries(selectors)) {
        const id = choices[0].id;
        controls[name] = { id, present: id.startsWith('home_') || state.surface === 'spaces',
          visible: label === 'after:event' && afterReads === 1 ? undefined : true,
          enabled: true, clickable: id.startsWith('home_') };
      }
      return { controls, routeName: 'pages/Index', windowId: 17, tree: { syntheticUnitFixture: true } };
    }
  };
  const result = await context.runTask09Case({ taskId: '09_spaces_lifecycle',
    caseId: 'sp_state_001_open_space', key: 'open_space', invariants: ['unchanged canonical invariant'] },
    { productionVariant: 'base', productionModuleUrl: 'unit-module' }, session, async () => ({}), () => {},
    (...args) => traces.push(args));
  assert.equal(afterReads, 2);
  assert.deepEqual(actions, ['home_chats_tab', 'home_spaces_tab']);
  const marker = result.evidence.find(item => item.label === 'Task09.missingFeatureEntry');
  assert.equal(marker.data.after.controls.placeholder.visible, true);
  assert.equal(traces.filter(item => item[0] === 'after:event').length, 1);
  assert.deepEqual(Object.keys(result.observed), []);
  assert.equal(result.invariantChecks.length, 0);
});

test('automatic original pagination can complete during read-only manual-control acquisition', async () => {
  const prepare = acquisitionFunctions().prepareTask09LeavePagination;
  for (const code of ['TASK09_CONTROL_NOT_ELIGIBLE_BEFORE_DISPATCH', 'target_changed']) {
    const initial = { selectedSpaceId: '!space', hasMoreChildren: true, loadingMore: false, childrenLoading: false };
    const state = { spaces: { ...initial }, paginationEvents: [] };
    let clicks = 0, records = 0;
    const actual = await prepare(() => state, async () => {
      clicks++;
      state.paginationEvents.push({ before: initial });
      state.spaces = { ...initial, hasMoreChildren: false };
      const error = new Error(code === 'target_changed' ? 'Original UI action target changed' : 'read-only acquisition ended');
      error.code = code;
      throw error;
    }, async predicate => { assert.equal(predicate(state), true); return state; }, () => records++);
    assert.equal(actual, state);
    assert.equal(clicks, 1);
    assert.equal(records, 1);
  }
});

test('pagination setup never ignores delivered-action failures or unavailable original dispatch evidence', async () => {
  const prepare = acquisitionFunctions().prepareTask09LeavePagination;
  for (const mode of ['after_dispatch_error', 'no_original_dispatch', 'different_space']) {
    const initial = { selectedSpaceId: '!space', hasMoreChildren: true, loadingMore: false, childrenLoading: false };
    const state = { spaces: { ...initial }, paginationEvents: [] };
    await assert.rejects(prepare(() => state, async () => {
      state.spaces.hasMoreChildren = false;
      if (mode !== 'no_original_dispatch') state.paginationEvents.push({ before: {
        ...initial, selectedSpaceId: mode === 'different_space' ? '!other' : '!space' } });
      const error = new Error('must propagate');
      if (mode !== 'after_dispatch_error') error.code = 'TASK09_CONTROL_NOT_ELIGIBLE_BEFORE_DISPATCH';
      throw error;
    }, async () => assert.fail('Unproven operation must not proceed'), () => assert.fail('Unproven dispatch')),
    /must propagate/);
  }
});

function fixture(key) {
  const context = { Map, Promise };
  vm.createContext(context);
  vm.runInContext(fs.readFileSync(path.join(__dirname, 'Task09Repository.js'), 'utf8').replace(/^export /gm, ''), context);
  class Repository {
    constructor() { this.account = { spaces: [], rooms: new Map(), invites: [], seenSpaceIds: [] }; }
    settle() { return Promise.resolve(); }
    loadHome() { return this.settle(); }
    markInviteSeen() { return this.settle(); }
    respondToInvite() { return Promise.reject(new Error('real repository rejection')); }
    loadChildrenPage() { return this.settle(); }
    joinChildRoom() { return this.settle().then(() => 'original-membership'); }
    loadLeaveCandidates() { return this.settle(); }
    leaveSpace() { throw new Error('original sync failure'); }
  }
  class Spaces {
    view() { return { originalSnapshot: true }; }
  }
  class Leave { view() { return { rooms: [] }; } }
  for (const method of ['load', 'selectSpace', 'openSelectedSpace', 'loadMoreChildren', 'joinChild',
    'clearJoinFailure', 'retryJoin', 'acceptInvite']) Spaces.prototype[method] = function() { return 'original-' + method; };
  for (const method of ['bind', 'load', 'setSelected', 'selectAll', 'deselectAll', 'confirmLeave',
    'clearLeaveFailure', 'retryLeave']) Leave.prototype[method] = function() { return 'original-' + method; };
  const repository = new Repository(), original = Repository.prototype.respondToInvite;
  const events = [];
  const observer = context.observeTask09Repository({ SpacesPresenter: Spaces }, { LeaveSpacePresenter: Leave },
    { SpaceServiceRegistry: { getRepository: () => repository } }, { key }, event => events.push(event));
  return { observer, repository, Spaces, Leave, original, Repository, events };
}

test('input fixtures preserve direct rooms and actual account seen records', () => {
  const { observer, repository, Spaces } = fixture('default_leave_selection');
  try {
    assert.equal(repository.account.rooms.get('!dm').isDirect, true);
    const presenter = new Spaces();
    assert.equal(presenter.load(), 'original-load');
    assert.equal(observer.read().spaces.originalSnapshot, true);
    repository.account.seenSpaceIds.push('!invited');
    assert.deepEqual(Array.from(observer.read().account.seenSpaceIds), ['!invited']);
  } finally { observer.dispose(); }
});

test('original failures and return values survive observation, and descriptors restore', async () => {
  const { observer, repository, Repository, original } = fixture('join_child_success');
  try {
    assert.equal(await repository.joinChildRoom('!space', '!a'), 'original-membership');
    await assert.rejects(repository.respondToInvite('!invited', 'accept'), /real repository rejection/);
    assert.throws(() => repository.leaveSpace('!space', ['!a']), /original sync failure/);
    assert.equal(observer.read().attempts['!a'], 1);
    assert.equal(observer.read().calls.find(call => call.method === 'leaveSpace').error, 'Error: original sync failure');
  } finally { observer.dispose(); }
  assert.equal(Repository.prototype.respondToInvite, original);
});

test('pending request stays pending until external latency release; no success output injected', async () => {
  const { observer, repository } = fixture('open_space');
  try {
    let completed = false;
    const request = repository.loadChildrenPage('!space', '', 4).then(() => { completed = true; });
    await Promise.resolve(); assert.equal(completed, false);
    observer.release(); await request; assert.equal(completed, true);
  } finally { observer.dispose(); }
});

test('automatic seen tracking cannot mutate the given before the Accept event', async () => {
  const { observer, repository } = fixture('accept_invite');
  try {
    let completed = false;
    const pending = repository.markInviteSeen('!invited').then(() => { completed = true; });
    await Promise.resolve(); assert.equal(completed, false);
    assert.deepEqual(Array.from(repository.account.seenSpaceIds), []);
    observer.release(); await pending; assert.equal(completed, true);
  } finally { observer.dispose(); }
});

test('pagination input contains an overlapping page without changing original pagination logic', () => {
  const { observer, repository } = fixture('paginate_children');
  try {
    const ids = repository.account.spaces[0].childRoomIds;
    assert.deepEqual(Array.from(new Set(ids.slice(0, 4))), ['!a', '!b']);
    assert.deepEqual(Array.from(ids.slice(4)), ['!b', '!c']);
  } finally { observer.dispose(); }
});

test('automatic pagination retains the real pre-dispatch state and holds only request latency', async () => {
  const { observer, repository, Spaces } = fixture('paginate_children');
  try {
    Spaces.prototype.view = () => ({ hasMoreChildren: true, loadingMore: false, childrenLoading: false,
      children: [{ roomId: '!a' }, { roomId: '!b' }] });
    new Spaces().loadMoreChildren();
    const event = observer.read().paginationEvents[0];
    assert.deepEqual(Array.from(event.before.children, child => child.roomId), ['!a', '!b']);
    let completed = false;
    const request = repository.loadChildrenPage('!space', 'next', 4).then(() => { completed = true; });
    await Promise.resolve(); assert.equal(completed, false);
    observer.release(); await request; assert.equal(completed, true);
  } finally { observer.dispose(); }
});

// These are adapter unit tests, not benchmark scores or device evidence.
async function projectRuntimeSnapshot(key, state) {
  const context = { Map, Promise };
  vm.createContext(context);
  vm.runInContext(fs.readFileSync(path.join(__dirname, 'Task09Repository.js'), 'utf8').replace(/^export /gm, ''), context);
  context.observeTask09Repository = () => ({ read: () => state, dispose() {}, release() {} });
  const session = { async reloadOriginalPage() {}, async delay() {}, async action() {},
    async observe(_label, selectors) {
      const controls = {};
      for (const [name, alternatives] of Object.entries(selectors)) {
        const id = alternatives[0].id;
        controls[name] = { present: !id?.startsWith('space_child_joined_'),
          visible: !id?.startsWith('space_child_joined_'), enabled: !id?.endsWith('__admin') };
      }
      return { controls, routeName: key.includes('leave') ? 'pages/LeaveSpace' : 'pages/Index' };
    } };
  const prepared = context.observeTask09Repository();
  return context.runTask09RepositoryCase({ key, invariants: ['unchanged invariant'] },
    { repositoryModules: {}, entryRoute: 'pages/Index' }, session, async () => ({}), () => {}, () => {}, prepared);
}

const snapshot = () => ({ spaces: { loading: false, childrenLoading: false,
  spaces: [{ spaceId: '!space' }], children: [{ roomId: '!a', membership: 'joined', joinState: 'success' },
    { roomId: '!b', membership: 'none', joinState: 'idle' }] },
  account: { spaces: [{ spaceId: '!invited', joined: true }], invites: [], seenSpaceIds: ['!invited'] },
  calls: [{ method: 'acceptInvite', completed: true }, { method: 'respondToInvite', completed: true },
    { method: 'joinChildRoom', completed: true }], attempts: { '!a': 1 },
  leave: { loading: false, rooms: [{ roomId: '!normal', selected: true, eligible: true },
    { roomId: '!admin', selected: false, eligible: false, isLastAdmin: true },
    { roomId: '!dm', selected: false, eligible: false, isDirect: true }] } });

test('adapter does not erase a real seen invitation to match the contract', async () => {
  const result = await projectRuntimeSnapshot('accept_invite', snapshot());
  assert.equal(result.unsupported, undefined);
  assert.deepEqual(Array.from(result.observed.seenInvites), ['!invited']);
});

test('adapter does not hide a direct-message row retained by production', async () => {
  const result = await projectRuntimeSnapshot('default_leave_selection', snapshot());
  assert.equal(result.unsupported, undefined);
  assert.deepEqual(Array.from(result.observed.visibleChildren), ['!normal', '!admin', '!dm']);
  assert.equal(result.invariantChecks[0].passed, false);
});

test('internal success with a stale Join control is not normalized to cleared', async () => {
  const result = await projectRuntimeSnapshot('join_child_success', snapshot());
  assert.equal(result.unsupported, undefined);
  assert.equal(result.observed.joinActions['!a'], 'success');
  assert.notEqual(result.observed.joinActions['!a'], 'cleared');
});

test('repository fixture installation follows initial ability load and precedes original page re-entry', () => {
  const adapter = fs.readFileSync(path.join(__dirname, 'Task09Adapter.js'), 'utf8');
  assert.ok(adapter.indexOf('await startTask11Page(') < adapter.indexOf('await prepareTask09Repository('));
  assert.ok(adapter.indexOf('await prepareTask09Repository(') < adapter.indexOf('await session.reloadOriginalPage('));
  const source = fs.readFileSync(path.join(__dirname, 'Task09Repository.js'), 'utf8');
  assert.doesNotMatch(source, /session\.reloadOriginalPage\(/);
  assert.match(source, /await repository\.loadHome\(\);\s+await repository\.loadHome\(\)/);
  assert.match(source, /fixtures must be installed before original page launch/);
});
