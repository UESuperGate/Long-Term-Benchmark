'use strict';

const feature = 'entry/src/main/ets/features/AccountDeactivationFeature.ets';
const page = 'entry/src/main/ets/pages/Index.ets';
const clone = value => JSON.parse(JSON.stringify(value));
const requireEvidence = (condition, reason) => { if (!condition) throw new Error(reason); };
function destructiveColor(node) {
  const attrs = node && (node.$attrs || node.attrs || node.attributes);
  const value = String(attrs && (attrs.fontColor || attrs.foregroundColor || attrs.fontColorValue) || '').toLowerCase();
  return value === '#b42318' || value === '#ffb42318' || value === '0xffb42318';
}

async function runCase(args) {
  const result = { observed: {}, invariantChecks: [], evidence: [], observationLevel: 'native_candidate_ui',
    integrationBoundary: { entry: 'original native AccountDeactivation page', appEntryExecuted: false, externalServicesExecuted: false } };
  try {
    const spec = args.caseSpec, native = args.native || args.context?.native;
    requireEvidence(args.taskId === '15_account_deactivation' && ['capability_gates_entry', 'first_submit_confirms', 'confirm_sends_payload'].includes(spec.key), 'Unsupported Task15 native case');
    const raw = await native.runTask15UI(spec);
    result.evidence.push({ nativePageTransition: clone(raw) });
    for (const frame of raw.frames || []) args.trace?.('task15_ui_' + frame.label, clone(frame));
    if (spec.key === 'capability_gates_entry') {
      const after = raw.frames?.find(frame => frame.label === 'after_event');
      const before = raw.frames?.find(frame => frame.label === 'before_event');
      const window = after?.windowIdentity;
      requireEvidence(raw.taskId === args.taskId && raw.caseId === spec.caseId && raw.traceDigest === spec.traceDigest &&
        /^[a-f0-9]{64}$/.test(raw.traceDigest) && raw.entryExecuted && raw.eventExecuted && !raw.failure &&
        raw.readiness?.ready && raw.prerequisite?.rootConfirmed && raw.sessionId &&
        before?.sessionId === raw.sessionId && after?.sessionId === raw.sessionId && before.sequence < after.sequence &&
        before.phase === 'before_startAbility' && before.uiObserved === false && after.bundleName === native.bundleName &&
        window?.bundleName === native.bundleName && window.focused === true && window.hostVerified === true &&
        Number.isInteger(window.stageMainWindowId) && window.stageMainWindowId >= 0 && window.lastWindowId === window.stageMainWindowId &&
        window.ability?.bundleName === native.bundleName && window.ability.name === 'EntryAbility' && window.ability.moduleName === 'entry' &&
        ['settings', 'notifications'].every(name => after.controls?.some(c => c.name === name && c.present && c.visible)) &&
        [feature, page].every(path => raw.productionSources?.some(s => s.path === path && /^[a-f0-9]{64}$/.test(s.sha256))),
        'Original settings entry/window/source evidence incomplete: ' + (raw.failure?.message || raw.unsupported || ''));
      // Register source only. The actual settings page was launched, not a
      // second presenter. Absence alone cannot establish capability readiness.
      await args.load(feature);
      const entry = after.controls?.find(c => c.name === 'entry');
      const login = raw.integration?.login;
      if (entry?.present === true && entry.visible === true && entry.id === 'deactivate_account_entry' &&
        login?.entryVisible === true && login.providerLoginCount === 1) {
        result.observed.deactivateEntryVisible = true;
      }
      if (destructiveColor(login?.entryInspector)) {
        result.observed.entryStyle = 'destructive';
      }
      result.integrationBoundary.appEntryExecuted = true;
      result.integrationBoundary.externalServicesExecuted = login?.providerLoginCount === 1;
      if (login?.entryHiddenBeforeLogin === true) {
        result.invariantChecks.push({ description: 'the entry is hidden when the server reports unsupported',
          passed: true, observed: { beforeAuthenticatedCapability: false, entryPresent: false,
            afterAuthenticatedCapability: true, entryPresentAfterLogin: login.entryVisible } });
      }
      if (result.observed.deactivateEntryVisible !== true || result.observed.entryStyle !== 'destructive' ||
        result.invariantChecks.length !== (spec.invariants || []).length) {
        result.unsupported = 'Native capability entry/style/negative-branch evidence incomplete';
      }
      return result;
    }
    if (spec.key === 'confirm_sends_payload') {
      // Partial diagnostic only. Neither old disabled nor staged modal-block
      // invariants may pass from settled controls or source configuration.
      await args.load(feature);
      result.unsupported = raw.failure ? (raw.failure.stage + ': ' + raw.failure.message) :
        (raw.unsupported || 'Actual simultaneous Loading/modal/input-routing evidence incomplete');
      return result;
    }
    const before = raw.frames?.find(frame => frame.label === 'before_event');
    const after = raw.frames?.find(frame => frame.label === 'after_event');
    requireEvidence(raw.taskId === args.taskId && raw.caseId === spec.caseId && raw.traceDigest === spec.traceDigest &&
      /^[a-f0-9]{64}$/.test(raw.traceDigest) && raw.entryExecuted && raw.eventExecuted && before && after &&
      !raw.failure && raw.readiness?.ready === true && raw.prerequisite?.rootConfirmed && raw.sessionId && before.sessionId === raw.sessionId && after.sessionId === raw.sessionId &&
      before.bundleName === native.bundleName && after.bundleName === native.bundleName && before.sequence < after.sequence,
      'Native entry/event/frame identity incomplete: ' + (raw.failure ? (raw.failure.stage || 'cleanup') + ': ' +
        (raw.failure.message || raw.failure.cleanupError) : raw.unsupported || ''));
    requireEvidence([feature, page].every(path => raw.productionSources?.some(source => source.path === path && /^[a-f0-9]{64}$/.test(source.sha256))),
      'Original page/feature source provenance incomplete');
    const control = (frame, name) => frame.controls?.find(item => item.name === name);
    const visible = (frame, name) => control(frame, name)?.present === true && control(frame, name)?.visible === true;
    for (const frame of [before, after]) {
      const window = frame.windowIdentity;
      requireEvidence(window && window.bundleName === native.bundleName && window.focused === true && window.hostVerified === true &&
        Number.isInteger(window.stageMainWindowId) && window.stageMainWindowId >= 0 && window.lastWindowId === window.stageMainWindowId &&
        window.ability?.bundleName === native.bundleName && window.ability.name === 'EntryAbility' && window.ability.moduleName === 'entry',
        'Original foreground main-window identity incomplete');
      const p = frame.presenter;
      if (p?.requestCountOrigin === 'pass_through_since_observer_install') {
        requireEvidence((frame !== before || p.accountSessionActive === true) &&
          ['services/AccountClient.ets', 'services/NativeAccountClient.ets', 'components/AccountSessionControls.ets'].every(file =>
            raw.productionSources?.some(source => source.path === 'entry/src/main/ets/' + file && /^[a-f0-9]{64}$/.test(source.sha256))),
          'Production AccountClient requires a real restored/login session and complete service source closure');
      }
      requireEvidence(p?.available === true && p.instanceCount === 1 && p.originalService === true &&
        typeof p.instanceId === 'number' && typeof p.serviceId === 'number' &&
        Number.isInteger(p.requestCount) && typeof p.action === 'string' && Array.isArray(p.calls) && Array.isArray(p.serviceCalls) &&
        p.binding?.importCompleted === true && p.binding.importPhase === 'after_original_page_ready_before_fixture' &&
        p.binding.productionModuleUrl === '@bundle:' + native.bundleName + '/entry/ets/features/AccountDeactivationFeature',
        'Original presenter and real service receiver unavailable');
      requireEvidence(visible(frame, 'password') && visible(frame, 'erase') && visible(frame, 'submit') &&
        control(frame, 'erase').checked === p.eraseData &&
        p.calls.some(call => call.method === 'setPassword' && call.returned && call.args[0] === spec.given.password) &&
        p.calls.some(call => call.method === 'setEraseData' && call.returned && call.args[0] === spec.given.eraseData),
        'Same-page native form and original setter evidence incomplete');
      requireEvidence(['confirmation', 'confirm', 'cancel'].every(name => typeof control(frame, name)?.present === 'boolean' &&
        typeof control(frame, name)?.visible === 'boolean'), 'Native confirmation controls were not queried');
    }
    const prior = before.presenter, next = after.presenter;
    requireEvidence(prior.instanceId === next.instanceId && prior.serviceId === next.serviceId &&
      Object.entries(spec.given).every(([key, value]) => prior[key] === value), 'Canonical given or stable receiver/service identity not established');
    const actions = raw.actions || [];
    requireEvidence(actions.some(a => a.kind === 'input' && a.target === 'password' && a.executed && a.value === spec.given.password &&
      a.sessionId === raw.sessionId && a.sequence < before.sequence) &&
      actions.some(a => a.kind === 'click' && a.target === 'erase' && a.executed && a.sessionId === raw.sessionId && a.sequence < before.sequence),
      'Canonical fixture lacks physical UI actions');
    requireEvidence(control(before, 'submit').enabled === true && actions.filter(a => a.kind === 'click' && a.target === 'submit' && a.executed &&
      a.sessionId === raw.sessionId && a.sequence > before.sequence && a.sequence < after.sequence).length === 1,
      'First submit did not execute through exactly one enabled native control');
    const events = next.calls.filter(call => call.method === 'deactivateAccount');
    requireEvidence(prior.calls.every(call => call.method !== 'deactivateAccount') && events.length === 1 && events[0].returned &&
      events[0].args[0] === spec.event.isRetry && events[0].before.action === spec.given.action &&
      events[0].before.password === spec.given.password && events[0].before.eraseData === spec.given.eraseData,
      'Real first-submit receiver call does not match the canonical event');
    requireEvidence(!actions.some(a => a.target === 'confirm' && a.executed), 'Confirmation action must not be injected');
    await args.load(feature); // Source registration only; never invoke its test-copy class.
    result.integrationBoundary.appEntryExecuted = true;
    result.observed = { action: next.action, requestCount: next.requestCount,
      confirmationVisible: ['confirmation', 'confirm', 'cancel'].every(name => visible(after, name)) };
    const checkpoints = [prior, next, ...next.calls.flatMap(call => [call.before, call.after]).filter(Boolean)];
    result.invariantChecks.push({ description: 'a destructive request is never sent before confirmation',
      passed: checkpoints.every(state => state.requestCount === 0 && state.serviceId === prior.serviceId) &&
        next.serviceCalls.filter(call => call.instanceId === prior.serviceId).length === 0,
      observed: { before: clone(prior), after: clone(next), physicalActions: clone(actions) } });
    result.nativeUI = { observed: true, transitionObserved: true, samePresenterInstance: true, productionSources: clone(raw.productionSources) };
  } catch (error) {
    result.unsupported = String(error.message || error);
  }
  return result;
}
module.exports = { runCase };
