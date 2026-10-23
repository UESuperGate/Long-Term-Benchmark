export interface GifPageResult {
  failed: boolean;
  ids: string[];
  hasMore: boolean;
}

export interface KeyboardSticker {
  packId: string;
  packKey: string;
  stickerId: number;
}

export interface ConversationEffects {
  visibility(value: boolean): void;
  onSend(sticker: KeyboardSticker): void;
}

export interface MediaKeyboardState {
  initialized: boolean;
  offeredTabs: string[];
  availableTabs: string[];
  selectedTab: string;
  preferredTab: string;
  restrictedTo: string[] | null;
  searchActive: boolean;
  searchQuery: string;
}

export interface GifState {
  gifs: string[];
  isLoading: boolean;
  isLoadingMore: boolean;
  hasMore: boolean;
  loadFailed: boolean;
}

export interface MediaRuntimeEffect {
  name: string;
  count?: number;
  value?: boolean;
  stickerId?: number;
  query?: string;
  offset?: number;
  limit?: number;
  confirmationAtCallback?: KeyboardSticker | null;
}

function cloneSticker(sticker: KeyboardSticker | null): KeyboardSticker | null {
  return sticker === null ? null : {
    packId: sticker.packId,
    packKey: sticker.packKey,
    stickerId: sticker.stickerId
  };
}

export class MediaKeyboardEnvironment implements ConversationEffects {
  private tabs: string[] = ['EMOJI', 'STICKER', 'GIF'];
  private gifPages: Map<number, GifPageResult> = new Map();
  private effects: MediaRuntimeEffect[] = [];
  private confirmationReader: (() => KeyboardSticker | null) | null = null;

  configureTabs(tabs: string[]): void { this.tabs = [...tabs]; }
  configuredTabs(): string[] { return [...this.tabs]; }
  configureGifPage(offset: number, page: GifPageResult): void {
    this.gifPages.set(offset, { failed: page.failed, ids: [...page.ids], hasMore: page.hasMore });
  }
  configuredGifPage(offset: number): GifPageResult {
    const page: GifPageResult | undefined = this.gifPages.get(offset);
    return page === undefined ? { failed: true, ids: [], hasMore: false } : {
      failed: page.failed,
      ids: [...page.ids],
      hasMore: page.hasMore
    };
  }
  bindConfirmationReader(reader: () => KeyboardSticker | null): void { this.confirmationReader = reader; }
  resetEffects(): void { this.effects = []; }
  effectCursor(): number { return this.effects.length; }
  effectsAfter(cursor: number): MediaRuntimeEffect[] { return this.effects.slice(cursor); }
  getAvailableTabs(): string[] {
    this.effects.push({ name: 'getAvailableTabs', count: 1 });
    return [...this.tabs];
  }
  getGifs(query: string, offset: number, limit: number): GifPageResult {
    this.effects.push({ name: 'getGifs', query, offset, limit });
    return this.configuredGifPage(offset);
  }
  visibility(value: boolean): void { this.effects.push({ name: 'confirmationVisibility', value }); }
  onSend(sticker: KeyboardSticker): void {
    const pending: KeyboardSticker | null = this.confirmationReader === null ? null : this.confirmationReader();
    this.effects.push({ name: 'onSend', stickerId: sticker.stickerId, count: 1, confirmationAtCallback: cloneSticker(pending) });
  }
}

export class MediaKeyboardStore {
  offeredTabs: string[] = [];
  preferredTab: string = 'EMOJI';
  restrictedTo: string[] | null = null;
  initialized: boolean = false;
  searchActive: boolean = false;
  searchQuery: string = '';
  private readonly getAvailableTabs: () => string[];

  constructor(getAvailableTabs: () => string[]) { this.getAvailableTabs = getAvailableTabs; }
  initialize(): void { this.offeredTabs = [...this.getAvailableTabs()]; }
  restrictTabs(_tabs: string[] | null): void {}
  setSearch(active: boolean, query: string): void { this.searchActive = active; this.searchQuery = query; }
  selectTab(tab: string): void { this.preferredTab = tab; }
  keyboardState(): MediaKeyboardState {
    return {
      initialized: this.initialized,
      offeredTabs: [...this.offeredTabs],
      availableTabs: [...this.offeredTabs],
      selectedTab: this.preferredTab,
      preferredTab: this.preferredTab,
      restrictedTo: this.restrictedTo === null ? null : [...this.restrictedTo],
      searchActive: this.searchActive,
      searchQuery: this.searchQuery
    };
  }
}

export class GifStore {
  gifs: string[] = [];
  isLoading: boolean = false;
  isLoadingMore: boolean = false;
  hasMore: boolean = true;
  loadFailed: boolean = false;
  private readonly getGifs: (query: string, offset: number, limit: number) => GifPageResult;

  constructor(getGifs: (query: string, offset: number, limit: number) => GifPageResult) { this.getGifs = getGifs; }
  loadFirstPage(): void {
    this.isLoading = true;
    const page: GifPageResult = this.getGifs('', 0, 20);
    if (!page.failed) {
      this.gifs = [...page.ids];
      this.hasMore = page.hasMore;
      this.isLoading = false;
    }
  }
  retry(): void {}
  loadMore(): void {
    const page: GifPageResult = this.getGifs('', 0, 20);
    this.gifs = [...page.ids];
    this.hasMore = page.hasMore;
  }
  state(): GifState {
    return {
      gifs: [...this.gifs],
      isLoading: this.isLoading,
      isLoadingMore: this.isLoadingMore,
      hasMore: this.hasMore,
      loadFailed: this.loadFailed
    };
  }
}

export class ConversationMediaStore {
  private pending: KeyboardSticker | null = null;
  private readonly effects: ConversationEffects;

  constructor(effects: ConversationEffects) { this.effects = effects; }
  tapSticker(sticker: KeyboardSticker): void { this.effects.onSend(sticker); }
  cancelConfirmation(): void {}
  confirmSend(): void {}
  confirmation(): KeyboardSticker | null { return cloneSticker(this.pending); }
}

export class MediaKeyboardPageOwner {
  readonly ownerId: string = `media-page-owner-${Date.now()}`;
  private readonly environment: MediaKeyboardEnvironment = new MediaKeyboardEnvironment();
  private keyboard: MediaKeyboardStore = new MediaKeyboardStore((): string[] => this.environment.getAvailableTabs());
  private gifs: GifStore = new GifStore((query: string, offset: number, limit: number): GifPageResult => this.environment.getGifs(query, offset, limit));
  private conversation: ConversationMediaStore = new ConversationMediaStore(this.environment);

  constructor() { this.bindOwnerGraph(); }

  private bindOwnerGraph(): void {
    this.environment.bindConfirmationReader((): KeyboardSticker | null => this.conversation.confirmation());
  }

  externalLeaf(): MediaKeyboardEnvironment { return this.environment; }
  appear(): void { this.initializeKeyboard(); }
  reopen(): void {
    this.keyboard = new MediaKeyboardStore((): string[] => this.environment.getAvailableTabs());
    this.gifs = new GifStore((query: string, offset: number, limit: number): GifPageResult => this.environment.getGifs(query, offset, limit));
    this.conversation = new ConversationMediaStore(this.environment);
    this.bindOwnerGraph();
  }
  initializeKeyboard(): void { this.keyboard.initialize(); }
  restrictTabs(tabs: string[] | null): void { this.keyboard.restrictTabs(tabs); }
  setSearch(active: boolean, query: string): void { this.keyboard.setSearch(active, query); }
  selectTab(tab: string): void { this.keyboard.selectTab(tab); }
  loadFirstGifPage(): void { this.gifs.loadFirstPage(); }
  retryGifLoad(): void { this.gifs.retry(); }
  loadMoreGifs(): void { this.gifs.loadMore(); }
  tapSticker(sticker: KeyboardSticker): void { this.conversation.tapSticker(sticker); }
  cancelStickerConfirmation(): void { this.conversation.cancelConfirmation(); }
  confirmStickerSend(): void { this.conversation.confirmSend(); }
  keyboardState(): MediaKeyboardState { return this.keyboard.keyboardState(); }
  gifState(): GifState { return this.gifs.state(); }
  confirmation(): KeyboardSticker | null { return this.conversation.confirmation(); }
}
