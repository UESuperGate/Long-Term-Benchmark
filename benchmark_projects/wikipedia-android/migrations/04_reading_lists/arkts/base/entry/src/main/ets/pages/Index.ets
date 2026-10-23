import { common } from '@kit.AbilityKit';
import { CallbackSavedPageOwner, SavedInput, SavedPageOwner } from '../integration/SavedPageIntegration';
import { LegacySavedStore } from '../model/LegacySavedStore';

@Entry
@Component
struct Index {
  @State selectedTab: string = 'COLLECTIONS';
  @State phase: string = 'legacy';
  private store?: LegacySavedStore;
  private runtimeOwnerId: string = 'SavedIndex:' + String(Date.now());

  async aboutToAppear(): Promise<void> {
  }

  createRuntimeOwner(): SavedPageOwner {
    return new CallbackSavedPageOwner(
      async (context: common.UIAbilityContext, input: SavedInput): Promise<void> => {
        this.store = await LegacySavedStore.create(context, input);
      },
      [
        async (): Promise<void> => { await this.store?.openSavedSurface(); },
        async (tab: Object): Promise<void> => { await this.store?.selectSavedTab(String(tab)); },
        async (query: Object, elapsed: Object): Promise<void> => {
          await this.store?.enterSavedSearchQuery(String(query), Number(elapsed));
        },
        async (filter: Object): Promise<void> => { await this.store?.selectArticleFilter(String(filter)); },
        async (): Promise<void> => { await this.store?.selectAllVisibleRows(); },
        async (): Promise<void> => { await this.store?.openSaveArticleSheet(); },
        async (): Promise<void> => { await this.store?.cancelUnsaveConfirmation(); },
        async (): Promise<void> => { await this.store?.undoArticleDeletion(); },
        async (): Promise<void> => { await this.store?.resumeQueuedCollectionToggle(); },
        async (): Promise<void> => { await this.store?.retryPullToRefreshAndCompleteSync(); }
      ],
      (): Record<string, Object> => this.store?.currentState() ?? {},
      (): Record<string, Object> => this.store?.currentPersistence() ?? {},
      (): boolean => false,
      (): string => this.runtimeOwnerId
    );
  }

  build() {
    Column({ space: 16 }) {
      Text('Wikipedia Saved')
        .fontSize(28)
        .fontWeight(FontWeight.Bold)
      Text('Reading lists')
      Button('Open reading list').onClick(() => { this.phase = 'legacy_list'; })
      Text(this.selectedTab + ' · ' + this.phase)
    }
    .width('100%')
    .height('100%')
    .padding(24)
  }
}
