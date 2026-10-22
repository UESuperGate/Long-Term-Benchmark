// Evaluator-only bridge. Original app OHM import is deferred until the mounted
// page is positively observed. Never import a relative .ets copy or construct a presenter.
let configured;
let active;
let cancelled = false;

export function configureTasks16To18UI(probe, bundleName, bindingJson, sourceJson, AudioViewPicker,
  importModule = url => import(url)) {
  if (active) throw new Error('Cannot reconfigure an active Tasks16_18 observer');
  const binding = bindingJson === undefined ? null : JSON.parse(bindingJson);
  if (binding && (binding.bundleName !== bundleName || !binding.moduleName || !binding.abilityName ||
    binding.presenterExport !== 'NotificationSettingsPresenter' ||
    (binding.moduleUrl && (!['NotificationSoundFeature', 'NotificationSettingsBase'].includes(binding.feature) ||
      binding.moduleUrl !== `@bundle:${bundleName}/${binding.moduleName}/ets/features/${binding.feature}`)))) {
    throw new Error('Original app module URL is not bound to the candidate manifest');
  }
  configured = { probe, bundleName, binding, importModule, AudioViewPicker, source: JSON.parse(sourceJson) };
}

function observePresenter(Presenter, state) {
  const { instances, calls, restores, contexts } = state;
  const prototype = Presenter && Presenter.prototype;
  if (prototype) {
    for (const method of Object.getOwnPropertyNames(prototype)) {
      const descriptor = Object.getOwnPropertyDescriptor(prototype, method);
      if (method === 'constructor' || !descriptor.configurable || typeof descriptor.value !== 'function') continue;
      Object.defineProperty(prototype, method, { ...descriptor, value: function(...args) {
        if (!instances.includes(this)) instances.push(this);
        const instanceId = instances.indexOf(this) + 1;
        if (method === 'load') contexts[instanceId - 1] = args[0];
        const call = { sequence: calls.length + 1, instanceId, method,
          slot: ['launchSystemPicker', 'showDialog', 'dismissDialog'].includes(method) ? args[0] : undefined,
          enteredAtMs: Date.now() };
        calls.push(call);
        // Preserve original receiver, arguments, throws and returned Promise.
        try {
          const returned = descriptor.value.apply(this, args);
          call.outcome = 'returned';
          return returned;
        } catch (error) { call.outcome = 'threw'; throw error; }
        finally {
          call.returnedAtMs = Date.now();
          // Forward only calls intercepted on the post-mounted original app
          // prototype. Recording must never change the production return/throw.
          if (state.observationRecorder && state.moduleBinding?.importCompleted &&
            configured.source?.path && /^[a-f0-9]{64}$/.test(configured.source.sha256)) {
            try {
              state.observationRecorder({ method: 'Tasks18.originalPage.' + method,
                available: true, bundleName: configured.bundleName, caseId: state.request.caseId,
                productionSource: configured.source, originalModuleUrl: state.moduleBinding.requestedModuleUrl,
                presenterExport: state.moduleBinding.presenterExport, actualCall: { ...call },
                scope: 'Pass-through observation of an actual mounted-page production method; no adapter invocation.' });
            } catch (error) { state.recorderError = String(error); }
          }
        }
      } });
      restores.push(() => Object.defineProperty(prototype, method, descriptor));
    }
  }
}

function contextScope(context) {
  if (!context) return undefined;
  try {
    return { bundleName: context.abilityInfo?.bundleName, abilityName: context.abilityInfo?.name,
      moduleName: context.abilityInfo?.moduleName, filesDir: context.filesDir, preferencesDir: context.preferencesDir,
      cacheDir: context.cacheDir };
  } catch (error) { return { error: String(error) }; }
}

export async function bindTasks16To18OriginalPage(context, readinessJson) {
  const state = active, binding = configured?.binding;
  if (!state || state.cancelled || cancelled || state.request?.taskId !== '18_custom_notification_sounds' ||
    state.request?.key !== 'message_picker_launch' || state.bindingAttempted) throw new Error('Original-page binding unavailable or already attempted');
  const readiness = JSON.parse(readinessJson);
  const visible = node => node?.bounds?.right > node?.bounds?.left && node?.bounds?.bottom > node?.bounds?.top;
  if (!context || readiness.focusedBundle !== configured.bundleName || readiness.completed !== true || readiness.error ||
    !readiness.nodes?.some(node => node.text === 'Notifications' && visible(node)) ||
    !readiness.nodes?.some(node => node.id === 'message_sound_row' && node.enabled && node.clickable && visible(node))) {
    throw new Error('Original module import requires the mounted candidate page and positive controls');
  }
  state.bindingAttempted = true;
  state.pageContext = context;
  state.contextBinding = { origin: 'AbilityDelegator.waitAbilityMonitor().context after mounted-page controls', scope: contextScope(context) };
  if (!binding?.moduleUrl) throw new Error('No original sound presenter module mapping; no copied-class fallback');
  state.moduleBinding = { requestedModuleUrl: binding.moduleUrl, importCompleted: false,
    timing: binding.importTiming, readiness, monitoredContext: state.contextBinding };
  const namespace = await configured.importModule(binding.moduleUrl);
  if (active !== state || state.cancelled || cancelled) throw new Error('Original module binding cancelled during import');
  const Presenter = namespace?.[binding.presenterExport];
  if (typeof Presenter !== 'function' || !Presenter.prototype) throw new Error('Original presenter export unavailable');
  const before = Object.getOwnPropertyDescriptors(Presenter.prototype);
  observePresenter(Presenter, state);
  const after = Object.getOwnPropertyDescriptors(Presenter.prototype);
  const wrappedNames = Object.keys(before).filter(name => name !== 'constructor' && before[name].value !== after[name]?.value);
  if (!wrappedNames.length) throw new Error('Original presenter observer wrapped no methods');
  observePicker(state, configured.AudioViewPicker);
  state.moduleBinding = { ...state.moduleBinding, importCompleted: true, namespaceExports: Object.keys(namespace),
    presenterExport: binding.presenterExport, wrappedNames,
    prototypeDescriptors: Object.fromEntries(Object.entries(before).map(([name, d]) => [name,
      { configurable: d.configurable, writable: d.writable, valueType: typeof d.value }])),
    receiverObserved: false, scope: 'Import/observer installation only; receiver is established exclusively by subsequent physical page events.' };
  return JSON.stringify(state.moduleBinding);
}

function observePicker(state, Picker) {
  const prototype = Picker && Picker.prototype;
  const descriptor = prototype && Object.getOwnPropertyDescriptor(prototype, 'select');
  if (!descriptor || !descriptor.configurable || typeof descriptor.value !== 'function') {
    state.pickerObserver.reason = 'Original native AudioViewPicker.select descriptor is not observable.';
    return;
  }
  try {
    Object.defineProperty(prototype, 'select', { ...descriptor, value: function(...args) {
      const preceding = state.calls[state.calls.length - 1];
      const pickerScope = contextScope(this.context), pageScope = contextScope(state.pageContext);
      const exactContext = state.pageContext !== undefined && this.context === state.pageContext;
      const sameScope = ['bundleName', 'abilityName', 'moduleName', 'filesDir', 'preferencesDir', 'cacheDir'].every(key =>
        typeof pageScope?.[key] === 'string' && pageScope[key].length > 0 && pickerScope?.[key] === pageScope[key]) &&
        pageScope.bundleName === configured.bundleName && pageScope.moduleName === configured.binding?.moduleName &&
        pageScope.abilityName === configured.binding?.abilityName;
      const call = { id: state.pickerCalls.length + 1, api: '@ohos.file.picker.AudioViewPicker.select',
        startedAtMs: Date.now(), presenterCallsBeforeSelect: state.calls.map(item => ({ ...item })),
        argumentCount: args.length, argumentTypes: args.map(arg => typeof arg),
        precedingPresenterCall: preceding, instanceCount: state.instances.length,
        samePageContext: exactContext || sameScope,
        contextEvidence: { origin: state.contextBinding?.origin, exactMonitoredContext: exactContext,
          matchingMonitoredAbilityScope: sameScope, monitored: pageScope, picker: pickerScope,
          observedLoadCall: state.contexts.length > 0 },
        status: 'invoked' };
      state.pickerCalls.push(call);
      let returned;
      try { returned = descriptor.value.apply(this, args); }
      catch (error) { call.status = 'threw'; call.settledAtMs = Date.now(); call.error = String(error); throw error; }
      // Observe settlement without replacing the SDK Promise or waiting for user selection.
      if (returned && typeof returned.then === 'function') {
        call.status = 'pending';
        returned.then(value => {
          call.status = 'resolved';
          call.settledAtMs = Date.now();
          call.result = Array.isArray(value) ? value.slice() : typeof value;
        }, error => { call.status = 'rejected'; call.settledAtMs = Date.now(); call.error = String(error); });
      } else call.status = 'non_promise';
      return returned;
    } });
    state.restores.push(() => Object.defineProperty(prototype, 'select', descriptor));
    state.pickerObserver = { available: true, api: '@ohos.file.picker.AudioViewPicker.select',
      scope: 'Original SDK prototype pass-through; unchanged receiver, arguments, return identity and errors.' };
  } catch (error) { state.pickerObserver.reason = String(error); }
}

export function readTasks16To18Picker() {
  return JSON.stringify(active ? { observer: active.pickerObserver, calls: active.pickerCalls } :
    { observer: { available: false, reason: 'No active native picker observer.' }, calls: [] });
}

export function publishTasks16To18UI(resultJson, stage) {
  if (!active || active.cancelled) return;
  const result = JSON.parse(resultJson);
  const request = active.request;
  if (!request || ['taskId', 'caseId', 'key', 'bundleName'].some(key => result[key] !== request[key])) {
    throw new Error('Progress does not belong to the active Tasks16_18 UI request');
  }
  active.progress = { result, stage, elapsedMs: Date.now() - active.startedAt };
}

export function tasks16To18UICancelled() {
  return cancelled;
}

function pageFixture() {
  if (!active || active.cancelled || cancelled || active.request?.taskId !== '17_pinned_messages' ||
    active.request?.key !== 'view_in_timeline' || !active.fixtureCallbacks) {
    throw new Error('No active task17 actual-AbilityContext fixture');
  }
  return active;
}

export async function prepareTasks16To18Page(context) {
  const state = pageFixture();
  if (!context || state.fixtureStarted) throw new Error('Page fixture requires one original AbilityContext');
  state.fixtureStarted = true;
  // Keep the SDK object itself. Only observation metadata may cross JSON boundaries.
  state.fixtureContext = context;
  await state.fixtureCallbacks.prepare(context);
  if (active !== state || state.cancelled || cancelled) throw new Error('Page fixture was cancelled during preparation');
  state.fixturePrepared = true;
}

export async function finishTasks16To18Page(context) {
  const state = pageFixture();
  if (!state.fixturePrepared || state.fixtureFinished || context !== state.fixtureContext) {
    throw new Error('Page fixture readback requires the same prepared AbilityContext exactly once');
  }
  state.fixtureFinished = true;
  await state.fixtureCallbacks.afterEvent(context);
  if (active !== state || state.cancelled || cancelled) throw new Error('Page fixture was cancelled during readback');
}

export function attachTasks16To18UI(bridge, taskId, key) {
  const supported = taskId === '16_identity_reset' && ['oidc_handle_routes_and_resets', 'cancel_cleans_up'].includes(key) ||
    taskId === '17_pinned_messages' && ['open_loading', 'view_in_timeline'].includes(key) ||
    taskId === '18_custom_notification_sounds' && key === 'message_picker_launch';
  if (!supported) return false;
  if (!configured || typeof configured.probe !== 'function' || !configured.bundleName) {
    throw new Error('ArkTS test entry did not configure the Tasks16_18 UI probe');
  }
  if (active) throw new Error('Tasks16_18 UI observers cannot overlap');
  cancelled = false;
  active = { instances: [], stores: [], calls: [], restores: [], contexts: [], pickerCalls: [],
    pickerObserver: { available: false, reason: 'Awaiting mounted original-page binding.' },
    dispose() { for (const restore of this.restores.reverse()) restore(); } };
  const originalRecorder = bridge.setObservationRecorder;
  if (typeof originalRecorder === 'function') {
    const state = active;
    bridge.setObservationRecorder = function(callback) {
      state.observationRecorder = callback;
      return originalRecorder.call(this, callback);
    };
    state.restores.push(() => { bridge.setObservationRecorder = originalRecorder; });
  }
  bridge.bundleName = configured.bundleName;
  bridge.runTasks16To18UI = async (request, fixtureCallbacks) => {
    if (request.bundleName !== configured.bundleName) throw new Error('UI request targets a different candidate bundle');
    if (active.request) throw new Error('Only one UI request is permitted per original-page observer');
    if (fixtureCallbacks !== undefined && (taskId !== '17_pinned_messages' || key !== 'view_in_timeline' ||
      request.taskId !== taskId || request.key !== key || typeof fixtureCallbacks.prepare !== 'function' ||
      typeof fixtureCallbacks.afterEvent !== 'function')) throw new Error('Unsupported original-page fixture callbacks');
    const state = active;
    state.fixtureCallbacks = fixtureCallbacks;
    active.request = { ...request };
    active.startedAt = Date.now();
    try {
      const result = JSON.parse(await configured.probe(JSON.stringify(request)));
      if (state.recorderError) result.unsupported = 'Original-page production recorder failed: ' + state.recorderError;
      return result;
    }
    finally { state.fixtureCallbacks = undefined; state.fixtureContext = undefined; }
  };
  bridge.getTasks16To18UIProgress = () => active?.progress ?
    JSON.parse(JSON.stringify({ ...active.progress, livePicker: JSON.parse(readTasks16To18Picker()) })) : undefined;
  bridge.cancelTasks16To18UI = () => { cancelled = true; if (active) active.cancelled = true; };
  bridge.disposeTasks16To18UI = () => {
    cancelled = true;
    if (active) {
      active.fixtureCallbacks = undefined;
      active.fixtureContext = undefined;
      active.dispose();
    }
    active = undefined;
    delete bridge.runTasks16To18UI;
    delete bridge.getTasks16To18UIProgress;
    delete bridge.cancelTasks16To18UI;
  };
  return true;
}

export async function readTasks16To18Page(context) {
  const observed = { available: false, source: configured && configured.source,
    instanceCount: active ? active.instances.length : 0, calls: active ? active.calls.slice() : [],
    originalModuleBinding: active?.moduleBinding ? { ...active.moduleBinding, receiverObserved: active.instances.length > 0 } : undefined,
    contextBinding: active?.contextBinding };
  if (!active || active.instances.length !== 1) {
    return JSON.stringify({ ...observed, reason: 'Exactly one original page presenter must be observed; no unrelated instance is selected.' });
  }
  if (context !== active.pageContext) {
    return JSON.stringify({ ...observed, reason: 'Persistence read requires the original monitored AbilityContext used at post-load binding.' });
  }
  const presenter = active.instances[0];
  if (!presenter.snapshot || !presenter.store || typeof presenter.store.load !== 'function') {
    return JSON.stringify({ ...observed, reason: 'This original presenter does not expose the mapped sound snapshot/store API.' });
  }
  if (!active.stores.includes(presenter.store)) active.stores.push(presenter.store);
  const state = { instanceId: 1, storeId: active.stores.indexOf(presenter.store) + 1,
    messagePickerToken: presenter.pendingMessageSoundPickerLaunch,
    callPickerToken: presenter.pendingCallRingtonePickerLaunch,
    messageDialog: presenter.showMessageSoundDialog, callDialog: presenter.showCallRingtoneDialog,
    snapshot: presenter.snapshot, messageError: presenter.messageCopyError, callError: presenter.callCopyError };
  try {
    // This is the real page's repository, not another presenter. Snapshot
    // before awaiting I/O so the checkpoint does not retain mutable aliases.
    const copied = JSON.parse(JSON.stringify(state));
    const persisted = await presenter.store.load(context);
    return JSON.stringify({ ...observed, ...copied, persisted, available: true });
  } catch (error) {
    return JSON.stringify({ ...observed, ...state, reason: 'Same-page persistence read failed: ' + String(error) });
  }
}
