// Diagnostic-only pass-through. Import ORIGINAL mounted-app exports before
// installing; test-HAP duplicate classes do not establish page identity.
export function observeTask17Loading(Presenter, Repository, preferences, abilityContext, hooks = {}) {
  const calls = [], restores = [], errors = [], presenters = [], repositories = [];
  let disposed = false, sequence = 0, owner = null;
  const bindings = {};
  const scope = () => ({ bundleName: abilityContext?.abilityInfo?.bundleName,
    moduleName: abilityContext?.abilityInfo?.moduleName || abilityContext?.currentHapModuleInfo?.name,
    preferencesDir: abilityContext?.preferencesDir, area: abilityContext?.area });
  const id = (items, value) => {
    if (!items.includes(value)) items.push(value);
    return items.indexOf(value) + 1;
  };
  const state = presenter => presenter ? { listState: presenter.listState,
    pinnedEventIds: presenter.pinnedMessages?.map(row => row.eventId),
    pinnedMessages: presenter.pinnedMessages?.map(row => ({ eventId: row.eventId, sender: row.sender, body: row.body })),
    errorMessage: presenter.errorMessage, retryEnabled: presenter.retryEnabled } : undefined;
  const record = (call, phase, presenter) => {
    if (disposed) return;
    try {
      calls.push({ sequence: ++sequence, callId: call.callId, method: call.method, phase,
        presenterId: call.presenterId, repositoryId: call.repositoryId,
        parentCallId: call.parentCallId, sameAbilityContext: call.sameAbilityContext,
        samePresenterRepository: call.samePresenterRepository, state: state(presenter),
        messages: call.messages, resolvedMessages: call.resolvedMessages,
        // An unrun .then handler is NOT proof that the SDK Promise is unresolved.
        promiseObservation: call.promiseObservation, nativePromisePending: 'unproven' });
    } catch (error) { errors.push('Observation failed: ' + String(error)); }
  };
  const descriptorInfo = descriptor => descriptor ? { present: true, configurable: descriptor.configurable,
    enumerable: descriptor.enumerable, writable: descriptor.writable,
    valueType: typeof descriptor.value, getter: typeof descriptor.get === 'function', setter: typeof descriptor.set === 'function' }
    : { present: false };
  function bind(target, method, kind) {
    const descriptor = target && Object.getOwnPropertyDescriptor(target, method);
    if (kind === 'sdk' && hooks.nativeReadback === true || !descriptor || !descriptor.configurable || typeof descriptor.value !== 'function') {
      const diagnostic = { targetType: typeof target, ownDescriptor: descriptorInfo(descriptor), prototypeDescriptors: [] };
      try {
        diagnostic.exportKeys = target ? Object.keys(target) : [];
        diagnostic.readableMethodType = target ? typeof target[method] : 'undefined';
        diagnostic.defaultDescriptor = descriptorInfo(target && Object.getOwnPropertyDescriptor(target, 'default'));
        let proto = target && Object.getPrototypeOf(target);
        for (let depth = 1; proto && depth <= 3; depth++, proto = Object.getPrototypeOf(proto)) {
          diagnostic.prototypeDescriptors.push({ depth, ...descriptorInfo(Object.getOwnPropertyDescriptor(proto, method)) });
        }
      } catch (error) { diagnostic.prototypeInspectionError = String(error); }
      bindings[method] = { available: false, reason: kind === 'sdk' && hooks.nativeReadback === true
        ? 'Native SDK not instrumented; use original-operation persistence readback' : 'Original method descriptor is not observable', diagnostic };
      return;
    }
    const original = descriptor.value;
    const wrapped = function(...args) {
      if (disposed) return original.apply(this, args);
      const parent = owner;
      const presenter = kind === 'presenter' ? this : parent?.presenter ||
        (kind === 'repository' ? presenters.find(value => value.repository === this) : undefined);
      const call = { callId: ++sequence, method, parentCallId: parent?.callId,
        presenterId: presenter ? id(presenters, presenter) : undefined,
        repositoryId: kind === 'repository' ? id(repositories, this) : parent?.repositoryId,
        sameAbilityContext: args[0] === abilityContext,
        samePresenterRepository: kind === 'repository' ? presenter?.repository === this : undefined,
        promiseObservation: 'not_returned', presenter };
      if (method === 'persistPinnedState' && Array.isArray(args[1])) {
        call.messages = args[1].map(row => ({ eventId: row.eventId, sender: row.sender, body: row.body }));
      }
      record(call, 'entered', presenter);
      owner = call;
      let returned;
      try { returned = original.apply(this, args); }
      catch (error) { record(call, 'threw', presenter); throw error; }
      finally { owner = parent; }
      try {
        if (returned && typeof returned.then === 'function') {
          call.promiseObservation = 'settlement_not_observed';
          record(call, 'returned', presenter);
          if (kind === 'presenter' && method === 'openPinnedMessages' && typeof hooks.onOpenReturned === 'function') {
            try { hooks.onOpenReturned(); }
            catch (error) { errors.push('Frame observation registration failed: ' + String(error)); }
          }
          // Observe only. Return the ORIGINAL Promise, never this .then result.
          returned.then(value => {
            if (method === 'openPinnedTimeline' && Array.isArray(value)) {
              call.resolvedMessages = value.map(row => ({ eventId: row.eventId, sender: row.sender, body: row.body }));
            }
            call.promiseObservation = 'fulfillment_observed'; record(call, 'fulfilled', presenter);
          }, () => {
            call.promiseObservation = 'rejection_observed'; record(call, 'rejected', presenter);
          });
        } else {
          call.promiseObservation = 'not_a_promise'; record(call, 'returned', presenter);
        }
      } catch (error) { errors.push('Promise observation failed: ' + String(error)); }
      return returned;
    };
    try {
      Object.defineProperty(target, method, { ...descriptor, value: wrapped });
      bindings[method] = { available: true };
      restores.push(() => {
        if (Object.getOwnPropertyDescriptor(target, method)?.value === wrapped) {
          Object.defineProperty(target, method, descriptor);
        } else errors.push('Descriptor changed externally; not overwritten: ' + method);
      });
    } catch (error) { bindings[method] = { available: false, reason: String(error) }; }
  }
  bind(Repository?.prototype, 'openPinnedTimeline', 'repository');
  if (hooks.nativeReadback === true) bind(Repository?.prototype, 'persistPinnedState', 'repository');
  bind(Presenter?.prototype, 'openPinnedMessages', 'presenter');
  bind(preferences, 'getPreferences', 'sdk');
  return {
    snapshot() {
      return JSON.stringify({ schemaVersion: 1, observationLevel: 'original_call_diagnostic',
        semanticVerdict: null, context: scope(), disposed, bindings, errors,
        presenterCount: presenters.length, repositoryCount: repositories.length,
        currentPresenterState: presenters.length === 1 ? state(presenters[0]) : undefined,
        singlePresenterCallChainObserved: presenters.length === 1 && calls.some(call =>
          call.method === 'openPinnedTimeline' && call.samePresenterRepository && call.sameAbilityContext),
        renderedLoadingObserved: false, navigationParentObserved: false,
        nativePromisePending: 'unproven', calls });
    },
    dispose() {
      if (disposed) return;
      disposed = true;
      for (const restore of restores.reverse()) {
        try { restore(); } catch (error) { errors.push('Restore failed: ' + String(error)); }
      }
    }
  };
}
