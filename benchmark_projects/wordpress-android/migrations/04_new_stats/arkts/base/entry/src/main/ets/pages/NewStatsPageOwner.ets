import { common } from '@kit.AbilityKit';
import { NewStatsInput, NewStatsPageOwner } from '../integration/NewStatsPageIntegration';
import { LegacyNewStatsStore } from '../model/LegacyNewStatsStore';

export class MountedNewStatsPageOwner implements NewStatsPageOwner {
  private store?: LegacyNewStatsStore;
  private ready: Promise<void> = Promise.resolve();
  private readonly pageOwnerId: string;
  private readonly controllerOwnerId: string;

  constructor(generation: number) {
    this.pageOwnerId = 'newstats-page-owner-' + generation.toString();
    this.controllerOwnerId = 'newstats-controller-' + generation.toString();
  }

  mount(context: common.UIAbilityContext, input: NewStatsInput, initialize: boolean): Promise<void> {
    this.ready = LegacyNewStatsStore.create(context, input, initialize).then((value: LegacyNewStatsStore) => {
      this.store = value;
    });
    return this.ready;
  }

  async waitUntilReady(): Promise<void> { await this.ready; }
  async invoke(name: string, event: Record<string, Object>): Promise<void> {
    await this.ready;
    if (this.store === undefined) throw new Error('NewStats store is not mounted');
    await this.store.invoke(name, event);
  }
  currentState(): Record<string, Object> { return this.store?.currentState() ?? {}; }
  currentPersistence(): Record<string, Object> { return this.store?.currentPersistence() ?? {}; }
  ownerId(): string { return this.pageOwnerId; }
  controllerId(): string { return this.controllerOwnerId; }
  storeSource(): string { return 'Index.NewStatsPageOwner.controller.store'; }
  featureAvailable(): boolean { return this.store !== undefined; }
}

export class NewStatsPageRuntime {
  private static context?: common.UIAbilityContext;
  private static input?: NewStatsInput;
  private static current?: MountedNewStatsPageOwner;
  private static generation: number = 0;

  static configure(context: common.UIAbilityContext, input: NewStatsInput): void {
    NewStatsPageRuntime.context = context;
    NewStatsPageRuntime.input = input;
    NewStatsPageRuntime.current = undefined;
    NewStatsPageRuntime.generation = 0;
  }

  static createOwner(): MountedNewStatsPageOwner {
    const context = NewStatsPageRuntime.context;
    const input = NewStatsPageRuntime.input;
    if (context === undefined || input === undefined) throw new Error('NewStats runtime is not configured');
    NewStatsPageRuntime.generation += 1;
    const owner = new MountedNewStatsPageOwner(NewStatsPageRuntime.generation);
    NewStatsPageRuntime.current = owner;
    void owner.mount(context, input, NewStatsPageRuntime.generation === 1);
    return owner;
  }

  static async waitForOwnerAfter(previous: string = '', attempt: number = 0): Promise<MountedNewStatsPageOwner> {
    const owner = NewStatsPageRuntime.current;
    if (owner !== undefined && owner.ownerId() !== previous) {
      await owner.waitUntilReady();
      return owner;
    }
    if (attempt >= 120) throw new Error('NewStats page owner mount timed out');
    await new Promise<void>((resolve) => setTimeout(() => resolve(), 25));
    return NewStatsPageRuntime.waitForOwnerAfter(previous, attempt + 1);
  }
}
