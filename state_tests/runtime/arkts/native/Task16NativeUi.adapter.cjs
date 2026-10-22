'use strict';

const finalFeature = 'entry/src/main/ets/features/IdentityResetFeature.ets';
const baseFeature = 'entry/src/main/ets/features/SecureBackupBase.ets';
const page = 'entry/src/main/ets/pages/Index.ets';
const keys = new Set([
  'continue_requests_confirmation',
  'dismiss_confirmation',
  'confirm_starts_handle',
  'password_handle_routes',
  'oidc_handle_routes_and_resets',
  'handle_failure_recovers',
  'password_submit_calls_handle',
  'password_failure_clears_on_edit',
  'success_waits_for_verification',
  'cancel_cleans_up'
]);
const requireEvidence = (condition, message) => {
  if (!condition) throw new Error(message);
};

async function runCase(args) {
  const result = {
    observed: {},
    invariantChecks: [],
    evidence: [],
    observationLevel: 'openharmony_api23_native_candidate_ui_and_production_runtime',
    integrationBoundary: {
      appEntryExecuted: false,
      externalServicesExecuted: false,
      boundary: 'Original ArkUI page and original Task16 presenter/manager/demo SDK handle on API23; evaluator only configures the SDK boundary result.'
    }
  };
  try {
    const spec = args.caseSpec, native = args.native || args.context?.native;
    requireEvidence(args.taskId === '16_identity_reset' && keys.has(spec.key), 'Unsupported Task16 UI case');
    const raw = await native.runTask16UI(spec);
    result.evidence.push({ nativePageTransition: raw });
    for (const frame of raw.frames || []) args.trace?.('task16_ui_' + frame.label, frame);
    requireEvidence(raw.caseId === spec.caseId && raw.taskId === args.taskId && raw.traceDigest === spec.traceDigest &&
      /^[a-f0-9]{64}$/.test(raw.traceDigest) && raw.entryExecuted && raw.eventExecuted && !raw.failure,
    'Original Task16 UI transition incomplete: ' + JSON.stringify(raw.failure || {}));
    requireEvidence(raw.frames?.some(frame => frame.label === 'before_event') &&
      raw.frames.some(frame => frame.label === 'after_event'), 'Ordered before/after native checkpoints unavailable');
    requireEvidence(raw.actions?.length > 0 && raw.actions.every(action => action.executed &&
      action.sessionId === raw.sessionId), 'Executed native action receipts unavailable');
    requireEvidence(raw.frames.every(frame => frame.sessionId === raw.sessionId && frame.bundleName === native.bundleName &&
      frame.windowIdentity?.focused && frame.windowIdentity.hostVerified && frame.windowIdentity.bundleName === native.bundleName &&
      frame.windowIdentity.ability?.name === 'EntryAbility' && frame.windowIdentity.ability.moduleName === 'entry' &&
      ['pages/Index', 'pages/Index.ets'].includes(frame.windowIdentity.routeName)),
    'Original Task16 ability/window/route identity changed');

    const sourcePaths = raw.productionSources?.map(item => item.path) || [];
    requireEvidence(sourcePaths.includes(page), 'Original Task16 page provenance missing');
    if (raw.baseFeatureAbsent) {
      requireEvidence(raw.basePositiveControl?.rendered && raw.basePositiveControl.enabledBackupThroughActualUi,
        'Base positive control did not execute');
      const base = await args.load(baseFeature);
      const presenter = new base.SecureBackupBasePresenter();
      presenter.enableBackup();
      requireEvidence(presenter.backupState === 'enabled', 'Base production presenter positive control failed');
    } else {
      requireEvidence(sourcePaths.includes(finalFeature), 'Original Task16 final feature provenance missing');
      await args.load(finalFeature);
      const presenterFrames = raw.frames.filter(frame => frame.presenter?.available);
      requireEvidence(presenterFrames.length > 0 && presenterFrames.every(frame => frame.presenter.originalManager &&
        frame.presenter.originalService && frame.presenter.binding?.importCompleted &&
        frame.presenter.binding.productionModuleUrl === '@bundle:' + native.bundleName + '/entry/ets/features/IdentityResetFeature') &&
        presenterFrames.every(frame => frame.presenter.managerId === presenterFrames[0].presenter.managerId &&
          frame.presenter.instanceId === presenterFrames[0].presenter.instanceId),
      'Original Task16 presenter/manager/service identity missing');
    }

    result.observed = raw.observed;
    result.invariantChecks = raw.invariantChecks;
    result.integrationBoundary.appEntryExecuted = true;
    result.nativeUI = {
      observed: true,
      transitionObserved: true,
      freshInstallRequiredByBuild: true,
      productionSources: raw.productionSources,
      baseFeatureAbsent: raw.baseFeatureAbsent === true
    };
  } catch (error) {
    result.unsupported = String(error.message || error);
  }
  return result;
}

module.exports = { runCase };
