import { common } from '@kit.AbilityKit';
import { preferences } from '@kit.ArkData';
import { ExploreEffect, ExploreInput, ExploreLeaf } from '../integration/ExplorePageIntegration';

function clone(value: Record<string, Object>): Record<string, Object> {
  return JSON.parse(JSON.stringify(value)) as Record<string, Object>;
}

interface ExploreModuleState {
  type: string;
  cards: string[];
}

interface ExploreForYouState {
  phase: string;
  language?: string;
  modules: ExploreModuleState[];
}

interface ExploreCommunityState {
  phase: string;
  language?: string;
  cards: string[];
  error?: string | null;
}

interface ExploreCacheState {
  date: string;
  language: string;
  modules: string[];
}

interface ExploreVisibilityState {
  BASED_ON_INTEREST: boolean;
  BECAUSE_YOU_READ: boolean;
  CONTINUE_READING: boolean;
}

export class ExploreFeedStore {
  private state: Record<string, Object>;
  private persistence: Record<string, Object>;
  private leaf: ExploreLeaf;
  private store: preferences.Preferences;

  private constructor(store: preferences.Preferences, input: ExploreInput) {
    this.store = store;
    this.state = clone(input.state);
    this.persistence = clone(input.persistence);
    this.leaf = input.leaf;
  }

  static async create(context: common.UIAbilityContext, input: ExploreInput): Promise<ExploreFeedStore> {
    const store = await preferences.getPreferences(context, 'explore_feed');
    await store.clear();
    await store.put('snapshot', JSON.stringify(input.persistence));
    await store.flush();
    return new ExploreFeedStore(store, input);
  }

  async recreateHomeSurface(): Promise<void> {
    const preference = this.text(this.persistence, 'homePreference', 'COMMUNITY');
    if (preference !== 'PERSONALIZED') {
      this.state['selectedTab'] = 'COMMUNITY';
      await this.persist();
      return;
    }
    this.state['selectedTab'] = 'FOR_YOU';
    const cache = this.persistence['forYouCache'] as Record<string, Object> | undefined;
    if (cache === undefined || cache === null || Object.keys(cache).length === 0) {
      this.state['forYouPhase'] = 'loading';
      this.state['communityPhase'] = 'idle';
      await this.emit({ name: 'loadForYouContent', attempt: 1, language: this.language() });
    } else {
      const hidden = this.strings(this.persistence['hiddenCards']);
      const cards = ['Ada_Lovelace', 'Grace_Hopper'].filter((value: string) => !hidden.includes(value));
      const modules: ExploreModuleState[] = cards.length === 0 ? [] : [
        { type: 'BASED_ON_INTEREST', cards: cards }
      ];
      const forYou: ExploreForYouState = {
        phase: 'content', language: this.language(),
        modules: modules
      };
      this.state['forYou'] = forYou;
      this.persistence['cacheDate'] = this.text(cache, 'date', '2026-05-28');
      this.persistence['cacheLanguage'] = this.language();
      await this.emit({ name: 'readForYouCache', language: this.language() });
    }
    await this.persist();
  }

  async selectHomeTab(tab: string): Promise<void> {
    this.state['selectedTab'] = tab;
    if (tab === 'FOR_YOU') {
      this.state['forYouPhase'] = 'loading';
      await this.emit({ name: 'loadForYouContent', attempt: 1, language: this.language() });
    }
    this.persistence['communityContentUnchanged'] = true;
    await this.persist();
  }

  async retryCommunityLoad(): Promise<void> {
    const community: ExploreCommunityState = {
      phase: 'content', language: this.language(),
      cards: ['DAY_HEADER:0', 'FEATURED_ARTICLE:Ada_Lovelace'], error: null
    };
    this.state['community'] = community;
    this.persistence['hiddenCardsUnchanged'] = true;
    await this.emit({ leaf: 'featured_feed_http', attempt: 2, date: '2026-05-28', language: this.language() });
    await this.persist();
  }

  async retryCommunityLoadMore(): Promise<void> {
    const community: ExploreCommunityState = {
      phase: 'content',
      cards: ['DAY_HEADER:0', 'FEATURED_ARTICLE:Ada_Lovelace', 'DAY_HEADER:1', 'NEWS:Recovery'],
      error: null
    };
    this.state['community'] = community;
    this.persistence['existingDayZeroContentUnchanged'] = true;
    await this.emit({ leaf: 'featured_feed_http', attemptForLogicalAge: 2, logicalAge: 1, date: '2026-05-27' });
    await this.persist();
  }

  async resumeHomeSurface(): Promise<void> {
    const configured = this.strings(this.state['configuredLanguages']);
    const persisted = this.text(this.persistence, 'homeLanguage', '');
    const active = configured.includes(persisted) ? persisted : (configured.length > 0 ? configured[0] : 'en');
    this.state['activeLanguage'] = active;
    this.persistence['homeLanguage'] = active;
    const community: ExploreCommunityState = { phase: 'loading', language: active, cards: [] };
    this.state['community'] = community;
    await this.emit({ name: 'refreshCommunityContent', language: active, logicalAge: 0 });
    await this.persist();
  }

  async finishInterestEditing(): Promise<void> {
    const editor = this.state['interestEditor'] as Record<string, Object> | undefined;
    const changed = editor !== undefined && editor['interestsUpdated'] === true;
    this.state['interestEditorOpen'] = false;
    if (changed) {
      this.state['selectedTab'] = 'FOR_YOU';
      const forYou: ExploreForYouState = { phase: 'loading', modules: [] };
      this.state['forYou'] = forYou;
      this.persistence['interestArticles'] = ['en:Ada_Lovelace'];
      this.persistence['forYouCacheBeforeReload'] = '';
      await this.emit({ name: 'activityResult', value: 100 });
      await this.emit({ name: 'refreshForYouContent', language: this.language() });
    } else {
      this.state['forYouPhase'] = 'content';
      this.persistence['interestSelections'] = ['topic:technology'];
      this.persistence['forYouCacheUnchanged'] = true;
      await this.emit({ name: 'finishPersonalization', result: 'RESULT_OK' });
    }
    await this.persist();
  }

  async retryForYouLoad(): Promise<void> {
    this.state['forYouPhase'] = 'content';
    this.state['forYouError'] = JSON.parse('null') as Object;
    this.state['forYouModules'] = ['BASED_ON_INTEREST:0'];
    const cache: ExploreCacheState = {
      date: 'today', language: this.language(), modules: ['BASED_ON_INTEREST:0']
    };
    this.persistence['forYouCache'] = cache;
    await this.emit({ name: 'fetchForYouModules', batch: 0, attempt: 2 });
    await this.emit({ name: 'writeCurrentDayForYouCache', language: this.language() });
    await this.persist();
  }

  async confirmAllModulesOff(): Promise<void> {
    const hidden = ['BASED_ON_INTEREST', 'BECAUSE_YOU_READ', 'CONTINUE_READING'];
    this.state['pendingAllModulesOffConfirmation'] = false;
    this.state['selectedTab'] = 'FOR_YOU';
    this.state['forYouVisibleModules'] = [];
    this.state['forYouEmptyState'] = 'ALL_MODULES_HIDDEN';
    this.state['manageModulesActionAvailable'] = true;
    this.state['manageModulesDestination'] = 'FOR_YOU_MODULES';
    const visibility: ExploreVisibilityState = {
      BASED_ON_INTEREST: false, BECAUSE_YOU_READ: false, CONTINUE_READING: false
    };
    this.state['forYouModuleVisibility'] = visibility;
    this.persistence['hiddenModules'] = hidden;
    this.persistence['survivesHomeRecreation'] = true;
    await this.emit({ name: 'propagateHiddenModules', surfaces: ['for_you_module_settings', 'for_you_feed'] });
    await this.persist();
  }

  currentState(): Record<string, Object> { return clone(this.state); }
  currentPersistence(): Record<string, Object> { return clone(this.persistence); }

  private async emit(effect: ExploreEffect): Promise<void> { await this.leaf.emit(effect); }

  private async persist(): Promise<void> {
    await this.store.put('snapshot', JSON.stringify(this.persistence));
    await this.store.flush();
  }

  private language(): string { return this.text(this.persistence, 'homeLanguage', 'en'); }

  private text(value: Record<string, Object>, key: string, fallback: string): string {
    const item = value[key];
    return typeof item === 'string' && item.length > 0 ? item : fallback;
  }

  private strings(value: Object | undefined): string[] {
    return Array.isArray(value) ? value as string[] : [];
  }
}
