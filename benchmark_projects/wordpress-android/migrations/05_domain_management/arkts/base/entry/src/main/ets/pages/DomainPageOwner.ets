import { common } from '@kit.AbilityKit';
import { DomainBackend, DomainEffect, DomainInput, DomainLeaf, DomainPageOwner } from '../integration/DomainIntegration';
import { DomainStore } from '../model/DomainStore';

class EmptyBackend implements DomainBackend {
  async fetchAllDomains(): Promise<Record<string, Object>> { return JSON.parse('{"type":"empty"}') as Record<string, Object>; }
  async searchForDomains(query: string): Promise<string[]> { return []; }
  async createCart(mode: string, domain: string): Promise<Record<string, Object>> { return JSON.parse('{"type":"error"}') as Record<string, Object>; }
}
class EmptyLeaf implements DomainLeaf { async emit(effect: DomainEffect): Promise<void> {} }

export class MountedDomainPageOwner implements DomainPageOwner {
  private store?: DomainStore;
  private ready: Promise<void> = Promise.resolve();
  private readonly pageOwnerId: string;
  private readonly controllerOwnerId: string;
  constructor(generation: number) {
    this.pageOwnerId = 'domain-page-owner-' + generation.toString();
    this.controllerOwnerId = 'domain-controller-' + generation.toString();
  }
  mount(context: common.UIAbilityContext, input: DomainInput, initialize: boolean): Promise<void> {
    this.ready = DomainStore.create(context, input, initialize).then((value: DomainStore) => { this.store = value; });
    return this.ready;
  }
  async waitUntilReady(): Promise<void> { await this.ready; }
  async invoke(name: string, event: Record<string, Object>): Promise<void> {
    await this.ready;
    if (this.store === undefined) throw new Error('Domain store is not mounted');
    await this.store.invoke(name, event);
  }
  currentState(): Record<string, Object> { return this.store?.currentState() ?? {}; }
  ownerId(): string { return this.pageOwnerId; }
  controllerId(): string { return this.controllerOwnerId; }
  storeSource(): string { return 'Index.DomainPageOwner.controller.store'; }
  featureAvailable(): boolean { return this.store !== undefined; }
}

export class DomainPageRuntime {
  private static context?: common.UIAbilityContext;
  private static input?: DomainInput;
  private static current?: MountedDomainPageOwner;
  private static generation: number = 0;
  static configure(context: common.UIAbilityContext, input: DomainInput): void {
    DomainPageRuntime.context = context; DomainPageRuntime.input = input;
    DomainPageRuntime.current = undefined; DomainPageRuntime.generation = 0;
  }
  static configureDefault(context: common.UIAbilityContext): void {
    DomainPageRuntime.configure(context, { backend: new EmptyBackend(), leaf: new EmptyLeaf() });
  }
  static createOwner(): MountedDomainPageOwner {
    const context = DomainPageRuntime.context; const input = DomainPageRuntime.input;
    if (context === undefined || input === undefined) throw new Error('Domain runtime is not configured');
    DomainPageRuntime.generation += 1;
    const owner = new MountedDomainPageOwner(DomainPageRuntime.generation);
    DomainPageRuntime.current = owner;
    void owner.mount(context, input, DomainPageRuntime.generation === 1);
    return owner;
  }
  static async waitForOwner(attempt: number = 0): Promise<MountedDomainPageOwner> {
    const owner = DomainPageRuntime.current;
    if (owner !== undefined) { await owner.waitUntilReady(); return owner; }
    if (attempt >= 120) throw new Error('Domain page owner mount timed out');
    await new Promise<void>((resolve) => setTimeout(() => resolve(), 25));
    return DomainPageRuntime.waitForOwner(attempt + 1);
  }
}
