import { configureTask17Loading, runTask17LoadingUi } from './Task17LoadingUi';

const STORE_NAME = 'element_x_pinned_messages';
const PINNED_KEY = 'room_design_pinned_events';
let binding;

export function configureTask17StrictBinding(configJson, importModule = url => import(url)) {
  const config = JSON.parse(configJson);
  if (!config.bundleName || config.moduleName !== 'entry' || config.productionModuleUrl !==
    '@bundle:' + config.bundleName + '/entry/ets/features/PinnedMessagesFeature') {
    throw new Error('Invalid Task17 strict original module identity');
  }
  binding = { config, importModule };
  configureTask17Loading(configJson, importModule);
}

function visibleTreeNode(frame, id) {
  const found = [];
  function walk(node, hidden = false) {
    if (!node || typeof node !== 'object') return;
    const attrs = node.$attrs || {};
    const blocked = hidden || ['Visibility.Hidden', 'Visibility.None'].includes(attrs.visibility) ||
      (attrs.opacity !== undefined && Number(attrs.opacity) === 0);
    if (attrs.id === id && !blocked) found.push(node);
    for (const child of node.$children || node.children || []) walk(child, blocked);
  }
  walk(frame.tree);
  if (found.length !== 1 || found[0].$attrs.visibility !== 'Visibility.Visible') return false;
  const rectangle = frame.rectangles?.[id];
  const bounds = frame.windowIdentity?.bounds;
  if (!rectangle || !bounds) return false;
  const x = rectangle.screenOffset?.x;
  const y = rectangle.screenOffset?.y;
  const width = rectangle.size?.width;
  const height = rectangle.size?.height;
  return [x, y, width, height].every(Number.isFinite) && width > 0 && height > 0 &&
    Math.min(x + width, bounds.right) > Math.max(x, bounds.left) &&
    Math.min(y + height, bounds.bottom) > Math.max(y, bounds.top);
}

function stateOf(presenter) {
  return {
    listState: presenter.listState,
    visibleEventIds: presenter.pinnedMessages.map(message => message.eventId),
    loadedPinnedMessagesCount: presenter.pinnedMessages.length,
    errorVisible: presenter.errorMessage.length > 0,
    failureVisible: presenter.listState === 'failed',
    emptyStateVisible: presenter.listState === 'empty',
    retryEnabled: presenter.retryEnabled,
    focusedEventId: presenter.focusedEventId
  };
}

function row(namespace, value) {
  return new namespace.PinnedMessage(value.eventId, value.sender || 'Evaluator', value.body || '');
}

export async function runTask17StrictNativeUi(caseJson, bundleName, driver, ON, launch, preferences) {
  const spec = JSON.parse(caseJson);
  const result = {
    taskId: spec.taskId,
    caseId: spec.caseId,
    key: spec.key,
    traceDigest: spec.traceDigest,
    bundleName,
    sessionId: spec.caseId + ':' + Date.now(),
    frames: [],
    actions: [],
    entryExecuted: false,
    eventExecuted: false,
    runtimeMode: 'uninitialized'
  };
  let stage = 'validate';
  let disposedByLoadingProbe = false;
  let namespace;

  async function find(selector) {
    const nodes = await driver.findComponents(selector.inWindow(bundleName)) || [];
    if (nodes.length > 1) throw new Error('Ambiguous Task17 strict selector');
    return nodes[0];
  }

  async function inspectId(id) {
    const window = await launch.check(driver);
    const node = await find(ON.id(id));
    if (!node) return { id, present: false, visible: false };
    const bounds = await node.getBounds();
    const viewport = window.bounds;
    return { id, present: true, text: await node.getText(), enabled: await node.isEnabled(),
      clickable: await node.isClickable(), bounds,
      visible: Math.min(viewport.right, bounds.right) > Math.max(viewport.left, bounds.left) &&
        Math.min(viewport.bottom, bounds.bottom) > Math.max(viewport.top, bounds.top) };
  }

  async function visibleTexts() {
    await launch.check(driver);
    const nodes = await driver.findComponents(ON.type('Text').inWindow(bundleName)) || [];
    const values = [];
    for (const node of nodes) values.push(await node.getText());
    return values;
  }

  async function capture(label, extra = {}) {
    const ids = ['pinned_messages_banner', 'pinned_banner_next', 'open_pinned_messages',
      'pinned_messages_back', 'pinned_messages_loading', 'pinned_messages_filled',
      'pinned_messages_empty', 'pinned_messages_failed', 'focused_event_label'];
    const controls = [];
    for (const id of ids) controls.push(await inspectId(id));
    const frame = { label, sequence: result.frames.length + result.actions.length + 1,
      sessionId: result.sessionId, bundleName, windowIdentity: launch.read().lastReady,
      controls, visibleTexts: await visibleTexts(), ...extra };
    result.frames.push(frame);
    return frame;
  }

  async function clickId(id) {
    const control = await inspectId(id);
    if (!control.visible || !control.enabled || !control.clickable) {
      throw new Error('Task17 strict control unavailable: ' + id);
    }
    const node = await find(ON.id(id));
    const action = { kind: 'click', target: id, sequence: result.frames.length + result.actions.length + 1,
      sessionId: result.sessionId, executed: false };
    result.actions.push(action);
    await node.click();
    action.executed = true;
  }

  async function settle(name, predicate, budgetMs = 6000) {
    const started = Date.now();
    const attempts = [];
    for (let attempt = 0; attempt < 48 && Date.now() - started < budgetMs; attempt++) {
      try {
        const ready = await predicate();
        attempts.push({ attempt: attempt + 1, ready });
        if (ready) return { ready: true, attempts };
      } catch (error) {
        attempts.push({ attempt: attempt + 1, error: String(error) });
      }
      await driver.delayMs(120);
    }
    throw new Error('Task17 strict readiness exhausted: ' + name + ': ' + JSON.stringify(attempts[attempts.length - 1]));
  }

  async function readRaw(context) {
    const store = await preferences.getPreferences(context, STORE_NAME);
    const present = await store.has(PINNED_KEY);
    const raw = await store.get(PINNED_KEY, '');
    let rows = [];
    if (present && typeof raw === 'string' && raw.length > 0) rows = JSON.parse(raw);
    return { present, raw, rows };
  }

  function sourceRows() {
    const given = spec.given;
    if (Array.isArray(given.pinnedTimelineItems)) return given.pinnedTimelineItems.map(value => row(namespace, value));
    if (Array.isArray(given.visibleEventIds)) return given.visibleEventIds.map((eventId, index) =>
      row(namespace, { eventId, sender: index === 0 ? 'Alice' : 'Bob', body: index === 0 ? 'Alpha' : 'Beta' }));
    if (given.eventId) return [row(namespace, { eventId: given.eventId, sender: 'Alice', body: 'Alpha' })];
    return [];
  }

  try {
    if (spec.taskId !== '17_pinned_messages' || !/^[a-f0-9]{64}$/.test(spec.traceDigest) ||
      !binding || binding.config.bundleName !== bundleName) throw new Error('Unsupported Task17 strict case/binding');
    result.evaluatorRole = binding.config.evaluatorRole;

    stage = 'launch_original_candidate';
    await launch.start();
    result.entryExecuted = true;
    stage = 'classify_runtime_entry';
    await settle('Task17 candidate room entry', async () =>
      (await inspectId('open_pinned_messages')).visible || (await inspectId('pinned_banner_next')).visible);
    const finalEntryAvailable = (await inspectId('open_pinned_messages')).visible;
    result.runtimeClassification = finalEntryAvailable ? 'feature_entry_present' : 'feature_entry_absent';
    if (!finalEntryAvailable) {
      result.runtimeMode = 'actual_base_page_feature_absence_with_positive_control';
      stage = 'await_base_positive_control';
      await settle('base pinned banner', async () => (await inspectId('pinned_banner_next')).visible);
      const before = await capture('before_event');
      if ((await inspectId('open_pinned_messages')).present) throw new Error('Base unexpectedly exposes final collection entry');
      stage = 'physical_base_banner_next';
      await clickId('pinned_banner_next');
      await settle('base banner body changed', async () => (await visibleTexts()).includes('Welcome to the room'));
      const after = await capture('after_event');
      result.eventExecuted = true;
      result.baseFeatureAbsent = true;
      result.basePositiveControl = {
        clickedBannerNext: result.actions.some(action => action.target === 'pinned_banner_next' && action.executed),
        bodyChanged: !before.visibleTexts.includes('Welcome to the room') && after.visibleTexts.includes('Welcome to the room'),
        finalEntryAbsentBefore: !before.controls.find(control => control.id === 'open_pinned_messages')?.present,
        finalEntryAbsentAfter: !after.controls.find(control => control.id === 'open_pinned_messages')?.present
      };
      result.observed = {};
      result.invariantChecks = [];
      return JSON.stringify(result);
    }

    if (spec.key === 'open_loading') {
      stage = 'delegate_natural_loading_probe';
      disposedByLoadingProbe = true;
      const raw = JSON.parse(await runTask17LoadingUi(caseJson, bundleName, driver, ON, launch, preferences, true));
      raw.key = spec.key;
      raw.evaluatorRole = binding.config.evaluatorRole;
      raw.runtimeClassification = 'feature_entry_present';
      raw.runtimeMode = 'actual_page_natural_loading_frame_and_original_repository';
      raw.frames.push({ ...(raw.frames.find(frame => frame.label === 'after_event_settled_or_bounded') || {}),
        label: 'after_event' });
      const loading = raw.loadingFrames?.frames?.find(frame =>
        frame.observer?.currentPresenterState?.listState === 'loading' &&
        visibleTreeNode(frame, 'pinned_messages_loading') && visibleTreeNode(frame, 'pinned_messages_back'));
      const before = raw.frames.find(frame => frame.label === 'before_event');
      const returned = raw.frames.find(frame => frame.label === 'after_parent_return');
      const visible = (frame, name) => frame?.controls?.some(control => control.name === name && control.visible);
      raw.naturalLoadingFrame = loading;
      raw.nativePreferences = { sameAbilityContext: raw.persistence?.before?.sameAbilityContext === true &&
        raw.persistence?.after?.sameAbilityContext === true, storeName: STORE_NAME, key: PINNED_KEY,
        before: raw.persistence?.before, after: raw.persistence?.after };
      raw.observed = loading ? { screen: 'pinned_messages', listState: 'loading', effects: ['open_pinned_timeline'] } : {};
      raw.invariantChecks = [{ description: spec.invariants[0], passed: Boolean(loading && before && returned &&
        visible(before, 'room') && visible(returned, 'room') && visible(returned, 'banner') &&
        visible(returned, 'open') && !visible(returned, 'back')),
      evidence: 'Physical Open and Back on the same original page with a natural ArkUI loading frame.' }];
      return JSON.stringify(raw);
    }

    result.runtimeMode = spec.key === 'view_in_timeline'
      ? 'actual_page_ui_navigation_and_native_preferences'
      : 'original_installed_module_presenter_repository_and_native_preferences';
    stage = 'await_final_room';
    await settle('final room entry', async () => (await inspectId('open_pinned_messages')).visible);
    stage = 'bind_original_installed_module';
    namespace = await binding.importModule(binding.config.productionModuleUrl);
    result.binding = { ...binding.config, importCompleted: true, phase: 'after_original_room_ready_before_fixture' };
    const context = launch.current().abilityContext;
    const repository = new namespace.PinnedMessagesRepository();
    const presenter = new namespace.PinnedMessagesListPresenter(repository);
    const operations = [];
    const beforeStore = await readRaw(context);
    const rows = sourceRows();
    if (spec.key !== 'load_failure') {
      await repository.persistPinnedState(context, rows);
      operations.push({ method: 'PinnedMessagesRepository.persistPinnedState', eventIds: rows.map(value => value.eventId) });
    }
    const seededStore = await readRaw(context);
    result.nativePreferences = { sameAbilityContext: context === launch.current().abilityContext,
      storeName: STORE_NAME, key: PINNED_KEY, before: beforeStore, seeded: seededStore, operations };

    if (spec.key === 'view_in_timeline') {
      stage = 'ui_navigation_given';
      const before = await capture('before_event', { persisted: seededStore });
      await clickId('open_pinned_messages');
      await settle('filled list', async () => (await inspectId('pinned_messages_filled')).visible);
      const target = 'view_in_timeline_' + spec.given.eventId;
      await clickId(target);
      await settle('focused timeline', async () => {
        const label = await inspectId('focused_event_label');
        return label.visible && label.text === 'Focused ' + spec.given.eventId &&
          (await inspectId('open_pinned_messages')).visible;
      });
      const afterStore = await readRaw(context);
      const after = await capture('after_event', { persisted: afterStore });
      result.nativePreferences.after = afterStore;
      result.eventExecuted = true;
      result.observed = { screen: 'room_timeline', focusedEventId: spec.given.eventId,
        effects: ['navigate_to_event'] };
      result.invariantChecks = [{ description: spec.invariants[0], passed: seededStore.raw === afterStore.raw,
        evidence: { before: before.persisted, after: after.persisted } }];
      return JSON.stringify(result);
    }

    if (spec.key === 'load_failure') repository.failNextLoad = true;
    presenter.setPermission(Boolean(spec.given.canPinUnpin));
    const completionCase = ['load_failure', 'empty_success', 'filled_list'].includes(spec.key);
    const openOperation = presenter.openPinnedMessages(context);
    operations.push({ method: 'PinnedMessagesListPresenter.openPinnedMessages' });
    let before;
    if (completionCase) {
      before = stateOf(presenter);
      if (before.listState !== 'loading') throw new Error('Canonical loading GIVEN was not established synchronously');
      await openOperation;
    } else {
      await openOperation;
      before = stateOf(presenter);
    }
    result.frames.push({ label: 'before_event', sequence: 1, sessionId: result.sessionId, bundleName,
      presenter: before, persisted: seededStore, windowIdentity: launch.read().lastReady });

    if (completionCase) {
      result.actions.push({ kind: 'production_completion', target: 'openPinnedMessages', executed: true,
        sequence: 2, sessionId: result.sessionId });
      result.observed = stateOf(presenter);
      if (spec.key === 'load_failure') result.observed = { listState: presenter.listState,
        emptyStateVisible: presenter.listState === 'empty', errorVisible: presenter.errorMessage.length > 0 };
      if (spec.key === 'empty_success') result.observed = { listState: presenter.listState,
        loadedPinnedMessagesCount: presenter.pinnedMessages.length, failureVisible: presenter.listState === 'failed' };
      if (spec.key === 'filled_list') result.observed = { listState: presenter.listState,
        visibleEventIds: presenter.pinnedMessages.map(value => value.eventId),
        loadedPinnedMessagesCount: presenter.pinnedMessages.length };
    } else if (['unpin_permission_denied', 'unpin_permission_allowed'].includes(spec.key)) {
      const actions = presenter.availableActions();
      operations.push({ method: 'PinnedMessagesListPresenter.availableActions', returned: actions });
      result.actions.push({ kind: 'production_call', target: 'availableActions', executed: true,
        sequence: 2, sessionId: result.sessionId });
      result.observed = { actionsVisible: actions };
      if (spec.key === 'unpin_permission_denied') result.observed.actionsHidden = ['unpin'].filter(value => !actions.includes(value));
    } else if (['unpin_success', 'unpin_failure_recovery'].includes(spec.key)) {
      if (spec.key === 'unpin_failure_recovery') repository.failNextUnpin = true;
      const success = await presenter.unpin(context, spec.event.eventId);
      operations.push({ method: 'PinnedMessagesListPresenter.unpin', eventId: spec.event.eventId, returned: success });
      result.actions.push({ kind: 'production_call', target: 'unpin', eventId: spec.event.eventId,
        executed: true, sequence: 2, sessionId: result.sessionId });
      result.observed = { visibleEventIds: presenter.pinnedMessages.map(value => value.eventId),
        errorVisible: presenter.errorMessage.length > 0, retryEnabled: presenter.retryEnabled };
      if (spec.key === 'unpin_success') result.observed.effects = repository.lastUnpinnedEventId === spec.event.eventId
        ? ['unpin_event', 'persist_pinned_state'] : [];
      else result.observed.effects = presenter.errorMessage.length > 0 ? ['show_error'] : [];
    } else throw new Error('Unhandled Task17 strict key: ' + spec.key);

    const afterStore = await readRaw(context);
    const after = stateOf(presenter);
    result.nativePreferences.after = afterStore;
    result.frames.push({ label: 'after_event', sequence: 3, sessionId: result.sessionId, bundleName,
      presenter: after, persisted: afterStore, windowIdentity: launch.read().lastReady });
    const sameRaw = seededStore.raw === afterStore.raw;
    if (spec.key === 'load_failure') result.invariantChecks = [{ description: spec.invariants[0],
      passed: presenter.listState === 'failed' && presenter.listState !== 'empty', evidence: after }];
    if (spec.key === 'empty_success') result.invariantChecks = [{ description: spec.invariants[0],
      passed: presenter.listState === 'empty' && presenter.errorMessage.length === 0, evidence: after }];
    if (spec.key === 'filled_list') result.invariantChecks = [{ description: spec.invariants[0],
      passed: JSON.stringify(presenter.pinnedMessages.map(value => value.eventId)) ===
        JSON.stringify(spec.given.pinnedTimelineItems.map(value => value.eventId)), evidence: after }];
    if (spec.key === 'unpin_permission_denied') result.invariantChecks = [{ description: spec.invariants[0],
      passed: sameRaw && presenter.pinnedMessages.length === rows.length, evidence: { before: seededStore, after: afterStore } }];
    if (spec.key === 'unpin_permission_allowed') {
      presenter.setPermission(false);
      const denied = presenter.availableActions();
      result.invariantChecks = [{ description: spec.invariants[0],
        passed: result.observed.actionsVisible.includes('unpin') && !denied.includes('unpin') && sameRaw,
        evidence: { allowed: result.observed.actionsVisible, denied, persisted: afterStore } }];
    }
    if (spec.key === 'unpin_success') result.invariantChecks = [{ description: spec.invariants[0],
      passed: JSON.stringify(presenter.pinnedMessages.map(value => value.eventId)) === JSON.stringify(['$b']) &&
        JSON.stringify(afterStore.rows.map(value => value.eventId)) === JSON.stringify(['$b']),
      evidence: { presenter: after, persisted: afterStore, lastUnpinnedEventId: repository.lastUnpinnedEventId } }];
    if (spec.key === 'unpin_failure_recovery') result.invariantChecks = [{ description: spec.invariants[0],
      passed: !sameRaw ? false : JSON.stringify(presenter.pinnedMessages.map(value => value.eventId)) ===
        JSON.stringify(spec.given.visibleEventIds), evidence: { presenter: after, persisted: afterStore } }];
    result.eventExecuted = true;
  } catch (error) {
    result.failure = { stage, message: String(error), stack: error?.stack };
    if (result.frames.length === 0) result.frames.push({ label: 'before_event', failureStage: stage });
    result.frames.push({ label: 'after_event', failureStage: stage, error: String(error) });
  } finally {
    result.launchEvidence = launch.read();
    if (!disposedByLoadingProbe) {
      try { await launch.dispose(); }
      catch (error) { result.failure = { ...result.failure, cleanupError: String(error) }; }
    }
  }
  return JSON.stringify(result);
}
