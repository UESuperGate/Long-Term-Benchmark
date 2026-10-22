'use strict';

const feature = 'entry/src/main/ets/features/PinnedMessagesFeature.ets';
const baseFeature = 'entry/src/main/ets/features/PinnedMessagesBase.ets';
const page = 'entry/src/main/ets/pages/Index.ets';
const keys = new Set([
  'open_loading', 'load_failure', 'empty_success', 'filled_list',
  'unpin_permission_denied', 'unpin_permission_allowed', 'view_in_timeline',
  'unpin_success', 'unpin_failure_recovery'
]);
const need = (condition, message) => { if (!condition) throw new Error(message); };

async function runCase(args) {
  const result = {
    observed: {},
    invariantChecks: [],
    evidence: [],
    observationLevel: 'openharmony_api23_native_candidate_ui_and_original_production_runtime',
    integrationBoundary: {
      appEntryExecuted: false,
      externalServicesExecuted: false,
      boundary: 'Original installed ArkUI page plus original presenter/repository on ArkVM and native Preferences; no source observer or Matrix server claim.'
    }
  };
  try {
    const spec = args.caseSpec;
    const native = args.native || args.context?.native;
    need(args.taskId === '17_pinned_messages' && keys.has(spec.key), 'Unsupported Task17 strict native case');
    const raw = await native.runTask17StrictUI(spec);
    result.evidence.push({ nativeTransition: raw });
    for (const frame of raw.frames || []) args.trace?.('task17_strict_' + frame.label, frame);
    need(raw.taskId === args.taskId && raw.caseId === spec.caseId && raw.key === spec.key &&
      raw.traceDigest === spec.traceDigest && /^[a-f0-9]{64}$/.test(raw.traceDigest) &&
      raw.entryExecuted && raw.eventExecuted && !raw.failure,
    'Task17 strict native transition incomplete: ' + JSON.stringify(raw.failure || {}));
    need(raw.frames?.some(frame => frame.label === 'before_event') &&
      raw.frames.some(frame => frame.label === 'after_event'), 'Ordered native before/after checkpoints missing');
    need(raw.productionSources?.some(item => item.path === page && /^[a-f0-9]{64}$/.test(item.sha256)),
      'Task17 production page provenance missing');

    if (raw.baseFeatureAbsent) {
      need(raw.basePositiveControl?.clickedBannerNext && raw.basePositiveControl?.bodyChanged &&
        (raw.evaluatorRole === 'agent' || raw.productionSources.some(item => item.path === baseFeature)),
      'Base positive control and feature-absence proof are incomplete');
      if (raw.evaluatorRole !== 'agent') await args.load(baseFeature);
    } else {
      need(raw.binding?.importCompleted && raw.binding.productionModuleUrl ===
        '@bundle:' + native.bundleName + '/entry/ets/features/PinnedMessagesFeature' &&
        raw.productionSources.some(item => item.path === feature),
      'Original installed Task17 feature binding missing');
      await args.load(feature);
      need(raw.nativePreferences?.sameAbilityContext === true && raw.nativePreferences?.storeName ===
        'element_x_pinned_messages', 'Native Preferences evidence missing or uses another context');
    }

    result.observed = raw.observed;
    result.invariantChecks = raw.invariantChecks;
    result.integrationBoundary.appEntryExecuted = true;
    result.integrationBoundary.nativePreferencesExecuted = raw.baseFeatureAbsent !== true;
    result.nativeUI = {
      observed: true,
      transitionObserved: true,
      freshInstallRequiredByBuild: true,
      runtimeMode: raw.runtimeMode,
      runtimeClassification: raw.runtimeClassification,
      productionSources: raw.productionSources,
      baseFeatureAbsent: raw.baseFeatureAbsent === true
    };
  } catch (error) {
    result.unsupported = String(error.message || error);
  }
  return result;
}

module.exports = { runCase };
