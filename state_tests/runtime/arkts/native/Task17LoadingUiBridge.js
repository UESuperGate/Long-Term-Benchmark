let configured;
export function configureTask17LoadingUI(probe, bundleName, sourcesJson) {
  configured = { probe, bundleName, sources: JSON.parse(sourcesJson) };
}
export function attachTask17LoadingUI(bridge, taskId, key) {
  if (taskId !== '17_pinned_messages' || key !== 'open_loading') return false;
  if (!configured || typeof bridge.setObservationRecorder !== 'function') throw new Error('Task17 loading recorder unavailable');
  const original = bridge.setObservationRecorder;
  let recorder;
  bridge.setObservationRecorder = function(callback) { recorder = callback; return original.call(this, callback); };
  bridge.bundleName = configured.bundleName;
  bridge.runTask17LoadingUI = async spec => {
    const raw = JSON.parse(await configured.probe(JSON.stringify(spec), configured.bundleName));
    if (raw.taskId !== taskId || raw.caseId !== spec.caseId || raw.traceDigest !== spec.traceDigest) throw new Error('Task17 loading identity mismatch');
    raw.productionSources = configured.sources;
    if (recorder && raw.entryExecuted && raw.readiness?.ready) recorder({ method: 'Task17.originalLoadingPage', available: true,
      bundleName: configured.bundleName, caseId: raw.caseId, traceDigest: raw.traceDigest, sessionId: raw.sessionId,
      frames: raw.frames, actions: raw.actions, productionSources: configured.sources });
    return raw;
  };
  bridge.disposeTask17LoadingUI = () => {
    bridge.setObservationRecorder = original;
    delete bridge.runTask17LoadingUI;
    delete bridge.disposeTask17LoadingUI;
  };
  return true;
}
