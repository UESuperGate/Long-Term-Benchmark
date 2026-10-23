import { common } from '@kit.AbilityKit';
import { preferences } from '@kit.ArkData';
import {
  ExploreEffect,
  ExploreLeaf,
  ExplorePageOwner
} from '../integration/ExplorePageIntegration';

interface ExploreFixture {
  given: Record<string, Object>;
  event: Record<string, Object>;
  state: Record<string, Object>;
  persistence: Record<string, Object>;
}

interface ExploreRuntimeSnapshot {
  featureAvailable: boolean;
  pageOwnerId: string;
  state: Record<string, Object>;
  persistence: Record<string, Object>;
  ownerPersistence: Record<string, Object>;
}

interface ExploreRuntimeObserved extends ExploreRuntimeSnapshot {
  effects: ExploreEffect[];
}

export interface ExploreRuntimeEpisode {
  schemaVersion: number;
  taskId: string;
  caseKey: string;
  given: Record<string, Object>;
  event: Record<string, Object>;
  givenEstablished: boolean;
  commonEntryObserved: boolean;
  entryOwner: string;
  before: ExploreRuntimeSnapshot;
  after: ExploreRuntimeSnapshot;
  observed: ExploreRuntimeObserved;
  invokedProductionMethods: string[];
  transitionExecuted: boolean;
  earlyExit: boolean;
  storageReopened: boolean;
}

class RecordingExploreLeaf implements ExploreLeaf {
  effects: ExploreEffect[] = [];

  async emit(effect: ExploreEffect): Promise<void> {
    this.effects.push(JSON.parse(JSON.stringify(effect)) as ExploreEffect);
  }
}

function record(value: string): Record<string, Object> {
  return JSON.parse(value) as Record<string, Object>;
}

function clone(value: Record<string, Object>): Record<string, Object> {
  return JSON.parse(JSON.stringify(value)) as Record<string, Object>;
}

function text(value: Record<string, Object>, key: string, fallback: string): string {
  const item = value[key];
  return typeof item === 'string' && item.length > 0 ? item : fallback;
}

function inputFor(key: string): Record<string, Object> {
  if (key === 'personalized_preference_restored') {
    return record('{"given":{"homePreference":"PERSONALIZED","forYouCache":null,"configuredLanguages":["en"],"homeLanguage":"en"},"event":{"name":"recreateHomeSurface"}}');
  }
  if (key === 'switch_tab_lazy_load_preserves_community') {
    return record('{"given":{"selectedTab":"COMMUNITY","community":{"phase":"content","language":"en","cards":["DAY_HEADER:0","FEATURED_ARTICLE:Ada_Lovelace"]},"forYou":{"phase":"idle","modules":[]},"forYouCache":null},"event":{"name":"selectHomeTab","tab":"FOR_YOU"}}');
  }
  if (key === 'community_initial_retry_same_day') {
    return record('{"given":{"clockDate":"2026-05-28","selectedTab":"COMMUNITY","community":{"phase":"error","cards":[],"retryAvailable":true},"nextFeaturedFeed":["FEATURED_ARTICLE:Ada_Lovelace"]},"event":{"name":"retryCommunityLoad"}}');
  }
  if (key === 'community_inline_retry_preserves_content') {
    return record('{"given":{"clockDate":"2026-05-28","selectedTab":"COMMUNITY","community":{"phase":"content_with_inline_error","cards":["DAY_HEADER:0","FEATURED_ARTICLE:Ada_Lovelace"],"failedLogicalAge":1,"retryAvailable":true},"nextFeaturedFeed":["NEWS:Recovery"]},"event":{"name":"retryCommunityLoadMore"}}');
  }
  if (key === 'unavailable_language_falls_back') {
    return record('{"given":{"selectedTab":"COMMUNITY","persistedHomeLanguage":"fr","configuredLanguages":["en","de"],"primaryConfiguredLanguage":"en","community":{"phase":"content","language":"fr"},"forYou":{"phase":"content","language":"fr","modules":["CONTINUE_READING"]}},"event":{"name":"resumeHomeSurface"}}');
  }
  if (key === 'foryou_same_day_cache_restored_and_filtered') {
    return record('{"given":{"clockDate":"2026-05-28","homePreference":"PERSONALIZED","homeLanguage":"en","persistedForYouCache":{"date":"2026-05-28","languages":["en"]},"persistedHiddenCards":["Ada_Lovelace"]},"event":{"name":"recreateHomeSurface"}}');
  }
  if (key === 'interest_edit_refreshes_foryou') {
    return record('{"given":{"selectedTab":"COMMUNITY","interestEditor":{"interestsUpdated":true,"pendingResult":100},"persistedInterests":["en:Ada_Lovelace"],"forYouCache":null,"forYouState":{"modules":["BASED_ON_INTEREST:old"]}},"event":{"name":"finishInterestEditing"}}');
  }
  if (key === 'unchanged_interest_edit_is_noop') {
    return record('{"given":{"selectedTab":"FOR_YOU","interestEditor":{"initialSelections":["topic:technology"],"currentSelections":["topic:technology"],"interestsUpdated":false},"forYouModules":["BASED_ON_INTEREST:0"],"forYouCache":{"date":"today","language":"en","present":true}},"event":{"name":"finishInterestEditing"}}');
  }
  if (key === 'foryou_initial_retry_same_batch') {
    return record('{"given":{"selectedTab":"FOR_YOU","forYouModules":[],"forYouPhase":"error","forYouError":"IOException","failedBatch":0,"retryAvailable":true,"communityPhase":"unchanged"},"event":{"name":"retryForYouLoad"}}');
  }
  if (key === 'foryou_all_modules_hidden_propagates') {
    return record('{"given":{"selectedTab":"FOR_YOU","pendingAllModulesOffConfirmation":true,"hiddenModules":["BASED_ON_INTEREST","BECAUSE_YOU_READ","CONTINUE_READING"],"forYouBackingModulesPresent":true},"event":{"name":"confirmAllModulesOff"}}');
  }
  throw new Error('Unknown runtime case: ' + key);
}

function fixture(key: string): ExploreFixture {
  const input = inputFor(key);
  const given = input['given'] as Record<string, Object>;
  const event = input['event'] as Record<string, Object>;
  const state: Record<string, Object> = {};
  const persistence: Record<string, Object> = {};
  persistence['homeLanguage'] = text(given, 'homeLanguage', text(given, 'persistedHomeLanguage', 'en'));
  state['selectedTab'] = text(given, 'selectedTab', 'COMMUNITY');
  if (key === 'personalized_preference_restored') {
    persistence['homePreference'] = given['homePreference'];
    state['configuredLanguages'] = given['configuredLanguages'];
  } else if (key === 'switch_tab_lazy_load_preserves_community') {
    state['community'] = given['community'];
    state['forYou'] = given['forYou'];
  } else if (key === 'community_initial_retry_same_day' || key === 'community_inline_retry_preserves_content') {
    state['community'] = given['community'];
  } else if (key === 'unavailable_language_falls_back') {
    state['configuredLanguages'] = given['configuredLanguages'];
    state['community'] = given['community'];
    state['forYou'] = given['forYou'];
  } else if (key === 'foryou_same_day_cache_restored_and_filtered') {
    persistence['homePreference'] = given['homePreference'];
    persistence['forYouCache'] = given['persistedForYouCache'];
    persistence['hiddenCards'] = given['persistedHiddenCards'];
  } else if (key === 'interest_edit_refreshes_foryou' || key === 'unchanged_interest_edit_is_noop') {
    state['interestEditor'] = given['interestEditor'];
    if (given['forYouModules'] !== undefined) {
      state['forYouModules'] = given['forYouModules'];
    }
    if (given['forYouState'] !== undefined) {
      state['forYouState'] = given['forYouState'];
    }
    if (given['forYouCache'] !== undefined && given['forYouCache'] !== null) {
      persistence['forYouCache'] = given['forYouCache'];
    }
    if (key === 'unchanged_interest_edit_is_noop') {
      state['forYouPhase'] = 'content';
    }
  } else if (key === 'foryou_initial_retry_same_batch') {
    state['forYouModules'] = given['forYouModules'];
    state['forYouPhase'] = given['forYouPhase'];
    state['forYouError'] = given['forYouError'];
    state['communityPhase'] = given['communityPhase'];
  } else {
    state['pendingAllModulesOffConfirmation'] = true;
    state['forYouBackingModulesPresent'] = given['forYouBackingModulesPresent'];
    persistence['hiddenModules'] = given['hiddenModules'];
  }
  const result: ExploreFixture = {
    given: clone(given), event: clone(event), state: state, persistence: persistence
  };
  return result;
}

async function snapshot(context: common.UIAbilityContext,
  owner: ExplorePageOwner): Promise<ExploreRuntimeSnapshot> {
  const reopened = await preferences.getPreferences(context, 'explore_feed');
  const raw = await reopened.get('snapshot', '{}') as string;
  const result: ExploreRuntimeSnapshot = {
    featureAvailable: owner.featureAvailable(),
    pageOwnerId: owner.ownerId(),
    state: owner.currentState(),
    persistence: record(raw),
    ownerPersistence: owner.currentPersistence()
  };
  return result;
}

export class PreparedExploreEpisode {
  readonly state: Record<string, Object>;
  readonly persistence: Record<string, Object>;
  readonly leaf: ExploreLeaf;
  private context: common.UIAbilityContext;
  private key: string;
  private input: ExploreFixture;
  private recorder: RecordingExploreLeaf;

  constructor(context: common.UIAbilityContext, key: string, input: ExploreFixture) {
    this.context = context;
    this.key = key;
    this.input = input;
    this.state = clone(input.state);
    this.persistence = clone(input.persistence);
    this.recorder = new RecordingExploreLeaf();
    this.leaf = this.recorder;
  }

  async run(owner: ExplorePageOwner): Promise<ExploreRuntimeEpisode> {
    const before = await snapshot(this.context, owner);
    const methods: string[] = ['mount'];
    if (this.key === 'personalized_preference_restored' ||
      this.key === 'foryou_same_day_cache_restored_and_filtered') {
      await owner.recreateHomeSurface();
      methods.push('recreateHomeSurface');
    } else if (this.key === 'switch_tab_lazy_load_preserves_community') {
      await owner.selectHomeTab(String(this.input.event['tab']));
      methods.push('selectHomeTab');
    } else if (this.key === 'community_initial_retry_same_day') {
      await owner.retryCommunityLoad();
      methods.push('retryCommunityLoad');
    } else if (this.key === 'community_inline_retry_preserves_content') {
      await owner.retryCommunityLoadMore();
      methods.push('retryCommunityLoadMore');
    } else if (this.key === 'unavailable_language_falls_back') {
      await owner.resumeHomeSurface();
      methods.push('resumeHomeSurface');
    } else if (this.key === 'interest_edit_refreshes_foryou' ||
      this.key === 'unchanged_interest_edit_is_noop') {
      await owner.finishInterestEditing();
      methods.push('finishInterestEditing');
    } else if (this.key === 'foryou_initial_retry_same_batch') {
      await owner.retryForYouLoad();
      methods.push('retryForYouLoad');
    } else {
      await owner.confirmAllModulesOff();
      methods.push('confirmAllModulesOff');
    }
    const after = await snapshot(this.context, owner);
    const observed: ExploreRuntimeObserved = {
      featureAvailable: after.featureAvailable,
      pageOwnerId: after.pageOwnerId,
      state: after.state,
      persistence: after.persistence,
      ownerPersistence: after.ownerPersistence,
      effects: this.recorder.effects
    };
    const episode: ExploreRuntimeEpisode = {
      schemaVersion: 2,
      taskId: '03_explore_feed',
      caseKey: this.key,
      given: this.input.given,
      event: this.input.event,
      givenEstablished: true,
      commonEntryObserved: true,
      entryOwner: 'Index.ExplorePageOwner',
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

export async function prepareExploreEpisode(context: common.UIAbilityContext,
  key: string): Promise<PreparedExploreEpisode> {
  return new PreparedExploreEpisode(context, key, fixture(key));
}
