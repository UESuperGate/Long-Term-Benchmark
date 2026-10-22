'use strict';
const feature = 'entry/src/main/ets/features/PinnedMessagesFeature.ets', page = 'entry/src/main/ets/pages/Index.ets';
const need = (condition, message) => { if (!condition) throw new Error(message); };
function visibleNode(frame, id) {
  const found = [];
  function walk(node, hidden = false) {
    if (!node || typeof node !== 'object') return;
    const a = node.$attrs || {};
    const blocked = hidden || ['Visibility.Hidden', 'Visibility.None'].includes(a.visibility) ||
      (a.opacity !== undefined && Number(a.opacity) === 0);
    if (a.id === id && !blocked) found.push(node);
    for (const child of node.$children || node.children || []) walk(child, blocked);
  }
  walk(frame.tree);
  if (found.length !== 1 || found[0].$attrs.visibility !== 'Visibility.Visible') return false;
  const rectangle = frame.rectangles?.[id], bounds = frame.windowIdentity?.bounds;
  if (!rectangle || !bounds) return false;
  const x = rectangle.screenOffset?.x, y = rectangle.screenOffset?.y;
  const width = rectangle.size?.width, height = rectangle.size?.height;
  return [x, y, width, height].every(Number.isFinite) && width > 0 && height > 0 &&
    Math.min(x + width, bounds.right) > Math.max(x, bounds.left) && Math.min(y + height, bounds.bottom) > Math.max(y, bounds.top);
}
function verifyNativeReadback(raw, observer, beforeFrame, settledFrame, backFrame) {
  const proof = raw.persistence, before = proof?.before, after = proof?.after;
  const expectedContext = observer.context;
  const sameContext = value => value?.sameAbilityContext === true && value.context?.bundleName === expectedContext.bundleName &&
    value.context.moduleName === expectedContext.moduleName && value.context.area === expectedContext.area &&
    value.context.preferencesDir === expectedContext.preferencesDir && typeof value.context.preferencesDir === 'string' && value.context.preferencesDir.length > 0;
  need(proof?.mechanism === 'native_preferences_absent_before_then_cache_eviction_and_reopen_after_original_completion' &&
    before?.phase === 'before_open' && after?.phase === 'after_cache_reopen' && sameContext(before) && sameContext(after) &&
    before.sequence < beforeFrame.sequence && proof.originalCompletionSequence > settledFrame.sequence &&
    after.sequence > proof.originalCompletionSequence && after.sequence < backFrame.sequence &&
    before.present === false && after.present === true && after.cacheEvicted === true && !after.parseError &&
    proof.evaluatorDataWrites?.length === 0 && proof.prepared && proof.finished &&
    [proof, before, after].every(v => v.storeName === 'element_x_pinned_messages' && v.key === 'room_design_pinned_events'),
    'Native persistence readback missing, pre-populated, wrong-context or unordered');
  need(proof.originalCompletion?.presenterCount === 1 && proof.originalCompletion.repositoryCount === 1 &&
    JSON.stringify(proof.originalCompletion.context) === JSON.stringify(observer.context) &&
    JSON.stringify(proof.originalCompletion.calls) === JSON.stringify(observer.calls),
    'Original completion must precede cache eviction with the same untouched call evidence');
  const expectedOperations = ['getPreferences', 'has', 'get', 'removePreferencesFromCache', 'getPreferences', 'has', 'get'];
  need(proof.operations?.length === expectedOperations.length && proof.operations.every((o, i) => o.sequence === i + 1 && o.completed === true &&
    !o.error && o.method === expectedOperations[i] && o.phase === (i < 3 ? 'before_open' : i === 3 ? 'after_original_completion' : 'after_cache_reopen')),
    'Actual native read/cache-reopen operation receipts incomplete');
  const once = (method, phase) => {
    const calls = observer.calls.filter(c => c.method === method && c.phase === phase);
    need(calls.length === 1, 'Original ' + method + '/' + phase + ' must execute once');
    return calls[0];
  };
  const open = once('openPinnedTimeline', 'entered'), persisted = once('persistPinnedState', 'entered');
  const flushed = once('persistPinnedState', 'fulfilled'), returned = once('openPinnedTimeline', 'fulfilled');
  const completed = once('openPinnedMessages', 'fulfilled');
  need(observer.bindings.persistPinnedState?.available && persisted.sameAbilityContext && persisted.samePresenterRepository &&
    persisted.presenterId === open.presenterId && persisted.repositoryId === open.repositoryId &&
    flushed.callId === persisted.callId && returned.callId === open.callId &&
    open.sequence < persisted.sequence && persisted.sequence < flushed.sequence && flushed.sequence < returned.sequence &&
    returned.sequence < completed.sequence, 'Original same-repository initialization/completion chain incomplete');
  const validRows = rows => Array.isArray(rows) && rows.length > 0 && rows.every(row => row &&
    Object.keys(row).length === 3 && ['eventId', 'sender', 'body'].every(key => typeof row[key] === 'string'));
  need(validRows(persisted.messages) && validRows(returned.resolvedMessages) && validRows(after.rows) &&
    typeof after.rawValue === 'string', 'Original initialized/returned/native-readback rows unavailable');
  const serial = rows => JSON.stringify(rows.map(row => [row.eventId, row.sender, row.body]));
  need(serial(persisted.messages) === serial(returned.resolvedMessages) && serial(returned.resolvedMessages) === serial(after.rows) &&
    serial(after.rows) === serial(completed.state.pinnedMessages) &&
    JSON.stringify(JSON.parse(after.rawValue)) === JSON.stringify(after.rows), 'Native reopened contents differ from original persistence/return/presenter values');
}
async function runCase(args) {
  const result = { observed: {}, invariantChecks: [], evidence: [], observationLevel: 'native_candidate_ui',
    integrationBoundary: { appEntryExecuted: false, externalServicesExecuted: false,
      boundary: 'Original page/presenter/repository and native Preferences; no Matrix server/network asserted' } };
  try {
    const spec = args.caseSpec, native = args.native || args.context?.native;
    need(args.taskId === '17_pinned_messages' && spec.key === 'open_loading', 'Unsupported Task17 loading case');
    const raw = await native.runTask17LoadingUI(spec);
    result.evidence.push({ nativePageTransition: raw });
    for (const f of raw.frames || []) args.trace?.('task17_loading_' + f.label, f);
    need(raw.taskId === args.taskId && raw.caseId === spec.caseId && raw.traceDigest === spec.traceDigest &&
      /^[a-f0-9]{64}$/.test(raw.traceDigest) && raw.entryExecuted && raw.eventExecuted && raw.parentReturnExecuted &&
      raw.readiness?.ready && !raw.failure, 'Native loading transition incomplete: ' + JSON.stringify(raw.failure || {}));
    need(raw.binding?.importCompleted && raw.binding.phase === 'after_original_room_ready_before_open' && raw.binding.productionModuleUrl ===
      '@bundle:' + native.bundleName + '/entry/ets/features/PinnedMessagesFeature', 'Original app module binding missing');
    need([feature, page].every(path => raw.productionSources?.some(s => s.path === path && /^[a-f0-9]{64}$/.test(s.sha256))), 'Production provenance incomplete');
    const before = raw.frames.find(f => f.label === 'before_event'), settled = raw.frames.find(f => f.label === 'after_event_settled_or_bounded');
    const back = raw.frames.find(f => f.label === 'after_parent_return');
    need(before && settled && back && before.sequence < settled.sequence && settled.sequence < back.sequence, 'Ordered original-page checkpoints missing');
    const windowValid = w => w?.focused && w.hostVerified && w.bundleName === native.bundleName &&
      Number.isInteger(w.stageMainWindowId) && w.stageMainWindowId === w.lastWindowId && w.lastWindowId === before.windowIdentity.lastWindowId &&
      w.ability?.name === 'EntryAbility' && w.ability.moduleName === 'entry' && ['pages/Index', 'pages/Index.ets'].includes(w.routeName);
    for (const f of [before, settled, back]) need(f.sessionId === raw.sessionId && f.bundleName === native.bundleName && windowValid(f.windowIdentity), 'Original window/page lifetime changed');
    const control = (f, name) => f.controls.find(c => c.name === name);
    const visible = (f, name) => control(f, name)?.present && control(f, name)?.visible;
    need(visible(before, 'room') && visible(before, 'banner') && visible(before, 'open') && control(before, 'open').enabled &&
      !['back', 'loading', 'empty', 'filled', 'failed'].some(name => visible(before, name)) &&
      before.observer?.presenterCount === 0 && before.observer.calls.length === 0, 'Canonical actual room/list-closed given not established');
    const clicked = (target, low, high) => raw.actions.filter(a => a.kind === 'click' && a.target === target && a.executed &&
      a.sessionId === raw.sessionId && a.sequence > low && a.sequence < high).length === 1;
    need(clicked('open', before.sequence, settled.sequence) && clicked('back', settled.sequence, back.sequence), 'Real Open/Back receipts missing');
    const observer = raw.observer;
    need(observer?.presenterCount === 1 && observer.repositoryCount === 1 && observer.singlePresenterCallChainObserved &&
      ['openPinnedMessages', 'openPinnedTimeline'].every(method => observer.bindings[method]?.available) &&
      observer.calls.filter(c => c.method === 'openPinnedMessages' && c.phase === 'entered').length === 1 &&
      observer.calls.filter(c => c.method === 'openPinnedTimeline' && c.phase === 'entered' && c.samePresenterRepository && c.sameAbilityContext).length === 1,
      'Original receiver/repository call chain incomplete');
    verifyNativeReadback(raw, observer, before, settled, back);
    await args.load(feature);
    result.integrationBoundary.appEntryExecuted = true;
    result.integrationBoundary.nativePreferencesExecuted = true;
    result.integrationBoundary.nativeIoProof = 'absent key -> original persist/return -> native cache eviction/reopen content equality';
    const loading = raw.loadingFrames?.frames.find(f => windowValid(f.windowIdentity) &&
      ['pages/Index', 'pages/Index.ets'].includes(String(f.route?.path || '') + String(f.route?.name || '')) &&
      f.observer?.presenterCount === 1 && f.observer.repositoryCount === 1 && f.observer.singlePresenterCallChainObserved &&
      f.observer.currentPresenterState?.listState === 'loading' && visibleNode(f, 'pinned_messages_loading') && visibleNode(f, 'pinned_messages_back'));
    if (!loading) {
      result.unsupported = 'Original Loading call transition observed, but no qualifying natural same-page loading frame; do not substitute settled UI or claim pending native I/O.';
      result.evidence.push({ loadingSampling: raw.loadingFrames, originalCalls: observer.calls });
      return result;
    }
    result.observed = { screen: 'pinned_messages', listState: loading.observer.currentPresenterState.listState, effects: ['open_pinned_timeline'] };
    result.invariantChecks.push({ description: 'the room timeline remains the navigation parent',
      passed: visible(back, 'room') && visible(back, 'banner') && visible(back, 'open') && !visible(back, 'back') &&
        control(back, 'room').text === control(before, 'room').text && visible(before, 'focus') && visible(back, 'focus') &&
        control(back, 'focus').text === control(before, 'focus').text,
      observed: { beforeRoom: before, naturalLoadingFrame: loading, physicalBackResult: back,
        scope: 'Actual Back returns to original room screen in same live page; no separate router-stack claim' } });
    result.nativeUI = { observed: true, transitionObserved: true, samePresenterInstance: true, productionSources: raw.productionSources };
  } catch (error) { result.unsupported = String(error.message || error); }
  return result;
}
module.exports = { runCase };
