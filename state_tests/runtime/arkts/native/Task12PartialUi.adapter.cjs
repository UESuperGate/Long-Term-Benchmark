'use strict';
const feature = 'entry/src/main/ets/features/ReportRoomFeature.ets', page = 'entry/src/main/ets/pages/Index.ets';
const copy = value => JSON.parse(JSON.stringify(value));
const requireEvidence = (condition, message) => { if (!condition) throw new Error(message); };
async function runCase(args) {
  const result = { observed: {}, invariantChecks: [], evidence: [], observationLevel: 'native_candidate_ui',
    integrationBoundary: { entry: 'original report page; real retry control on same live page', appEntryExecuted: false,
      externalServicesExecuted: false, boundaryFixture: 'Existing original ReportRoomGateway result flags; no network request or real server claimed' } };
  try {
    const spec = args.caseSpec, native = args.native || args.context?.native;
    requireEvidence(args.taskId === '12_report_room' && spec.key === 'leave_failure_is_partial', 'Unsupported Task12 partial case');
    const raw = await native.runTask12PartialUI(spec);
    result.evidence.push({ nativePageTransition: copy(raw) });
    for (const frame of raw.frames || []) args.trace?.('task12_partial_' + frame.label, copy(frame));
    const frame = label => raw.frames?.find(f => f.label === label);
    const before = frame('before_event'), after = frame('after_event'), retryBefore = frame('retry_boundary_recovered'), retried = frame('after_invariant_retry');
    requireEvidence(raw.taskId === args.taskId && raw.caseId === spec.caseId && raw.traceDigest === spec.traceDigest && /^[a-f0-9]{64}$/.test(raw.traceDigest) &&
      raw.entryExecuted && raw.eventExecuted && raw.invariantEventExecuted && !raw.failure && raw.readiness?.ready &&
      raw.prerequisite?.rootConfirmed && before && after && retryBefore && retried,
      'Native partial/retry transition incomplete: ' + (raw.failure ? (raw.failure.stage || 'cleanup') + ': ' +
        (raw.failure.message || raw.failure.cleanupError) : raw.unsupported || ''));
    requireEvidence([feature, page].every(path => raw.productionSources?.some(s => s.path === path && /^[a-f0-9]{64}$/.test(s.sha256))),
      'Original source provenance incomplete');
    const ordered = [before, after, retryBefore, retried];
    const initial = before.presenter, initialWindow = before.windowIdentity;
    for (let i = 0; i < ordered.length; i++) {
      const f = ordered[i], p = f.presenter, w = f.windowIdentity;
      requireEvidence(f.sessionId === raw.sessionId && f.bundleName === native.bundleName && (!i || ordered[i - 1].sequence < f.sequence),
        'Canonical checkpoints are not one ordered native session');
      requireEvidence(w && w.focused && w.hostVerified && w.bundleName === native.bundleName && Number.isInteger(w.stageMainWindowId) &&
        w.stageMainWindowId === w.lastWindowId && w.lastWindowId === initialWindow.lastWindowId && w.routeName === initialWindow.routeName &&
        ['pages/Index', 'pages/Index.ets'].includes(w.routeName) && w.ability?.name === 'EntryAbility' && w.ability.moduleName === 'entry',
        'Original live report page/main-window identity changed');
      requireEvidence(p?.available && p.instanceCount === 1 && p.instanceId === initial.instanceId && p.serviceId === initial.serviceId &&
        p.gatewayId === initial.gatewayId && p.originalService && p.originalGateway && p.binding?.importCompleted &&
        p.binding.importPhase === 'after_original_page_ready_before_fixture' && p.binding.productionModuleUrl ===
        '@bundle:' + native.bundleName + '/entry/ets/features/ReportRoomFeature' &&
        Array.isArray(p.calls) && Array.isArray(p.serviceCalls) && Array.isArray(p.gatewayCalls) && Array.isArray(p.effects),
        'Original same-page presenter/service/gateway binding incomplete');
    }
    const control = (f, name) => f.controls.find(c => c.name === name);
    const visible = (f, name) => control(f, name)?.present && control(f, name)?.visible;
    requireEvidence(visible(before, 'reason') && control(before, 'reason').text === spec.given.reason &&
      visible(before, 'leave') && control(before, 'leave').checked === spec.given.leaveRoom && visible(before, 'submit') && control(before, 'submit').enabled === true &&
      initial.reason === spec.given.reason && initial.leaveRoom === spec.given.leaveRoom && initial.reportAction === 'uninitialized' &&
      initial.reportCalls === 0 && initial.leaveCalls === 0 && initial.effects.length === 0 && initial.reportShouldFail === false && initial.leaveShouldFail === true &&
      initial.fixtures?.some(f => f.phase === 'canonical_given' && f.reportResult === spec.given.reportResult && f.leaveResult === spec.given.leaveResult),
      'Canonical original form and gateway result givens were not established');
    const actions = raw.actions || [];
    const actionsBetween = (target, lower, upper) => actions.filter(a => a.kind === 'click' && a.target === target && a.executed &&
      a.sessionId === raw.sessionId && a.sequence > lower && a.sequence < upper);
    requireEvidence(actions.some(a => a.kind === 'input' && a.target === 'reason' && a.executed && a.value === spec.given.reason && a.sequence < before.sequence) &&
      actionsBetween('leave', 0, before.sequence).length === 1 && actionsBetween('submit', before.sequence, after.sequence).length === 1 &&
      actionsBetween('retry', retryBefore.sequence, retried.sequence).length === 1, 'Missing physical original form/submit/retry actions');
    requireEvidence(visible(after, 'retry') && typeof control(after, 'retry').enabled === 'boolean' && visible(retryBefore, 'retry') && control(retryBefore, 'retry').enabled === true,
      'Actual native retry control observation unavailable');
    const failure = after.presenter, recovery = retryBefore.presenter, final = retried.presenter;
    requireEvidence(initial.calls.some(c => c.method === 'updateReason' && c.returned && c.args[0] === spec.given.reason) &&
      initial.calls.some(c => c.method === 'toggleLeaveRoom' && c.returned) &&
      failure.calls.some(c => c.method === 'submit' && c.returned && c.before.reportAction === 'uninitialized') &&
      final.calls.some(c => c.method === 'retry' && c.returned && c.before.reportAction === failure.reportAction) &&
      failure.serviceCalls.length > 0 && final.serviceCalls.length > failure.serviceCalls.length,
      'Physical UI actions did not reach the original live production methods');
    requireEvidence(recovery.fixtures?.some(f => f.phase === 'invariant_retry_recovery' && f.reportResult === 'success' && f.leaveResult === 'success') &&
      recovery.reportShouldFail === false && recovery.leaveShouldFail === false &&
      ['reportCalls', 'leaveCalls', 'reportAction', 'reason', 'leaveRoom'].every(key => recovery[key] === failure[key]) &&
      JSON.stringify(recovery.effects) === JSON.stringify(failure.effects), 'Retry recovery changed business state instead of gateway outcome configuration');
    // All canonical expected fields come from the partial-failure checkpoint,
    // never from the later retry-success state.
    result.observed = { reportAction: failure.reportAction, reportCalls: failure.reportCalls, leaveCalls: failure.leaveCalls,
      retryEnabled: control(after, 'retry').enabled };
    const gatewayDelta = final.gatewayCalls.slice(failure.gatewayCalls.length);
    const serviceDelta = final.serviceCalls.slice(failure.serviceCalls.length);
    result.invariantChecks.push({ description: 'the successful report is remembered',
      passed: failure.reportCalls === 1 && failure.gatewayCalls.some(c => c.method === 'reportRoom' && c.returned && c.result === true) &&
        final.reportCalls === failure.reportCalls && final.leaveCalls === failure.leaveCalls + 1 && final.reportAction === 'success' &&
        gatewayDelta.length === 1 && gatewayDelta[0].method === 'leaveRoom' && gatewayDelta[0].returned && gatewayDelta[0].result === true &&
        serviceDelta.length === 1 && serviceDelta[0].returned && serviceDelta[0].args[0] === spec.given.reason &&
        serviceDelta[0].args[1] === false && serviceDelta[0].args[2] === true,
      observed: { afterCanonicalEvent: copy(after), beforePhysicalRetry: copy(retryBefore), afterPhysicalRetry: copy(retried) } });
    await args.load(feature);
    result.integrationBoundary.appEntryExecuted = true;
    result.nativeUI = { observed: true, transitionObserved: true, samePresenterInstance: true, sourcePageLifetimeVerified: true,
      productionSources: copy(raw.productionSources) };
  } catch (error) { result.unsupported = String(error.message || error); }
  return result;
}
module.exports = { runCase };
