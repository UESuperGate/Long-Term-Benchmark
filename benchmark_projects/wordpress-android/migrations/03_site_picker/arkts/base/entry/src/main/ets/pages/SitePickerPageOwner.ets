import { common } from '@kit.AbilityKit';
import { SitePickerInput, SitePickerPageOwner } from '../integration/SitePickerPageIntegration';
import { LegacySitePickerStore } from '../model/LegacySitePickerStore';

export class MountedSitePickerPageOwner implements SitePickerPageOwner {
  private store?: LegacySitePickerStore;
  private ready: Promise<void> = Promise.resolve();
  private readonly pageOwnerId: string;
  private readonly controllerOwnerId: string;

  constructor(generation: number) {
    this.pageOwnerId = 'sitepicker-page-owner-' + generation.toString();
    this.controllerOwnerId = 'sitepicker-controller-' + generation.toString();
  }

  mount(context: common.UIAbilityContext, input: SitePickerInput, initialize: boolean): Promise<void> {
    this.ready = LegacySitePickerStore.create(context, input, initialize).then((value: LegacySitePickerStore) => {
      this.store = value;
    });
    return this.ready;
  }

  async waitUntilReady(): Promise<void> { await this.ready; }
  async invoke(name: string, event: Record<string, Object>): Promise<void> {
    await this.ready;
    if (this.store === undefined) throw new Error('SitePicker store is not mounted');
    await this.store.invoke(name, event);
  }
  currentState(): Record<string, Object> { return this.store?.currentState() ?? {}; }
  currentPersistence(): Record<string, Object> { return this.store?.currentPersistence() ?? {}; }
  ownerId(): string { return this.pageOwnerId; }
  controllerId(): string { return this.controllerOwnerId; }
  storeSource(): string { return 'Index.SitePickerPageOwner.controller.store'; }
  featureAvailable(): boolean { return this.store !== undefined; }
}

export class SitePickerPageRuntime {
  private static context?: common.UIAbilityContext;
  private static input?: SitePickerInput;
  private static current?: MountedSitePickerPageOwner;
  private static generation: number = 0;

  static configure(context: common.UIAbilityContext, input: SitePickerInput): void {
    SitePickerPageRuntime.context = context;
    SitePickerPageRuntime.input = input;
    SitePickerPageRuntime.current = undefined;
    SitePickerPageRuntime.generation = 0;
  }

  static createOwner(): MountedSitePickerPageOwner {
    const context = SitePickerPageRuntime.context;
    const input = SitePickerPageRuntime.input;
    if (context === undefined || input === undefined) throw new Error('SitePicker runtime is not configured');
    SitePickerPageRuntime.generation += 1;
    const owner = new MountedSitePickerPageOwner(SitePickerPageRuntime.generation);
    SitePickerPageRuntime.current = owner;
    void owner.mount(context, input, SitePickerPageRuntime.generation === 1);
    return owner;
  }

  static async waitForOwnerAfter(previous: string = '', attempt: number = 0): Promise<MountedSitePickerPageOwner> {
    const owner = SitePickerPageRuntime.current;
    if (owner !== undefined && owner.ownerId() !== previous) {
      await owner.waitUntilReady();
      return owner;
    }
    if (attempt >= 120) throw new Error('SitePicker page owner mount timed out');
    await new Promise<void>((resolve) => setTimeout(() => resolve(), 25));
    return SitePickerPageRuntime.waitForOwnerAfter(previous, attempt + 1);
  }
}
