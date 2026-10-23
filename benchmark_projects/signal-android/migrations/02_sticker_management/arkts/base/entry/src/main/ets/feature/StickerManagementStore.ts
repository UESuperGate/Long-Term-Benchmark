export interface StickerPack {
  id: string;
  key: string;
  title: string;
  installed: boolean;
  official: boolean;
  order: number;
}

export interface StickerRuntimeEffect {
  name: string;
  packId?: string;
  packIds?: string[];
  operation?: string;
  notify?: boolean;
  count?: number;
}

export interface StickerLeaf {
  loadPacks(): StickerPack[];
  hasLinkedDevices(): boolean;
  enqueueDownload(id: string, key: string, notify: boolean): void;
  uninstall(ids: string[]): void;
  persistOrder(ids: string[]): void;
  clearTransientDownloadStatus(id: string): void;
  markReferenceInstalled(id: string, notify: boolean): void;
  enqueueLinked(id: string, key: string, operation: string): void;
}

export interface StickerConfirmation {
  type: string;
  title?: string;
  count?: number;
}

export interface StickerManagementState {
  installedPackIds: string[];
  availableOfficialIds: string[];
  availableOtherIds: string[];
  selectedPackIds: string[];
  multiSelectEnabled: boolean;
  prompt: number | null;
  confirmation: StickerConfirmation | null;
}

function clonePack(pack: StickerPack): StickerPack {
  return {
    id: pack.id,
    key: pack.key,
    title: pack.title,
    installed: pack.installed,
    official: pack.official,
    order: pack.order
  };
}

export class StickerManagementEnvironment implements StickerLeaf {
  private records: StickerPack[] = [];
  private linkedDevices: boolean = false;
  private effects: StickerRuntimeEffect[] = [];
  private timeline: string[] = [];

  replacePacks(records: StickerPack[]): void { this.records = records.map((pack: StickerPack) => clonePack(pack)); }
  configureLinkedDevices(value: boolean): void { this.linkedDevices = value; }
  resetEffects(): void { this.effects = []; this.timeline = []; }
  effectCursor(): number { return this.effects.length; }
  effectsAfter(cursor: number): StickerRuntimeEffect[] { return this.effects.slice(cursor); }
  orderedTimeline(): string[] { return [...this.timeline]; }
  recordState(value: string): void { this.timeline.push(`state:${value}`); }
  loadPacks(): StickerPack[] {
    return this.records.map((pack: StickerPack) => clonePack(pack)).sort((a: StickerPack, b: StickerPack) => a.order - b.order);
  }
  hasLinkedDevices(): boolean { return this.linkedDevices; }
  repositoryInstalledIds(): string[] {
    return this.loadPacks().filter((pack: StickerPack) => pack.installed).map((pack: StickerPack) => pack.id);
  }
  enqueueDownload(id: string, _key: string, notify: boolean): void {
    this.effects.push({ name: 'installStickerPack', packId: id, notify, count: 1 });
    this.timeline.push('effect:installStickerPack');
    this.records = this.records.map((pack: StickerPack) => pack.id === id ? {
      id: pack.id,
      key: pack.key,
      title: pack.title,
      installed: true,
      official: pack.official,
      order: pack.order
    } : pack);
  }
  uninstall(ids: string[]): void {
    this.effects.push({ name: 'uninstallStickerPacks', packIds: [...ids], count: 1 });
    this.timeline.push('effect:uninstallStickerPacks');
    this.records = this.records.map((pack: StickerPack) => ids.includes(pack.id) ? {
      id: pack.id,
      key: pack.key,
      title: pack.title,
      installed: false,
      official: pack.official,
      order: pack.order
    } : pack);
  }
  persistOrder(ids: string[]): void {
    this.effects.push({ name: 'setStickerPacksOrder', packIds: [...ids], count: 1 });
    this.timeline.push('effect:setStickerPacksOrder');
    this.records = this.records.map((pack: StickerPack) => {
      const order: number = ids.indexOf(pack.id);
      return order < 0 ? clonePack(pack) : {
        id: pack.id,
        key: pack.key,
        title: pack.title,
        installed: pack.installed,
        official: pack.official,
        order
      };
    });
  }
  clearTransientDownloadStatus(id: string): void {
    this.effects.push({ name: 'clearTransientDownloadStatus', packId: id, count: 1 });
    this.timeline.push('effect:clearTransientDownloadStatus');
  }
  markReferenceInstalled(id: string, notify: boolean): void {
    this.effects.push({ name: 'markReferenceInstalled', packId: id, notify, count: 1 });
    this.timeline.push('effect:markReferenceInstalled');
  }
  enqueueLinked(id: string, _key: string, operation: string): void {
    this.effects.push({ name: 'enqueueLinkedOperation', packId: id, operation, count: 1 });
    this.timeline.push('effect:enqueueLinkedOperation');
  }
}

export class StickerManagementRepository {
  private readonly leaf: StickerLeaf;
  constructor(leaf: StickerLeaf) { this.leaf = leaf; }
  loadPacks(): StickerPack[] { return this.leaf.loadPacks(); }
  hasLinkedDevices(): boolean { return this.leaf.hasLinkedDevices(); }
  install(pack: StickerPack, notify: boolean, _linked: boolean, _reference: boolean): void {
    this.leaf.enqueueDownload(pack.id, pack.key, notify);
  }
  uninstall(keys: Map<string, string>, _linked: boolean): void { this.leaf.uninstall(Array.from(keys.keys())); }
  persistOrder(_ids: string[]): void {}
  clearTransientDownloadStatus(_id: string): void {}
}

export class StickerManagementStore {
  private installed: StickerPack[] = [];
  private official: StickerPack[] = [];
  private other: StickerPack[] = [];
  private selected: string[] = [];
  private statuses: Map<string, string> = new Map();
  private prompt: number | null = null;
  private confirmation: StickerConfirmation | null = null;
  private multiSelectEnabled: boolean = false;
  private readonly repository: StickerManagementRepository;
  private readonly stateObserver: (value: string) => void;

  constructor(repository: StickerManagementRepository, stateObserver: (value: string) => void) {
    this.repository = repository;
    this.stateObserver = stateObserver;
  }
  open(): void { this.onPacksUpdated(this.repository.loadPacks()); }
  onPacksUpdated(records: StickerPack[]): void {
    const ordered: StickerPack[] = [...records].sort((a: StickerPack, b: StickerPack) => a.order - b.order);
    this.installed = ordered.filter((pack: StickerPack) => pack.installed);
    this.official = ordered.filter((pack: StickerPack) => !pack.installed && pack.official);
    this.other = ordered.filter((pack: StickerPack) => !pack.installed && !pack.official);
  }
  install(pack: StickerPack, linked: boolean, reference: boolean): void { this.repository.install(pack, true, linked, reference); }
  installationLingerElapsed(_id: string): void {}
  move(_from: number, _to: number): void {}
  saveOrder(): void {}
  toggleSelection(_id: string): void {}
  setMultiSelectEnabled(_enabled: boolean): void {}
  toggleSelectAll(): void {}
  requestUninstall(ids: string[]): void {
    this.repository.uninstall(new Map(ids.map((id: string): [string, string] => [id, `key-${id}`])), false);
  }
  cancelUninstall(): void {}
  confirmUninstall(ids: string[], linked: boolean): void {
    this.repository.uninstall(new Map(ids.map((id: string): [string, string] => [id, `key-${id}`])), linked);
  }
  downloadStatus(id: string): string | null { return this.statuses.get(id) ?? null; }
  pack(id: string): StickerPack | null {
    const match: StickerPack | undefined = [...this.installed, ...this.official, ...this.other].find((item: StickerPack) => item.id === id);
    return match === undefined ? null : clonePack(match);
  }
  state(): StickerManagementState {
    return {
      installedPackIds: this.installed.map((pack: StickerPack) => pack.id),
      availableOfficialIds: this.official.map((pack: StickerPack) => pack.id),
      availableOtherIds: this.other.map((pack: StickerPack) => pack.id),
      selectedPackIds: [...this.selected],
      multiSelectEnabled: this.multiSelectEnabled,
      prompt: this.prompt,
      confirmation: this.confirmation
    };
  }
}

export class StickerManagementPageOwner {
  readonly ownerId: string = `sticker-page-owner-${Date.now()}`;
  private readonly environment: StickerManagementEnvironment = new StickerManagementEnvironment();
  private repository: StickerManagementRepository = new StickerManagementRepository(this.environment);
  private store: StickerManagementStore = new StickerManagementStore(this.repository, (value: string): void => this.environment.recordState(value));

  externalLeaf(): StickerManagementEnvironment { return this.environment; }
  appear(): void { this.store.open(); }
  reopen(): void {
    this.repository = new StickerManagementRepository(this.environment);
    this.store = new StickerManagementStore(this.repository, (value: string): void => this.environment.recordState(value));
    this.store.open();
  }
  installPack(id: string): void {
    const pack: StickerPack | null = this.store.pack(id);
    if (pack !== null) this.store.install(pack, this.repository.hasLinkedDevices(), false);
  }
  installationLingerElapsed(id: string): void { this.store.installationLingerElapsed(id); }
  movePack(from: number, to: number): void { this.store.move(from, to); }
  completeDrag(from: number, to: number): void { this.store.move(from, to); this.store.saveOrder(); }
  toggleSelection(id: string): void { this.store.toggleSelection(id); }
  setMultiSelectEnabled(enabled: boolean): void { this.store.setMultiSelectEnabled(enabled); }
  toggleSelectAll(): void { this.store.toggleSelectAll(); }
  requestUninstall(ids: string[]): void { this.store.requestUninstall(ids); }
  cancelUninstall(): void { this.store.cancelUninstall(); }
  confirmUninstall(): void {
    const selected: string[] = this.store.state().selectedPackIds;
    this.store.confirmUninstall(selected, this.repository.hasLinkedDevices());
  }
  state(): StickerManagementState { return this.store.state(); }
  downloadStatus(id: string): string | null { return this.store.downloadStatus(id); }
}
