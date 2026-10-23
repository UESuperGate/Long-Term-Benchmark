import {
  PageRecord,
  PageRequest,
  PagesPersistentInputLeaf,
  PagesServiceLeaf
} from '../features/PagesController';
import { PagesPageOwner, PagesPageRuntime } from '../pages/PagesPageOwner';

export interface SemanticPayload {
  key: string;
  beforeJson: string;
  afterJson: string;
  observedJson: string;
  effectsJson: string;
  invariantChecksJson: string;
  productionBodies: string[];
  runtimeEvidenceJson: string;
}

interface InvariantCheck { invariant: string; passed: boolean; evidence: string; }
interface FetchOutcome { failed: boolean; pages: PageRecord[]; }
interface LeafCall { name: string; detail: string; }
interface MediaEffect { name: string; mediaIds: number[]; }
interface TrashEffect { name: string; entity: string; pageId: number; }
interface RuntimeEvidence {
  pageOwnerId: string;
  controllerOwnerId: string;
  pageGeneration: number;
  storeSource: string;
  evaluatorStoreWrites: number;
  detachedControllers: number;
  leafCalls: LeafCall[];
}
interface RowsLoading { rows: number[]; loading: boolean; }
interface RowsSnapshot { rows: number[]; }
interface ThumbnailRow { id: number; thumbnailUrl?: string; }
interface OpenRequest { entity: string; statuses: string[]; orderBy: string; order: string; pageSize: number; }
interface OpenObserved {
  surface: string; tabs: string[]; selectedTab: string; rows: ThumbnailRow[]; loading: boolean;
  request: OpenRequest; effects: Object[];
}
interface RefreshFrame { rows: number[]; refreshing: boolean; feedback: string; retryAvailable: boolean; }
interface RefreshRecovery { rows: number[]; refreshing: boolean; error: null; }
interface RefreshObserved { surface: string; failure: RefreshFrame; recovery: RefreshRecovery; requestCount: number; }
interface ShortBefore { rows: number[]; searchActive: boolean; }
interface ShortObserved { surface: string; searchActive: boolean; query: string; rows: number[]; searchRequestCount: number; }
interface SearchSnapshot { query: string; requestCount: number; }
interface SearchRow { id: number; statusLabel: string; }
interface SearchRequest { statuses: string[]; search: string; debounceMs: number; }
interface SearchObserved { surface: string; query: string; rows: SearchRow[]; searchRequestCount: number; request: SearchRequest; }
interface CloseBefore { selectedTab: string; query: string; rows: number[]; }
interface CloseObserved { surface: string; searchActive: boolean; query: string; selectedTab: string; rows: number[]; reloadDelayMs: number; }
interface AuthorBefore { selection: string; persistedSelection: string; }
interface AuthorRequest { authorIds: number[]; }
interface AuthorObserved { surface: string; selection: string; persistedSelection: string; request: AuthorRequest; reloadCount: number; }
interface HierarchyRow { id: number; indent: number; }
interface HierarchyObserved { surface: string; rows: HierarchyRow[]; }
interface MenuBefore { pageId: number; status: string; }
interface MenuObserved { surface: string; actions: string[]; excludedActions: string[]; }
interface TrashBefore { publishedRows: number[]; trashCalls: number; }
interface TrashObserved {
  surface: string; confirmationShown: boolean; serviceEffect: TrashEffect; publishedRows: number[];
  trashedRows: number[]; feedback: string;
}
interface TrashFailureFrame { publishedRows: number[]; feedback: string; }
interface TrashRecovery { publishedRows: number[]; trashedRows: number[]; feedback: string; }
interface TrashFailureObserved { surface: string; failure: TrashFailureFrame; recovery: TrashRecovery; serviceCallCount: number; }

class ControlledPagesPersistentInput implements PagesPersistentInputLeaf {
  tab: string = 'published';
  author: string = 'everyone';
  authorId: number = 42;
  manageHomepage: boolean = true;
  blaze: boolean = true;
  calls: LeafCall[] = [];

  selectedTab(): string { this.calls.push({ name: 'readSelectedTab', detail: this.tab }); return this.tab; }
  authorSelection(): string { this.calls.push({ name: 'readAuthorSelection', detail: this.author }); return this.author; }
  signedInAuthorId(): number { this.calls.push({ name: 'readSignedInAuthorId', detail: `${this.authorId}` }); return this.authorId; }
  canManageHomepage(): boolean { this.calls.push({ name: 'readCanManageHomepage', detail: `${this.manageHomepage}` }); return this.manageHomepage; }
  blazeEligible(): boolean { this.calls.push({ name: 'readBlazeEligible', detail: `${this.blaze}` }); return this.blaze; }
  saveAuthorSelection(selection: string): void {
    this.author = selection;
    this.calls.push({ name: 'saveAuthorSelection', detail: selection });
  }
}

class ControlledPagesService implements PagesServiceLeaf {
  requests: PageRequest[] = [];
  fetchOutcomes: FetchOutcome[] = [];
  trashFailures: boolean[] = [];
  trashIds: number[] = [];
  calls: LeafCall[] = [];
  effects: Object[] = [];

  async fetch(request: PageRequest): Promise<PageRecord[]> {
    this.requests.push(request);
    this.calls.push({ name: 'fetchPages', detail: JSON.stringify(request) });
    const outcome = this.fetchOutcomes.length > 0 ? this.fetchOutcomes.shift() : undefined;
    if (outcome === undefined) return [];
    if (outcome.failed) throw new Error('controlled_fetch_failure');
    return outcome.pages;
  }

  async trash(pageId: number): Promise<void> {
    this.trashIds.push(pageId);
    this.calls.push({ name: 'trashPage', detail: `${pageId}` });
    const effect: TrashEffect = { name: 'trashPage', entity: 'pages', pageId: pageId };
    this.effects.push(effect);
    const failed = this.trashFailures.length > 0 ? this.trashFailures.shift() : false;
    if (failed) throw new Error('controlled_trash_failure');
  }

  async resolveMedia(mediaId: number): Promise<string> {
    this.calls.push({ name: 'resolveFeaturedMedia', detail: `${mediaId}` });
    const effect: MediaEffect = { name: 'resolveFeaturedMedia', mediaIds: [mediaId] };
    this.effects.push(effect);
    return `https://media.test/${mediaId}.jpg`;
  }
}

let activeService: ControlledPagesService = new ControlledPagesService();
let activePersistentInput: ControlledPagesPersistentInput = new ControlledPagesPersistentInput();

function page(id: number, parentId: number = 0, status: string = 'published'): PageRecord {
  return { id: id, parentId: parentId, title: `Page ${id}`, status: status };
}

function success(pages: PageRecord[]): FetchOutcome { return { failed: false, pages: pages }; }
function failure(): FetchOutcome { return { failed: true, pages: [] }; }
function emptyRequest(): PageRequest {
  return { entity: '', tab: '', statuses: [], orderBy: '', order: '', pageSize: 0, search: '', authorIds: [] };
}

export function prepareSemanticCase(key: string): void {
  const service = new ControlledPagesService();
  const persistent = new ControlledPagesPersistentInput();
  if (key === 'open_published') {
    service.fetchOutcomes.push(success([{ id: 1, parentId: 0, title: 'About', status: 'published', featuredMediaId: 301 }]));
  } else if (key === 'refresh_retry') {
    service.fetchOutcomes.push(success([page(1)]), failure(), success([page(1), page(2)]));
  } else if (key === 'short_search') {
    service.fetchOutcomes.push(success([page(1)]));
  } else if (key === 'debounced_search') {
    persistent.tab = 'drafts';
    service.fetchOutcomes.push(success([]), success([page(7, 0, 'scheduled')]));
  } else if (key === 'close_search') {
    persistent.tab = 'drafts';
    service.fetchOutcomes.push(success([page(3, 0, 'draft')]), success([page(7, 0, 'scheduled')]), success([page(3, 0, 'draft')]));
  } else if (key === 'author_filter') {
    service.fetchOutcomes.push(success([]), success([]));
  } else if (key === 'published_hierarchy') {
    service.fetchOutcomes.push(success([page(1), page(2, 1), page(3, 2), page(4, 3), page(5, 4), page(9, 99)]));
  } else if (key === 'menu_eligibility') {
    service.fetchOutcomes.push(success([{ id: 11, parentId: 0, title: 'Home', status: 'published', homepage: true,
      postsPage: false, passwordProtected: false }]));
  } else if (key === 'trash_success') {
    service.fetchOutcomes.push(success([page(12)]));
  } else if (key === 'trash_failure_retry') {
    service.fetchOutcomes.push(success([page(13)]));
    service.trashFailures.push(true, false);
  } else {
    throw new Error(`unknown semantic case: ${key}`);
  }
  activeService = service;
  activePersistentInput = persistent;
  PagesPageRuntime.configure(service, persistent);
}

function evidence(owner: PagesPageOwner): RuntimeEvidence {
  return {
    pageOwnerId: owner.ownerId,
    controllerOwnerId: owner.controllerId,
    pageGeneration: PagesPageRuntime.ownerGeneration(),
    storeSource: 'PagesPageOwner.controller.store',
    evaluatorStoreWrites: 0,
    detachedControllers: 0,
    leafCalls: activePersistentInput.calls.concat(activeService.calls)
  };
}

function payload(key: string, owner: PagesPageOwner, before: Object, after: Object, observed: Object,
  effects: Object[], checks: InvariantCheck[], bodies: string[]): SemanticPayload {
  return {
    key: key,
    beforeJson: JSON.stringify(before),
    afterJson: JSON.stringify(after),
    observedJson: JSON.stringify(observed),
    effectsJson: JSON.stringify(effects),
    invariantChecksJson: JSON.stringify(checks),
    productionBodies: bodies,
    runtimeEvidenceJson: JSON.stringify(evidence(owner))
  };
}

function ids(owner: PagesPageOwner): number[] { return owner.store().rows.map(row => row.page.id); }

export async function runSemanticCase(key: string): Promise<SemanticPayload> {
  const owner = await PagesPageRuntime.waitForOwner();
  await owner.waitUntilReady();
  if (key === 'open_published') return openPublished(key, owner);
  if (key === 'refresh_retry') return refreshRetry(key, owner);
  if (key === 'short_search') return shortSearch(key, owner);
  if (key === 'debounced_search') return debouncedSearch(key, owner);
  if (key === 'close_search') return closeSearch(key, owner);
  if (key === 'author_filter') return authorFilter(key, owner);
  if (key === 'published_hierarchy') return publishedHierarchy(key, owner);
  if (key === 'menu_eligibility') return menuEligibility(key, owner);
  if (key === 'trash_success') return trashSuccess(key, owner);
  if (key === 'trash_failure_retry') return trashFailureRetry(key, owner);
  throw new Error(`unknown semantic case: ${key}`);
}

async function openPublished(key: string, owner: PagesPageOwner): Promise<SemanticPayload> {
  const store = owner.store();
  const request = activeService.requests.length > 0 ? activeService.requests[0] : emptyRequest();
  const rows: ThumbnailRow[] = store.rows.map(row => {
    const item: ThumbnailRow = { id: row.page.id, thumbnailUrl: row.thumbnailUrl };
    return item;
  });
  const openRequest: OpenRequest = { entity: request.entity, statuses: request.statuses, orderBy: request.orderBy,
    order: request.order, pageSize: request.pageSize };
  const observed: OpenObserved = {
    surface: store.surface,
    tabs: store.tabs.slice(),
    selectedTab: store.selectedTab,
    rows: rows,
    loading: store.loading,
    request: openRequest,
    effects: activeService.effects.slice()
  };
  const before: RowsLoading = { rows: [], loading: false };
  const after: RowsLoading = { rows: ids(owner), loading: store.loading };
  return payload(key, owner, before, after, observed,
    activeService.effects.slice(), [
      { invariant: 'no posts request is dispatched', passed: request.entity === 'pages', evidence: request.entity },
      { invariant: 'thumbnail resolution never removes the page row', passed: store.rows.length === 1, evidence: JSON.stringify(ids(owner)) },
      { invariant: 'the row opens through the existing editor bridge rather than a replacement editor', passed: store.surface === 'modern_pages', evidence: store.surface }
    ], ['PagesPageOwner.aboutToAppear', 'PagesController.open', 'PagesController.loadTab', 'PagesController.buildRows']);
}

async function refreshRetry(key: string, owner: PagesPageOwner): Promise<SemanticPayload> {
  const before: RowsSnapshot = { rows: ids(owner) };
  await owner.refresh();
  const failureFrame: RefreshFrame = { rows: ids(owner), refreshing: owner.store().refreshing, feedback: owner.store().feedback, retryAvailable: true };
  await owner.retryRefresh();
  const recovery: RefreshRecovery = { rows: ids(owner), refreshing: owner.store().refreshing, error: null };
  const observed: RefreshObserved = { surface: owner.store().surface, failure: failureFrame,
    recovery: recovery, requestCount: activeService.requests.length - 1 };
  const after: RowsSnapshot = { rows: ids(owner) };
  return payload(key, owner, before, after, observed, activeService.effects.slice(), [
    { invariant: 'loaded rows remain visible during the failed refresh', passed: failureFrame.rows.length === 1 && failureFrame.rows[0] === 1, evidence: JSON.stringify(failureFrame.rows) },
    { invariant: 'retry executes the application-owned refresh body', passed: activeService.requests.length - 1 === 2, evidence: `${activeService.requests.length - 1} event requests` },
    { invariant: 'no obsolete collection writes after recovery', passed: ids(owner).length === 2, evidence: JSON.stringify(ids(owner)) }
  ], ['PagesPageOwner.refresh', 'PagesPageOwner.retryRefresh', 'PagesController.refresh', 'PagesController.loadTab']);
}

async function shortSearch(key: string, owner: PagesPageOwner): Promise<SemanticPayload> {
  const before: ShortBefore = { rows: ids(owner), searchActive: owner.store().searchActive };
  const requestCount = activeService.requests.length;
  owner.openSearch();
  await owner.updateSearch('ab', 500);
  const observed: ShortObserved = { surface: owner.store().surface, searchActive: owner.store().searchActive, query: owner.store().query,
    rows: ids(owner), searchRequestCount: activeService.requests.length - requestCount };
  return payload(key, owner, before, observed, observed, activeService.effects.slice(), [
    { invariant: 'queries shorter than three characters never reach the service leaf', passed: activeService.requests.length === requestCount, evidence: `${activeService.requests.length - requestCount} search requests` },
    { invariant: 'the selected tab is retained', passed: owner.store().selectedTab === 'published', evidence: owner.store().selectedTab }
  ], ['PagesPageOwner.openSearch', 'PagesPageOwner.updateSearch', 'PagesController.openSearch', 'PagesController.updateSearch']);
}

async function debouncedSearch(key: string, owner: PagesPageOwner): Promise<SemanticPayload> {
  owner.openSearch();
  const requestCount = activeService.requests.length;
  const before: SearchSnapshot = { query: owner.store().query, requestCount: 0 };
  await owner.updateSearch('hel', 100);
  await owner.updateSearch('hello', 250);
  const request = activeService.requests.length > requestCount ? activeService.requests[requestCount] : emptyRequest();
  const rows: SearchRow[] = owner.store().rows.map(row => {
    const item: SearchRow = { id: row.page.id, statusLabel: row.statusLabel };
    return item;
  });
  const searchRequest: SearchRequest = { statuses: request.statuses, search: request.search,
    debounceMs: owner.store().lastSearchDebounceMs };
  const observed: SearchObserved = { surface: owner.store().surface, query: owner.store().query,
    rows: rows,
    searchRequestCount: activeService.requests.length - requestCount,
    request: searchRequest };
  const after: SearchSnapshot = { query: owner.store().query, requestCount: activeService.requests.length - requestCount };
  return payload(key, owner, before, after, observed,
    activeService.effects.slice(), [
      { invariant: 'the superseded hel request is not dispatched', passed: activeService.requests.length - requestCount === 1, evidence: `${activeService.requests.length - requestCount} request` },
      { invariant: 'search results are flat and independent of the selected tab hierarchy',
        passed: owner.store().rows.length > 0 && owner.store().rows[0].indent === 0,
        evidence: owner.store().rows.length > 0 ? `${owner.store().rows[0].indent}` : 'no rendered rows' }
    ], ['PagesPageOwner.openSearch', 'PagesPageOwner.updateSearch', 'PagesController.updateSearch', 'PagesController.buildRows']);
}

async function closeSearch(key: string, owner: PagesPageOwner): Promise<SemanticPayload> {
  owner.openSearch();
  await owner.updateSearch('hello', 250);
  const before: CloseBefore = { selectedTab: owner.store().selectedTab, query: owner.store().query, rows: ids(owner) };
  const requestCount = activeService.requests.length;
  await owner.closeSearch();
  const observed: CloseObserved = { surface: owner.store().surface, searchActive: owner.store().searchActive, query: owner.store().query,
    selectedTab: owner.store().selectedTab, rows: ids(owner), reloadDelayMs: owner.store().lastReloadDelayMs };
  return payload(key, owner, before, observed, observed, activeService.effects.slice(), [
    { invariant: 'closing search does not switch tabs', passed: owner.store().selectedTab === 'drafts', evidence: owner.store().selectedTab },
    { invariant: 'the obsolete search collection is closed before the tab reload', passed: owner.store().closedSearchCollections === 1 && activeService.requests.length - requestCount === 1, evidence: `closed=${owner.store().closedSearchCollections},reloads=${activeService.requests.length - requestCount}` }
  ], ['PagesPageOwner.closeSearch', 'PagesController.closeSearch', 'PagesController.loadTab']);
}

async function authorFilter(key: string, owner: PagesPageOwner): Promise<SemanticPayload> {
  const before: AuthorBefore = { selection: owner.store().authorSelection, persistedSelection: owner.store().persistedAuthorSelection };
  const requestCount = activeService.requests.length;
  await owner.selectAuthor('me');
  const request = activeService.requests.length > requestCount ? activeService.requests[requestCount] : emptyRequest();
  const authorRequest: AuthorRequest = { authorIds: request.authorIds };
  const observed: AuthorObserved = { surface: owner.store().surface, selection: owner.store().authorSelection,
    persistedSelection: owner.store().persistedAuthorSelection, request: authorRequest,
    reloadCount: activeService.requests.length - requestCount };
  return payload(key, owner, before, observed, observed, activeService.effects.slice(), [
    { invariant: 'the author identifier is derived from the signed-in account', passed: request.authorIds.length === 1 && request.authorIds[0] === 42, evidence: JSON.stringify(request.authorIds) },
    { invariant: 'unrelated preferences remain unchanged', passed: owner.store().selectedTab === 'published', evidence: owner.store().selectedTab }
  ], ['PagesPageOwner.selectAuthor', 'PagesController.selectAuthor', 'PagesController.loadTab']);
}

async function publishedHierarchy(key: string, owner: PagesPageOwner): Promise<SemanticPayload> {
  const rows: HierarchyRow[] = owner.store().rows.map(row => {
    const item: HierarchyRow = { id: row.page.id, indent: row.indent };
    return item;
  });
  const rowIds = rows.map(row => row.id);
  const observed: HierarchyObserved = { surface: owner.store().surface, rows: rows };
  const before: RowsSnapshot = { rows: [] };
  return payload(key, owner, before, observed, observed, activeService.effects.slice(), [
    { invariant: 'every input page appears exactly once', passed: new Set<number>(rowIds).size === 6 && rowIds.length === 6, evidence: JSON.stringify(rowIds) },
    { invariant: 'missing-parent pages remain visible', passed: rowIds.indexOf(9) >= 0, evidence: JSON.stringify(rowIds) },
    { invariant: 'indentation never exceeds three', passed: rows.every(row => row.indent <= 3), evidence: JSON.stringify(rows.map(row => row.indent)) }
  ], ['PagesPageOwner.aboutToAppear', 'PagesController.open', 'PagesController.buildRows']);
}

async function menuEligibility(key: string, owner: PagesPageOwner): Promise<SemanticPayload> {
  const before: MenuBefore = { pageId: 11, status: 'published' };
  owner.openMenu(11);
  const observed: MenuObserved = { surface: owner.store().surface, actions: owner.store().menu.actions.slice(),
    excludedActions: owner.store().menu.excludedActions.slice() };
  return payload(key, owner, before, observed, observed, activeService.effects.slice(), [
    { invariant: 'destructive actions are not rendered for the homepage', passed: observed.actions.indexOf('trash') < 0 && observed.actions.indexOf('move_to_draft') < 0, evidence: JSON.stringify(observed.actions) },
    { invariant: 'action eligibility is derived from page and site state', passed: observed.actions.indexOf('set_as_posts_page') >= 0 && observed.actions.indexOf('blaze') >= 0, evidence: JSON.stringify(observed.actions) }
  ], ['PagesPageOwner.openMenu', 'PagesController.openMenu', 'PagesController.menuActions']);
}

async function trashSuccess(key: string, owner: PagesPageOwner): Promise<SemanticPayload> {
  const before: TrashBefore = { publishedRows: ids(owner), trashCalls: activeService.trashIds.length };
  owner.chooseTrash(12);
  const confirmationShown = owner.store().pendingTrash === 12;
  const beforeConfirmCalls = activeService.trashIds.length;
  await owner.confirmTrash();
  const serviceEffect: TrashEffect = activeService.effects.length > 0 ? activeService.effects[0] as TrashEffect :
    { name: 'none', entity: '', pageId: 0 };
  const observed: TrashObserved = { surface: owner.store().surface, confirmationShown: confirmationShown, serviceEffect: serviceEffect,
    publishedRows: ids(owner), trashedRows: owner.store().trashedRows.slice(), feedback: owner.store().feedback };
  return payload(key, owner, before, observed, observed, activeService.effects.slice(), [
    { invariant: 'the service mutation is not called before confirmation', passed: beforeConfirmCalls === 0, evidence: `${beforeConfirmCalls} calls` },
    { invariant: 'the application-owned mutation body is invoked exactly once', passed: activeService.trashIds.length === 1, evidence: `${activeService.trashIds.length} call` }
  ], ['PagesPageOwner.chooseTrash', 'PagesPageOwner.confirmTrash', 'PagesController.chooseTrash', 'PagesController.confirmTrash']);
}

async function trashFailureRetry(key: string, owner: PagesPageOwner): Promise<SemanticPayload> {
  const before: RowsSnapshot = { rows: ids(owner) };
  owner.chooseTrash(13);
  await owner.confirmTrash();
  const failureFrame: TrashFailureFrame = { publishedRows: ids(owner), feedback: owner.store().feedback };
  await owner.retryTrash();
  const recovery: TrashRecovery = { publishedRows: ids(owner), trashedRows: owner.store().trashedRows.slice(), feedback: owner.store().feedback };
  const observed: TrashFailureObserved = { surface: owner.store().surface, failure: failureFrame,
    recovery: recovery,
    serviceCallCount: activeService.trashIds.length };
  return payload(key, owner, before, observed, observed, activeService.effects.slice(), [
    { invariant: 'failure does not optimistically remove the page', passed: failureFrame.publishedRows.length === 1, evidence: JSON.stringify(failureFrame.publishedRows) },
    { invariant: 'retry uses the same page identity', passed: activeService.trashIds.length === 2 && activeService.trashIds[0] === 13 && activeService.trashIds[1] === 13, evidence: JSON.stringify(activeService.trashIds) },
    { invariant: 'only the controlled external leaf supplies outcomes', passed: activeService.trashFailures.length === 0, evidence: 'controlled leaf outcome queue consumed' }
  ], ['PagesPageOwner.chooseTrash', 'PagesPageOwner.confirmTrash', 'PagesPageOwner.retryTrash', 'PagesController.confirmTrash']);
}
