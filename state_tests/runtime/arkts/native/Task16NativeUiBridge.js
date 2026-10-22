let configured;
export function configureTask16UI(probe, bundleName, sourcesJson) {
  configured = { probe, bundleName, sources: JSON.parse(sourcesJson) };
}
export function attachTask16UI(bridge, taskId, key) {
  const keys = ['continue_requests_confirmation', 'dismiss_confirmation', 'confirm_starts_handle',
    'password_handle_routes', 'oidc_handle_routes_and_resets', 'handle_failure_recovers',
    'password_submit_calls_handle', 'password_failure_clears_on_edit',
    'success_waits_for_verification', 'cancel_cleans_up'];
  if (taskId !== '16_identity_reset' || !keys.includes(key)) return false;
  if (!configured || typeof bridge.setObservationRecorder !== 'function') throw new Error('Task16 native recorder unavailable');
  const original = bridge.setObservationRecorder;
  let recorder;
  bridge.setObservationRecorder = function(callback) { recorder = callback; return original.call(this, callback); };
  bridge.bundleName = configured.bundleName;
  bridge.runTask16UI = async spec => {
    const raw = JSON.parse(await configured.probe(JSON.stringify(spec), configured.bundleName));
    if (raw.taskId !== taskId || raw.caseId !== spec.caseId || raw.traceDigest !== spec.traceDigest) throw new Error('Task16 UI identity mismatch');
    raw.productionSources = configured.sources;
    if (recorder && raw.entryExecuted && (raw.readiness?.ready || raw.basePositiveControl?.rendered)) recorder({ method: 'Task16.originalIdentityResetPage', available: true,
      bundleName: configured.bundleName, caseId: raw.caseId, traceDigest: raw.traceDigest, sessionId: raw.sessionId,
      frames: raw.frames, actions: raw.actions, productionSources: configured.sources });
    return raw;
  };
  bridge.disposeTask16UI = () => {
    bridge.setObservationRecorder = original;
    delete bridge.runTask16UI;
    delete bridge.disposeTask16UI;
  };
  return true;
}
