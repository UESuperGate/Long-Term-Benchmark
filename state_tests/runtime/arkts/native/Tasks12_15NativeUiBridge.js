let configured;

export function configureTasks12To15UI(probe, bundleName, sourcesJson) {
  configured = { probe, bundleName, sources: JSON.parse(sourcesJson) };
}

export function attachTasks12To15UI(bridge, taskId, key) {
  if (taskId !== '12_report_room' || key !== 'blank_reason_disabled') return false;
  if (!configured || !configured.bundleName || typeof configured.probe !== 'function') {
    throw new Error('Original ArkTS page UI probe was not configured');
  }
  if (typeof bridge.setObservationRecorder !== 'function') throw new Error('Native observation recorder is unavailable');
  const original = bridge.setObservationRecorder;
  let recorder;
  bridge.setObservationRecorder = function(callback) {
    recorder = callback;
    return original.call(this, callback);
  };
  bridge.bundleName = configured.bundleName;
  bridge.runTasks12To15UI = async caseSpec => {
    if (caseSpec.taskId !== taskId || caseSpec.key !== key) throw new Error('UI bridge case identity differs');
    const result = JSON.parse(await configured.probe(JSON.stringify(caseSpec), configured.bundleName));
    result.productionSources = configured.sources;
    if (result.taskId !== taskId || result.caseId !== caseSpec.caseId || result.traceDigest !== caseSpec.traceDigest) {
      throw new Error('UI probe returned a different canonical identity');
    }
    // The shared productionLoader recorder adds the ORIGINAL page metadata and
    // actual UI call to evaluateCase's own arrays. No verdict is changed here.
    if (recorder && result.entryExecuted && result.prerequisite?.rootConfirmed) {
      recorder({ method: 'Tasks12To15.originalPageTransition', available: true,
        bundleName: configured.bundleName, caseId: result.caseId, traceDigest: result.traceDigest,
        sessionId: result.sessionId, frames: result.frames, actions: result.actions,
        productionSources: configured.sources });
    }
    return result;
  };
  bridge.disposeTasks12To15UI = () => {
    bridge.setObservationRecorder = original;
    delete bridge.runTasks12To15UI;
    delete bridge.disposeTasks12To15UI;
  };
  return true;
}
