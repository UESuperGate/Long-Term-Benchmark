// Independent evaluator module, not another bundled CJS adapter or scorer.
let configured;
let active;
let cancelled = false;

export function configureTask13UI(probe, configJson, importModule = url => import(url)) {
  if (active) throw new Error('Task13 observer is active');
  const config = JSON.parse(configJson);
  if (!config.bundleName || !config.moduleName || !config.abilityName ||
    config.moduleUrl !== `@bundle:${config.bundleName}/${config.moduleName}/ets/features/UserVerificationFeature`) {
    throw new Error('Original task13 manifest identity is invalid');
  }
  configured = { probe, config, importModule };
}

export function task13UICancelled() { return cancelled; }

export function publishTask13UI(json) {
  if (!active || cancelled) return;
  const value = JSON.parse(json), spec = active.spec;
  if (!spec || value.taskId !== spec.taskId || value.caseId !== spec.caseId ||
    value.traceDigest !== spec.traceDigest || value.bundleName !== configured.config.bundleName) {
    throw new Error('Task13 partial evidence identity differs');
  }
  active.partial = value;
}

function presenterSnapshot(p) {
  return { request: p.request ? { type: p.request.type, userId: p.request.userId } : null,
    step: p.step, identityUserId: p.identityStore?.userId,
    requestUserCalls: p.gateway?.requestUserCalls,
    requestCurrentSessionCalls: p.gateway?.requestCurrentSessionCalls,
    lastRequestedUserId: p.gateway?.lastRequestedUserId };
}

export async function installTask13AfterReady(readinessJson) {
  const state = active, readiness = JSON.parse(readinessJson);
  if (!state || cancelled || state.binding) throw new Error('Task13 binding unavailable or repeated');
  const { config, importModule } = configured;
  const control = readiness.controls?.find(c => c.id === 'verify_user_action');
  if (readiness.bundleName !== config.bundleName || readiness.focusedBundle !== config.bundleName ||
    readiness.profileUserId !== state.spec.given.profileUserId || !control?.visible ||
    !control.enabled || !control.clickable || readiness.completed !== true) {
    throw new Error('Postload import requires the actual profile and actionable Verify button');
  }
  const namespace = await importModule(config.moduleUrl);
  if (active !== state || cancelled) throw new Error('Task13 import was cancelled');
  const P = namespace.UserVerificationPresenter, G = namespace.VerificationGateway;
  const methods = [[P?.prototype, 'requestVerification'], [G?.prototype, 'requestUserVerification'],
    [G?.prototype, 'requestCurrentSessionVerification']];
  const descriptors = methods.map(([prototype, name]) => prototype && Object.getOwnPropertyDescriptor(prototype, name));
  if (descriptors.some(d => !d || !d.configurable || typeof d.value !== 'function')) {
    throw new Error('Original presenter/gateway descriptors cannot be observed');
  }
  state.types = { user: namespace.VerificationRequestType?.User,
    currentSession: namespace.VerificationRequestType?.CurrentSession };
  state.binding = { moduleUrl: config.moduleUrl, importPhase: 'after_mounted_profile_before_click',
    namespaceExports: Object.keys(namespace), readiness, receiverObserved: false };
  let parent;
  try {
    methods.forEach(([prototype, name], index) => {
      const descriptor = descriptors[index];
      const wrapped = function(...args) {
        if (cancelled || active !== state) return descriptor.value.apply(this, args);
        const previous = parent;
        const isPresenter = index === 0;
        if (isPresenter && !state.instances.includes(this)) state.instances.push(this);
        const p = isPresenter ? this : parent?.receiver;
        const call = { sequence: state.calls.length + 1, method: name,
          instanceId: p ? state.instances.indexOf(p) + 1 : null,
          parentSequence: parent?.sequence, completed: false,
          sameGatewayReceiver: !isPresenter && p ? p.gateway === this : undefined,
          userId: name === 'requestUserVerification' ? args[0] : undefined };
        try { if (p) call.before = presenterSnapshot(p); }
        catch (error) { state.errors.push('Before observation: ' + String(error)); }
        state.calls.push(call);
        if (isPresenter) parent = { receiver: this, sequence: call.sequence };
        try {
          const returned = descriptor.value.apply(this, args);
          call.completed = true;
          return returned;
        } catch (error) { call.error = String(error); throw error; }
        finally {
          try { if (p) call.after = presenterSnapshot(p); }
          catch (error) { state.errors.push('After observation: ' + String(error)); }
          parent = previous;
        }
      };
      Object.defineProperty(prototype, name, { ...descriptor, value: wrapped });
      state.restores.push(() => {
        if (Object.getOwnPropertyDescriptor(prototype, name)?.value === wrapped) Object.defineProperty(prototype, name, descriptor);
        else state.errors.push('Descriptor changed externally: ' + name);
      });
    });
  } catch (error) {
    for (const restore of state.restores.splice(0).reverse()) restore();
    throw error;
  }
}

export function readTask13Page() {
  const state = active;
  if (!state) return JSON.stringify({ available: false, reason: 'No active original-page observer' });
  const available = !!state.binding && state.instances.length === 1 && !state.errors.length;
  return JSON.stringify({ available, instanceCount: state.instances.length,
    instanceId: available ? 1 : null, binding: state.binding ? { ...state.binding, receiverObserved: available } : null,
    requestTypes: state.types, calls: state.calls, errors: state.errors,
    state: available ? presenterSnapshot(state.instances[0]) : null });
}

function projectEvidence(spec, raw) {
  const result = { observed: {}, invariantChecks: [], evidence: [{ nativePageTransition: raw }],
    observationLevel: 'native_candidate_ui', unsupportedObservations: [] };
  const before = raw.frames?.find(f => f.label === 'before_event');
  const after = raw.frames?.find(f => f.label === 'after_event');
  const page = after?.pageEvidence;
  const action = raw.actions?.find(a => a.id === 'verify_user_action' && a.executed === true);
  const invocation = page?.calls?.find(c => c.method === 'requestVerification' && c.completed && c.instanceId === 1);
  const sdk = page?.calls?.filter(c => c.parentSequence === invocation?.sequence && c.completed && c.sameGatewayReceiver);
  const givenControl = before?.controls?.find(c => c.id === 'verify_user_action' && c.visible && c.enabled && c.clickable);
  const bound = before?.completed && after?.completed && before.focusedBundle === raw.bundleName &&
    after.focusedBundle === raw.bundleName && before.profileUserId === spec.given.profileUserId && givenControl && action &&
    action.before === before.label && action.after === after.label &&
    page?.available && page.instanceCount === 1 && invocation && sdk?.length === 1;
  if (bound) {
    result.observed.request = invocation.before.request;
    const types = page.requestTypes;
    if (typeof types?.user === 'string' && typeof types?.currentSession === 'string' &&
      typeof invocation.before.requestCurrentSessionCalls === 'number' && typeof invocation.after.requestCurrentSessionCalls === 'number') {
      result.invariantChecks.push({ description: 'self-session verification remains a distinct request type',
        passed: types.user !== types.currentSession && invocation.before.request?.type === types.user &&
          sdk[0].method === 'requestUserVerification' &&
          invocation.after.requestCurrentSessionCalls === invocation.before.requestCurrentSessionCalls,
        observed: { requestTypes: types, originalInvocation: invocation, gatewayInvocation: sdk[0] } });
    }
  }
  // A verification step/request is not a navigation route or current-account identity.
  result.unsupportedObservations.push({ fields: ['route', 'given.isCurrentUser'],
    reason: 'Original page screen/router observations are retained, but no mapped verify_user navigation or actual current-session identity is exposed.' });
  result.unsupported = raw.unsupported || (!bound ? 'Original profile click and same receiver evidence incomplete.' :
    'Same-page request is observed; canonical navigation route and non-self GIVEN remain unestablished.');
  return result;
}

export function attachTask13UI(bridge, taskId, key) {
  if (taskId !== '13_user_verification' || key !== 'profile_routes_user_request') return false;
  if (!configured || typeof configured.probe !== 'function' || active) throw new Error('Task13 UI is not configured or overlaps');
  if (typeof bridge.setObservationRecorder !== 'function') throw new Error('Native recorder unavailable');
  const state = { instances: [], calls: [], restores: [], errors: [] };
  active = state; cancelled = false;
  const original = bridge.setObservationRecorder;
  let recorder;
  bridge.setObservationRecorder = function(callback) { recorder = callback; return original.call(this, callback); };
  bridge.evaluateTask13UI = async args => {
    const spec = args.caseSpec;
    if (args.taskId !== taskId || spec.taskId !== taskId || spec.key !== key || state.spec) throw new Error('Task13 canonical identity differs or repeated');
    state.spec = spec;
    let raw, timer;
    try {
      raw = JSON.parse(await Promise.race([
        configured.probe(JSON.stringify(spec), JSON.stringify(configured.config)),
        new Promise((_resolve, reject) => { timer = setTimeout(() => { cancelled = true; reject(new Error('Task13 native observation watchdog elapsed')); }, 45000); })
      ]));
    } catch (error) {
      raw = state.partial || { taskId, caseId: spec.caseId, key, traceDigest: spec.traceDigest,
        bundleName: configured.config.bundleName, frames: [], actions: [] };
      raw.unsupported = String(error);
    } finally { clearTimeout(timer); }
    if (raw.taskId !== taskId || raw.caseId !== spec.caseId || raw.key !== key ||
      raw.traceDigest !== spec.traceDigest || raw.bundleName !== configured.config.bundleName) {
      return { observed: {}, invariantChecks: [], evidence: [{ rejectedNativePageTransition: raw }], unsupported: 'Task13 native case identity mismatch' };
    }
    const sources = configured.config.sources;
    for (const frame of raw.frames || []) {
      if (typeof frame.pageEvidenceJson === 'string') {
        try { frame.pageEvidence = JSON.parse(frame.pageEvidenceJson); }
        catch (error) { raw.unsupported = raw.unsupported || 'Original page evidence is malformed: ' + String(error); }
      }
    }
    for (const frame of raw.frames || []) args.trace('task13_' + frame.label, frame);
    const page = raw.frames?.find(f => f.label === 'after_event')?.pageEvidence;
    if (recorder && page?.available && raw.actions?.some(a => a.executed)) {
      recorder({ method: 'Task13.originalProfileClick', available: true, productionSources: sources,
        bundleName: raw.bundleName, caseId: raw.caseId, traceDigest: raw.traceDigest, frames: raw.frames, actions: raw.actions });
    }
    const result = projectEvidence(spec, raw);
    result.evidence.push({ productionSources: sources, projection: 'Same original-page invocation only; no separately constructed domain presenter.' });
    return result;
  };
  bridge.disposeTask13UI = () => {
    cancelled = true;
    for (const restore of state.restores.splice(0).reverse()) restore();
    bridge.setObservationRecorder = original;
    delete bridge.evaluateTask13UI;
    delete bridge.disposeTask13UI;
    if (active === state) active = undefined;
  };
  return true;
}
