// Native lifecycle, Driver events and scoped inspector transport only.
import { findActionAncestor, sameBounds, inspectorBounds } from './Task14AncestorObserver';
export async function startTask14Page(ports, config, record) {
  const required = ['bundleName', 'moduleName', 'abilityName', 'entryRoute'];
  if (required.some(key => !config[key]) || !config.allowedRoutes?.includes(config.entryRoute))
    throw new Error('Original candidate identity/routes unavailable');
  const identity = ability => ability?.context?.abilityInfo;
  const matches = ability => {
    const i = identity(ability);
    return i?.bundleName === config.bundleName && i?.moduleName === config.moduleName && i?.name === config.abilityName;
  };
  const validRect = r => r && ['left', 'top', 'right', 'bottom'].every(k => Number.isFinite(r[k])) && r.right > r.left && r.bottom > r.top;
  const intersects = (a, b) => validRect(a) && validRect(b) &&
    Math.min(a.right, b.right) > Math.max(a.left, b.left) && Math.min(a.bottom, b.bottom) > Math.max(a.top, b.top);
  const delegator = ports.getDelegator();
  const application = ports.getApplicationContext();
  let ability, stage, foreground = false, lifecycleError, lifecycleId, monitorAdded = false, released = false;
  const monitor = { abilityName: config.abilityName, moduleName: config.moduleName,
    onAbilityCreate(value) {
      if (!matches(value)) return;
      if (ability && ability !== value) lifecycleError = 'Multiple original ability instances';
      ability = value;
      record({ method: 'Task14.abilityCreate', identity: identity(value) });
    },
    onAbilityForeground(value) { if (matches(value)) foreground = true; },
    onAbilityBackground(value) { if (matches(value)) foreground = false; },
    onAbilityDestroy(value) { if (matches(value)) { foreground = false; lifecycleError = 'Original ability destroyed'; } }
  };
  const lifecycle = {
    onAbilityCreate() {}, onAbilityForeground() {}, onAbilityBackground() {}, onAbilityContinue() {},
    onWindowStageActive() {}, onWindowStageInactive() {}, onAbilityDestroy() {},
    onWindowStageCreate(value, actualStage) {
      if (!matches(value)) return;
      if (stage && stage !== actualStage) lifecycleError = 'Multiple original window stages';
      stage = actualStage;
      record({ method: 'Task14.windowStageCreate', identity: identity(value) });
    },
    onWindowStageDestroy(value) { if (matches(value)) { stage = undefined; lifecycleError = 'Original stage destroyed'; } }
  };
  const release = async () => {
    if (released) return;
    released = true;
    try { if (monitorAdded) await delegator.removeAbilityMonitor(monitor); }
    finally { if (lifecycleId !== undefined) await application.off('abilityLifecycle', lifecycleId); }
  };
  const nodes = tree => {
    const all = [];
    function visit(node) {
      if (!node || typeof node !== 'object') return;
      if (node.$type) all.push(node);
      for (const child of node.$children || node.children || []) visit(child);
    }
    visit(tree); return all;
  };
  try {
    lifecycleId = application.on('abilityLifecycle', lifecycle);
    if (!Number.isInteger(lifecycleId)) throw new Error('Application lifecycle callback ID unavailable');
    await delegator.addAbilityMonitor(monitor); monitorAdded = true;
    await delegator.startAbility({ bundleName: config.bundleName, abilityName: config.abilityName, moduleName: config.moduleName });
    const driver = ports.createDriver();
    const snapshot = async () => {
      if (lifecycleError || !ability || !stage || !foreground || !matches(await delegator.getCurrentTopAbility()))
        throw new Error(lifecycleError || 'Original cold-created foreground ability/stage unavailable');
      const main = await stage.getMainWindow();
      const win = await ports.getLastWindow(ability.context);
      const a = main.getWindowProperties(), b = win.getWindowProperties();
      if (!Number.isFinite(a.id) || a.id !== b.id) throw new Error('Last window is not original Stage main window');
      const context = win.getUIContext();
      if (!matches({ context: context.getHostContext() })) throw new Error('Foreign UIContext host');
      const nativeWindow = await driver.findWindow({ bundleName: config.bundleName, focused: true });
      if (!nativeWindow || await nativeWindow.getBundleName() !== config.bundleName || !await nativeWindow.isFocused())
        throw new Error('Original Driver window ownership/focus unavailable');
      const viewport = await nativeWindow.getBounds();
      if (!validRect(viewport)) throw new Error('Original Driver viewport unavailable');
      for (const props of [a, b]) if (!props.windowRect || props.windowRect.left !== viewport.left || props.windowRect.top !== viewport.top ||
          props.windowRect.width !== viewport.right - viewport.left || props.windowRect.height !== viewport.bottom - viewport.top)
        throw new Error('Driver/native Stage window geometry differs');
      const router = context.getRouter();
      let raw, route, routeParams;
      context.runScopedTask(() => {
        route = router.getState();
        routeParams = typeof router.getParams === 'function' ? router.getParams() : undefined;
        raw = ports.getInspectorTree();
      });
      const routeName = route.path ? route.path.replace(/\/$/, '') + '/' + route.name.replace(/\.ets$/, '') : route.name.replace(/\.ets$/, '');
      if (!config.allowedRoutes.includes(routeName)) throw new Error('Route is not owned by the candidate: ' + routeName);
      const tree = typeof raw === 'string' ? JSON.parse(raw) : raw;
      if (!nodes(tree).length) throw new Error('Original inspector tree is empty');
      return { tree, viewport, routeName, routeParams, windowId: a.id, context,
        stackLength: typeof router.getLength === 'function' ? router.getLength() : undefined };
    };
    const find = async (selector, strict = false, state) => {
      let result = await driver.findComponents(ports.selector(selector, config.bundleName));
      if (strict && result == null) {
        // A null filtered query is not absence evidence. Independently enumerate
        // the actual candidate window and match its concrete component fields.
        if (!state.driverInventory) {
          const all = await driver.findComponents(ports.selector({}, config.bundleName));
          if (!Array.isArray(all) || all.length === 0) throw new Error('Driver inventory unavailable during bracketed acquisition');
          state.driverInventory = [];
          for (const component of all) state.driverInventory.push({ component,
            id: await component.getId(), type: await component.getType(), text: await component.getText() });
          record({ method: 'Task14.driverInventory', windowId: state.windowId, routeName: state.routeName,
            queryScope: config.bundleName, count: all.length,
            components: state.driverInventory.map(({ id, type, text }) => ({ id, type, text })) });
        }
        const matching = state.driverInventory.filter(item => (!selector.id || item.id === selector.id) &&
          (!selector.type || item.type === selector.type) && (selector.text === undefined || item.text === selector.text));
        record({ method: 'Task14.driverQueryResolvedByInventory', selector, rawFilteredResult: result === null ? 'null' : 'undefined',
          inventoryCount: state.driverInventory.length, matchedCount: matching.length, windowId: state.windowId });
        result = matching.map(item => item.component);
      }
      if (result == null) return [];
      if (!Array.isArray(result)) throw new Error('Malformed Driver query result');
      if (selector.bounds) {
        const matching = [];
        for (const component of result) if (sameBounds(await component.getBounds(), selector.bounds)) matching.push(component);
        result = matching;
      }
      if (result.length > 1) throw new Error('Ambiguous original UI selector: ' + JSON.stringify(selector));
      return result;
    };
    const inspect = async (selector, state, strict = false) => {
      const all = nodes(state.tree);
      const matching = all.filter(node => {
        const attrs = node.$attrs || {};
        return (selector.inspectorId === undefined || node.$ID === selector.inspectorId) &&
          (!selector.bounds || sameBounds(inspectorBounds(node), selector.bounds)) &&
          (!selector.id || attrs.id === selector.id) && (!selector.type || node.$type === selector.type) &&
          (selector.text === undefined || [attrs.content, attrs.text, attrs.label, attrs.value].includes(selector.text));
      });
      const found = await find(selector, strict, state);
      if (!found.length) {
        // A node missing from accessibility but present in inspector is not a
        // proven invisible control. Keep it unavailable instead of guessing.
        return { selector, present: matching.length ? null : false, visible: matching.length ? undefined : false,
          inspectorMatches: matching.length };
      }
      const component = found[0];
      const id = await component.getId(), text = await component.getText(), type = await component.getType();
      const bounds = await component.getBounds();
      const exact = matching.filter(node => (!id || !node.$attrs?.id || node.$attrs.id === id) && node.$type === type);
      const attrs = exact.length === 1 ? exact[0].$attrs : undefined;
      const opacity = attrs?.opacity;
      const visibilityKnown = typeof attrs?.visibility === 'string' &&
        (typeof opacity === 'number' || typeof opacity === 'string' && opacity.trim() !== '') && Number.isFinite(Number(opacity));
      const control = { selector, present: true, id, text, type, bounds, enabled: await component.isEnabled(),
        focused: await component.isFocused(), clickable: await component.isClickable(),
        visible: visibilityKnown ? attrs.visibility === 'Visibility.Visible' && Number(opacity) > 0 && intersects(bounds, state.viewport) : undefined,
        visibility: attrs?.visibility, opacity, inspectorMatches: exact.length,
        observationScope: 'Actual Driver + scoped inspector attributes/geometry, not screenshot occlusion' };
      if (selector.actionAncestor && exact.length === 1 && control.visible === true && control.clickable !== true) {
        const ancestor = await findActionAncestor(state.tree, exact[0], bounds, candidate => inspect(candidate, state, strict));
        if (ancestor) control.actionAncestor = { ...ancestor, anchorSelector: selector };
      }
      return control;
    };
    const observeFrom = async (label, selectors, state, strict = false) => {
      const controls = {};
      for (const [name, alternatives] of Object.entries(selectors)) {
        const attempted = [];
        for (const selector of alternatives) {
          const control = await inspect(selector, state, strict);
          attempted.push(control);
          if (control.present === true) break;
        }
        controls[name] = attempted.find(control => control.present === true) || attempted.find(control => control.present === null) || attempted[attempted.length - 1];
        controls[name].attemptedSelectors = attempted.map(control => ({ selector: control.selector, present: control.present }));
      }
      const frame = { label, available: true, routeName: state.routeName, routeParams: state.routeParams, windowId: state.windowId,
        viewport: state.viewport, stackLength: state.stackLength, tree: state.tree, controls };
      return frame;
    };
    const observe = async (label, selectors) => observeFrom(label, selectors, await snapshot());
    const observeBracketed = async (label, selectors, readState) => {
      const stateBefore = readState();
      const view = await observeFrom(label, selectors, await snapshot(), true);
      const end = await snapshot();
      return { ...view, stateBefore, stateAfter: readState(),
        bracketEnd: { tree: end.tree, routeName: end.routeName, routeParams: end.routeParams, windowId: end.windowId } };
    };
    const action = async (kind, control, value) => {
      if (!control || control.present !== true || control.visible !== true || control.enabled !== true)
        throw new Error('Original UI action control is absent/disabled or visibility unobserved');
      const state = await snapshot();
      const fresh = control.anchorSelector ? (await inspect(control.anchorSelector, state)).actionAncestor : await inspect(control.selector, state);
      if (!fresh || control.anchorSelector && (fresh.selector.inspectorId !== control.selector.inspectorId ||
          !sameBounds(fresh.bounds, control.bounds))) throw new Error('Original action ancestor changed');
      if (fresh.visible !== true || fresh.enabled !== true) throw new Error('Original UI action target changed');
      const [component] = await find(control.selector);
      if (!component) throw new Error('Original UI action target disappeared');
      if (kind === 'click') { if (!fresh.clickable) throw new Error('Original control is not clickable'); await component.click(); }
      else if (kind === 'input') await component.inputText(value);
      else throw new Error('Unsupported Task14 event transport');
      record({ method: 'Task14.uiAction', available: true, kind, selector: control.selector, value,
        target: fresh, semanticVerdict: null });
    };
    const dismissKeyboard = async () => {
      if (typeof ports.dismissKeyboard !== 'function') throw new Error('Native input-method controller unavailable');
      const before = await snapshot();
      await ports.dismissKeyboard();
      await ports.delay(100);
      const after = await snapshot();
      if (before.windowId !== after.windowId || before.routeName !== after.routeName)
        throw new Error('Keyboard dismissal changed the candidate route/window');
      record({ method: 'Task14.keyboardDismissed', available: true, routeName: after.routeName,
        windowId: after.windowId, semanticVerdict: null, scope: 'OS input-method housekeeping only' });
    };
    const deadline = Date.now() + 10000;
    let initial, lastError;
    do {
      try { initial = await snapshot(); if (initial.routeName === config.entryRoute) break; }
      catch (error) { lastError = String(error); }
      initial = undefined; await ports.delay(50);
    } while (Date.now() < deadline);
    if (!initial) throw new Error('Original candidate page unavailable: ' + lastError);
    return { observe, observeBracketed, action, dismissKeyboard, release, delay: ports.delay };
  } catch (error) { await release(); throw error; }
}
