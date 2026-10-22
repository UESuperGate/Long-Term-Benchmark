let configured;

export function configureTask17OwnerUI(probe, bundleName, sourcesJson) {
  configured = { probe, bundleName, sources: JSON.parse(sourcesJson) };
}

export function attachTask17OwnerUI(bridge, taskId, key) {
  if (taskId !== '17_pinned_messages') return false;
  if (!configured || typeof bridge.setObservationRecorder !== 'function') {
    throw new Error('Task17 owner-bound native recorder unavailable');
  }
  const original = bridge.setObservationRecorder;
  let recorder;
  bridge.setObservationRecorder = function(callback) {
    recorder = callback;
    return original.call(this, callback);
  };
  bridge.bundleName = configured.bundleName;
  bridge.runTask17OwnerUI = async spec => {
    const raw = JSON.parse(await configured.probe(JSON.stringify(spec), configured.bundleName));
    if (raw.taskId !== taskId || raw.caseId !== spec.caseId || raw.traceDigest !== spec.traceDigest || raw.key !== key) {
      throw new Error('Task17 owner-bound native identity mismatch');
    }
    raw.productionSources = configured.sources;
    if (recorder && raw.entryExecuted) {
      recorder({ method: 'Task17.ownerBoundNativeRuntime', available: true,
        bundleName: configured.bundleName, caseId: raw.caseId, traceDigest: raw.traceDigest,
        sessionId: raw.sessionId, runtimeMode: raw.runtimeMode, frames: raw.frames,
        actions: raw.actions, productionSources: configured.sources });
    }
    return raw;
  };
  bridge.disposeTask17OwnerUI = () => {
    bridge.setObservationRecorder = original;
    delete bridge.runTask17OwnerUI;
    delete bridge.disposeTask17OwnerUI;
  };
  return true;
}
