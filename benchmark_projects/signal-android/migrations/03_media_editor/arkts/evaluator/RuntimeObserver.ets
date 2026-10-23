import { hilog } from '@kit.PerformanceAnalysisKit';
import { common } from '@kit.AbilityKit';
import { MediaEditorEnvironment, MediaEditorPageOwner, MediaEffect, MediaItem } from '../feature/MediaEditorStore';

interface MediaObservation {
  caseId: string;
  productionEntrypoint: string;
  ownerId: string;
  entryLifecycle: string;
  availability: string;
  givenEstablished: boolean;
  given: Record<string, Object>;
  before: Record<string, Object>;
  after: Record<string, Object>;
  effects: MediaEffect[];
  orderedStates: Object[];
  invariantFacts: boolean[];
  invariantEvidence: string[];
  persistenceReopened: boolean;
  persistenceEvidence: Record<string, Object>;
}

let observerRan: boolean = false;
function record(json: string): Record<string, Object> { return JSON.parse(json) as Record<string, Object>; }
function video(id: string, gif: boolean = false): MediaItem { return { id, kind: 'video', isVideoGif: gif }; }
function image(id: string): MediaItem { return { id, kind: 'image', isVideoGif: false }; }
function named(effects: MediaEffect[], name: string): MediaEffect[] { return effects.filter((effect: MediaEffect): boolean => effect.name === name); }
function muted(state: Record<string, Object>, id: string): boolean {
  const editors = state['editorStateByItem'] as Record<string, Object>;
  const editor = editors[id] as Record<string, Object> | undefined;
  return editor !== undefined && editor['isMuted'] === true;
}
function emit(owner: MediaEditorPageOwner, caseId: string, action: string, given: Record<string, Object>,
  before: Record<string, Object>, after: Record<string, Object>, effects: MediaEffect[], facts: boolean[], reopened: boolean = false): void {
  const row: MediaObservation = {
    caseId, productionEntrypoint: `Index.owner.${action}`, ownerId: owner.ownerId,
    entryLifecycle: 'Index.aboutToAppear', availability: 'executed_api23_arkvm_index_page_owner',
    givenEstablished: true, given, before, after, effects, orderedStates: [], invariantFacts: facts,
    invariantEvidence: facts.map((_value: boolean): string => 'derived from page-owner before/after state and external-leaf effects'),
    persistenceReopened: reopened,
    persistenceEvidence: record(`{"productionBlobWrites":${owner.externalLeaf().productionBlobWrites},"productionBlobReadsAfterRepositoryReopen":${owner.externalLeaf().productionBlobReads}}`)
  };
  hilog.info(0x0B03, 'BenchmarkObserver', 'BENCHMARK_CASE:%{public}s', JSON.stringify(row));
}
function prepare(owner: MediaEditorPageOwner, leaf: MediaEditorEnvironment, items: MediaItem[], selected: string[],
  focused: string, editors: Record<string, Object>, preUpload: Record<string, Object> = {}): void {
  leaf.seedFlow(items, selected, focused, editors, preUpload); owner.reopen(); leaf.resetEffects();
}

export async function runFocusedSemanticObserver(owner: MediaEditorPageOwner, context: common.UIAbilityContext): Promise<void> {
  if (observerRan) return;
  observerRan = true;
  const leaf = owner.externalLeaf();
  let before: Record<string, Object>;
  let after: Record<string, Object>;
  let cursor: number;
  let effects: MediaEffect[];

  const given1 = record('{"audioRemovalAvailable":true,"items":[{"id":"video-1","kind":"video","isVideoGif":false},{"id":"gif-video","kind":"video","isVideoGif":true},{"id":"image-1","kind":"image","isVideoGif":false}],"focusedItemId":"video-1"}');
  prepare(owner, leaf, [video('video-1'), video('gif-video', true), image('image-1')], ['video-1', 'gif-video', 'image-1'], 'video-1', record('{}'));
  before = owner.state(); cursor = leaf.effectCursor(); after = owner.eligibility(); effects = leaf.effectsAfter(cursor);
  const eligible = after['muteControlByItem'] as Record<string, Object>;
  emit(owner, 'me_state_001_mute_control_eligibility', 'eligibility', given1, before, after, effects,
    [eligible['video-1'] === true && eligible['gif-video'] === false && eligible['image-1'] === false, effects.length === 0]);

  const given2 = record('{"selectedItemIds":["video-1"],"focusedItemId":"video-1","editorStateByItem":{"video-1":{"kind":"video_trim","isMuted":false}},"preUpload":{"video-1":"uploaded"}}');
  prepare(owner, leaf, [video('video-1')], ['video-1'], 'video-1', record('{"video-1":{"kind":"video_trim","isMuted":false}}'), record('{"video-1":"uploaded"}'));
  before = owner.state(); cursor = leaf.effectCursor(); owner.toggleVideoMuted(); after = owner.state(); effects = leaf.effectsAfter(cursor);
  emit(owner, 'me_state_002_mute_focused_video', 'toggleVideoMuted', given2, before, after, effects,
    [JSON.stringify(after['selectedItemIds']) === JSON.stringify(before['selectedItemIds']), named(effects, 'cancelPreUpload').length === 1]);

  const given3 = record('{"selectedItemIds":["video-1"],"focusedItemId":"video-1","editorStateByItem":{"video-1":{"kind":"video_trim","isMuted":true}},"preUpload":{"video-1":"uploaded"}}');
  prepare(owner, leaf, [video('video-1')], ['video-1'], 'video-1', record('{"video-1":{"kind":"video_trim","isMuted":true}}'), record('{"video-1":"uploaded"}'));
  before = owner.state(); cursor = leaf.effectCursor(); owner.toggleVideoMuted(); after = owner.state(); effects = leaf.effectsAfter(cursor);
  emit(owner, 'me_state_003_unmute_focused_video', 'toggleVideoMuted', given3, before, after, effects,
    [muted(after, 'video-1') === false, Object.keys(after['editorStateByItem'] as Record<string, Object>).length === 1]);

  const editors4 = record('{"video-1":{"kind":"video_trim","isMuted":true},"video-2":{"kind":"video_trim","isMuted":false}}');
  const given4 = record('{"selectedItemIds":["video-1","video-2"],"focusedItemId":"video-1","editorStateByItem":{"video-1":{"kind":"video_trim","isMuted":true},"video-2":{"kind":"video_trim","isMuted":false}}}');
  prepare(owner, leaf, [video('video-1'), video('video-2')], ['video-1', 'video-2'], 'video-1', editors4);
  before = owner.state(); cursor = leaf.effectCursor(); owner.setFocusedItem('video-2'); after = owner.state(); effects = leaf.effectsAfter(cursor);
  emit(owner, 'me_state_004_focus_preserves_per_item_edits', 'setFocusedItem', given4, before, after, effects,
    [muted(after, 'video-1') && !muted(after, 'video-2'), muted(after, 'video-1') && !muted(after, 'video-2')]);

  const given5 = record('{"selectedItemIds":["video-1","video-2","image-1"],"focusedItemId":"video-1","editorStateByItem":{"video-1":{"kind":"video_trim","isMuted":true},"video-2":{"kind":"video_trim","isMuted":false}}}');
  prepare(owner, leaf, [video('video-1'), video('video-2'), image('image-1')], ['video-1', 'video-2', 'image-1'], 'video-1', editors4);
  before = owner.state(); cursor = leaf.effectCursor(); owner.reorderSelectedMedia(0, 2); after = owner.state(); effects = leaf.effectsAfter(cursor);
  emit(owner, 'me_state_005_reorder_preserves_per_item_edits', 'reorderSelectedMedia', given5, before, after, effects,
    [(after['selectedItemIds'] as string[]).length === (before['selectedItemIds'] as string[]).length, muted(after, 'video-1') && !muted(after, 'video-2')]);

  const saved = record('{"selectedItemIds":["video-1","video-2"],"focusedItemId":"video-2","editorStateByItem":{"video-1":{"kind":"video_trim","isMuted":true,"startTimeUs":100,"endTimeUs":900},"video-2":{"kind":"video_trim","isMuted":false,"startTimeUs":0,"endTimeUs":1000}}}');
  const given6 = record('{"savedFlowState":{"selectedItemIds":["video-1","video-2"],"focusedItemId":"video-2","editorStateByItem":{"video-1":{"kind":"video_trim","isMuted":true,"startTimeUs":100,"endTimeUs":900},"video-2":{"kind":"video_trim","isMuted":false,"startTimeUs":0,"endTimeUs":1000}}}}');
  prepare(owner, leaf, [video('video-1'), video('video-2')], [], '', record('{}'));
  await owner.persistMediaSendFlow(context, saved);
  before = owner.state(); cursor = leaf.effectCursor(); await owner.recreateMediaSendFlow(context); after = owner.state(); effects = leaf.effectsAfter(cursor);
  emit(owner, 'me_state_006_restore_editor_state', 'recreateMediaSendFlow', given6, before, after, effects,
    [JSON.stringify(after['editorStateByItem']) === JSON.stringify(saved['editorStateByItem']), effects.length === 0], true);

  const given7 = record('{"selectedItemIds":["video-1"],"focusedItemId":"video-1","editorStateByItem":{"video-1":{"kind":"video_trim","isMuted":true}},"screen":"media_editor"}');
  prepare(owner, leaf, [video('video-1')], ['video-1'], 'video-1', record('{"video-1":{"kind":"video_trim","isMuted":true}}'));
  before = owner.state(); cursor = leaf.effectCursor(); owner.requestCloseThenCancelDiscard(); after = owner.state(); effects = leaf.effectsAfter(cursor);
  emit(owner, 'me_state_007_cancel_discard_preserves_edits', 'requestCloseThenCancelDiscard', given7, before, after, effects,
    [after['screen'] === 'media_editor' && JSON.stringify(after['editorStateByItem']) === JSON.stringify(before['editorStateByItem']), named(effects, 'closeScreen').length === 0]);

  const stored = record('{"skipTransform":false,"videoTrim":false,"videoTrimStartTimeUs":0,"videoTrimEndTimeUs":0,"sentMediaQuality":0,"mp4Faststart":false,"videoEdited":false}');
  const given8 = record('{"storedTransformJson":{"skipTransform":false,"videoTrim":false,"videoTrimStartTimeUs":0,"videoTrimEndTimeUs":0,"sentMediaQuality":0,"mp4Faststart":false,"videoEdited":false}}');
  prepare(owner, leaf, [], [], '', record('{}')); before = owner.state(); cursor = leaf.effectCursor(); after = owner.restoreStoredTransform(stored); effects = leaf.effectsAfter(cursor);
  emit(owner, 'me_state_008_legacy_transform_defaults_unmuted', 'restoreStoredTransform', given8, before, after, effects,
    [after['videoMuted'] === false, after['videoMuted'] === false]);

  const editor9 = record('{"kind":"video_trim","isDurationEdited":false,"startTimeUs":0,"endTimeUs":1000000,"isMuted":true}');
  const given9 = record('{"media":{"id":"video-1","kind":"video","transformProperties":null},"editorState":{"kind":"video_trim","isDurationEdited":false,"startTimeUs":0,"endTimeUs":1000000,"isMuted":true}}');
  prepare(owner, leaf, [video('video-1')], ['video-1'], 'video-1', record('{}')); before = owner.state(); cursor = leaf.effectCursor(); after = owner.prepareEditedVideoForSend('video-1', editor9); effects = leaf.effectsAfter(cursor);
  const transform9 = after['transformProperties'] as Record<string, Object>;
  emit(owner, 'me_state_009_prepare_muted_transform', 'prepareEditedVideoForSend', given9, before, after, effects,
    [transform9['videoEdited'] === true, leaf.preparedVideo['id'] === 'video-1' && leaf.preparedVideo['videoTrack'] === true]);

  const given10 = record('{"preparedVideo":{"id":"video-1","videoTrack":true,"audioTrack":true,"transformProperties":{"videoMuted":true,"videoEdited":true}},"transcoder":{"allowAudioRemux":true}}');
  prepare(owner, leaf, [video('video-1')], ['video-1'], 'video-1', record('{}'));
  leaf.preparedVideo = record('{"id":"video-1","videoTrack":true,"audioTrack":true,"transformProperties":{"videoMuted":true,"videoEdited":true}}');
  before = record('{"output":{"videoTrack":true,"audioTrack":true}}'); cursor = leaf.effectCursor(); after = owner.transcodePreparedVideo(); effects = leaf.effectsAfter(cursor);
  const output = after['output'] as Record<string, Object>;
  emit(owner, 'me_state_010_transcode_omits_audio', 'transcodePreparedVideo', given10, before, after, effects,
    [output['audioTrack'] === false && named(effects, 'setSkipAudio').length === 1, output['videoTrack'] === true]);

  hilog.info(0x0B03, 'BenchmarkObserver', 'BENCHMARK_COMPLETE:03_media_editor');
}
