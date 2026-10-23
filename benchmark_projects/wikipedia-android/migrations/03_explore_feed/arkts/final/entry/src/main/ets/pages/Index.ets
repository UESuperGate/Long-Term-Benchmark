import { common } from '@kit.AbilityKit';
import { CallbackExplorePageOwner, ExploreInput, ExplorePageOwner } from '../integration/ExplorePageIntegration';
import { ExploreFeedStore } from '../model/ExploreFeedStore';

@Entry
@Component
struct Index {
  @State selectedTab: string = 'COMMUNITY';
  @State phase: string = 'idle';
  private store?: ExploreFeedStore;
  private runtimeOwnerId: string = 'ExploreIndex:' + String(Date.now());

  async aboutToAppear(): Promise<void> {
  }

  private syncSurface(): void {
    const state = this.store?.currentState();
    this.selectedTab = String(state?.['selectedTab'] ?? 'COMMUNITY');
    this.phase = String(state?.['forYouPhase'] ?? 'content');
  }

  private async chooseTab(tab: string): Promise<void> {
    await this.store?.selectHomeTab(tab);
    this.syncSurface();
  }

  createRuntimeOwner(): ExplorePageOwner {
    return new CallbackExplorePageOwner(
      async (context: common.UIAbilityContext, input: ExploreInput): Promise<void> => {
        this.store = await ExploreFeedStore.create(context, input);
        this.syncSurface();
      },
      async (): Promise<void> => { await this.store?.recreateHomeSurface(); this.syncSurface(); },
      async (tab: string): Promise<void> => { await this.chooseTab(tab); },
      async (): Promise<void> => { await this.store?.retryCommunityLoad(); this.syncSurface(); },
      async (): Promise<void> => { await this.store?.retryCommunityLoadMore(); this.syncSurface(); },
      async (): Promise<void> => { await this.store?.resumeHomeSurface(); this.syncSurface(); },
      async (): Promise<void> => { await this.store?.finishInterestEditing(); this.syncSurface(); },
      async (): Promise<void> => { await this.store?.retryForYouLoad(); this.syncSurface(); },
      async (): Promise<void> => { await this.store?.confirmAllModulesOff(); this.syncSurface(); },
      (): Record<string, Object> => this.store?.currentState() ?? {},
      (): Record<string, Object> => this.store?.currentPersistence() ?? {},
      (): boolean => true,
      (): string => this.runtimeOwnerId
    );
  }

  build() {
    Column({ space: 16 }) {
      Text('Wikipedia Explore')
        .fontSize(28)
        .fontWeight(FontWeight.Bold)
      Row({ space: 12 }) {
        Button('Community').onClick(() => { void this.chooseTab('COMMUNITY'); })
        Button('For you').onClick(() => { void this.chooseTab('FOR_YOU'); })
      }
      Button('Customize interests')
        .onClick(() => { void this.store?.finishInterestEditing().then(() => this.syncSurface()); })
      Text(this.selectedTab + ' · ' + this.phase)
    }
    .width('100%')
    .height('100%')
    .padding(24)
  }
}
