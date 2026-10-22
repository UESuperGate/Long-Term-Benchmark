const copy = value => value === undefined ? undefined : JSON.parse(JSON.stringify(value));
const requireObserved = (value, message) => { if (!value) throw new Error(message); };

export function effectiveHighOverhead(state) {
  const meta = state.view.metadata;
  const option = state.view.plan.options.find(value => value.preset === 'high');
  const codec = state.estimatorSpecs?.find(value => value.preset === 'high');
  requireObserved(meta && option && codec && Number.isFinite(codec.videoBitrateBps) &&
    Number.isFinite(codec.audioBitrateBps) && meta.durationMs > 0, 'Actual codec/metadata overhead inputs unavailable');
  const scale = Math.min(1, codec.maxLongEdge / Math.max(meta.width, meta.height));
  const bytes = (Math.round(codec.videoBitrateBps * scale * scale) + codec.audioBitrateBps) * meta.durationMs / 8000;
  requireObserved(bytes > 0, 'Actual codec payload size unavailable');
  return option.estimatedBytes / Math.min(meta.bytesKnown ? meta.bytes : bytes, bytes);
}

export async function runTask10RepositoryCase(args, session, observer, ports, record) {
  const spec = args.caseSpec;
  const result = { observed: {}, invariantChecks: [], evidence: [],
    observationLevel: 'actual_original_arkui_and_repository_production_runtime',
    limitations: ['Only picker/HTTP delivery and native preference givens are controlled; all production decisions and user UI events are original.'] };
  const selectors = {
    caption: [{ id: 'attachment_caption' }, { type: 'TextInput' }],
    send: [{ id: 'attachment_send' }, { type: 'Button', text: 'Send' }],
    cancel: [{ id: 'attachment_cancel' }],
    quality: [{ id: 'video_quality_button' }, { type: 'Button', text: 'Change' }],
    dismiss: [{ id: 'video_quality_cancel' }],
    high: [{ type: 'Text', text: 'High' }],
    optimization: [{ id: 'image_optimization_toggle' }],
    modal: [{ type: 'AlertDialog' }, { type: 'CustomDialog' }, { type: 'Dialog' }]
  };
  const wait = async predicate => {
    for (let index = 0; index < 200; index++) {
      const state = observer.read();
      if (predicate(state)) return state;
      await session.delay(25);
    }
    throw new Error('Actual production receiver did not reach required input/completion boundary');
  };
  const frame = async label => {
    for (let attempt = 0; attempt < 5; attempt++) {
      const value = await session.observeBracketed(label, selectors, () => observer.read());
      if (JSON.stringify(value.stateBefore.view) !== JSON.stringify(value.stateAfter.view)) {
        await session.delay(25); continue;
      }
      const observed = { ...value, state: value.stateAfter };
      args.trace(label, observed);
      return observed;
    }
    throw new Error('Original production state changed across UI acquisition');
  };
  const action = (kind, control, value) => session.action(kind, control.actionAncestor || control, value);
  const visible = control => {
    if (control.present === false && control.inspectorMatches === 0) return false;
    requireObserved(typeof control.visible === 'boolean', 'Actual UI visibility unavailable');
    return control.visible;
  };
  const invariant = (passed, actual) => {
    requireObserved(spec.invariants.length === 1, 'Canonical invariant cardinality changed');
    result.invariantChecks.push({ description: spec.invariants[0], passed: Boolean(passed), observed: copy(actual) });
  };
  await wait(state => state.available && state.instanceCount === 1 && state.requests.length === 1);
  const heldMetadata = ['estimate_video_presets', 'choose_best_preset', 'block_when_all_oversized'].includes(spec.key);
  if (heldMetadata) await wait(state => state.metadataPending);
  else if (!['async_loading', 'limit_fallback'].includes(spec.key)) await wait(state => state.view.metadataStatus === 'loaded');
  const before = await frame('before:event');
  const current = before.state.view;
  requireObserved(visible(before.controls.caption) && visible(before.controls.send), 'Real common preview inputs unavailable');
  record({ method: 'Task10.givenEstablished', roleIndependent: true, key: spec.key,
    actual: current, externalAttachment: observer.attachment, request: before.state.requests });
  let after;
  if (spec.key === 'async_loading') {
    requireObserved(current.metadataStatus === 'loading' && current.limit.status === 'loading' &&
      before.state.requests.some(request => !request.completed), 'Loading given was not held at real SDK response');
    await action('input', before.controls.caption, 'while loading');
    await wait(state => state.view.caption === 'while loading');
    await ports.dismissKeyboard();
    await session.delay(150);
    const edited = await frame('caption-edited-during-loading');
    await action('click', edited.controls.cancel);
    await wait(state => state.view.previewVisible === false);
    after = await frame('after:event');
    result.observed = { limitState: current.limit.status, estimationState: current.metadataStatus,
      previewUsable: edited.state.view.caption === 'while loading' && after.state.view.previewVisible === false,
      sendState: current.sendState };
    invariant(result.observed.previewUsable && edited.state.requests.some(request => !request.completed),
      { edited: edited.state.view, cancelled: after.state.view, pending: edited.state.requests });
  } else if (spec.key === 'limit_fallback') {
    requireObserved(before.state.requests.some(request => !request.completed), 'Real failed-request given was not held');
    observer.releaseLimit();
    await wait(state => state.view.metadataStatus === 'loaded');
    after = await frame('after:event');
    const limit = after.state.view.limit;
    result.observed = { limitState: after.state.requests.every(request => request.completed) &&
      limit.maxUploadSize > 0 ? 'success' : limit.status, maxUploadSize: limit.maxUploadSize, fallbackUsed: limit.usedFallback };
    invariant(limit.maxUploadSize === 100 * 1024 * 1024 && limit.usedFallback,
      { rawProductionLimit: limit, originalHttpFailureDelivered: after.state.requests });
  } else if (spec.key === 'image_optimization') {
    requireObserved(current.metadata.mediaType === 'image' && current.optimizeImages === true, 'Image input given unavailable');
    await action('click', before.controls.optimization);
    await wait(state => state.view.optimizeImages === false);
    const changed = await frame('optimization-changed');
    await action('click', changed.controls.send);
    await wait(state => state.calls.some(call => call.owner === 'gateway' && call.method === 'sendAsync'));
    after = await frame('after:event');
    const send = after.state.calls.find(call => call.owner === 'gateway' && call.method === 'sendAsync');
    result.observed = { optimizeImages: changed.state.view.optimizeImages,
      videoEstimationState: changed.state.view.metadata.mediaType === 'image' && changed.state.view.plan.options.length === 0 ?
        'uninitialized' : changed.state.view.metadataStatus,
      preprocessConfig: { compressImages: send.request.quality.optimizeImages } };
    invariant(changed.state.view.metadata.mediaType === 'image' && changed.state.view.metadata.durationMs === 0 &&
      changed.state.view.plan.options.length === 0, { image: changed.state.view.metadata, options: changed.state.view.plan.options,
        actualSenderQualityInput: send.request.quality });
  } else if (spec.key === 'estimate_video_presets') {
    observer.releaseMetadata();
    await wait(state => state.view.metadataStatus === 'loaded');
    await action('click', before.controls.quality);
    await wait(state => state.view.selectorOpen);
    after = await frame('after:event');
    const sizes = {}, canUpload = {};
    for (const option of after.state.view.plan.options) { sizes[option.preset] = option.estimatedBytes; canUpload[option.preset] = option.canUpload; }
    result.observed = { sizes, canUpload, safetyOverhead: effectiveHighOverhead(after.state) };
    const inclusive = observer.inclusiveComparison();
    invariant(inclusive.option.canUpload === true && inclusive.option.estimatedBytes === inclusive.limit, inclusive);
  } else if (spec.key === 'choose_best_preset') {
    observer.releaseMetadata();
    await wait(state => state.view.metadataStatus === 'loaded');
    after = await frame('after:event');
    const options = after.state.view.plan.options;
    result.observed = { selectedPreset: after.state.view.plan.selectedPreset,
      selectionState: after.state.view.plan.status === 'loaded' ? 'success' : after.state.view.plan.status };
    invariant(!options.find(option => option.preset === 'high').canUpload &&
      options.find(option => option.preset === result.observed.selectedPreset).canUpload,
      { externalHighDefault: true, plan: after.state.view.plan });
  } else if (spec.key === 'dismiss_preserves_selection' || spec.key === 'reject_oversized_preset') {
    requireObserved(current.plan.selectedPreset === 'standard' && current.selectorOpen === false, 'Standard-selection given not reached');
    await action('click', before.controls.quality);
    await wait(state => state.view.selectorOpen);
    const highLabel = observer.read().view.plan.options.find(option => option.preset === 'high').label;
    selectors.high = [{ type: 'Text', text: highLabel }];
    const opened = await frame('selector-opened');
    if (spec.key === 'dismiss_preserves_selection') {
      await action('click', opened.controls.dismiss);
      await wait(state => state.view.selectorOpen === false);
    } else {
      requireObserved(opened.state.view.plan.options.find(option => option.preset === 'high').canUpload === false,
        'Oversized high preset given unavailable');
      requireObserved(visible(opened.controls.high), 'Production-labelled oversized preset is not visible');
      await ports.globalTap(opened.controls.high.bounds);
      if (opened.controls.high.enabled === true) await wait(state => state.calls.some(call => call.owner === 'presenter' &&
        call.method === 'chooseQuality' && call.args[0] === 'high'));
    }
    after = await frame('after:event');
    result.observed = { selectedPreset: after.state.view.plan.selectedPreset, selectorOpen: after.state.view.selectorOpen };
    if (spec.key === 'reject_oversized_preset') result.observed.sendable = after.controls.send.enabled;
    invariant(after.state.view.plan.selectedPreset === current.plan.selectedPreset,
      { before: current.plan.selectedPreset, after: after.state.view.plan.selectedPreset,
        actualUiCall: after.state.calls.filter(call => ['chooseQuality', 'dismissQualitySelector'].includes(call.method)) });
  } else if (spec.key === 'block_when_all_oversized') {
    observer.releaseMetadata();
    await wait(state => state.view.metadataStatus === 'loaded');
    const calculated = await frame('estimations-completed-before-global-tap');
    const blockedState = calculated.state.view;
    requireObserved(blockedState.plan.options.length === 3 && blockedState.plan.options.every(option => !option.canUpload),
      'All-oversized given was not calculated by production');
    const modalVisible = visible(calculated.controls.modal);
    const callsBefore = calculated.state.calls.filter(call => call.owner === 'gateway' && call.method === 'sendAsync').length;
    await ports.globalTap(calculated.controls.send.bounds);
    await session.delay(100);
    after = await frame('after:event');
    const callsAfter = after.state.calls.filter(call => call.owner === 'gateway' && call.method === 'sendAsync').length;
    result.observed = { fileTooLargeError: blockedState.plan.availability === 'exceedsLimit' && blockedState.statusTone === 'error',
      selectedPreset: blockedState.plan.selectedPreset,
      sendBlockedByModal: modalVisible && calculated.controls.send.enabled === true && visible(after.controls.modal) && callsAfter === callsBefore };
    invariant(after.state.view.plan.options.every(option => !option.canUpload) && after.state.view.plan.selectedPreset === null,
      { plan: after.state.view.plan, modalVisible, underlyingSendEnabled: calculated.controls.send.enabled, callsBefore, callsAfter });
  } else if (spec.key === 'background_failure_cleanup') {
    await action('input', before.controls.caption, spec.given.caption);
    await wait(state => state.view.caption === spec.given.caption);
    await ports.dismissKeyboard();
    await session.delay(150);
    const captioned = await frame('prefix:caption-and-quality');
    await action('click', captioned.controls.send);
    await wait(state => state.calls.some(call => call.method === 'sendAsync_completed'));
    after = await frame('after:event');
    result.unsupported = 'Canonical pre-event prepared media is not established by this production prefix; no artifact or preprocessing is fabricated.';
    result.evidence.push({ label: 'actual_send_prefix_without_prepared_given', data: after.state });
  } else throw new Error('Unbound canonical case');
  return result;
}
