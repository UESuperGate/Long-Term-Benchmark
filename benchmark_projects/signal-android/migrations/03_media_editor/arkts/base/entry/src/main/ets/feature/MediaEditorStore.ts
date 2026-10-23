import { common } from '@kit.AbilityKit';
import { preferences } from '@kit.ArkData';

export interface MediaItem { id: string; kind: string; isVideoGif: boolean; }
export interface MediaEffect { name: string; itemId?: string; itemIds?: string[]; value?: boolean; count?: number; }
function clone(value: Object): Record<string, Object> { return JSON.parse(JSON.stringify(value)) as Record<string, Object>; }
export class MediaEditorEnvironment {
  items: MediaItem[] = []; selectedItemIds: string[] = []; focusedItemId: string = '';
  editorStateByItem: Record<string, Object> = {}; preUpload: Record<string, Object> = {};
  savedFlowBlob: string = '{}'; effects: MediaEffect[] = []; preparedVideo: Record<string, Object> = {};
  productionBlobWrites: number = 0; productionBlobReads: number = 0;
  seedFlow(items: MediaItem[], selected: string[], focused: string, editors: Record<string, Object>, preUpload: Record<string, Object> = {}): void {
    this.items = items; this.selectedItemIds = [...selected]; this.focusedItemId = focused;
    this.editorStateByItem = clone(editors); this.preUpload = clone(preUpload); this.effects = [];
  }
  resetEffects(): void { this.effects = []; }
  effectCursor(): number { return this.effects.length; }
  effectsAfter(cursor: number): MediaEffect[] { return this.effects.slice(cursor); }
  record(effect: MediaEffect): void { this.effects.push(effect); }
}
export class MediaEditorRepository {
  private readonly leaf: MediaEditorEnvironment;
  constructor(leaf: MediaEditorEnvironment) { this.leaf = leaf; }
  loadFlow(): Record<string, Object> { return { selectedItemIds: [...this.leaf.selectedItemIds], focusedItemId: this.leaf.focusedItemId, editorStateByItem: clone(this.leaf.editorStateByItem) }; }
  async persistFlow(context: common.UIAbilityContext, flow: Record<string, Object>): Promise<void> {
    const store = await preferences.getPreferences(context, 'signal_media_editor_flow');
    await store.clear(); await store.put('flow', JSON.stringify(flow)); await store.flush(); this.leaf.productionBlobWrites += 1;
  }
  async reopenPersistedFlow(context: common.UIAbilityContext): Promise<Record<string, Object>> {
    const reopened = await preferences.getPreferences(context, 'signal_media_editor_flow');
    await reopened.get('flow', '{}'); this.leaf.productionBlobReads += 1;
    return { selectedItemIds: [], focusedItemId: '', editorStateByItem: {} };
  }
  closeScreen(): void { this.leaf.record({ name: 'closeScreen', count: 1 }); }
  applyVideoTransform(itemId: string): void { this.leaf.record({ name: 'applyVideoTransform', itemId, count: 1 }); }
  convertVideo(): void { this.leaf.record({ name: 'convertVideo', count: 1 }); }
}
export class MediaEditorStore {
  private selectedItemIds: string[] = []; private focusedItemId: string = '';
  private editorStateByItem: Record<string, Object> = {}; private screen: string = 'media_editor';
  private readonly repository: MediaEditorRepository; private readonly leaf: MediaEditorEnvironment;
  constructor(repository: MediaEditorRepository, leaf: MediaEditorEnvironment) { this.repository = repository; this.leaf = leaf; }
  open(): void { this.applyFlow(this.repository.loadFlow()); }
  private applyFlow(flow: Record<string, Object>): void {
    this.selectedItemIds = [...(flow['selectedItemIds'] as string[])]; this.focusedItemId = String(flow['focusedItemId']);
    this.editorStateByItem = clone(flow['editorStateByItem']); this.screen = 'media_editor';
  }
  eligibility(): Record<string, Object> { const result: Record<string, Object> = {}; this.leaf.items.forEach((item: MediaItem): void => { result[item.id] = false; }); return { muteControlByItem: result }; }
  toggleVideoMuted(): void {}
  setFocusedItem(itemId: string): void { this.focusedItemId = itemId; this.editorStateByItem = {}; }
  reorderSelectedMedia(fromIndex: number, toIndex: number): void { const next = [...this.selectedItemIds]; const moved = next.splice(fromIndex, 1)[0]; next.splice(toIndex, 0, moved); this.selectedItemIds = next; this.editorStateByItem = {}; }
  async recreateFromPersistence(context: common.UIAbilityContext): Promise<void> { this.applyFlow(await this.repository.reopenPersistedFlow(context)); }
  requestCloseThenCancelDiscard(): void { this.screen = 'closed'; this.repository.closeScreen(); }
  state(): Record<string, Object> { const focused = this.editorStateByItem[this.focusedItemId]; return { selectedItemIds: [...this.selectedItemIds], focusedItemId: this.focusedItemId, focusedEditorState: focused === undefined ? {} : clone(focused), editorStateByItem: clone(this.editorStateByItem), screen: this.screen }; }
  restoreStoredTransform(stored: Record<string, Object>): Record<string, Object> { return { videoMuted: true, videoEdited: stored['videoEdited'] === true, videoTrim: stored['videoTrim'] === true, sentMediaQuality: Number(stored['sentMediaQuality']) }; }
  prepareEditedVideoForSend(itemId: string, editor: Record<string, Object>): Record<string, Object> {
    const durationEdited = editor['isDurationEdited'] === true;
    const transform: Record<string, Object> = { videoTrim: durationEdited, videoTrimStartTimeUs: 0, videoTrimEndTimeUs: 0, videoMuted: false, videoEdited: durationEdited };
    this.repository.applyVideoTransform(itemId); this.leaf.preparedVideo = { id: itemId, videoTrack: true, audioTrack: true, transformProperties: clone(transform) }; return { transformProperties: transform };
  }
  transcodePreparedVideo(): Record<string, Object> { this.repository.convertVideo(); return { output: { videoTrack: true, audioTrack: true } }; }
}
export class MediaEditorPageOwner {
  readonly ownerId: string = `media-editor-owner-${Date.now()}`;
  private readonly leaf: MediaEditorEnvironment = new MediaEditorEnvironment();
  private repository: MediaEditorRepository = new MediaEditorRepository(this.leaf);
  private store: MediaEditorStore = new MediaEditorStore(this.repository, this.leaf);
  externalLeaf(): MediaEditorEnvironment { return this.leaf; }
  appear(): void { this.store.open(); }
  reopen(): void { this.repository = new MediaEditorRepository(this.leaf); this.store = new MediaEditorStore(this.repository, this.leaf); this.store.open(); }
  eligibility(): Record<string, Object> { return this.store.eligibility(); }
  toggleVideoMuted(): void { this.store.toggleVideoMuted(); }
  setFocusedItem(id: string): void { this.store.setFocusedItem(id); }
  reorderSelectedMedia(from: number, to: number): void { this.store.reorderSelectedMedia(from, to); }
  async persistMediaSendFlow(context: common.UIAbilityContext, flow: Record<string, Object>): Promise<void> { await this.repository.persistFlow(context, flow); }
  async recreateMediaSendFlow(context: common.UIAbilityContext): Promise<void> { this.repository = new MediaEditorRepository(this.leaf); this.store = new MediaEditorStore(this.repository, this.leaf); await this.store.recreateFromPersistence(context); }
  requestCloseThenCancelDiscard(): void { this.store.requestCloseThenCancelDiscard(); }
  restoreStoredTransform(value: Record<string, Object>): Record<string, Object> { return this.store.restoreStoredTransform(value); }
  prepareEditedVideoForSend(id: string, editor: Record<string, Object>): Record<string, Object> { return this.store.prepareEditedVideoForSend(id, editor); }
  transcodePreparedVideo(): Record<string, Object> { return this.store.transcodePreparedVideo(); }
  state(): Record<string, Object> { return this.store.state(); }
}

