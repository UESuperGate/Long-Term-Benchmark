import {
  DemoPagesPersistentInput,
  DemoPagesService,
  PageRecord,
  PagesController,
  PagesPersistentInputLeaf,
  PagesServiceLeaf,
  PagesStore
} from '../features/PagesController';

export class PagesPageOwner {
  readonly ownerId: string;
  readonly controllerId: string;
  readonly controller: PagesController;
  private lifecycle: Promise<void> = Promise.resolve();

  constructor(ownerId: string, controllerId: string, service: PagesServiceLeaf,
    persistentInput: PagesPersistentInputLeaf) {
    this.ownerId = ownerId;
    this.controllerId = controllerId;
    this.controller = new PagesController(service, persistentInput);
  }

  aboutToAppear(): void { this.lifecycle = this.controller.open(); }
  waitUntilReady(): Promise<void> { return this.lifecycle; }
  store(): PagesStore { return this.controller.store; }
  refresh(): Promise<boolean> { return this.controller.refresh(); }
  retryRefresh(): Promise<boolean> { return this.controller.retryRefresh(); }
  openSearch(): void { this.controller.openSearch(); }
  updateSearch(query: string, settledForMs: number): Promise<boolean> {
    return this.controller.updateSearch(query, settledForMs);
  }
  closeSearch(): Promise<void> { return this.controller.closeSearch(); }
  selectAuthor(selection: string): Promise<void> { return this.controller.selectAuthor(selection); }
  openMenu(pageId: number): void { this.controller.openMenu(pageId); }
  chooseTrash(pageId: number): void { this.controller.chooseTrash(pageId); }
  confirmTrash(): Promise<boolean> { return this.controller.confirmTrash(); }
  retryTrash(): Promise<boolean> { return this.controller.retryTrash(); }
  page(pageId: number): PageRecord | undefined {
    const row = this.controller.store.rows.find(candidate => candidate.page.id === pageId);
    return row === undefined ? undefined : row.page;
  }
}

export class PagesPageRuntime {
  private static service: PagesServiceLeaf = new DemoPagesService();
  private static persistentInput: PagesPersistentInputLeaf = new DemoPagesPersistentInput();
  private static current?: PagesPageOwner;
  private static generation: number = 0;

  static configure(service: PagesServiceLeaf, persistentInput: PagesPersistentInputLeaf): void {
    PagesPageRuntime.service = service;
    PagesPageRuntime.persistentInput = persistentInput;
    PagesPageRuntime.current = undefined;
    PagesPageRuntime.generation = 0;
  }

  static createOwner(): PagesPageOwner {
    PagesPageRuntime.generation += 1;
    const suffix = PagesPageRuntime.generation.toString();
    const owner = new PagesPageOwner(`pages-owner-${suffix}`, `pages-controller-${suffix}`,
      PagesPageRuntime.service, PagesPageRuntime.persistentInput);
    PagesPageRuntime.current = owner;
    return owner;
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
