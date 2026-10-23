import { common } from '@kit.AbilityKit';
import { preferences } from '@kit.ArkData';
import { SavedInput } from '../integration/SavedPageIntegration';

function clone(value: Record<string, Object>): Record<string, Object> {
  return JSON.parse(JSON.stringify(value)) as Record<string, Object>;
}

export class LegacySavedStore {
  private state: Record<string, Object>;
  private persistence: Record<string, Object>;

  private constructor(input: SavedInput) {
    this.state = clone(input.state);
    this.persistence = clone(input.persistence);
  }

  static async create(context: common.UIAbilityContext, input: SavedInput): Promise<LegacySavedStore> {
    const store = await preferences.getPreferences(context, 'saved_surface');
    await store.clear();
    await store.put('snapshot', JSON.stringify(input.persistence));
    await store.flush();
    return new LegacySavedStore(input);
  }

  async openSavedSurface(): Promise<void> {}
  async selectSavedTab(_tab: string): Promise<void> {}
  async enterSavedSearchQuery(_query: string, _elapsedMillis: number): Promise<void> {}
  async selectArticleFilter(_filter: string): Promise<void> {}
  async selectAllVisibleRows(): Promise<void> {}
  async openSaveArticleSheet(): Promise<void> {}
  async cancelUnsaveConfirmation(): Promise<void> {}
  async undoArticleDeletion(): Promise<void> {}
  async resumeQueuedCollectionToggle(): Promise<void> {}
  async retryPullToRefreshAndCompleteSync(): Promise<void> {}
  currentState(): Record<string, Object> { return clone(this.state); }
  currentPersistence(): Record<string, Object> { return clone(this.persistence); }
}
