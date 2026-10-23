import { CASES } from './CaseData';
import { jsonMap, JsonMap, WaveformPageOwner } from '../feature/WaveformPageOwner';
import { currentWaveformPageOwner } from '../integration/PageOwnerRegistry';

function map(value: Object | undefined): JsonMap {
  return value !== undefined && value !== null && !Array.isArray(value) ? value as JsonMap : {};
}

function fullScale(): number[] {
  const samples: number[] = [];
  for (let index = 0; index < 100; index++) samples.push(32767);
  return samples;
}
function silenceThenFullScale(): number[] {
  const samples: number[] = [];
  for (let index = 0; index < 100; index++) samples.push(index < 50 ? 0 : 32767);
  return samples;
}

function snapshot(owner: WaveformPageOwner): JsonMap {
  return jsonMap(
    ['state', 'persistence', 'effects', 'productionCalls'],
    [owner.currentState(), owner.currentPersistence(), owner.currentEffects(), owner.productionTrace()]
  );
}

async function mountedOwner(): Promise<WaveformPageOwner> {
  for (let attempt = 0; attempt < 100; attempt++) {
    const owner = currentWaveformPageOwner();
    if (owner !== undefined) return owner;
    await new Promise<void>((resolve: () => void): void => { setTimeout(resolve, 50); });
  }
  throw new Error('Index page owner did not mount');
}

function emit(key: string, episode: JsonMap): void {
  const payload = JSON.stringify(episode);
  const chunkSize = 1500;
  const total = Math.ceil(payload.length / chunkSize);
  for (let index = 0; index < total; index++) {
    const chunk = payload.slice(index * chunkSize, (index + 1) * chunkSize);
    console.info(`LTB_RUNTIME_CHUNK:${key}:${index}:${total}:${chunk}`);
  }
}

export async function runRuntimeCase(key: string): Promise<void> {
  const data = map(CASES[key]);
  const given = map(data['given']);
  const event = map(data['event']);
  const owner = await mountedOwner();
  await owner.mount(given);
  const before = snapshot(owner);
  let checkpoint: JsonMap = {};
  switch (key) {
    case 'generate_upload_ready_waveform':
      await owner.generateWaveform(fullScale(), 2000000);
      break;
    case 'audio_upload_waits_for_waveform':
      await owner.startUploadGraph(); checkpoint = snapshot(owner);
      await owner.releaseHeldWaveform(fullScale(), 2000000);
      break;
    case 'mixed_uploads_gate_only_audio':
      await owner.startMixedUploadGraph(); checkpoint = snapshot(owner);
      await owner.releaseMixedAudio(fullScale(), 2000000);
      break;
    case 'outgoing_pointer_carries_waveform':
      await owner.serializeOutgoingPointer();
      break;
    case 'reject_oversized_remote_waveform':
      await owner.validateIncomingEnvelope();
      break;
    case 'persist_valid_sender_waveform':
      await owner.importIncomingAttachment();
      break;
    case 'resample_sender_waveform_without_media':
      await owner.requestRenderableWaveform(fullScale(), 10000000);
      break;
    case 'regenerate_stale_local_waveform':
      await owner.requestRenderableWaveform(fullScale(), 2000000);
      break;
    case 'recover_empty_generation_placeholder':
      await owner.requestRenderableWaveform(silenceThenFullScale(), 4000000);
      break;
    case 'backup_round_trip_sender_waveform':
      await owner.backupRestoreAndRender();
      break;
    default:
      throw new Error(`unknown case key: ${key}`);
  }
  const after = snapshot(owner);
  const reopened = await owner.reopenedPersistence();
  emit(key, jsonMap(
    [
      'schemaVersion', 'taskId', 'caseKey', 'key', 'given', 'event', 'givenEstablished',
      'pageOwnerId', 'commonEntryObserved', 'before', 'checkpoint', 'after', 'observed',
      'productionCalls', 'transitionExecuted', 'reopenedPersistence', 'storageReopened'
    ],
    [
      1, '07_voice_note_waveforms', key, key, given, event, true,
      'Index:WaveformPageOwner', true, before, checkpoint, after, after,
      owner.productionTrace(), true, reopened,
      JSON.stringify(reopened) === JSON.stringify(owner.currentPersistence())
    ]
  ));
}
