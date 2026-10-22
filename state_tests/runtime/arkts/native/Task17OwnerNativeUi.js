let binding;

export function configureTask17OwnerBinding(configJson, importModule = url => import(url)) {
  const config = JSON.parse(configJson);
  if (!config.bundleName || config.moduleName !== 'entry' ||
      !['base', 'final', 'agent'].includes(config.evaluatorRole) || !config.roomModuleUrl) {
    throw new Error('Invalid Task17 owner-bound module identity');
  }
  binding = { config, importModule };
}

function createFixture(spec, namespace) {
  const given = spec.given || {};
  const source = Array.isArray(given.pinnedTimelineItems) ? given.pinnedTimelineItems :
    Array.isArray(given.visibleEventIds) ? given.visibleEventIds.map((eventId, index) => ({
      eventId, sender: index === 0 ? 'Alice' : 'Bob', body: index === 0 ? 'Alpha' : 'Beta'
    })) : given.eventId ? [{ eventId: given.eventId, sender: 'Alice', body: 'Alpha' }] : [];
  const rows = source.map(value => new namespace.PinnedMessage(value.eventId, value.sender || 'Evaluator', value.body || ''));
  const timelineListeners = [];
  const summaryListeners = [];
  const calls = [];
  let current = rows.slice();
  const copy = () => current.slice();
  const emit = () => timelineListeners.slice().forEach(listener => listener(copy()));
  const emitSummary = () => summaryListeners.slice().forEach(listener => listener(summary()));
  const summary = () => namespace.PinnedSummary ? new namespace.PinnedSummary(current.length, copy()) :
    { count: current.length, items: copy(), hasPinnedMessages: () => current.length > 0 };
  const page = items => namespace.PinnedTimelinePage ? new namespace.PinnedTimelinePage(items, false) :
    { items, hasMore: false };
  const timeline = {
    subscribeItems(listener) {
      timelineListeners.push(listener);
      calls.push({ method: 'subscribeItems' });
      if (!['open_loading', 'load_failure'].includes(spec.key)) Promise.resolve().then(() => listener(copy()));
      return () => {
        const index = timelineListeners.indexOf(listener);
        if (index >= 0) timelineListeners.splice(index, 1);
      };
    },
    async loadNextPage() {
      calls.push({ method: 'loadNextPage' });
      if (spec.key === 'open_loading') return new Promise(() => {});
      emit();
      return page(copy());
    },
    async unpinEvent(eventId) {
      calls.push({ method: 'unpinEvent', eventId });
      if (spec.key === 'unpin_failure_recovery') throw new Error('Evaluator room rejected unpin');
      const before = current.length;
      current = current.filter(item => item.eventId !== eventId);
      if (current.length === before) return false;
      emit();
      emitSummary();
      return true;
    },
    close() { calls.push({ method: 'closeTimeline' }); }
  };
  const room = {
    roomId: '!task17-owner:benchmark',
    async pinnedEventsTimeline() {
      calls.push({ method: 'pinnedEventsTimeline' });
      if (spec.key === 'load_failure') throw new Error('Evaluator room failed pinned timeline');
      if (spec.key === 'open_loading') return new Promise(() => {});
      return timeline;
    },
    async canPinUnpin() {
      const allowed = given.canPinUnpin === undefined ? true : Boolean(given.canPinUnpin);
      calls.push({ method: 'canPinUnpin', returned: allowed });
      return allowed;
    },
    subscribeSync(listener) {
      calls.push({ method: 'subscribeSync' });
      return () => {};
    },
    async loadTimeline(focusedEventId) {
      calls.push({ method: 'loadTimeline', focusedEventId: focusedEventId || '' });
      return copy();
    },
    async loadPinnedSummary() {
      calls.push({ method: 'loadPinnedSummary' });
      return summary();
    },
    subscribePinnedSummary(listener) {
      summaryListeners.push(listener);
      calls.push({ method: 'subscribePinnedSummary' });
      return () => {
        const index = summaryListeners.indexOf(listener);
        if (index >= 0) summaryListeners.splice(index, 1);
      };
    },
    async pinEvent(eventId) {
      calls.push({ method: 'pinEvent', eventId });
      return false;
    }
  };
  return { room, calls, eventIds: () => current.map(item => item.eventId), messages: () => copy() };
}

export async function runTask17OwnerNativeUi(caseJson, bundleName, driver, ON, launch) {
  const spec = JSON.parse(caseJson);
  const result = {
    taskId: spec.taskId, caseId: spec.caseId, key: spec.key, traceDigest: spec.traceDigest,
    bundleName, sessionId: spec.caseId + ':' + Date.now(), frames: [], actions: [],
    entryExecuted: false, eventExecuted: false, runtimeMode: 'uninitialized'
  };
  let stage = 'validate';
  let fixture;
  let bindingDiagnostics = {};
  const featureAbsentObservation = () => {
    if (spec.key === 'open_loading') return { screen: 'room_timeline', listState: 'closed', effects: [] };
    if (spec.key === 'load_failure') return { listState: 'unavailable', emptyStateVisible: false, errorVisible: false };
    if (spec.key === 'empty_success') return { listState: 'unavailable', loadedPinnedMessagesCount: 0, failureVisible: false };
    if (spec.key === 'filled_list') return { listState: 'unavailable', visibleEventIds: [], loadedPinnedMessagesCount: 0 };
    if (spec.key === 'unpin_permission_denied') return { actionsVisible: [], actionsHidden: ['unpin'] };
    if (spec.key === 'unpin_permission_allowed') return { actionsVisible: [] };
    if (spec.key === 'view_in_timeline') return { screen: 'room_timeline', focusedEventId: '', effects: [] };
    if (spec.key === 'unpin_success') return { visibleEventIds: [], effects: [], errorVisible: false };
    return { visibleEventIds: [], effects: [], retryEnabled: false };
  };
  const serialize = () => {
    result.fixture = fixture ? { calls: fixture.calls, eventIds: fixture.eventIds() } : undefined;
    result.launchEvidence = launch.read();
    return JSON.stringify(result);
  };

  async function find(selector) {
    const nodes = await driver.findComponents(selector.inWindow(bundleName)) || [];
    if (nodes.length > 1) throw new Error('Ambiguous Task17 owner-bound selector');
    return nodes[0];
  }
  async function inspect(selector, name) {
    await launch.check(driver);
    const node = await find(selector);
    if (!node) return { name, present: false, visible: false };
    const bounds = await node.getBounds();
    const viewport = launch.read().lastReady.bounds;
    return { name, present: true, text: await node.getText(), enabled: await node.isEnabled(),
      clickable: await node.isClickable(), bounds,
      visible: Math.min(viewport.right, bounds.right) > Math.max(viewport.left, bounds.left) &&
        Math.min(viewport.bottom, bounds.bottom) > Math.max(viewport.top, bounds.top) };
  }
  async function byId(id) { return inspect(ON.id(id), id); }
  async function byText(text, type) {
    const selector = type ? ON.type(type).text(text) : ON.text(text);
    return inspect(selector, text);
  }
  async function firstVisible(candidates) {
    for (const candidate of candidates) {
      const value = candidate.kind === 'id' ? await byId(candidate.value) :
        await byText(candidate.value, candidate.type);
      if (value.visible) return { ...value, candidate };
    }
    return undefined;
  }
  async function click(target, name) {
    const node = await find(target);
    if (!node || !await node.isEnabled() || !await node.isClickable()) {
      throw new Error('Task17 owner-bound control unavailable: ' + name);
    }
    const action = { kind: 'physical_click', target: name, executed: false,
      sequence: result.frames.length + result.actions.length + 1 };
    result.actions.push(action);
    await node.click();
    action.executed = true;
  }
  async function clickChoice(choice) {
    const selector = choice.candidate.kind === 'id' ? ON.id(choice.candidate.value) :
      choice.candidate.type ? ON.type(choice.candidate.type).text(choice.candidate.value) : ON.text(choice.candidate.value);
    await click(selector, choice.candidate.value);
  }
  async function settle(name, predicate, budgetMs = 7000) {
    const started = Date.now();
    const attempts = [];
    while (Date.now() - started < budgetMs && attempts.length < 56) {
      try {
        const ready = await predicate();
        attempts.push({ attempt: attempts.length + 1, ready });
        if (ready) return;
      } catch (error) {
        attempts.push({ attempt: attempts.length + 1, error: String(error) });
      }
      await driver.delayMs(120);
    }
    throw new Error('Task17 owner-bound readiness exhausted: ' + name + ': ' +
      JSON.stringify(attempts[attempts.length - 1]));
  }
  async function settleSemantic(predicate, budgetMs = 4500) {
    const started = Date.now();
    while (Date.now() - started < budgetMs) {
      try {
        if (await predicate()) return true;
      } catch (error) {
        // A transient render lookup is retried inside the bounded semantic window.
      }
      await driver.delayMs(120);
    }
    return false;
  }
  async function visibleIds(ids) {
    const found = [];
    for (const id of ids) if ((await byId(id)).visible) found.push(id);
    return found;
  }
  async function capture(label) {
    const ids = ['pinned_messages_banner', 'open_pinned_messages', 'pinned_banner_next',
      'pinned_list_loading', 'pinned_messages_loading', 'pinned_list_error', 'pinned_messages_failed',
      'pinned_list_empty', 'pinned_messages_empty', 'pinned_messages_list', 'pinned_messages_filled'];
    const controls = [];
    for (const id of ids) controls.push(await byId(id));
    const frame = { label, sequence: result.frames.length + result.actions.length + 1,
      route: launch.read().lastReady.routeName, controls };
    result.frames.push(frame);
    return frame;
  }
  const openChoices = [
    { kind: 'id', value: 'open_pinned_messages' },
    { kind: 'text', value: 'Tap to open the pinned messages' },
    { kind: 'text', value: 'Tap to check for pins' }
  ];
  const stateIds = {
    loading: ['pinned_list_loading', 'pinned_messages_loading'],
    failed: ['pinned_list_error', 'pinned_messages_failed'],
    empty: ['pinned_list_empty', 'pinned_messages_empty'],
    filled: ['pinned_messages_list', 'pinned_messages_filled']
  };
  const stateVisible = async name => (await visibleIds(stateIds[name])).length === 1;
  async function detectState() {
    for (const name of ['failed', 'empty', 'filled', 'loading']) if (await stateVisible(name)) return name;
    return 'unknown';
  }

  try {
    if (!binding || binding.config.bundleName !== bundleName || spec.taskId !== '17_pinned_messages' ||
        !/^[a-f0-9]{64}$/.test(spec.traceDigest)) throw new Error('Unsupported Task17 owner-bound case');
    result.evaluatorRole = binding.config.evaluatorRole;
    stage = 'launch_module_loader_ability';
    await launch.start();
    await settle('room timeline ready', async () => (await byText('Design team')).visible);
    if (binding.config.evaluatorRole === 'base') {
      result.entryExecuted = true;
      result.runtimeMode = 'actual_base_page_feature_absence_with_positive_control';
      result.binding = { ...binding.config, baseDoesNotImportAbsentCollection: true };
      await capture('before_event');
      if (await firstVisible(openChoices)) throw new Error('Base unexpectedly exposes pinned collection entry');
      const next = await byId('pinned_banner_next');
      if (!next.visible) throw new Error('Base positive control unavailable');
      await click(ON.id('pinned_banner_next'), 'pinned_banner_next');
      await driver.delayMs(120);
      await capture('after_event');
      result.semanticFeatureAbsent = true;
      result.basePositiveControl = { clickedBannerNext: true, finalEntryAbsent: true };
      result.observed = featureAbsentObservation();
      result.invariantChecks = [{ description: spec.invariants[0], passed: false,
        evidence: 'The installed base page is live but has no pinned collection entry.' }];
      return serialize();
    }
    stage = 'bind_room_before_scored_page_owner';
    const namespace = await binding.importModule(binding.config.roomModuleUrl);
    const sessionNamespace = binding.config.sessionModuleUrl === binding.config.roomModuleUrl ? namespace :
      await binding.importModule(binding.config.sessionModuleUrl);
    const timelineNamespace = binding.config.timelineModuleUrl ?
      await binding.importModule(binding.config.timelineModuleUrl) : undefined;
    const bannerNamespace = binding.config.bannerModuleUrl ?
      await binding.importModule(binding.config.bannerModuleUrl) : undefined;
    fixture = createFixture(spec, namespace);
    await launch.restart(async () => {
      if (binding.config.sessionExport === 'PinnedMessagesSession') {
        if (typeof namespace.PinnedMessagesSession?.configureRoom !== 'function') {
          throw new Error('Final production room configurator unavailable');
        }
        namespace.PinnedMessagesSession.configureRoom(fixture.room);
      } else {
        if (typeof namespace.RoomSession?.configureRoom !== 'function') {
          throw new Error('Baseline production room configurator unavailable');
        }
        if (binding.config.resetSharedSession) {
          const current = sessionNamespace.PinnedMessagesSession?.shared?.();
          current?.stop?.();
          sessionNamespace.PinnedMessagesSession.instance = undefined;
          const replacement = sessionNamespace.PinnedMessagesSession?.shared?.();
          const service = new namespace.MatrixRoomService(fixture.room);
          replacement.roomService = service;
          replacement.timelineController = new timelineNamespace.RoomTimelineController(service);
          replacement.banner = new bannerNamespace.PinnedMessagesBannerPresenter();
          replacement.banner.updateFrom(fixture.messages());
          replacement.pinnedList = undefined;
          replacement.started = true;
          bindingDiagnostics = {
            sessionStaticKeys: Object.getOwnPropertyNames(sessionNamespace.PinnedMessagesSession),
            previousInstanceKeys: current ? Object.keys(current) : [],
            replacementInstanceKeys: replacement ? Object.keys(replacement) : [],
            replacementCreated: current !== replacement,
            roomFactoryBound: namespace.RoomSession.createService?.()?.port === fixture.room,
            replacementRoomBound: replacement?.roomService?.port === fixture.room,
            candidateLifecycleDependencyBound: replacement.roomService === service &&
              replacement.timelineController !== undefined && replacement.started === true
          };
        }
        namespace.RoomSession.configureRoom(fixture.room);
      }
    });
    result.entryExecuted = true;
    result.binding = { ...binding.config, importCompleted: true,
      configuredBeforeScoredAbilityStart: true, loaderAbilityExcludedFromFrames: true,
      diagnostics: bindingDiagnostics };
    stage = 'launch_original_candidate';
    await settle('scored room timeline ready', async () => (await byText('Design team')).visible);
    const before = await capture('before_event');
    const open = await firstVisible(openChoices);
    if (!open) {
      result.runtimeMode = 'actual_base_page_feature_absence_with_positive_control';
      const next = await byId('pinned_banner_next');
      if (!next.visible) throw new Error('Base positive control unavailable');
      await click(ON.id('pinned_banner_next'), 'pinned_banner_next');
      await driver.delayMs(120);
      await capture('after_event');
      result.semanticFeatureAbsent = true;
      result.basePositiveControl = { clickedBannerNext: true, finalEntryAbsent: true };
      result.observed = featureAbsentObservation();
      result.invariantChecks = [{ description: spec.invariants[0], passed: false,
        evidence: 'The installed base page is live but has no pinned collection entry.' }];
      return serialize();
    }

    stage = 'open_real_pinned_collection';
    await clickChoice(open);
    result.eventExecuted = true;
    result.runtimeMode = 'actual_candidate_page_owner_with_evaluator_matrix_room_port';
    if (spec.key === 'open_loading') {
      await settle('loading state', () => stateVisible('loading'));
      const loadingFrame = await capture('after_event');
      const close = await firstVisible([{ kind: 'id', value: 'pinned_messages_back' },
        { kind: 'id', value: 'pinned_messages_close' }]);
      let parentRestored = false;
      if (close) {
        await clickChoice(close);
        await settle('room parent restored', async () => (await byText('Design team')).visible);
        parentRestored = Boolean(await firstVisible(openChoices));
      }
      result.observed = { screen: 'pinned_messages', listState: 'loading',
        effects: fixture.calls.some(call => call.method === 'pinnedEventsTimeline') ? ['open_pinned_timeline'] : [] };
      result.invariantChecks = [{ description: spec.invariants[0], passed: parentRestored,
        evidence: { loadingFrame, parentRestored } }];
      return serialize();
    }

    const targetState = spec.key === 'load_failure' ? 'failed' :
      spec.key === 'empty_success' ? 'empty' : 'filled';
    stage = 'await_real_page_state';
    const targetReached = await settleSemantic(() => stateVisible(targetState));
    if (!targetReached) {
      const actualState = await detectState();
      await capture('after_event');
      if (spec.key === 'load_failure') {
        result.observed = { listState: actualState, emptyStateVisible: actualState === 'empty',
          errorVisible: actualState === 'failed' };
      } else if (spec.key === 'empty_success') {
        result.observed = { listState: actualState, loadedPinnedMessagesCount: 0,
          failureVisible: actualState === 'failed' };
      } else if (spec.key === 'filled_list') {
        result.observed = { listState: actualState, visibleEventIds: [], loadedPinnedMessagesCount: 0 };
      } else if (spec.key === 'unpin_permission_denied') {
        result.observed = { actionsVisible: [], actionsHidden: ['unpin'] };
      } else if (spec.key === 'unpin_permission_allowed') {
        result.observed = { actionsVisible: [] };
      } else if (spec.key === 'view_in_timeline') {
        result.observed = { screen: 'pinned_messages', focusedEventId: '', effects: [] };
      } else if (spec.key === 'unpin_success') {
        result.observed = { visibleEventIds: [], effects: [], errorVisible: false };
      } else {
        result.observed = { visibleEventIds: [], effects: [], retryEnabled: false };
      }
      result.invariantChecks = [{ description: spec.invariants[0], passed: false,
        evidence: { targetState, actualState, boundedSemanticWaitMs: 4500 } }];
      result.semanticNonConvergence = { targetState, actualState, boundedWaitMs: 4500 };
      return serialize();
    }

    if (spec.key === 'load_failure') {
      await capture('after_event');
      result.observed = { listState: 'failed', emptyStateVisible: await stateVisible('empty'), errorVisible: true };
      result.invariantChecks = [{ description: spec.invariants[0],
        passed: !result.observed.emptyStateVisible, evidence: result.observed }];
    } else if (spec.key === 'empty_success') {
      await capture('after_event');
      result.observed = { listState: 'empty', loadedPinnedMessagesCount: 0, failureVisible: await stateVisible('failed') };
      result.invariantChecks = [{ description: spec.invariants[0],
        passed: !result.observed.failureVisible, evidence: result.observed }];
    } else if (spec.key === 'filled_list') {
      const eventIds = spec.given.pinnedTimelineItems.map(item => item.eventId);
      const candidateIds = await visibleIds(eventIds.map(id => 'pinned_item_actions_' + id));
      const finalIds = await visibleIds(eventIds.map(id => 'message_actions_' + id));
      const visibleEventIds = eventIds.filter(id => candidateIds.includes('pinned_item_actions_' + id) ||
        finalIds.includes('message_actions_' + id));
      await capture('after_event');
      result.observed = { listState: 'filled', visibleEventIds, loadedPinnedMessagesCount: visibleEventIds.length };
      result.invariantChecks = [{ description: spec.invariants[0],
        passed: JSON.stringify(visibleEventIds) === JSON.stringify(eventIds), evidence: result.observed }];
    } else {
      const eventId = spec.given.eventId || spec.event.eventId;
      const action = await firstVisible([{ kind: 'id', value: 'pinned_item_actions_' + eventId },
        { kind: 'id', value: 'message_actions_' + eventId }]);
      if (!action) throw new Error('Pinned row action control unavailable for ' + eventId);
      await clickChoice(action);
      const view = await firstVisible([{ kind: 'id', value: 'pinned_item_view_in_timeline_' + eventId },
        { kind: 'id', value: 'view_in_timeline_' + eventId }]);
      const unpin = await firstVisible([{ kind: 'id', value: 'pinned_item_unpin_' + eventId },
        { kind: 'id', value: 'unpin_' + eventId }]);
      if (spec.key === 'unpin_permission_denied' || spec.key === 'unpin_permission_allowed') {
        const actions = [...(view ? ['view_in_timeline'] : []), ...(unpin ? ['unpin'] : [])];
        await capture('after_event');
        result.observed = { actionsVisible: actions };
        if (spec.key === 'unpin_permission_denied') result.observed.actionsHidden = unpin ? [] : ['unpin'];
        result.invariantChecks = [{ description: spec.invariants[0],
          passed: JSON.stringify(fixture.eventIds()) === JSON.stringify([eventId]),
          evidence: { actions, fixtureEventIds: fixture.eventIds() } }];
      } else if (spec.key === 'view_in_timeline') {
        if (!view) throw new Error('View-in-timeline action unavailable');
        await clickChoice(view);
        await settle('focused room timeline', async () =>
          (await byText('Focused ' + eventId)).visible || (await byText('Focused from pinned messages')).visible);
        await capture('after_event');
        result.observed = { screen: 'room_timeline', focusedEventId: eventId, effects: ['navigate_to_event'] };
        result.invariantChecks = [{ description: spec.invariants[0],
          passed: fixture.eventIds().includes(eventId), evidence: { fixtureEventIds: fixture.eventIds() } }];
      } else {
        if (!unpin) throw new Error('Unpin action unavailable');
        await clickChoice(unpin);
        if (spec.key === 'unpin_success') {
          await settle('successful unpin emission', async () => {
            const removed = !(await firstVisible([{ kind: 'id', value: 'pinned_item_actions_' + eventId },
              { kind: 'id', value: 'message_actions_' + eventId }]));
            return removed && JSON.stringify(fixture.eventIds()) === JSON.stringify(['$b']);
          });
          result.observed = { visibleEventIds: fixture.eventIds(), effects: ['unpin_event', 'persist_pinned_state'],
            errorVisible: false };
          result.invariantChecks = [{ description: spec.invariants[0],
            passed: JSON.stringify(fixture.eventIds()) === JSON.stringify(['$b']), evidence: result.observed }];
        } else {
          const retryId = 'pinned_item_unpin_retry_' + eventId;
          await settle('failed unpin feedback', async () => (await byId(retryId)).visible ||
            (await byId('unpin_error')).visible);
          const retryVisible = (await byId(retryId)).visible;
          result.observed = { visibleEventIds: fixture.eventIds(), effects: ['show_error'], retryEnabled: retryVisible };
          result.invariantChecks = [{ description: spec.invariants[0],
            passed: JSON.stringify(fixture.eventIds()) === JSON.stringify(['$a', '$b']), evidence: result.observed }];
        }
        await capture('after_event');
      }
    }
  } catch (error) {
    result.failure = { stage, message: String(error), stack: error?.stack };
    if (result.frames.length === 0) result.frames.push({ label: 'before_event', failureStage: stage });
    result.frames.push({ label: 'after_event', failureStage: stage, error: String(error) });
  } finally {
    result.fixture = fixture ? { calls: fixture.calls, eventIds: fixture.eventIds() } : undefined;
    result.launchEvidence = launch.read();
    try { await launch.dispose(); }
    catch (error) { result.failure = { ...result.failure, cleanupError: String(error) }; }
  }
  return serialize();
}
