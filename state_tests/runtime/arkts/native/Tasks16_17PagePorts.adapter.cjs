'use strict';
async function runCase(args) {
  const raw = await args.native.runPagePortsUI({ taskId: args.taskId, ...args.caseSpec });
  const result = { observed: raw.observed, invariantChecks: raw.invariantChecks,
    evidence: [{ nativePagePorts: raw }], observationLevel: raw.integrationTier === 'actual_page_physical_prefix'
      ? 'native_original_page_physical_prefix' : 'native_original_page_controlled_external_SDK',
    integrationTier: raw.integrationTier, liveMatrixSdkOrServerVerified: false };
  for (const frame of raw.frames) args.trace('page_sdk_' + frame.label, frame);
  if (raw.integrationTier === 'actual_page_physical_prefix') {
    // Independent v3 eligibility/physical evidence verifier, not this marker, decides admission.
    result.unsupported = 'Physical prefix requires independent reviewed full-input eligibility v3';
    result.unevaluatedInvariants = raw.unevaluatedInvariants;
  }
  if (raw.failure || !raw.eventExecuted) result.unsupported = String(raw.failure?.message || 'Incomplete page/SDK transition');
  return result;
}
module.exports = { runCase };
