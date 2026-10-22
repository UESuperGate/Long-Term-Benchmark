// Native lifecycle/window boundary for Task17. Both the parent timeline and the
// pushed pinned-messages page are legitimate routes of the same candidate.
export function createTask17OwnerLaunchController(ports, bundleName) {
  const events = [];
  let ability, stage, foreground = false, destroyed = false, lifecycleId;
  let registered = false, disposed = false, lifecycleError, lastReady, lastNativeWindow;
  const identity = value => value && value.context && value.context.abilityInfo;
  const matches = value => {
    const info = identity(value);
    return info && info.bundleName === bundleName && info.name === 'EntryAbility' && info.moduleName === 'entry';
  };
  const routeName = route => String(route?.path || '') + String(route?.name || '');
  const supportedRoute = value => ['pages/Index', 'pages/Index.ets',
    'pages/PinnedMessages', 'pages/PinnedMessages.ets'].includes(value);
  const record = (method, value) => events.push({ method, at: Date.now(), identity: identity(value) });
  const monitor = {
    abilityName: 'EntryAbility', moduleName: 'entry',
    onAbilityCreate(value) {
      if (!matches(value)) return;
      if (ability && ability !== value) lifecycleError = 'Multiple candidate ability instances';
      ability = value;
      record('abilityCreate', value);
    },
    onAbilityForeground(value) {
      if (matches(value)) {
        foreground = true;
        record('abilityForeground', value);
      }
    },
    onAbilityBackground(value) {
      if (matches(value)) {
        foreground = false;
        record('abilityBackground', value);
      }
    },
    onAbilityDestroy(value) {
      if (matches(value)) {
        destroyed = true;
        foreground = false;
        record('abilityDestroy', value);
      }
    }
  };
  const lifecycle = {
    onAbilityCreate() {}, onAbilityForeground() {}, onAbilityBackground() {}, onAbilityContinue() {},
    onWindowStageActive() {}, onWindowStageInactive() {},
    onWindowStageCreate(value, createdStage) {
      if (!matches(value)) return;
      if (stage && stage !== createdStage) lifecycleError = 'Multiple candidate main-window stages';
      stage = createdStage;
      record('windowStageCreate', value);
    },
    onWindowStageDestroy(value) {
      if (matches(value)) {
        stage = undefined;
        destroyed = true;
        record('windowStageDestroy', value);
      }
    },
    onAbilityDestroy(value) {
      if (matches(value)) destroyed = true;
    }
  };
  async function currentWindow(driver) {
    if (disposed || destroyed || lifecycleError) throw new Error(lifecycleError || 'Candidate ability disposed/destroyed');
    if (!ability || !foreground) throw new Error('Original create/foreground callbacks not yet observed');
    if (!matches(await ports.delegator.getCurrentTopAbility())) throw new Error('Candidate is not the current top ability');
    if (!stage) throw new Error('Original candidate WindowStage not yet observed');
    const main = await stage.getMainWindow();
    const mainProperties = main.getWindowProperties();
    const last = await ports.getLastWindow(ability.context);
    const properties = last.getWindowProperties();
    if (!Number.isInteger(mainProperties.id) || mainProperties.id < 0 || properties.id !== mainProperties.id) {
      throw new Error('Candidate last window differs from observed Stage main window');
    }
    const uiContext = last.getUIContext();
    if (!uiContext || !matches({ context: uiContext.getHostContext() })) {
      throw new Error('Candidate main-window host context mismatch');
    }
    const route = uiContext.getRouter().getState();
    const activeRoute = routeName(route);
    if (!supportedRoute(activeRoute)) throw new Error('Unexpected Task17 candidate route: ' + activeRoute);
    const nativeWindow = await driver.findWindow({ bundleName, focused: true });
    if (!nativeWindow || await nativeWindow.getBundleName() !== bundleName || !await nativeWindow.isFocused()) {
      throw new Error('UiTest window identity/focus mismatch');
    }
    const bounds = await nativeWindow.getBounds();
    if (!bounds || !['left', 'top', 'right', 'bottom'].every(key => Number.isFinite(bounds[key])) ||
        bounds.right <= bounds.left || bounds.bottom <= bounds.top) {
      throw new Error('Candidate main window has invalid bounds');
    }
    for (const rect of [properties.windowRect, mainProperties.windowRect]) {
      if (!rect || rect.left !== bounds.left || rect.top !== bounds.top ||
          rect.width !== bounds.right - bounds.left || rect.height !== bounds.bottom - bounds.top) {
        throw new Error('UiTest geometry differs from actual Stage main window');
      }
    }
    lastNativeWindow = last;
    lastReady = { ability: identity(ability), stageMainWindowId: mainProperties.id,
      lastWindowId: properties.id, bounds, focused: true, hostVerified: true,
      bundleName, route, routeName: activeRoute, checkedAt: Date.now() };
    return lastReady;
  }
  return {
    async start() {
      if (registered || disposed) throw new Error('Task17 launch controller cannot be reused');
      lifecycleId = ports.applicationContext.on('abilityLifecycle', lifecycle);
      if (!Number.isInteger(lifecycleId)) throw new Error('Application lifecycle registration returned no ID');
      await ports.delegator.addAbilityMonitor(monitor);
      registered = true;
      record('startRequested');
      await ports.delegator.startAbility({ bundleName, abilityName: 'EntryAbility', moduleName: 'entry' });
      record('startReturned');
    },
    async restart(prepare) {
      if (!registered || disposed || !ability) throw new Error('Task17 initial ability is unavailable for restart');
      record('restartStopRequested', ability);
      await ability.context.terminateSelf();
      for (let attempt = 0; attempt < 80 && !destroyed; attempt++) {
        await new Promise(resolve => setTimeout(resolve, 100));
      }
      if (!destroyed) throw new Error('Task17 initial ability did not terminate');
      ability = undefined;
      stage = undefined;
      foreground = false;
      destroyed = false;
      lifecycleError = undefined;
      lastReady = undefined;
      lastNativeWindow = undefined;
      await prepare();
      record('restartStartRequested');
      await ports.delegator.startAbility({ bundleName, abilityName: 'EntryAbility', moduleName: 'entry' });
      record('restartStartReturned');
    },
    check(driver) { return currentWindow(driver); },
    current() {
      if (disposed || destroyed || !foreground || lifecycleError || !lastReady || !lastNativeWindow) {
        throw new Error('Original page lifetime unavailable');
      }
      const properties = lastNativeWindow.getWindowProperties();
      const uiContext = lastNativeWindow.getUIContext();
      if (properties.id !== lastReady.lastWindowId || !matches({ context: uiContext.getHostContext() }) ||
          !supportedRoute(routeName(uiContext.getRouter().getState()))) {
        throw new Error('Original frame context/window changed');
      }
      return { abilityContext: ability.context, uiContext, identity: lastReady };
    },
    read() {
      return { events: events.slice(), created: !!ability, foreground, stageObserved: !!stage,
        destroyed, lifecycleError, lastReady };
    },
    async dispose() {
      if (disposed) return;
      disposed = true;
      try {
        if (registered) await ports.delegator.removeAbilityMonitor(monitor);
      } finally {
        if (Number.isInteger(lifecycleId)) await ports.applicationContext.off('abilityLifecycle', lifecycleId);
      }
    }
  };
}
