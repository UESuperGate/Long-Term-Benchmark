import preferences from '@ohos.data.preferences';
import common from '@ohos.app.ability.common';

export const MAX_SEARCH_HISTORY_SIZE: number = 25;

export enum SearchHistoryResultType {
  Query = 'query',
  Room = 'room'
}

class PersistedSearchHistoryResult {
  type: string;
  value: string;

  constructor(type: string, value: string) {
    this.type = type;
    this.value = value;
  }
}

export class SearchHistoryResult {
  type: SearchHistoryResultType;
  value: string;

  constructor(type: SearchHistoryResultType, value: string) {
    this.type = type;
    this.value = value;
  }

  get id(): string {
    return `${this.type}:${this.value}`;
  }

  static query(term: string): SearchHistoryResult {
    return new SearchHistoryResult(SearchHistoryResultType.Query, term);
  }

  static room(roomId: string): SearchHistoryResult {
    return new SearchHistoryResult(SearchHistoryResultType.Room, roomId);
  }
}

export class SearchHistoryStore {
  private static readonly STORE_NAME: string = 'element_x_search_history';
  private static readonly HISTORY_KEY: string = 'recent_results';
  private cache: SearchHistoryResult[] = [];
  private isLoaded: boolean = false;

  async load(context: common.Context): Promise<SearchHistoryResult[]> {
    if (this.isLoaded) {
      return this.copy(this.cache);
    }
    this.cache = await this.readFromDisk(context);
    this.isLoaded = true;
    return this.copy(this.cache);
  }

  async add(context: common.Context, result: SearchHistoryResult): Promise<SearchHistoryResult[]> {
    await this.load(context);
    const updated: SearchHistoryResult[] = [result];
    this.cache.forEach((item: SearchHistoryResult) => {
      if (item.id !== result.id && updated.length < MAX_SEARCH_HISTORY_SIZE) {
        updated.push(item);
      }
    });
    this.cache = updated;
    await this.persist(context);
    return this.copy(this.cache);
  }

  async clear(context: common.Context): Promise<void> {
    this.cache = [];
    this.isLoaded = true;
    const store = await preferences.getPreferences(context, SearchHistoryStore.STORE_NAME);
    await store.delete(SearchHistoryStore.HISTORY_KEY);
    await store.flush();
  }

  private async readFromDisk(context: common.Context): Promise<SearchHistoryResult[]> {
    try {
      const store = await preferences.getPreferences(context, SearchHistoryStore.STORE_NAME);
      const value = await store.get(SearchHistoryStore.HISTORY_KEY, '');
      if (typeof value !== 'string' || value.length === 0) {
        return [];
      }
      const serialized = JSON.parse(value) as PersistedSearchHistoryResult[];
      const result: SearchHistoryResult[] = [];
      serialized.forEach((item: PersistedSearchHistoryResult) => {
        if (item.type === SearchHistoryResultType.Query) {
          result.push(SearchHistoryResult.query(item.value));
        } else if (item.type === SearchHistoryResultType.Room) {
          result.push(SearchHistoryResult.room(item.value));
        }
      });
      return result.slice(0, MAX_SEARCH_HISTORY_SIZE);
    } catch (error) {
      return [];
    }
  }

  private async persist(context: common.Context): Promise<void> {
    const serialized: PersistedSearchHistoryResult[] = this.cache.map((item: SearchHistoryResult) => {
      return new PersistedSearchHistoryResult(item.type, item.value);
    });
    const store = await preferences.getPreferences(context, SearchHistoryStore.STORE_NAME);
    await store.put(SearchHistoryStore.HISTORY_KEY, JSON.stringify(serialized));
    await store.flush();
  }

  private copy(items: SearchHistoryResult[]): SearchHistoryResult[] {
    return items.map((item: SearchHistoryResult) => new SearchHistoryResult(item.type, item.value));
  }
}
