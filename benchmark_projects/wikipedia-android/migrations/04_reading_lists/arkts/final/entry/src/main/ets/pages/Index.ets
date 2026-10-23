import { common } from '@kit.AbilityKit';
import { CallbackSavedPageOwner, SavedInput, SavedPageOwner } from '../integration/SavedPageIntegration';
import { SavedCollectionsStore } from '../model/SavedCollectionsStore';

@Entry
@Component
struct Index {
  @State selectedTab: string = 'ALL_ARTICLES';
  @State phase: string = 'idle';
  private store?: SavedCollectionsStore;
  private runtimeOwnerId: string = 'SavedIndex:' + String(Date.now());

  async aboutToAppear(): Promise<void> {
  }

  private syncSurface(): void {
    const state = this.store?.currentState();
    this.selectedTab = String(state?.['selectedTab'] ?? 'ALL_ARTICLES');
    this.phase = String(state?.['phase'] ?? 'content');
  }

  createRuntimeOwner(): SavedPageOwner {
    return new CallbackSavedPageOwner(
      async (context: common.UIAbilityContext, input: SavedInput): Promise<void> => {
        this.store = await SavedCollectionsStore.create(context, input);
        this.syncSurface();
      },
      [
        async (): Promise<void> => { await this.store?.openSavedSurface(); this.syncSurface(); },
        async (tab: Object): Promise<void> => { await this.store?.selectSavedTab(String(tab)); this.syncSurface(); },
        async (query: Object, elapsed: Object): Promise<void> => {
          await this.store?.enterSavedSearchQuery(String(query), Number(elapsed)); this.syncSurface();
        },
        async (filter: Object): Promise<void> => {
          await this.store?.selectArticleFilter(String(filter)); this.syncSurface();
        },
        async (): Promise<void> => { await this.store?.selectAllVisibleRows(); this.syncSurface(); },
        async (): Promise<void> => { await this.store?.openSaveArticleSheet(); this.syncSurface(); },
        async (): Promise<void> => { await this.store?.cancelUnsaveConfirmation(); this.syncSurface(); },
        async (): Promise<void> => { await this.store?.undoArticleDeletion(); this.syncSurface(); },
        async (): Promise<void> => { await this.store?.resumeQueuedCollectionToggle(); this.syncSurface(); },
        async (): Promise<void> => { await this.store?.retryPullToRefreshAndCompleteSync(); this.syncSurface(); }
      ],
      (): Record<string, Object> => this.store?.currentState() ?? {},
      (): Record<string, Object> => this.store?.currentPersistence() ?? {},
      (): boolean => true,
      (): string => this.runtimeOwnerId
    );
  }

  build() {
    Column({ space: 16 }) {
      Text('Wikipedia Saved')
        .fontSize(28)
        .fontWeight(FontWeight.Bold)
      Row({ space: 12 }) {
        Button('All articles').onClick(() => { void this.store?.selectSavedTab('ALL_ARTICLES').then(() => this.syncSurface()); })
        Button('Collections').onClick(() => { void this.store?.selectSavedTab('COLLECTIONS').then(() => this.syncSurface()); })
      }
      Button('Refresh').onClick(() => { void this.store?.retryPullToRefreshAndCompleteSync().then(() => this.syncSurface()); })
      Text(this.selectedTab + ' · ' + this.phase)
    }
    .width('100%')
    .height('100%')
    .padding(24)
  }
}
