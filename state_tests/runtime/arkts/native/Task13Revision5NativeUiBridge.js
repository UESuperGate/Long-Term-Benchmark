import { loadTask13Revision5Production } from './Task13Revision5NativeUi';

let configured;

export function configureTask13Revision5UI(probe, configJson, sourcesJson) {
  configured = { probe, config: JSON.parse(configJson), sources: JSON.parse(sourcesJson) };
}

export function attachTask13Revision5UI(bridge, taskId) {
  if (taskId !== '13_user_verification') return false;
  if (!configured || typeof configured.probe !== 'function' || typeof bridge.setObservationRecorder !== 'function') {
    throw new Error('Task13 revision5 UI bridge unavailable');
  }
  const original = bridge.setObservationRecorder;
  let recorder;
  bridge.setObservationRecorder = function(callback) { recorder = callback; return original.call(this, callback); };
  bridge.bundleName = configured.config.bundleName;
  bridge.task13Revision5Role = configured.config.role;
  bridge.task13ProductionFeature = configured.config.productionFeaturePath;
  bridge.loadTask13Production = loadTask13Revision5Production;
  bridge.runTask13Revision5UI = async spec => {
    const raw = JSON.parse(await configured.probe(JSON.stringify(spec), configured.config.bundleName));
    if (raw.taskId !== taskId || raw.caseId !== spec.caseId || raw.traceDigest !== spec.traceDigest ||
      raw.bundleName !== configured.config.bundleName || raw.role !== configured.config.role) {
      throw new Error('Task13 revision5 UI evidence identity mismatch');
    }
    raw.productionSources = configured.sources;
    if (recorder && raw.entryExecuted) recorder({ method: 'Task13Revision5.originalProfileRuntime',
      available: true, role: raw.role, bundleName: raw.bundleName, caseId: raw.caseId,
      traceDigest: raw.traceDigest, sessionId: raw.sessionId, frames: raw.frames,
      actions: raw.actions, entryAttempt: raw.entryAttempt, launchEvidence: raw.launchEvidence,
      launchCleanup: raw.launchCleanup, sdkInputReceipts: raw.sdkInputReceipts,
      oldTimelinePositiveControl: raw.oldTimelinePositiveControl,
      baseStreamPositiveControl: raw.baseStreamPositiveControl,
      semanticTier: raw.semanticTier, ownerCleanup: raw.ownerCleanup,
      pendingSdkPayload: raw.pendingSdkPayload,
      withdrawPositiveControl: raw.withdrawPositiveControl,
      productionSources: configured.sources });
    return raw;
  };
  bridge.disposeTask13Revision5UI = () => {
    bridge.setObservationRecorder = original;
    delete bridge.runTask13Revision5UI;
    delete bridge.loadTask13Production;
    delete bridge.disposeTask13Revision5UI;
  };
  return true;
}
