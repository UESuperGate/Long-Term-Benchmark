export async function runTask08StrictCase(args) {
  const native = args.native || args.context?.native;
  if (!native || typeof native.runTask08StrictUI !== 'function' || typeof args.sharedRunCase !== 'function') {
    return { observed: {}, invariantChecks: [], unsupported: 'Task08 strict device bridge or shared evaluator unavailable' };
  }
  let raw;
  try { raw = await native.runTask08StrictUI(args.caseSpec); }
  catch (error) {
    return { observed: {}, invariantChecks: [], unsupported: `Task08 device runtime failed: ${error.stack || error}` };
  }
  const earlyEntry = raw.productionVariant === 'base' && raw.prefixExecuted === true &&
    raw.entryFailure?.classification === 'required_feature_entry_missing' && raw.eventExecuted === false;
  const nestedEntry = raw.productionVariant === 'timeline' && raw.prefixExecuted === true &&
    raw.entryFailure?.classification === 'required_nested_entry_unreachable' && raw.eventExecuted === false;
  if (raw.failure || !raw.entryExecuted || (!raw.eventExecuted && !earlyEntry && !nestedEntry)) {
    return { observed: {}, invariantChecks: [], evidence: [raw],
      unsupported: `Task08 original application replay incomplete: ${raw.failure?.message || 'entry/event receipt missing'}` };
  }
  if (raw.productionVariant === 'base' && (!raw.basePositiveControl?.roomRendered ||
      !raw.basePositiveControl?.roomSendCompleted || raw.basePositiveControl?.routeAvailable !== false)) {
    return { observed: {}, invariantChecks: [], evidence: [raw],
      unsupported: 'Task08 base common-room positive control is incomplete' };
  }
  if (earlyEntry || nestedEntry) {
    for (const frame of raw.frames) args.trace?.(frame.label, frame);
    return { observed: {}, invariantChecks: [], evidence: [raw],
      observationLevel: 'openharmony_api23_original_application_ui_entry_prefix',
      limitations: ['Only the real common-page prefix executed; thread post-state and invariants are unevaluated.'] };
  }
  if (raw.productionVariant === 'base') return { observed: {}, invariantChecks: [], evidence: [raw],
    unsupported: 'Task08 base legacy projected post-state is withdrawn; require real entry-prefix proof' };
  if (raw.productionVariant === 'timeline') {
    if (!raw.observed || !raw.invariantChecks || !raw.uiAssertions || !Object.keys(raw.uiAssertions).length ||
        !raw.frames?.some(frame => frame.label === 'before_event') ||
        !raw.frames?.some(frame => frame.label === 'after_event') || !raw.actions?.length ||
        raw.actions.some(action => action.executed !== true) ||
        raw.verifiedWindow?.hostVerified !== true || raw.verifiedWindow?.bundleName !== raw.bundleName ||
        raw.launchEvidence?.created !== true || raw.launchEvidence?.destroyed !== true ||
        !raw.productionSources?.some(source => source.path === 'entry/src/main/ets/pages/Index.ets') ||
        raw.productionSources.some(source => !/^[a-f0-9]{64}$/.test(source.sha256)))
      return { observed: {}, invariantChecks: [], unsupported: 'Task08 native timeline replay receipt incomplete' };
    for (const frame of raw.frames) args.trace?.(frame.label, frame);
    return { observed: raw.observed, invariantChecks: raw.invariantChecks, evidence: [raw],
      observationLevel: 'openharmony_api23_original_application_ui_and_original_production_instances',
      limitations: ['Timeline input records and external send failures are fixture controlled; original page, presenter and gateway execute unchanged.'] };
  }
  if (raw.productionVariant !== 'base' && (!raw.finalPositiveControl?.threadOpened ||
      !raw.uiAssertions || !Object.values(raw.uiAssertions).every(Boolean))) {
    return { observed: {}, invariantChecks: [], evidence: [raw],
      unsupported: 'Task08 final original-application UI assertions are incomplete' };
  }
  const domain = await args.sharedRunCase(args);
  domain.evidence = [...(domain.evidence || []), raw];
  domain.observationLevel = 'openharmony_api23_original_application_ui_and_shared_production_domain';
  domain.limitations = ['External network/server delivery is fixture-controlled. Original candidate ArkUI, production presenter/gateway methods, and the shared evaluator execute in one API23 ohosTest process.'];
  return domain;
}
