let configured;

export function configureTask08StrictUI(probe, configJson, sourcesJson) {
  configured = { probe, config: JSON.parse(configJson), sources: JSON.parse(sourcesJson) };
}

export function attachTask08StrictUI(bridge, taskId) {
  if (taskId !== '08_threads') return false;
  if (!configured || typeof configured.probe !== 'function' || typeof bridge.setObservationRecorder !== 'function') {
    throw new Error('Task08 strict UI bridge unavailable');
  }
  const original = bridge.setObservationRecorder;
  let recorder;
  bridge.setObservationRecorder = function(callback) { recorder = callback; return original.call(this, callback); };
  bridge.runTask08StrictUI = async spec => {
    const raw = JSON.parse(await configured.probe(JSON.stringify(spec), configured.config.bundleName));
    if (raw.taskId !== taskId || raw.caseId !== spec.caseId || raw.traceDigest !== spec.traceDigest ||
      raw.bundleName !== configured.config.bundleName || raw.role !== configured.config.role) {
      throw new Error('Task08 strict UI evidence identity mismatch');
    }
    raw.productionSources = configured.sources;
    if (recorder && raw.entryExecuted) recorder({ method: 'Task08Strict.originalApplicationRuntime',
      available: !raw.failure, role: raw.role, bundleName: raw.bundleName, caseId: raw.caseId,
      traceDigest: raw.traceDigest, sessionId: raw.sessionId, frames: raw.frames,
      actions: raw.actions, productionSources: configured.sources });
    return raw;
  };
  bridge.disposeTask08StrictUI = () => {
    bridge.setObservationRecorder = original;
    delete bridge.runTask08StrictUI;
    delete bridge.disposeTask08StrictUI;
  };
  return true;
}
