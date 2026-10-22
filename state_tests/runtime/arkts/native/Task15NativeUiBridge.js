let configured;
export function configureTask15UI(probe, bundleName, sourcesJson) {
  configured = { probe, bundleName, sources: JSON.parse(sourcesJson) };
}

export function attachTask15UI(bridge, taskId, key) {
  if (taskId !== '15_account_deactivation' || !['capability_gates_entry', 'first_submit_confirms', 'confirm_sends_payload'].includes(key)) return false;
  if (!configured || typeof configured.probe !== 'function' || typeof bridge.setObservationRecorder !== 'function') {
    throw new Error('Task15 native probe/recorder unavailable');
  }
  const original = bridge.setObservationRecorder;
  let recorder;
  bridge.setObservationRecorder = function(callback) { recorder = callback; return original.call(this, callback); };
  bridge.bundleName = configured.bundleName;
  bridge.runTask15UI = async spec => {
    const raw = JSON.parse(await configured.probe(JSON.stringify(spec), configured.bundleName));
    if (raw.taskId !== taskId || raw.caseId !== spec.caseId || raw.traceDigest !== spec.traceDigest) throw new Error('Task15 native identity mismatch');
    raw.productionSources = configured.sources;
    if (recorder && raw.entryExecuted && raw.prerequisite?.rootConfirmed) recorder({
      method: 'Task15.originalPageTransition', available: true, bundleName: configured.bundleName,
      caseId: raw.caseId, traceDigest: raw.traceDigest, sessionId: raw.sessionId,
      frames: raw.frames, actions: raw.actions, productionSources: configured.sources
    });
    return raw;
  };
  bridge.disposeTask15UI = () => {
    bridge.setObservationRecorder = original;
    delete bridge.runTask15UI;
    delete bridge.disposeTask15UI;
  };
  return true;
}
