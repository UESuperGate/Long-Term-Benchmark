export interface PageRecord {
  id: number;
  parentId: number;
  title: string;
  status: string;
  featuredMediaId?: number;
  homepage?: boolean;
  postsPage?: boolean;
  passwordProtected?: boolean;
}

export interface PageRow {
  page: PageRecord;
  indent: number;
  thumbnailUrl?: string;
  statusLabel: string;
}

export interface PageRequest {
  entity: string;
  tab: string;
  statuses: string[];
  orderBy: string;
  order: string;
  pageSize: number;
  search: string;
  authorIds: number[];
}

export interface PagesServiceLeaf {
  fetch(request: PageRequest): Promise<PageRecord[]>;
  trash(pageId: number): Promise<void>;
  resolveMedia(mediaId: number): Promise<string>;
}

export interface PagesPersistentInputLeaf {
  selectedTab(): string;
  authorSelection(): string;
  signedInAuthorId(): number;
  canManageHomepage(): boolean;
  blazeEligible(): boolean;
  saveAuthorSelection(selection: string): void;
}

export class DemoPagesService implements PagesServiceLeaf {
  async fetch(_request: PageRequest): Promise<PageRecord[]> {
    return [
      { id: 1, parentId: 0, title: 'About', status: 'published', featuredMediaId: 301 },
      { id: 2, parentId: 1, title: 'Team', status: 'published' }
    ];
  }
  async trash(_pageId: number): Promise<void> {}
  async resolveMedia(mediaId: number): Promise<string> { return `media:${mediaId}`; }
}

export class DemoPagesPersistentInput implements PagesPersistentInputLeaf {
  private author: string = 'everyone';
  selectedTab(): string { return 'published'; }
  authorSelection(): string { return this.author; }
  signedInAuthorId(): number { return 42; }
  canManageHomepage(): boolean { return true; }
  blazeEligible(): boolean { return true; }
  saveAuthorSelection(selection: string): void { this.author = selection; }
}

export class PageMenuState {
  pageId?: number;
  actions: string[] = [];
  excludedActions: string[] = [];

  clear(): void {
    this.pageId = undefined;
    this.actions = [];
    this.excludedActions = [];
  }
}

export class PagesStore {
  surface: string = 'modern_pages';
  tabs: string[] = ['published', 'drafts', 'scheduled', 'trashed'];
  selectedTab: string = 'published';
  rows: PageRow[] = [];
  searchActive: boolean = false;
  query: string = '';
  authorSelection: string = 'everyone';
  persistedAuthorSelection: string = 'everyone';
  loading: boolean = false;
  refreshing: boolean = false;
  error: string = '';
  feedback: string = '';
  pendingTrash?: number;
  trashedRows: number[] = [];
  requestCount: number = 0;
  closedSearchCollections: number = 0;
  lastSearchDebounceMs: number = 0;
  lastReloadDelayMs: number = 0;
  menu: PageMenuState = new PageMenuState();
}

export class PagesController {
  readonly store: PagesStore = new PagesStore();
  private service: PagesServiceLeaf;
  private persistentInput: PagesPersistentInputLeaf;

  constructor(service: PagesServiceLeaf, persistentInput: PagesPersistentInputLeaf = new DemoPagesPersistentInput()) {
    this.service = service;
    this.persistentInput = persistentInput;
    this.store.selectedTab = persistentInput.selectedTab();
    this.store.authorSelection = persistentInput.authorSelection();
    this.store.persistedAuthorSelection = persistentInput.authorSelection();
  }

  async open(): Promise<void> { await this.loadTab(this.store.selectedTab); }

  async loadTab(tab: string): Promise<boolean> {
    this.store.loading = true;
    this.store.selectedTab = tab;
    try {
      this.store.requestCount += 1;
      const pages = await this.service.fetch(this.requestFor(tab, ''));
      this.store.rows = await this.buildRows(pages, tab === 'published' && !this.store.searchActive);
      this.store.error = '';
      this.store.feedback = '';
      return true;
    } catch (_error) {
      this.store.error = 'network_error';
      return false;
    } finally {
      this.store.loading = false;
    }
  }

  async refresh(): Promise<boolean> {
    const previous = this.store.rows;
    this.store.refreshing = true;
    try {
      const loaded = await this.loadTab(this.store.selectedTab);
      if (!loaded) {
        this.store.rows = previous;
        this.store.feedback = 'network_error';
        return false;
      }
      this.store.error = '';
      return true;
    } finally {
      this.store.refreshing = false;
    }
  }

  async retryRefresh(): Promise<boolean> { return this.refresh(); }
  openSearch(): void { this.store.searchActive = true; this.store.rows = []; }

  async updateSearch(query: string, settledForMs: number = 250): Promise<boolean> {
    this.store.query = query;
    this.store.rows = [];
    if (query.length < 3 || settledForMs < 250) return false;
    this.store.lastSearchDebounceMs = settledForMs;
    this.store.requestCount += 1;
    const pages = await this.service.fetch(this.requestFor(this.store.selectedTab, query));
    this.store.rows = await this.buildRows(pages, false);
    return true;
  }

  async closeSearch(): Promise<void> {
    this.store.closedSearchCollections += 1;
    this.store.searchActive = false;
    this.store.query = '';
    this.store.lastReloadDelayMs = 0;
    await this.loadTab(this.store.selectedTab);
  }

  async selectAuthor(selection: string): Promise<void> {
    if (selection === this.store.authorSelection) return;
    this.store.authorSelection = selection;
    this.persistentInput.saveAuthorSelection(selection);
    this.store.persistedAuthorSelection = selection;
    await this.loadTab(this.store.selectedTab);
  }

  openMenu(pageId: number): void {
    const row = this.store.rows.find((candidate: PageRow) => candidate.page.id === pageId);
    if (row === undefined) {
      this.store.menu.clear();
      return;
    }
    const actions = this.menuActions(row.page, this.persistentInput.canManageHomepage(), this.persistentInput.blazeEligible());
    const candidates = ['set_as_homepage', 'move_to_draft', 'trash'];
    this.store.menu.pageId = pageId;
    this.store.menu.actions = actions;
    this.store.menu.excludedActions = candidates.filter((action: string) => actions.indexOf(action) < 0);
  }

  menuActions(page: PageRecord, canManageHomepage: boolean, blazeEligible: boolean): string[] {
    if (page.status === 'trashed') return ['move_to_draft', 'delete_permanently'];
    if (page.status !== 'published') return ['view', 'set_parent', 'publish_now', 'duplicate'];
    const actions: string[] = ['view', 'set_parent'];
    if (canManageHomepage && !page.homepage) actions.push('set_as_homepage');
    if (canManageHomepage && !page.postsPage) actions.push('set_as_posts_page');
    if (!page.homepage) actions.push('move_to_draft');
    actions.push('duplicate', 'share', 'copy_url');
    if (blazeEligible && !page.passwordProtected) actions.push('blaze');
    if (!page.homepage) actions.push('trash');
    return actions;
  }

  chooseTrash(pageId: number): void { this.store.pendingTrash = pageId; }

  async confirmTrash(): Promise<boolean> {
    const pageId = this.store.pendingTrash;
    if (pageId === undefined) return false;
    try {
      await this.service.trash(pageId);
      this.store.rows = this.store.rows.filter((row: PageRow) => row.page.id !== pageId);
      this.store.trashedRows.push(pageId);
      this.store.feedback = 'moved_to_trash';
      this.store.pendingTrash = undefined;
      return true;
    } catch (_error) {
      this.store.feedback = 'status_change_error';
      return false;
    }
  }

  async retryTrash(): Promise<boolean> { return this.confirmTrash(); }

  private requestFor(tab: string, search: string): PageRequest {
    let statuses: string[];
    if (search.length > 0) statuses = ['published', 'private', 'draft', 'pending', 'scheduled', 'trashed'];
    else if (tab === 'published') statuses = ['published', 'private'];
    else if (tab === 'drafts') statuses = ['draft', 'pending'];
    else if (tab === 'scheduled') statuses = ['scheduled'];
    else statuses = ['trashed'];
    const authors = this.store.authorSelection === 'me' ? [this.persistentInput.signedInAuthorId()] : [];
    return { entity: 'pages', tab: tab, statuses: statuses, orderBy: tab === 'scheduled' && search.length === 0 ? 'date' : 'title', order: 'ascending', pageSize: 20, search: search, authorIds: authors };
  }

  private async row(page: PageRecord, indent: number): Promise<PageRow> {
    let thumbnail: string | undefined = undefined;
    if (page.featuredMediaId !== undefined && page.featuredMediaId !== 0) thumbnail = await this.service.resolveMedia(page.featuredMediaId);
    return { page: page, indent: Math.min(indent, 3), thumbnailUrl: thumbnail, statusLabel: page.status };
  }

  private async buildRows(pages: PageRecord[], hierarchy: boolean): Promise<PageRow[]> {
    if (!hierarchy) {
      const flat: PageRow[] = [];
      for (const page of pages) flat.push(await this.row(page, 0));
      return flat;
    }
    const rows: PageRow[] = [];
    const visited: Set<number> = new Set<number>();
    const append = async (page: PageRecord, depth: number): Promise<void> => {
      if (visited.has(page.id)) return;
      visited.add(page.id);
      rows.push(await this.row(page, depth));
      const children = pages.filter((candidate: PageRecord) => candidate.parentId === page.id);
      for (const child of children) await append(child, depth + 1);
    };
    const roots = pages.filter((page: PageRecord) => page.parentId === 0 || !pages.some((candidate: PageRecord) => candidate.id === page.parentId));
    for (const root of roots) await append(root, 0);
    for (const page of pages) await append(page, 0);
    return rows;
  }
}
