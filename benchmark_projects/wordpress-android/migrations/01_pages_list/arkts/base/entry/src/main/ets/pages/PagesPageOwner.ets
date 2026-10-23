import {
  LegacyPagesController,
  LegacyPagesStore,
  PageRecord,
  PagesPersistentInputLeaf,
  PagesServiceLeaf,
  PagesStore
} from '../features/PagesController';

export class LegacyPagesPageOwner {
  readonly ownerId: string;
  readonly controllerId: string;
  readonly controller: LegacyPagesController = new LegacyPagesController();

  constructor(ownerId: string, controllerId: string) {
    this.ownerId = ownerId;
    this.controllerId = controllerId;
  }

  aboutToAppear(): void { this.controller.open(); }
  store(): LegacyPagesStore { return this.controller.store; }
  openPages(): void { this.controller.open(); }
}

export class LegacyPagesPageRuntime {
  private static current?: LegacyPagesPageOwner;
  private static generation: number = 0;

  static reset(): void {
    LegacyPagesPageRuntime.current = undefined;
    LegacyPagesPageRuntime.generation = 0;
  }

  static createOwner(): LegacyPagesPageOwner {
    LegacyPagesPageRuntime.generation += 1;
    const suffix = LegacyPagesPageRuntime.generation.toString();
    const owner = new LegacyPagesPageOwner(`legacy-pages-owner-${suffix}`, `legacy-pages-controller-${suffix}`);
    LegacyPagesPageRuntime.current = owner;
    PagesPageRuntime.attachLegacy(owner);
    return owner;
  }

  static currentOwner(): LegacyPagesPageOwner {
    const owner = LegacyPagesPageRuntime.current;
    if (owner === undefined) throw new Error('Legacy Pages page owner is not mounted');
    return owner;
  }

  static async waitForOwner(attempt: number = 0): Promise<LegacyPagesPageOwner> {
    const owner = LegacyPagesPageRuntime.current;
    if (owner !== undefined) return owner;
    if (attempt >= 80) throw new Error('Legacy Pages page owner mount timed out');
    await new Promise<void>((resolve) => { setTimeout(() => resolve(), 25); });
    return LegacyPagesPageRuntime.waitForOwner(attempt + 1);
  }

  static ownerGeneration(): number { return LegacyPagesPageRuntime.generation; }
}

export class PagesPageOwner {
  readonly ownerId: string;
  readonly controllerId: string;
  private legacy: LegacyPagesPageOwner;

  constructor(legacy: LegacyPagesPageOwner) {
    this.legacy = legacy;
    this.ownerId = legacy.ownerId;
    this.controllerId = legacy.controllerId;
  }

  waitUntilReady(): Promise<void> { return Promise.resolve(); }
  store(): PagesStore { return this.legacy.store(); }
  refresh(): Promise<boolean> { return Promise.resolve(false); }
  retryRefresh(): Promise<boolean> { return Promise.resolve(false); }
  openSearch(): void {}
  updateSearch(_query: string, _settledForMs: number): Promise<boolean> { return Promise.resolve(false); }
  closeSearch(): Promise<void> { return Promise.resolve(); }
  selectAuthor(_selection: string): Promise<void> { return Promise.resolve(); }
  openMenu(_pageId: number): void {}
  chooseTrash(_pageId: number): void {}
  confirmTrash(): Promise<boolean> { return Promise.resolve(false); }
  retryTrash(): Promise<boolean> { return Promise.resolve(false); }
  page(_pageId: number): PageRecord | undefined { return undefined; }
}

export class PagesPageRuntime {
  private static current?: PagesPageOwner;
  private static generation: number = 0;

  static configure(_service: PagesServiceLeaf, _persistentInput: PagesPersistentInputLeaf): void {
    PagesPageRuntime.current = undefined;
    PagesPageRuntime.generation = 0;
  }

  static attachLegacy(owner: LegacyPagesPageOwner): void {
    PagesPageRuntime.current = new PagesPageOwner(owner);
    PagesPageRuntime.generation = LegacyPagesPageRuntime.ownerGeneration();
  }

  static currentOwner(): PagesPageOwner {
    const owner = PagesPageRuntime.current;
    if (owner === undefined) throw new Error('Pages page owner is not mounted');
    return owner;
  }

  static async waitForOwner(attempt: number = 0): Promise<PagesPageOwner> {
    const owner = PagesPageRuntime.current;
    if (owner !== undefined) return owner;
    if (attempt >= 80) throw new Error('Pages page owner mount timed out');
    await new Promise<void>((resolve) => { setTimeout(() => resolve(), 25); });
    return PagesPageRuntime.waitForOwner(attempt + 1);
  }

  static ownerGeneration(): number { return PagesPageRuntime.generation; }
}
