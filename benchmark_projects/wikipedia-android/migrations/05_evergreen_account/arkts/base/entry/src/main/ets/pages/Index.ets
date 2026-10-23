import { common } from '@kit.AbilityKit';
import { CallbackEvergreenPageOwner, EvergreenPageOwner } from '../integration/EvergreenPageIntegration';
import { EvergreenStore } from '../model/EvergreenStore';

@Entry
@Component
struct Index {
  @State surface: string = 'main';
  private store: EvergreenStore = new EvergreenStore();
  private runtimeOwnerId: string = 'EvergreenIndex:' + String(Date.now());

  async aboutToAppear(): Promise<void> {
  }

  createRuntimeOwner(): EvergreenPageOwner {
    const store = this.store;
    const ownerId = this.runtimeOwnerId;
    return new CallbackEvergreenPageOwner(
      async (context, input): Promise<void> => { await store.mount(context, input); },
      async (event): Promise<void> => { await store.dispatch(event); this.surface = String(store.currentState()['surface']); },
      async (): Promise<boolean> => store.ordinaryLaunchWouldShow(),
      (): Record<string, Object> => store.currentState(), (): Record<string, Object> => store.currentPersistence(),
      (): Record<string, Object> => store.currentDecision(), (): Record<string, Object> => store.currentDecisionAfterRelaunch(),
      (): Record<string, Object> => store.currentRouting(), (): string[] => store.currentHistoryDays(),
      (): boolean => store.featureAvailable(), (): string => ownerId
    );
  }

  build() {
    Column({ space: 18 }) {
      Text('Wikipedia').fontSize(30).fontWeight(FontWeight.Bold)
      Text(this.surface).fontSize(20)
    }.width('100%').height('100%').padding(24)
  }
}
