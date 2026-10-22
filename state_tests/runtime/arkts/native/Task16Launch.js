// Native lifecycle/window boundary only; no candidate behavior is replaced.
export function createTask16LaunchController(ports, bundleName) {
  const events = [];
  let ability, stage, foreground = false, destroyed = false, lifecycleId, registered = false, disposed = false;
  let lifecycleError, lastReady;
  const identity = value => value && value.context && value.context.abilityInfo;
  const matches = value => {
    const info = identity(value);
    return info && info.bundleName === bundleName && info.name === 'EntryAbility' && info.moduleName === 'entry';
  };
  const record = (method, value) => events.push({ method, at: Date.now(), identity: identity(value) });
  const monitor = {
    abilityName: 'EntryAbility', moduleName: 'entry',
    onAbilityCreate(value) {
      if (!matches(value)) return;
      if (ability && ability !== value && !destroyed) lifecycleError = 'Multiple candidate ability instances';
      ability = value; destroyed = false; record('abilityCreate', value);
    },
    onAbilityForeground(value) { if (matches(value)) { foreground = true; record('abilityForeground', value); } },
    onAbilityBackground(value) { if (matches(value)) { foreground = false; record('abilityBackground', value); } },
    onAbilityDestroy(value) { if (matches(value)) { destroyed = true; foreground = false; record('abilityDestroy', value); } }
  };
  const lifecycle = {
    onAbilityCreate() {}, onAbilityForeground() {}, onAbilityBackground() {}, onAbilityContinue() {},
    onWindowStageActive() {}, onWindowStageInactive() {},
    onWindowStageCreate(value, createdStage) {
      if (!matches(value)) return;
      if (stage && stage !== createdStage) lifecycleError = 'Multiple candidate main-window stages';
      stage = createdStage; record('windowStageCreate', value);
    },
    onWindowStageDestroy(value) { if (matches(value)) { stage = undefined; destroyed = true; record('windowStageDestroy', value); } },
    onAbilityDestroy(value) { if (matches(value)) destroyed = true; }
  };
  return {
    async start() {
      if (registered || disposed) throw new Error('Task16 launch controller cannot be reused');
      lifecycleId = ports.applicationContext.on('abilityLifecycle', lifecycle);
      if (!Number.isInteger(lifecycleId)) throw new Error('Application lifecycle registration returned no ID');
      await ports.delegator.addAbilityMonitor(monitor);
      registered = true;
      record('startRequested');
      await ports.delegator.startAbility({ bundleName, abilityName: 'EntryAbility', moduleName: 'entry' });
      record('startReturned');
    },
    async check(driver) {
      if (disposed || destroyed || lifecycleError) throw new Error(lifecycleError || 'Candidate ability disposed/destroyed');
      if (!ability || !foreground) throw new Error('Original create/foreground callbacks not yet observed');
      if (!matches(await ports.delegator.getCurrentTopAbility())) throw new Error('Candidate is not the current top ability');
      if (!stage) throw new Error('Original candidate WindowStage not yet observed');
      const main = await stage.getMainWindow();
      const mainProperties = main.getWindowProperties();
      const last = await ports.getLastWindow(ability.context);
      const properties = last.getWindowProperties();
      if (!Number.isInteger(mainProperties.id) || mainProperties.id < 0 || properties.id !== mainProperties.id) {
        throw new Error('Candidate last window differs from observed Stage main window: ' + JSON.stringify({ mainId: mainProperties.id, lastId: properties.id }));
      }
      const uiContext = last.getUIContext();
      if (!uiContext || !matches({ context: uiContext.getHostContext() })) throw new Error('Candidate main-window host context mismatch');
      const route = uiContext.getRouter().getState();
      const routeName = String(route.path || '') + String(route.name || '');
      if (!['pages/Index', 'pages/Index.ets'].includes(routeName)) throw new Error('Original identity-reset page route is not active: ' + routeName);
      const nativeWindow = await driver.findWindow({ bundleName, focused: true });
      if (!nativeWindow) throw new Error('Focused original candidate UiTest window unavailable');
      if (await nativeWindow.getBundleName() !== bundleName || !await nativeWindow.isFocused()) throw new Error('UiTest window identity/focus mismatch');
      const bounds = await nativeWindow.getBounds();
      if (!bounds || !['left', 'top', 'right', 'bottom'].every(key => Number.isFinite(bounds[key])) || bounds.right <= bounds.left || bounds.bottom <= bounds.top) {
        throw new Error('Candidate main window has invalid bounds');
      }
      for (const rect of [properties.windowRect, mainProperties.windowRect]) {
        if (!rect || rect.left !== bounds.left || rect.top !== bounds.top || rect.width !== bounds.right - bounds.left || rect.height !== bounds.bottom - bounds.top) {
          throw new Error('UiTest geometry differs from actual Stage main window');
        }
      }
      lastReady = { ability: identity(ability), stageMainWindowId: mainProperties.id, lastWindowId: properties.id,
        bounds, focused: true, hostVerified: true, bundleName, route, routeName, checkedAt: Date.now() };
      return lastReady;
    },
    read() { return { events: events.slice(), created: !!ability, foreground, stageObserved: !!stage, destroyed, lifecycleError, lastReady }; },
    async dispose(options = {}) {
      if (disposed) return;
      disposed = true;
      try {
        if (options.deferTermination) {
          record('terminationDeferredToExternalUninstall', ability);
        } else if (ability && ability.context && typeof ability.context.terminateSelf === 'function' && !destroyed) {
          record('terminateRequested', ability);
          await ability.context.terminateSelf();
          record('terminateReturned', ability);
          for (let attempt = 0; attempt < 40 && !destroyed; attempt++) await ports.delay(50);
          if (!destroyed) throw new Error('Candidate ability did not report destruction after terminateSelf');
        }
      } finally {
        try { if (registered) await ports.delegator.removeAbilityMonitor(monitor); }
        finally { if (Number.isInteger(lifecycleId)) await ports.applicationContext.off('abilityLifecycle', lifecycleId); }
      }
    }
  };
}

// The classifier and the UI probe must share one original page, not terminate
// the test process between classification and row persistence.
export function createTask16LaunchLease(factory) {
  let current;
  const release = async bundleName => {
    if (!current) return;
    if (current.bundleName !== bundleName) throw new Error('Task16 launch lease belongs to another bundle');
    const owned = current;
    current = undefined;
    await owned.controller.dispose({ deferTermination: true });
  };
  return {
    acquire(bundleName) {
      if (current && current.bundleName !== bundleName) throw new Error('Task16 launch lease already owned');
      if (!current) current = { bundleName, controller: factory(bundleName), started: false, retained: false };
      const owned = current;
      owned.retained = false;
      return {
        async start() {
          if (owned !== current) throw new Error('Task16 launch lease released');
          if (!owned.started) {
            await owned.controller.start();
            owned.started = true;
          }
        },
        check: driver => owned.controller.check(driver),
        read: () => owned.controller.read(),
        retain() { owned.retained = true; },
        async dispose() { if (!owned.retained && owned === current) await release(bundleName); }
      };
    },
    release
  };
}
