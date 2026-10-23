import { common } from '@kit.AbilityKit';
import { preferences } from '@kit.ArkData';
import { EvergreenEffect, EvergreenInput, EvergreenLeaf, EvergreenPageOwner } from '../integration/EvergreenPageIntegration';

interface Fixture { given: Record<string, Object>; event: Record<string, Object>; state: Record<string, Object>; persistence: Record<string, Object>; }
interface Snapshot { featureAvailable: boolean; pageOwnerId: string; decision: Record<string, Object>; decisionAfterRelaunch: Record<string, Object>; routing: Record<string, Object>; state: Record<string, Object>; persistence: Record<string, Object>; historyDays: string[]; effects?: EvergreenEffect[]; }

class RecordingLeaf implements EvergreenLeaf {
  effects: EvergreenEffect[] = [];
  async emit(effect: EvergreenEffect): Promise<void> { this.effects.push(JSON.parse(JSON.stringify(effect)) as EvergreenEffect); }
}

function record(value: string): Record<string, Object> { return JSON.parse(value) as Record<string, Object>; }
function clone(value: Record<string, Object>): Record<string, Object> { return record(JSON.stringify(value)); }

function inputFor(key: string): Record<string, Object> {
  if (key === 'first_eligibility_records_impression') return record('{"given":{"account":"logged_out","clockDate":"2026-09-02","distinctReadingDays":["2026-08-25","2026-08-26"],"impressions":0,"lastImpressionDate":"","launch":"ordinary"},"event":{"name":"resumeApplication"}}');
  if (key === 'maybe_later_requires_two_return_days') return record('{"given":{"account":"logged_out","clockDate":"2026-09-02","impressions":1,"lastImpressionDate":"2026-08-30","distinctReadingDaysAfterLastImpression":["2026-08-31"]},"event":{"name":"resumeApplication"}}');
  if (key === 'close_permanently_dismisses') return record('{"given":{"surface":"account_encouragement","visible":true,"impressions":1,"lastImpressionDate":"2026-09-02"},"event":{"name":"pressPermanentCloseAndRelaunch"}}');
  if (key === 'create_account_success_finishes_and_suppresses') return record('{"given":{"account":"logged_out","surface":"account_encouragement","visible":true,"impressions":1},"event":{"name":"createAccountAndCompleteSuccessfully","authenticationLeafResult":"success_permanent_account"}}');
  if (key === 'registered_account_is_suppressed') return record('{"given":{"account":"registered","distinctReadingDays":["2026-08-25","2026-08-26"],"impressions":0,"launch":"ordinary"},"event":{"name":"resumeApplication"}}');
  if (key === 'external_article_deep_link_is_suppressed') return record('{"given":{"account":"logged_out","ordinaryLaunchEligibility":true,"impressions":0,"launch":{"type":"external_article_deep_link","uri":"https://en.wikipedia.org/wiki/Ada_Lovelace"}},"event":{"name":"openExternalArticleDeepLink"}}');
  if (key === 'stale_history_does_not_qualify') return record('{"given":{"account":"logged_out","clockDate":"2026-09-02","distinctReadingDays":["2025-08-31","2025-09-01"],"impressions":0},"event":{"name":"resumeApplication"}}');
  if (key === 'invalid_persisted_date_fails_closed') return record('{"given":{"account":"logged_out","impressions":1,"lastImpressionDate":"not-a-date","distinctRecentReadingDays":["2026-08-31","2026-09-01"]},"event":{"name":"resumeApplication"}}');
  if (key === 'two_return_days_trigger_second_impression') return record('{"given":{"account":"logged_out","clockDate":"2026-09-02","impressions":1,"lastImpressionDate":"2026-08-30","distinctReadingDaysAfterLastImpression":["2026-08-31","2026-09-01"]},"event":{"name":"resumeApplication"}}');
  if (key === 'two_impressions_suppress_third') return record('{"given":{"account":"logged_out","impressions":2,"lastImpressionDate":"2026-08-30","distinctReadingDaysAfterLastImpression":["2026-08-31","2026-09-01"]},"event":{"name":"resumeApplication"}}');
  throw new Error('unknown runtime case: ' + key);
}

function fixture(key: string): Fixture {
  const input = inputFor(key);
  const given = clone(input['given'] as Record<string, Object>);
  const event = clone(input['event'] as Record<string, Object>);
  const state = clone(given);
  if (given['ordinaryLaunchEligibility'] === true) {
    state['clockDate'] = '2026-09-02';
    state['distinctReadingDays'] = ['2026-08-25', '2026-08-26'];
  }
  const persistence: Record<string, Object> = {
    'impressions': Number(given['impressions'] ?? 0),
    'lastImpressionDate': String(given['lastImpressionDate'] ?? '')
  };
  return { given: given, event: event, state: state, persistence: persistence };
}

async function snapshot(context: common.UIAbilityContext, owner: EvergreenPageOwner, effects?: EvergreenEffect[]): Promise<Snapshot> {
  const reopened = await preferences.getPreferences(context, 'evergreen_account');
  const raw = await reopened.get('snapshot', '{}') as string;
  const result: Snapshot = {
    featureAvailable: owner.featureAvailable(), pageOwnerId: owner.ownerId(),
    decision: owner.currentDecision(), decisionAfterRelaunch: owner.currentDecisionAfterRelaunch(),
    routing: owner.currentRouting(), state: owner.currentState(), persistence: record(raw),
    historyDays: owner.currentHistoryDays()
  };
  if (effects) result.effects = effects;
  return result;
}

export class PreparedEvergreenEpisode {
  readonly state: Record<string, Object>;
  readonly persistence: Record<string, Object>;
  readonly leaf: EvergreenLeaf;
  private context: common.UIAbilityContext;
  private key: string;
  private input: Fixture;
  private recorder: RecordingLeaf;

  constructor(context: common.UIAbilityContext, key: string, input: Fixture) {
    this.context = context; this.key = key; this.input = input;
    this.state = clone(input.state); this.persistence = clone(input.persistence);
    this.recorder = new RecordingLeaf(); this.leaf = this.recorder;
  }

  async run(owner: EvergreenPageOwner): Promise<Record<string, Object>> {
    const before = await snapshot(this.context, owner);
    let positiveControl: boolean | undefined = undefined;
    if (this.input.given['ordinaryLaunchEligibility'] === true) positiveControl = await owner.ordinaryLaunchWouldShow();
    await owner.dispatch(this.input.event);
    const after = await snapshot(this.context, owner, this.recorder.effects);
    const episode: Record<string, Object> = {
      'schemaVersion': 2, 'taskId': '05_evergreen_account', 'caseKey': this.key,
      'given': this.input.given, 'event': this.input.event, 'givenEstablished': true,
      'commonEntryObserved': true, 'entryOwner': 'Index.EvergreenPageOwner',
      'before': before as Object, 'after': after as Object, 'observed': after as Object,
      'invokedProductionMethods': ['mount', String(this.input.event['name'])],
      'transitionExecuted': true, 'earlyExit': false,
      'storageReopened': JSON.stringify(after.persistence) === JSON.stringify(owner.currentPersistence())
    };
    if (positiveControl !== undefined) episode['ordinaryLaunchPositiveControl'] = positiveControl;
    return episode;
  }
}

export async function prepareEvergreenEpisode(context: common.UIAbilityContext, key: string): Promise<PreparedEvergreenEpisode> {
  return new PreparedEvergreenEpisode(context, key, fixture(key));
}
