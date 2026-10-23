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
  id: number;
  title: string;
  page: PageRecord;
  indent: number;
  thumbnailUrl?: string;
  statusLabel: string;
}
export interface PageRequest {
  entity: string; tab: string; statuses: string[]; orderBy: string; order: string;
  pageSize: number; search: string; authorIds: number[];
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

export class PageMenuState {
  pageId?: number;
  actions: string[] = [];
  excludedActions: string[] = [];
}

export class PagesStore {
  surface: string = 'legacy_pages';
  tabs: string[] = [];
  selectedTab: string = '';
  rows: PageRow[] = [];
  searchActive: boolean = false;
  query: string = '';
  authorSelection: string = '';
  persistedAuthorSelection: string = '';
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

export class LegacyPagesStore extends PagesStore { title: string = 'Pages'; }

export class LegacyPagesController {
  readonly store: LegacyPagesStore = new LegacyPagesStore();

  open(): void {
    this.store.surface = 'legacy_pages';
  }
}
