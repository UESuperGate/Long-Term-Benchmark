import { common } from '@kit.AbilityKit';
import { CallbackExplorePageOwner, ExploreInput, ExplorePageOwner } from '../integration/ExplorePageIntegration';
import { LegacyExploreStore } from '../model/LegacyExploreStore';

@Entry
@Component
struct Index {
  @State selectedTab: string = 'COMMUNITY';
  @State phase: string = 'content';
  private store?: LegacyExploreStore;
  private runtimeOwnerId: string = 'ExploreIndex:' + String(Date.now());

  async aboutToAppear(): Promise<void> {
  }

  private syncSurface(): void {
    const state = this.store?.currentState();
    this.selectedTab = String(state?.['selectedTab'] ?? 'COMMUNITY');
    this.phase = String(state?.['forYouPhase'] ?? 'content');
  }

  createRuntimeOwner(): ExplorePageOwner {
    return new CallbackExplorePageOwner(
      async (context: common.UIAbilityContext, input: ExploreInput): Promise<void> => {
        this.store = await LegacyExploreStore.create(context, input);
        this.syncSurface();
      },
      async (): Promise<void> => { await this.store?.recreateHomeSurface(); this.syncSurface(); },
      async (tab: string): Promise<void> => { await this.store?.selectHomeTab(tab); this.syncSurface(); },
      async (): Promise<void> => { await this.store?.retryCommunityLoad(); this.syncSurface(); },
      async (): Promise<void> => { await this.store?.retryCommunityLoadMore(); this.syncSurface(); },
      async (): Promise<void> => { await this.store?.resumeHomeSurface(); this.syncSurface(); },
      async (): Promise<void> => { await this.store?.finishInterestEditing(); this.syncSurface(); },
      async (): Promise<void> => { await this.store?.retryForYouLoad(); this.syncSurface(); },
      async (): Promise<void> => { await this.store?.confirmAllModulesOff(); this.syncSurface(); },
      (): Record<string, Object> => this.store?.currentState() ?? {},
      (): Record<string, Object> => this.store?.currentPersistence() ?? {},
      (): boolean => false,
      (): string => this.runtimeOwnerId
    );
  }

  build() {
    Column({ space: 16 }) {
      Text('Wikipedia')
        .fontSize(28)
        .fontWeight(FontWeight.Bold)
      Text('Community feed')
      Button('Community')
        .onClick(() => { this.selectedTab = 'COMMUNITY'; })
      Text(this.selectedTab + ' · ' + this.phase)
    }
    .width('100%')
    .height('100%')
    .padding(24)
  }
}
