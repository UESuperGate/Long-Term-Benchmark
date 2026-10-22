'use strict';

const page = 'entry/src/main/ets/pages/Index.ets';
const roomPort = 'entry/src/main/ets/features/MatrixRoomServices.ets';
const keys = new Set([
  'open_loading', 'load_failure', 'empty_success', 'filled_list',
  'unpin_permission_denied', 'unpin_permission_allowed', 'view_in_timeline',
  'unpin_success', 'unpin_failure_recovery'
]);
const need = (condition, message) => { if (!condition) throw new Error(message); };

async function runCase(args) {
  const result = {
    observed: {}, invariantChecks: [], evidence: [],
    observationLevel: 'openharmony_api23_native_candidate_page_owner_and_matrix_room_port',
    integrationBoundary: {
      appEntryExecuted: false,
      externalServicesExecuted: false,
      boundary: 'Installed candidate ArkUI page and its own service/controller graph, driven through the pre-existing room port; no detached presenter or source observer.'
    }
  };
  try {
    const spec = args.caseSpec;
    const native = args.native || args.context?.native;
    need(args.taskId === '17_pinned_messages' && keys.has(spec.key), 'Unsupported Task17 owner-bound case');
    const raw = await native.runTask17OwnerUI(spec);
    result.evidence.push({ nativeTransition: raw });
    for (const frame of raw.frames || []) args.trace?.('task17_owner_' + frame.label, frame);
    need(raw.taskId === args.taskId && raw.caseId === spec.caseId && raw.key === spec.key &&
      raw.traceDigest === spec.traceDigest && /^[a-f0-9]{64}$/.test(raw.traceDigest) && raw.entryExecuted,
    'Task17 owner-bound native identity/entry incomplete');
    need(raw.frames?.some(frame => frame.label === 'before_event') &&
      raw.frames.some(frame => frame.label === 'after_event'), 'Ordered owner-bound before/after checkpoints missing');
    need(raw.productionSources?.some(item => item.path === page && /^[a-f0-9]{64}$/.test(item.sha256)),
      'Task17 production page provenance missing');

    if (raw.semanticFeatureAbsent) {
      need(raw.evaluatorRole === 'base' && raw.basePositiveControl?.clickedBannerNext &&
        raw.basePositiveControl?.finalEntryAbsent && !raw.failure,
      'Base feature-absence positive control is incomplete');
      result.observed = raw.observed || {};
      result.invariantChecks = raw.invariantChecks || [];
      result.integrationBoundary.appEntryExecuted = true;
      result.nativeUI = { observed: true, transitionObserved: false, semanticFeatureAbsent: true,
        runtimeMode: raw.runtimeMode, productionSources: raw.productionSources };
      return result;
    }

    need(raw.eventExecuted && !raw.failure && raw.binding?.configuredBeforeScoredAbilityStart === true &&
      raw.binding?.importCompleted === true && raw.fixture?.calls?.length > 0,
    'Task17 owner-bound transition incomplete: ' + JSON.stringify(raw.failure || {}));
    need(raw.productionSources.some(item => item.path === roomPort), 'Candidate room-port provenance missing');
    result.observed = raw.observed;
    result.invariantChecks = raw.invariantChecks;
    result.integrationBoundary.appEntryExecuted = true;
    result.integrationBoundary.externalServicesExecuted = true;
    result.nativeUI = { observed: true, transitionObserved: true, freshInstallRequiredByBuild: true,
      runtimeMode: raw.runtimeMode, productionSources: raw.productionSources,
      fixtureCalls: raw.fixture.calls };
  } catch (error) {
    result.unsupported = String(error.message || error);
  }
  return result;
}

module.exports = { runCase };
