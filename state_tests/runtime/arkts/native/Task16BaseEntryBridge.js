let configured;
let evidence;

export function configureTask16BaseEntry(probe, bundleName, sourcesJson, releaseLaunch) {
  if (configured) throw new Error('Task16 base entry probe already configured');
  configured = { probe, bundleName, sources: JSON.parse(sourcesJson), releaseLaunch };
}

export function attachTask16BaseEntry(bridge, taskId) {
  if (taskId !== '16_identity_reset') return false;
  if (!configured || typeof configured.probe !== 'function' || typeof bridge.setObservationRecorder !== 'function') {
    throw new Error('Task16 base entry probe/recorder is not configured');
  }
  const original = bridge.setObservationRecorder;
  let recorder;
  bridge.setObservationRecorder = function(callback) {
    recorder = callback;
    return original.call(this, callback);
  };
  bridge.runTask16BaseUI = async () => {
    if (!evidence) evidence = configured.probe(configured.bundleName);
    const raw = JSON.parse(await evidence);
    raw.productionSources = configured.sources;
    if (recorder && raw.entryExecuted) {
      recorder({ method: 'Task16.runtimeEntryClassification', available: true,
        bundleName: configured.bundleName, classification: raw.classification,
        frames: raw.frames, actions: raw.actions, productionSources: configured.sources });
    }
    return raw;
  };
  bridge.disposeTask16BaseUI = async () => {
    bridge.setObservationRecorder = original;
    delete bridge.runTask16BaseUI;
    delete bridge.disposeTask16BaseUI;
    if (configured.releaseLaunch) await configured.releaseLaunch(configured.bundleName);
  };
  return true;
}
