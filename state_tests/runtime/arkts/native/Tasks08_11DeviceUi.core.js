// Device transport only. The injectable OS ports make lifecycle guards unit
// testable; the device entry supplies native APIs, never business/UI substitutes.
export function createDeviceUiAugment(ports, config, observerFactory) {
  const required = ['bundleName', 'abilityName', 'moduleName', 'entryRoute'];
  for (const key of required) if (typeof config[key] !== 'string' || !config[key]) throw new Error('Missing device UI configuration: ' + key);
  if (!Array.isArray(config.allowedRoutes) || !config.allowedRoutes.includes(config.entryRoute)) throw new Error('Source-owned route allowlist is required');
  if (typeof observerFactory !== 'function') throw new Error('Same-module observer factory is required');
  const timeoutMs = config.timeoutMs === undefined ? 10000 : config.timeoutMs;
  if (!Number.isFinite(timeoutMs) || timeoutMs <= 0 || timeoutMs > 30000) throw new Error('Invalid UI startup timeout');
  let active = false;
  const clone = value => value === undefined ? undefined : JSON.parse(JSON.stringify(value));
  const identity = ability => ability && ability.context && ability.context.abilityInfo;
  const matches = ability => {
    const info = identity(ability);
    return info && info.bundleName === config.bundleName && info.name === config.abilityName && info.moduleName === config.moduleName;
  };
  const rectValid = rect => rect && ['left', 'top', 'right', 'bottom'].every(key => Number.isFinite(rect[key])) &&
    rect.right > rect.left && rect.bottom > rect.top;
  const intersects = (rect, viewport) => rectValid(rect) && rectValid(viewport) &&
    Math.min(rect.right, viewport.right) > Math.max(rect.left, viewport.left) &&
    Math.min(rect.bottom, viewport.bottom) > Math.max(rect.top, viewport.top);

  return async function augment(bridge) {
    if (active || bridge.deviceUi) throw new Error('A device UI case is already active; use one cold process per case');
    if (bridge.roomUpgrade) throw new Error('Observer already installed; device augmentation owns original-module binding');
    const scoredBinding = config.originalModuleImportMode === 'after-page-ready';
    const caseParts = String(bridge.caseId || '').split(':');
    const canonicalCaseId = caseParts[caseParts.length - 1];
    if (scoredBinding && (!['ru_state_005_room_list_tombstone_preview', 'ru_state_007_predecessor_banner'].includes(canonicalCaseId) ||
        caseParts.length > 1 && (caseParts.length !== 3 || caseParts[0] !== '11_room_upgrade_navigation')))
      throw new Error('after-page-ready is only bound for task11 canonical cases005/007; other cases remain unsupported');
    active = true;
    const delegator = ports.getDelegator();
    const original = { ui: bridge.ui, dispose: bridge.dispose, setObservationRecorder: bridge.setObservationRecorder };
    const evidence = [];
    const pending = [];
    let recorder;
    let observer;
    let registered = false;
    let disposed = false;
    let created;
    let foreground = false;
    let destroyed = false;
    let lifecycleError;
    let driver;
    let lastWindowEvidence;
    let applicationContext;
    let lifecycleId;
    let candidateStage;
    const record = data => {
      const event = clone({ caseId: bridge.caseId, backend: 'device_uitest', capturedAt: Date.now(), ...data });
      evidence.push(event);
      if (recorder) recorder(event);
      else pending.push(event);
    };
    const monitor = {
      abilityName: config.abilityName, moduleName: config.moduleName,
      onAbilityCreate(ability) {
        if (!matches(ability)) return;
        if (created && created !== ability) lifecycleError = 'Multiple candidate ability instances were created';
        created = ability;
        record({ method: 'abilityCreate', identity: identity(ability) });
      },
      onWindowStageCreate(ability) {
        if (matches(ability)) record({ method: 'windowStageCreate', identity: identity(ability) });
      },
      onAbilityForeground(ability) {
        if (!matches(ability)) return;
        foreground = true;
        record({ method: 'abilityForeground', identity: identity(ability) });
      },
      onAbilityBackground(ability) { if (matches(ability)) foreground = false; },
      onAbilityDestroy(ability) {
        if (matches(ability)) { destroyed = true; foreground = false; record({ method: 'abilityDestroy' }); }
      }
    };
    const lifecycle = {
      onAbilityCreate() {}, onAbilityForeground() {}, onAbilityBackground() {}, onAbilityContinue() {},
      onWindowStageActive() {}, onWindowStageInactive() {},
      onWindowStageCreate(ability, stage) {
        if (!matches(ability)) return;
        if (candidateStage && candidateStage !== stage) lifecycleError = 'Multiple candidate window stages were created';
        candidateStage = stage;
        record({ method: 'candidateStageCreated', identity: identity(ability), source: 'ApplicationContext.abilityLifecycle' });
      },
      onWindowStageDestroy(ability) { if (matches(ability)) { candidateStage = undefined; destroyed = true; } },
      onAbilityDestroy(ability) { if (matches(ability)) { destroyed = true; foreground = false; } }
    };
    const release = async () => {
      if (disposed) return;
      disposed = true;
      try {
        try { if (registered) await delegator.removeAbilityMonitor(monitor); }
        finally { if (lifecycleId !== undefined) await applicationContext.off('abilityLifecycle', lifecycleId); }
      }
      finally {
        try { if (observer) observer.dispose(); }
        finally {
          bridge.ui = original.ui;
          bridge.setObservationRecorder = original.setObservationRecorder;
          delete bridge.roomUpgrade;
          recorder = undefined;
          active = false;
        }
      }
    };
    bridge.deviceUi = { evidence, release, config: clone(config) };
    bridge.setObservationRecorder = function(callback) {
      if (typeof original.setObservationRecorder === 'function') original.setObservationRecorder.call(bridge, callback);
      recorder = callback;
      if (recorder) while (pending.length) recorder(pending.shift());
    };
    try {
      const deferredBinding = scoredBinding || config.originalModuleImportMode === 'after-page-ready-diagnostic';
      const bindObserver = async pageReadiness => {
        observer = await observerFactory(pageReadiness);
        if (!observer || typeof observer.read !== 'function' || typeof observer.dispose !== 'function') throw new Error('Invalid original-module observer');
        bridge.roomUpgrade = observer;
        if (observer.binding) {
          const diagnostic = { caseId: bridge.caseId, method: 'originalModuleBound', ...observer.binding };
          record(diagnostic);
          if (ports.emitDiagnostic) ports.emitDiagnostic(diagnostic);
        }
        record({ method: observer.unavailableReason ? 'observerUnavailable' : 'observerInstalled',
          beforeAbilityStart: !deferredBinding, reason: observer.unavailableReason });
      };
      if (!deferredBinding) await bindObserver();
      applicationContext = ports.getApplicationContext();
      lifecycleId = applicationContext.on('abilityLifecycle', lifecycle);
      if (!Number.isInteger(lifecycleId)) throw new Error('Application lifecycle registration returned no callback ID');
      await delegator.addAbilityMonitor(monitor);
      registered = true;
      record({ method: 'abilityStartRequested', identity: { bundleName: config.bundleName, name: config.abilityName, moduleName: config.moduleName } });
      await delegator.startAbility({ bundleName: config.bundleName, abilityName: config.abilityName, moduleName: config.moduleName });
      driver = ports.createDriver();
      const queryComponents = async id => {
        const result = await driver.findComponents(ports.selectorById(id, config.bundleName));
        if (result === null || result === undefined) return [];
        if (!Array.isArray(result)) throw new Error('Unexpected UiTest findComponents result for ' + id);
        return result;
      };

      const freshContext = async () => {
        if (disposed || destroyed || lifecycleError) throw new Error(lifecycleError || 'Candidate ability is disposed/destroyed');
        if (!created || !foreground) throw new Error('Cold candidate create/foreground callbacks have not been observed');
        if (!matches(await delegator.getCurrentTopAbility())) throw new Error('Candidate ability is not foreground');
        if (!candidateStage || typeof candidateStage.getMainWindow !== 'function') throw new Error('Original candidate WindowStage has not been observed');
        const mainWindow = await candidateStage.getMainWindow();
        const mainProperties = mainWindow.getWindowProperties();
        const nativeWindow = await ports.getLastWindow(created.context);
        const properties = nativeWindow.getWindowProperties();
        // The actual WindowStage establishes main-window identity. Runtime enum
        // exports can differ from declarations; retain them as diagnostics only.
        const windowEvidence = { source: 'window.getLastWindow(monitoredAbility.context)',
          ability: identity(created), properties: { id: properties.id, name: properties.name,
            type: properties.type === undefined ? null : properties.type, typeOf: typeof properties.type, windowRect: properties.windowRect },
          stageMainWindowId: mainProperties.id, mainWindowRect: mainProperties.windowRect,
          sdkMainEnum: { value: ports.mainWindowType === undefined ? null : ports.mainWindowType, typeOf: typeof ports.mainWindowType } };
        const serializedWindow = JSON.stringify(windowEvidence);
        if (serializedWindow !== lastWindowEvidence) {
          record({ method: 'candidateWindow', ...windowEvidence });
          lastWindowEvidence = serializedWindow;
        }
        if (!Number.isInteger(mainProperties.id) || mainProperties.id < 0 || properties.id !== mainProperties.id)
          throw new Error('Top candidate window is not the observed WindowStage main window: ' + JSON.stringify(windowEvidence));
        const uiContext = nativeWindow.getUIContext();
        if (!uiContext || !matches({ context: uiContext.getHostContext() })) throw new Error('UIContext does not belong to the monitored candidate ability');
        return { uiContext, windowEvidence };
      };
      const snapshot = async () => {
        const { uiContext, windowEvidence } = await freshContext();
        let rawTree;
        let route;
        uiContext.runScopedTask(() => { rawTree = ports.getInspectorTree(); route = uiContext.getRouter().getState(); });
        if (typeof rawTree === 'string') rawTree = JSON.parse(rawTree);
        const routeName = route && String(route.path || '') + String(route.name || '');
        const candidateRouteVerified = config.allowedRoutes.includes(routeName);
        const nativeWindow = await driver.findWindow({ bundleName: config.bundleName, focused: true });
        if (!nativeWindow) throw new Error('UiTest candidate window is absent');
        if (await nativeWindow.getBundleName() !== config.bundleName || !await nativeWindow.isFocused())
          throw new Error('UiTest candidate window ownership/focus is unverified');
        const viewport = await nativeWindow.getBounds();
        if (!rectValid(viewport)) throw new Error('UiTest candidate window has invalid bounds');
        for (const rect of [windowEvidence.properties.windowRect, windowEvidence.mainWindowRect]) {
          if (!rect || rect.left !== viewport.left || rect.top !== viewport.top ||
              rect.width !== viewport.right - viewport.left || rect.height !== viewport.bottom - viewport.top)
            throw new Error('UiTest bounds do not match the observed Stage main window: ' + JSON.stringify({ viewport, windowEvidence }));
        }
        const children = rawTree && (rawTree.$children || rawTree.children);
        const completeTree = Array.isArray(children) && children.length > 0;
        // Width/height are measured by UiTest, not guessed from a device preset.
        const tree = { ...(rawTree || {}), width: viewport.right - viewport.left, height: viewport.bottom - viewport.top };
        // Keep the full inspector payload once, under tree (legacy adapters
        // traverse it). Preserve its original dimensions before normalization.
        return { tree, inspectorTreeField: 'tree', inspectorTreeDimensions: rawTree ? { width: rawTree.width, height: rawTree.height } : null,
          viewport, route, routeName, completeTree, candidateRouteVerified, windowEvidence,
          candidatePageVerified: candidateRouteVerified && completeTree,
          geometrySource: 'UiTest.UiWindow.getBounds', uiContext };
      };
      const publicSnapshot = state => {
        const { uiContext, ...data } = state;
        return data;
      };
      const inspect = async (id, state) => {
        const found = await queryComponents(id);
        if (found.length > 1) throw new Error('Ambiguous candidate UI selector: ' + id);
        let raw;
        let inspectorError;
        try { state.uiContext.runScopedTask(() => { raw = ports.getInspectorByKey(id); }); }
        catch (error) { inspectorError = String(error); }
        const inspector = raw ? (typeof raw === 'string' ? JSON.parse(raw) : raw) : null;
        const identifiedInspector = inspector && inspector.$attrs && inspector.$attrs.id === id ? inspector : null;
        if (!found.length) return { id, node: identifiedInspector, inDriverTree: false, inspectorError,
          present: identifiedInspector ? true : inspectorError ? null : false,
          sources: { node: identifiedInspector ? 'ArkUI.getInspectorByKey' : 'UiTest query + keyed inspector' } };
        const component = found[0];
        const actualId = await component.getId();
        if (actualId !== id) throw new Error('UiTest returned a different control ID');
        const bounds = await component.getBounds();
        const content = await component.getText();
        const type = await component.getType();
        const enabled = await component.isEnabled();
        const attrs = { id: actualId, content, text: content, enabled };
        const unavailable = [];
        for (const name of ['visibility', 'opacity']) {
          const value = identifiedInspector ? identifiedInspector.$attrs[name] : undefined;
          if ((name === 'visibility' && typeof value === 'string') || (name === 'opacity' &&
              (typeof value === 'number' || typeof value === 'string' && value.trim() !== '') && Number.isFinite(Number(value)))) attrs[name] = value;
          else unavailable.push(name);
        }
        // UiTest coordinates are screen-relative; normalize to its measured app
        // window for the existing adapter viewport comparison. Raw bounds stay.
        const local = { left: bounds.left - state.viewport.left, top: bounds.top - state.viewport.top,
          right: bounds.right - state.viewport.left, bottom: bounds.bottom - state.viewport.top };
        return { id, present: true, inDriverTree: true, bounds, intersectsViewport: intersects(bounds, state.viewport),
          node: { $type: type, $rect: `[${local.left},${local.top}],[${local.right},${local.bottom}]`, $attrs: attrs },
          inspector: identifiedInspector, inspectorError, unobservedAttributes: unavailable,
          sources: { geometry: 'UiTest.Component.getBounds', text: 'UiTest.Component.getText', enabled: 'UiTest.Component.isEnabled',
            visibility: 'ArkUI.getInspectorByKey (only when present)', opacity: 'ArkUI.getInspectorByKey (only when present)' } };
      };
      const observe = async (ids, anchorId) => {
        const state = await snapshot();
        const inspections = [];
        for (const id of Array.from(new Set([anchorId, ...ids]))) inspections.push(await inspect(id, state));
        const anchor = inspections.find(item => item.id === anchorId);
        const available = state.candidateRouteVerified && anchor.inDriverTree === true && anchor.intersectsViewport === true;
        const controls = ids.map(id => {
          const control = inspections.find(item => item.id === id);
          return { ...control, present: available ? control.present : null };
        });
        const result = { available, anchor, snapshot: publicSnapshot(state), controls,
          reason: available ? '' : 'Verified candidate route and onscreen UiTest anchor are required; presence/geometry do not prove opacity or occlusion' };
        record({ method: 'observe', ...result });
        return result;
      };
      const gesture = async (id, kind) => {
        const before = await snapshot();
        if (!before.candidateRouteVerified) throw new Error('Refusing UI event outside candidate-owned routes');
        const matches = await queryComponents(id);
        if (matches.length !== 1) throw new Error('Click requires exactly one native control: ' + id);
        const component = matches[0];
        const bounds = await component.getBounds();
        const enabled = await component.isEnabled();
        const clickable = await component.isClickable();
        if (!enabled || !clickable || !intersects(bounds, before.viewport)) throw new Error('Native control is disabled, not clickable, or outside the app viewport');
        record({ method: 'beforeUiAction', id, action: kind, enabled, clickable, bounds, route: before.route });
        await component[kind]();
        record({ method: 'afterUiAction', id, action: kind, completed: true,
          snapshot: publicSnapshot(await snapshot()), semanticSuccess: null });
        return true;
      };
      const ui = {
        snapshot: async () => publicSnapshot(await snapshot()),
        inspect: async id => inspect(id, await snapshot()),
        observe,
        click: id => gesture(id, 'click'),
        doubleClick: id => gesture(id, 'doubleClick'),
        async sendEvent(id, action, params) {
          if (action !== 10 || (params && Object.keys(params).length)) throw new Error('Device UI bridge supports only parameterless click action 10');
          return gesture(id, 'click');
        },
        async navigate(url) {
          const current = await snapshot();
          if (url !== config.entryRoute || current.routeName !== config.entryRoute || !current.candidateRouteVerified)
            throw new Error('Device bootstrap must start at the real entry route; no evaluator router push is allowed');
          record({ method: 'navigate', available: true, alreadyMounted: true, snapshot: publicSnapshot(current) });
        }
      };
      const deadline = Date.now() + timeoutMs;
      let ready;
      let lastError;
      while (Date.now() < deadline) {
        try {
          ready = await snapshot();
          if (ready.routeName === config.entryRoute && ready.candidateRouteVerified) break;
          lastError = 'Entry route has not rendered';
          ready = undefined;
        } catch (error) { ready = undefined; lastError = String(error); }
        await ports.delay(50);
      }
      if (!ready) throw new Error('Candidate cold-start/UIContext unavailable: ' + lastError);
      if (deferredBinding) {
        const pageReadiness = await observe(['current_room_id'], 'current_room_id');
        if (!pageReadiness.available || !ready.completeTree) throw new Error('Original candidate page is not ready for diagnostic import or scored binding');
        const diagnostic = { caseId: bridge.caseId, method: 'beforeOriginalModuleImport',
          requestedModuleUrl: config.productionModuleUrl, routeName: ready.routeName,
          windowId: ready.windowEvidence.stageMainWindowId, anchor: pageReadiness.anchor,
          mode: config.originalModuleImportMode,
          reason: 'Opt-in post-load binding; native cache is not directly observable and a cache miss may still be fatal.' };
        record(diagnostic);
        if (ports.emitDiagnostic) ports.emitDiagnostic(diagnostic);
        await bindObserver(pageReadiness);
        // Establish the page receiver through its real room-list control.
        // Canonical givens remain the adapter's responsibility after this setup.
        await ui.click('room_list_tombstoned_room');
        const afterClick = await observe(['current_room_id'], 'current_room_id');
        const state = observer.read();
        const capture = { caseId: bridge.caseId, method: scoredBinding ? 'setupReceiverCapture' : 'diagnosticReceiverCapture',
          action: 'UiTest.Component.click(room_list_tombstoned_room)', state,
          roomBefore: pageReadiness.controls[0].node?.$attrs.content,
          roomAfter: afterClick.controls[0].node?.$attrs.content,
          capturedSelectOldRoom: state.available === true && Array.isArray(state.calls) &&
            state.calls.some(call => call.method === 'selectOldRoom'),
          semanticVerdict: null, canonicalSetupVerified: false };
        record(capture);
        if (ports.emitDiagnostic) ports.emitDiagnostic(capture);
        if (scoredBinding) {
          if (!afterClick.available || state.available !== true || !state.instanceId ||
              !Array.isArray(state.calls) || !state.calls.some(call => call.instanceId === state.instanceId) ||
              typeof state.currentRoomId !== 'string' || capture.roomAfter !== state.currentRoomId)
            throw new Error('Original page receiver and rendered room were not established by real setup click; canonical setup remains unsupported');
          // Preserve the actual observer. The adapter must select/verify its
          // own canonical room, metadata and history before observing the event.
          bridge.roomUpgrade = observer;
        } else {
          // Diagnostic setup is never promoted to a canonical result.
          bridge.roomUpgrade = {
            read: () => ({ available: false, reason: 'Post-load import/physical-click diagnostic only; see diagnosticReceiverCapture. Canonical transition was not executed.' }),
            dispose: () => observer.dispose()
          };
        }
      }
      bridge.ui = ui;
      bridge.capabilities.uiContext = { available: true, origin: 'Observed WindowStage.getMainWindow ID == monitored ability getLastWindow ID -> Window.getUIContext + matching host + focused UiTest bundle/geometry' };
      bridge.capabilities.deviceUI = { available: true, backend: 'UiTest.Component', coldCreateObserved: true,
        visibility: 'Only real inspector attributes; no defaults inferred from accessibility presence' };
      record({ method: 'deviceUiReady', available: true, snapshot: publicSnapshot(ready) });
      bridge.dispose = async function() {
        try { await release(); }
        finally { await original.dispose.call(bridge); }
      };
      return bridge;
    } catch (error) {
      record({ method: 'deviceUiUnavailable', available: false, error: String(error) });
      bridge.capabilities.deviceUI = { available: false, reason: String(error) };
      await release();
      throw error;
    }
  };
}
