import { common } from '@kit.AbilityKit';
import { preferences } from '@kit.ArkData';
import { ExploreInput, ExploreLeaf } from '../integration/ExplorePageIntegration';

function clone(value: Record<string, Object>): Record<string, Object> {
  return JSON.parse(JSON.stringify(value)) as Record<string, Object>;
}

export class LegacyExploreStore {
  private state: Record<string, Object>;
  private persistence: Record<string, Object>;
  private leaf: ExploreLeaf;
  private store: preferences.Preferences;

  private constructor(store: preferences.Preferences, input: ExploreInput) {
    this.store = store;
    this.state = clone(input.state);
    this.persistence = clone(input.persistence);
    this.leaf = input.leaf;
  }

  static async create(context: common.UIAbilityContext, input: ExploreInput): Promise<LegacyExploreStore> {
    const store = await preferences.getPreferences(context, 'explore_feed');
    await store.clear();
    await store.put('snapshot', JSON.stringify(input.persistence));
    await store.flush();
    return new LegacyExploreStore(store, input);
  }

  async recreateHomeSurface(): Promise<void> {}
  async selectHomeTab(_tab: string): Promise<void> {}
  async retryCommunityLoad(): Promise<void> {}
  async retryCommunityLoadMore(): Promise<void> {}
  async resumeHomeSurface(): Promise<void> {}
  async finishInterestEditing(): Promise<void> {}
  async retryForYouLoad(): Promise<void> {}
  async confirmAllModulesOff(): Promise<void> {}

  currentState(): Record<string, Object> { return clone(this.state); }
  currentPersistence(): Record<string, Object> { return clone(this.persistence); }
}
