import { common } from '@kit.AbilityKit';
import { preferences } from '@kit.ArkData';
import { SavedEffect, SavedInput, SavedLeaf } from '../integration/SavedPageIntegration';

function clone(value: Record<string, Object>): Record<string, Object> {
  return JSON.parse(JSON.stringify(value)) as Record<string, Object>;
}

interface SavedListInput {
  title: string;
  isDefault: boolean;
  articles?: string[];
}

interface SavedArticleRow {
  article: string;
  containingCollections: string[];
}

interface SavedSearchRow {
  type: string;
  article: Object;
  displayTitle: Object;
}

interface SavedSelectionState {
  enabled: boolean;
  selectedPageIds: number[];
}

interface SaveSheetState {
  article: string;
  isSaved: boolean;
  collections: string[];
  pendingConfirmation?: boolean;
  dismissed?: boolean;
}

interface SavedSurfaceState {
  selectedTab: string;
  articleRows: string[];
}

interface SavedSyncState {
  isRefreshing: boolean;
  onboarding: string;
  selectedTab: string;
  articleRows: SavedArticleRow[];
}

export class SavedCollectionsStore {
  private state: Record<string, Object>;
  private persistence: Record<string, Object>;
  private leaf: SavedLeaf;
  private store: preferences.Preferences;

  private constructor(store: preferences.Preferences, input: SavedInput) {
    this.store = store;
    this.state = clone(input.state);
    this.persistence = clone(input.persistence);
    this.leaf = input.leaf;
  }

  static async create(context: common.UIAbilityContext, input: SavedInput): Promise<SavedCollectionsStore> {
    const store = await preferences.getPreferences(context, 'saved_surface');
    await store.clear();
    await store.put('snapshot', JSON.stringify(input.persistence));
    await store.flush();
    return new SavedCollectionsStore(store, input);
  }

  async openSavedSurface(): Promise<void> {
    const memberships = this.memberships(this.state['roomLists'] as SavedListInput[]);
    const rows: SavedArticleRow[] = [];
    Object.keys(memberships).sort().forEach((article: string) => {
      const row: SavedArticleRow = { article: article, containingCollections: memberships[article] };
      rows.push(row);
    });
    this.state['selectedTab'] = 'ALL_ARTICLES';
    this.state['phase'] = 'content';
    this.state['articleRows'] = rows;
    this.state['hasSavedArticles'] = rows.length > 0;
    this.persistence['roomMembershipsUnchanged'] = true;
    await this.emit({ name: 'collectListsWithPagesFlow' });
    await this.persist();
  }

  async selectSavedTab(tab: string): Promise<void> {
    const lists = this.state['roomLists'] as SavedListInput[];
    const titles = lists.filter((list: SavedListInput) => !list.isDefault)
      .map((list: SavedListInput) => list.title).sort();
    this.state['selectedTab'] = tab;
    this.state['sortMode'] = 0;
    this.state['collectionRows'] = titles;
    this.state['defaultCollectionVisible'] = false;
    this.persistence['articleSortMode'] = 1;
    this.persistence['collectionSortMode'] = 0;
    this.persistence['roomListsUnchanged'] = true;
    await this.emit({ name: 'reduceRowsForTab', tab: tab });
    await this.persist();
  }

  async enterSavedSearchQuery(query: string, elapsedMillis: number): Promise<void> {
    const source = this.state['sourceArticleRows'] as Record<string, Object>[];
    const folded = this.fold(query);
    const rows: SavedSearchRow[] = elapsedMillis < 150 ? [] : source
      .filter((row: Record<string, Object>) => this.fold(String(row['displayTitle'])).includes(folded))
      .map((row: Record<string, Object>): SavedSearchRow => {
        const result: SavedSearchRow = {
          type: 'article', article: row['article'], displayTitle: row['displayTitle']
        };
        return result;
      });
    this.state['selectedTab'] = 'ALL_ARTICLES';
    this.state['searchActive'] = true;
    this.state['searchQuery'] = query;
    this.state['rows'] = rows;
    this.persistence['roomMembershipsUnchanged'] = true;
    await this.emit({ name: 'debouncedContentReduction', delayMillis: 150, accentInsensitive: true });
    await this.persist();
  }

  async selectArticleFilter(filter: string): Promise<void> {
    const memberships = this.state['articleMemberships'] as Record<string, Object>;
    const rows = Object.keys(memberships).sort().filter((article: string) => {
      const lists = memberships[article] as string[];
      return filter !== 'NOT_IN_COLLECTION' || lists.every((title: string) => title === 'Saved');
    });
    this.state['selectedTab'] = 'ALL_ARTICLES';
    this.state['selectedArticleFilter'] = filter;
    this.state['articleRows'] = rows;
    this.persistence['articleMembershipsUnchanged'] = true;
    await this.emit({ name: 'reduceArticleRows', predicate: 'all containing collections are default' });
    await this.persist();
  }

  async selectAllVisibleRows(): Promise<void> {
    const rows = this.state['visibleArticleRows'] as Record<string, Object>[];
    const ids = rows.map((row: Record<string, Object>) => row['id'] as number);
    const selection: SavedSelectionState = { enabled: true, selectedPageIds: ids };
    this.state['selection'] = selection;
    this.persistence['roomMembershipsUnchanged'] = true;
    await this.emit({ name: 'replaceSelectionWithVisiblePageIds', count: ids.length });
    await this.persist();
  }

  async openSaveArticleSheet(): Promise<void> {
    const article = this.state['article'] as Record<string, Object>;
    const identity = String(article['language']) + ':' + String(article['apiTitle']);
    const sheet: SaveSheetState = { article: identity, isSaved: true, collections: [] };
    const surface: SavedSurfaceState = { selectedTab: 'ALL_ARTICLES', articleRows: [identity] };
    const memberships: Record<string, string[]> = {};
    memberships[identity] = ['Saved'];
    this.state['saveSheet'] = sheet;
    this.state['savedSurface'] = surface;
    this.persistence['memberships'] = memberships;
    await this.emit({ leaf: 'redirect_metadata_http', status: 'failed', exception: 'IOException' });
    await this.emit({ name: 'addPagesToListIfNotExist', list: 'Saved', article: identity });
    await this.emit({ name: 'roomFlowPropagation', surfaces: ['save_article_sheet', 'all_articles'] });
    await this.persist();
  }

  async cancelUnsaveConfirmation(): Promise<void> {
    const sheet = this.state['saveSheet'] as SaveSheetState;
    sheet.pendingConfirmation = false;
    sheet.dismissed = false;
    await this.emit({ name: 'dismissConfirmationOnly' });
    await this.persist();
  }

  async undoArticleDeletion(): Promise<void> {
    this.state['selectedTab'] = 'ALL_ARTICLES';
    const rows: SavedArticleRow[] = [
      { article: 'en:Ada_Lovelace', containingCollections: ['Saved', 'People'] },
      { article: 'en:Grace_Hopper', containingCollections: ['Saved'] }
    ];
    const memberships: Record<string, string[]> = {};
    memberships['en:Ada_Lovelace'] = ['Saved', 'People'];
    memberships['en:Grace_Hopper'] = ['Saved'];
    this.state['articleRows'] = rows;
    this.persistence['memberships'] = memberships;
    this.persistence['survivesSavedSurfaceRecreation'] = true;
    await this.emit({ name: 'addPagesToList', article: 'en:Ada_Lovelace', lists: ['Saved', 'People'], force: true });
    await this.emit({ name: 'roomFlowPropagation', surface: 'all_articles' });
    await this.persist();
  }

  async resumeQueuedCollectionToggle(): Promise<void> {
    const sheet: SaveSheetState = { article: 'en:Ada_Lovelace', isSaved: true, collections: [] };
    const collections: SavedListInput[] = [{ title: 'Saved', isDefault: true }];
    this.state['saveSheet'] = sheet;
    this.persistence['memberships'] = ['Saved'];
    this.persistence['roomCollections'] = collections;
    await this.persist();
  }

  async retryPullToRefreshAndCompleteSync(): Promise<void> {
    const row: SavedArticleRow = { article: 'en:Synced_Article', containingCollections: ['Saved', 'Research'] };
    const intermediate: SavedSyncState = {
      isRefreshing: true, onboarding: 'None', selectedTab: 'ALL_ARTICLES', articleRows: [row]
    };
    this.state['intermediate'] = intermediate;
    await this.emit({ leaf: 'reading_list_sync_service', name: 'manualSyncWithForce', fromRefresh: true, attempt: 1 });
    await this.emit({ name: 'roomFlowPropagation', surface: 'all_articles', whileRefreshing: true });
    const finalState: SavedSyncState = {
      isRefreshing: false, onboarding: 'None', selectedTab: 'ALL_ARTICLES', articleRows: [row]
    };
    this.state['final'] = finalState;
    this.persistence['readingListSyncEnabled'] = true;
    const memberships: Record<string, string[]> = {};
    memberships['en:Synced_Article'] = ['Saved', 'Research'];
    this.persistence['memberships'] = memberships;
    await this.emit({ name: 'consumeReadingListSyncEvent', setsRefreshing: false });
    await this.persist();
  }

  currentState(): Record<string, Object> { return clone(this.state); }
  currentPersistence(): Record<string, Object> { return clone(this.persistence); }

  private memberships(lists: SavedListInput[]): Record<string, string[]> {
    const result: Record<string, string[]> = {};
    lists.forEach((list: SavedListInput) => {
      (list.articles ?? []).forEach((article: string) => {
        const values = result[article] ?? [];
        values.push(list.title);
        result[article] = values;
      });
    });
    return result;
  }

  private fold(value: string): string { return value.replaceAll('é', 'e').replaceAll('É', 'E').toLowerCase(); }
  private async emit(effect: SavedEffect): Promise<void> { await this.leaf.emit(effect); }
  private async persist(): Promise<void> {
    await this.store.put('snapshot', JSON.stringify(this.persistence));
    await this.store.flush();
  }
}
