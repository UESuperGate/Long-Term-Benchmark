let configured;
export function configureTask12PartialUI(probe, bundleName, sourcesJson) {
  configured = { probe, bundleName, sources: JSON.parse(sourcesJson) };
}
export function attachTask12PartialUI(bridge, taskId, key) {
  if (taskId !== '12_report_room' || key !== 'leave_failure_is_partial') return false;
  if (!configured || typeof bridge.setObservationRecorder !== 'function') throw new Error('Task12 partial UI recorder unavailable');
  const original = bridge.setObservationRecorder;
  let recorder;
  bridge.setObservationRecorder = function(callback) { recorder = callback; return original.call(this, callback); };
  bridge.bundleName = configured.bundleName;
  bridge.runTask12PartialUI = async spec => {
    const raw = JSON.parse(await configured.probe(JSON.stringify(spec), configured.bundleName));
    if (raw.taskId !== taskId || raw.caseId !== spec.caseId || raw.traceDigest !== spec.traceDigest) throw new Error('Task12 partial UI identity mismatch');
    raw.productionSources = configured.sources;
    if (recorder && raw.entryExecuted && raw.prerequisite?.rootConfirmed) recorder({ method: 'Task12.partialFailureOriginalPage',
      available: true, bundleName: configured.bundleName, caseId: raw.caseId, traceDigest: raw.traceDigest,
      sessionId: raw.sessionId, frames: raw.frames, actions: raw.actions, productionSources: configured.sources });
    return raw;
  };
  bridge.disposeTask12PartialUI = () => {
    bridge.setObservationRecorder = original;
    delete bridge.runTask12PartialUI;
    delete bridge.disposeTask12PartialUI;
  };
  return true;
}
