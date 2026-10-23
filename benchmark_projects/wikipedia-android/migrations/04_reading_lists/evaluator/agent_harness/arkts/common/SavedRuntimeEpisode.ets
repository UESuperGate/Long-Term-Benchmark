import { common } from '@kit.AbilityKit';
import { preferences } from '@kit.ArkData';
import {
  SavedEffect,
  SavedLeaf,
  SavedPageOwner
} from '../integration/SavedPageIntegration';

interface SavedFixture {
  given: Record<string, Object>;
  event: Record<string, Object>;
  state: Record<string, Object>;
  persistence: Record<string, Object>;
}

interface SavedRuntimeSnapshot {
  featureAvailable: boolean;
  pageOwnerId: string;
  state: Record<string, Object>;
  persistence: Record<string, Object>;
  ownerPersistence: Record<string, Object>;
}

interface SavedRuntimeObserved extends SavedRuntimeSnapshot {
  effects: SavedEffect[];
}

export interface SavedRuntimeEpisode {
  schemaVersion: number;
  taskId: string;
  caseKey: string;
  given: Record<string, Object>;
  event: Record<string, Object>;
  givenEstablished: boolean;
  commonEntryObserved: boolean;
  entryOwner: string;
  before: SavedRuntimeSnapshot;
  after: SavedRuntimeSnapshot;
  observed: SavedRuntimeObserved;
  invokedProductionMethods: string[];
  transitionExecuted: boolean;
  earlyExit: boolean;
  storageReopened: boolean;
}

class RecordingSavedLeaf implements SavedLeaf {
  effects: SavedEffect[] = [];

  async emit(effect: SavedEffect): Promise<void> {
    this.effects.push(JSON.parse(JSON.stringify(effect)) as SavedEffect);
  }
}

function record(value: string): Record<string, Object> {
  return JSON.parse(value) as Record<string, Object>;
}

function clone(value: Record<string, Object>): Record<string, Object> {
  return JSON.parse(JSON.stringify(value)) as Record<string, Object>;
}

function inputFor(key: string): Record<string, Object> {
  if (key === 'all_articles_deduplicates_memberships') {
    return record('{"given":{"roomLists":[{"title":"Saved","isDefault":true,"articles":["en:Ada_Lovelace","en:Paris"]},{"title":"People","isDefault":false,"articles":["en:Ada_Lovelace"]},{"title":"Places","isDefault":false,"articles":["fr:Paris"]}]},"event":{"name":"openSavedSurface"}}');
  }
  if (key === 'collections_tab_uses_own_sort_and_excludes_default') {
    return record('{"given":{"selectedTab":"ALL_ARTICLES","roomLists":[{"title":"Saved","isDefault":true},{"title":"Zoo","isDefault":false},{"title":"Alpha","isDefault":false}],"persistedSortModes":{"ALL_ARTICLES":1,"COLLECTIONS":0}},"event":{"name":"selectSavedTab","tab":"COLLECTIONS"}}');
  }
  if (key === 'all_articles_search_is_debounced_and_scoped') {
    return record('{"given":{"selectedTab":"ALL_ARTICLES","searchQuery":null,"searchDebounceMillis":150,"articleRows":["en:Cafe","en:Tea"],"collectionTitles":["Cafe Collection"]},"event":{"name":"enterSavedSearchQuery","query":"cafe","observeAfterMillis":150}}');
  }
  if (key === 'default_only_filter_uses_all_memberships') {
    return record('{"given":{"selectedTab":"ALL_ARTICLES","selectedArticleFilter":"ALL_ARTICLES","articleMemberships":{"en:Default_only":["Saved"],"en:Default_and_travel":["Saved","Travel"],"en:Travel_only":["Travel"]}},"event":{"name":"selectArticleFilter","filter":"NOT_IN_COLLECTION"}}');
  }
  if (key === 'select_all_targets_visible_deduplicated_rows') {
    return record('{"given":{"selectedTab":"ALL_ARTICLES","selectedArticleFilter":"NOT_IN_COLLECTION","visibleArticleRows":[{"id":11,"article":"en:Ada_Lovelace"},{"id":12,"article":"en:Grace_Hopper"}],"hiddenByFilter":[{"id":13,"article":"en:Paris","collections":["Saved","Travel"]}],"selection":{"enabled":true,"selectedPageIds":[]}},"event":{"name":"selectAllVisibleRows"}}');
  }
  if (key === 'offline_redirect_failure_saves_original_and_propagates') {
    return record('{"given":{"article":{"language":"en","apiTitle":"Original_Title","displayTitle":"Original Title"},"memberships":[],"redirectMetadataHttp":"error:io","savedSurface":{"selectedTab":"ALL_ARTICLES","articleRows":[]}},"event":{"name":"openSaveArticleSheet","article":"en:Original_Title"}}');
  }
  if (key === 'cancel_named_unsave_is_noop') {
    return record('{"given":{"saveSheet":{"article":"en:Ada_Lovelace","isSaved":true,"pendingConfirmation":true},"memberships":["Saved","People"]},"event":{"name":"cancelUnsaveConfirmation"}}');
  }
  if (key === 'delete_deduplicated_article_undo_restores_memberships') {
    return record('{"given":{"selectedTab":"ALL_ARTICLES","queuedForDeletion":{"en:Ada_Lovelace":["Saved","People"]},"visibleArticleRows":["en:Grace_Hopper"],"undoAvailable":true},"event":{"name":"undoArticleDeletion"}}');
  }
  if (key === 'missing_collection_toggle_is_noop') {
    return record('{"given":{"article":"en:Ada_Lovelace","memberships":["Saved"],"roomCollections":[{"title":"Saved","isDefault":true}],"queuedCollectionToggle":{"collectionId":"observed-created-People-id","title":"People"}},"event":{"name":"resumeQueuedCollectionToggle"}}');
  }
  if (key === 'login_then_refresh_retries_sync_to_completion') {
    return record('{"given":{"selectedTab":"ALL_ARTICLES","articleRows":[],"account":{"isLoggedIn":true,"isTemporary":false,"userName":"Ada"},"previousRefreshAttempt":{"outcome":"login_prompt","syncStarted":false},"isRefreshing":false,"readingListSyncEnabled":false,"onboarding":"SyncReminder","nextSyncCompletion":"held"},"event":{"name":"retryPullToRefreshAndCompleteSync"}}');
  }
  throw new Error('Unknown runtime case: ' + key);
}

function fixture(key: string): SavedFixture {
  const input = inputFor(key);
  const given = input['given'] as Record<string, Object>;
  const event = input['event'] as Record<string, Object>;
  const state: Record<string, Object> = {};
  const persistence: Record<string, Object> = {};
  state['selectedTab'] = typeof given['selectedTab'] === 'string' ? given['selectedTab'] : 'ALL_ARTICLES';
  if (key === 'all_articles_deduplicates_memberships' ||
    key === 'collections_tab_uses_own_sort_and_excludes_default') {
    state['roomLists'] = given['roomLists'];
  } else if (key === 'all_articles_search_is_debounced_and_scoped') {
    state['sourceArticleRows'] = JSON.parse('[{"article":"en:Cafe","displayTitle":"Café"},{"article":"en:Tea","displayTitle":"Tea"}]') as Object;
  } else if (key === 'default_only_filter_uses_all_memberships') {
    state['articleMemberships'] = given['articleMemberships'];
  } else if (key === 'select_all_targets_visible_deduplicated_rows') {
    state['visibleArticleRows'] = given['visibleArticleRows'];
  } else if (key === 'offline_redirect_failure_saves_original_and_propagates') {
    state['article'] = given['article'];
  } else if (key === 'cancel_named_unsave_is_noop') {
    state['saveSheet'] = given['saveSheet'];
    persistence['memberships'] = given['memberships'];
  } else if (key === 'delete_deduplicated_article_undo_restores_memberships') {
    state['visibleArticleRows'] = given['visibleArticleRows'];
    persistence['memberships'] = given['queuedForDeletion'];
  } else if (key === 'missing_collection_toggle_is_noop') {
    state['article'] = given['article'];
    state['queuedCollectionToggle'] = given['queuedCollectionToggle'];
    persistence['memberships'] = given['memberships'];
    persistence['roomCollections'] = given['roomCollections'];
  } else {
    state['articleRows'] = given['articleRows'];
    state['account'] = given['account'];
    state['previousRefreshAttempt'] = given['previousRefreshAttempt'];
    state['isRefreshing'] = given['isRefreshing'];
    state['onboarding'] = given['onboarding'];
    persistence['readingListSyncEnabled'] = given['readingListSyncEnabled'];
  }
  const result: SavedFixture = {
    given: clone(given), event: clone(event), state: state, persistence: persistence
  };
  return result;
}

async function snapshot(context: common.UIAbilityContext,
  owner: SavedPageOwner): Promise<SavedRuntimeSnapshot> {
  const reopened = await preferences.getPreferences(context, 'saved_surface');
  const raw = await reopened.get('snapshot', '{}') as string;
  const result: SavedRuntimeSnapshot = {
    featureAvailable: owner.featureAvailable(),
    pageOwnerId: owner.ownerId(),
    state: owner.currentState(),
    persistence: record(raw),
    ownerPersistence: owner.currentPersistence()
  };
  return result;
}

export class PreparedSavedEpisode {
  readonly state: Record<string, Object>;
  readonly persistence: Record<string, Object>;
  readonly leaf: SavedLeaf;
  private context: common.UIAbilityContext;
  private key: string;
  private input: SavedFixture;
  private recorder: RecordingSavedLeaf;

  constructor(context: common.UIAbilityContext, key: string, input: SavedFixture) {
    this.context = context;
    this.key = key;
    this.input = input;
    this.state = clone(input.state);
    this.persistence = clone(input.persistence);
    this.recorder = new RecordingSavedLeaf();
    this.leaf = this.recorder;
  }

  async run(owner: SavedPageOwner): Promise<SavedRuntimeEpisode> {
    const before = await snapshot(this.context, owner);
    const methods: string[] = ['mount'];
    if (this.key === 'all_articles_deduplicates_memberships') {
      await owner.openSavedSurface();
      methods.push('openSavedSurface');
    } else if (this.key === 'collections_tab_uses_own_sort_and_excludes_default') {
      await owner.selectSavedTab(String(this.input.event['tab']));
      methods.push('selectSavedTab');
    } else if (this.key === 'all_articles_search_is_debounced_and_scoped') {
      await owner.enterSavedSearchQuery(String(this.input.event['query']), Number(this.input.event['observeAfterMillis']));
      methods.push('enterSavedSearchQuery');
    } else if (this.key === 'default_only_filter_uses_all_memberships') {
      await owner.selectArticleFilter(String(this.input.event['filter']));
      methods.push('selectArticleFilter');
    } else if (this.key === 'select_all_targets_visible_deduplicated_rows') {
      await owner.selectAllVisibleRows();
      methods.push('selectAllVisibleRows');
    } else if (this.key === 'offline_redirect_failure_saves_original_and_propagates') {
      await owner.openSaveArticleSheet();
      methods.push('openSaveArticleSheet');
    } else if (this.key === 'cancel_named_unsave_is_noop') {
      await owner.cancelUnsaveConfirmation();
      methods.push('cancelUnsaveConfirmation');
    } else if (this.key === 'delete_deduplicated_article_undo_restores_memberships') {
      await owner.undoArticleDeletion();
      methods.push('undoArticleDeletion');
    } else if (this.key === 'missing_collection_toggle_is_noop') {
      await owner.resumeQueuedCollectionToggle();
      methods.push('resumeQueuedCollectionToggle');
    } else {
      await owner.retryPullToRefreshAndCompleteSync();
      methods.push('retryPullToRefreshAndCompleteSync');
    }
    const after = await snapshot(this.context, owner);
    const observed: SavedRuntimeObserved = {
      featureAvailable: after.featureAvailable,
      pageOwnerId: after.pageOwnerId,
      state: after.state,
      persistence: after.persistence,
      ownerPersistence: after.ownerPersistence,
      effects: this.recorder.effects
    };
    const episode: SavedRuntimeEpisode = {
      schemaVersion: 2,
      taskId: '04_reading_lists',
      caseKey: this.key,
      given: this.input.given,
      event: this.input.event,
      givenEstablished: true,
      commonEntryObserved: true,
      entryOwner: 'Index.SavedPageOwner',
      before: before,
      after: after,
      observed: observed,
      invokedProductionMethods: methods,
      transitionExecuted: true,
      earlyExit: false,
      storageReopened: JSON.stringify(after.persistence) === JSON.stringify(after.ownerPersistence)
    };
    return episode;
  }
}

export async function prepareSavedEpisode(context: common.UIAbilityContext,
  key: string): Promise<PreparedSavedEpisode> {
  return new PreparedSavedEpisode(context, key, fixture(key));
}
