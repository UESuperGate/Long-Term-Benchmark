import { common } from '@kit.AbilityKit';
import { preferences } from '@kit.ArkData';
import {
  ReadingIntegrationClock as ChallengeClock,
  ReadingIntegrationEffects as ChallengeEffects,
  ReadingIntegrationState as ChallengeViewState,
  ReadingPageOwner
} from '../integration/ReadingPageIntegration';

interface ChallengePreferences {
  enrolled: boolean;
  streak: number;
  lastReadDate?: string;
  enrollmentDate?: string;
}

interface ReadingFixture {
  date: string;
  event: string;
  preferences: ChallengePreferences;
}

interface ReadingPersistenceSnapshot {
  enrolled: boolean;
  streak: number;
  lastReadDate: string | null;
  enrollmentDate: string | null;
  unchanged?: boolean;
}

export interface ReadingRuntimeSnapshot {
  clockDate: string;
  featureAvailable: boolean;
  pageOwnerId: string;
  state: ChallengeViewState;
  persistence: ReadingPersistenceSnapshot;
}

interface ReadingObserved extends ReadingRuntimeSnapshot {
  effects: string[];
}

export interface ReadingRuntimeEpisode {
  caseKey: string;
  before: ReadingRuntimeSnapshot;
  after: ReadingRuntimeSnapshot;
  observed: ReadingObserved;
}

class FixedClock implements ChallengeClock {
  private value: string;

  constructor(value: string) {
    this.value = value;
  }

  today(): string {
    return this.value;
  }
}

class RecordingEffects implements ChallengeEffects {
  values: string[] = [];

  heartbeat(state: ChallengeViewState): void {
    this.values.push('heartbeat_requested');
  }

  updateWidget(): void {
    this.values.push('widget_update_requested');
  }

  refreshSurface(): void {
    this.values.push('challenge_surface_refreshed');
  }

  clear(): void {
    this.values = [];
  }
}

function fixture(key: string): ReadingFixture {
  if (key === 'before_start') {
    return { date: '2026-05-10', event: 'refresh', preferences: { enrolled: false, streak: 0 } };
  }
  if (key === 'start_not_enrolled') {
    return { date: '2026-05-11', event: 'refresh', preferences: { enrolled: false, streak: 0 } };
  }
  if (key === 'enroll') {
    return { date: '2026-05-11', event: 'enroll', preferences: { enrolled: false, streak: 0 } };
  }
  if (key === 'first_read') {
    return { date: '2026-05-11', event: 'openArticle',
      preferences: { enrolled: true, streak: 0, enrollmentDate: '2026-05-11' } };
  }
  if (key === 'duplicate_same_day') {
    return { date: '2026-05-11', event: 'openArticle',
      preferences: { enrolled: true, streak: 1, lastReadDate: '2026-05-11' } };
  }
  if (key === 'next_day_continues') {
    return { date: '2026-05-12', event: 'openArticle',
      preferences: { enrolled: true, streak: 1, lastReadDate: '2026-05-11' } };
  }
  if (key === 'gap_resets' || key === 'read_after_reset') {
    return { date: '2026-05-14', event: key === 'gap_resets' ? 'refresh' : 'openArticle',
      preferences: { enrolled: true, streak: 3, lastReadDate: '2026-05-12' } };
  }
  if (key === 'goal_completion') {
    return { date: '2026-06-04', event: 'openArticle',
      preferences: { enrolled: true, streak: 24, lastReadDate: '2026-06-03' } };
  }
  if (key === 'post_end_broken_rejected') {
    return { date: '2026-06-20', event: 'openArticle',
      preferences: { enrolled: true, streak: 10, lastReadDate: '2026-06-18' } };
  }
  throw new Error('Unknown runtime case: ' + key);
}

function samePreferences(left: ReadingPersistenceSnapshot, right: ReadingPersistenceSnapshot): boolean {
  return left.enrolled === right.enrolled && left.streak === right.streak &&
    left.lastReadDate === right.lastReadDate && left.enrollmentDate === right.enrollmentDate;
}

async function seedPreferences(context: common.UIAbilityContext, value: ChallengePreferences): Promise<void> {
  const store = await preferences.getPreferences(context, 'reading_challenge');
  await store.clear();
  await store.put('enrolled', value.enrolled);
  await store.put('streak', value.streak);
  await store.put('lastReadDate', value.lastReadDate ?? '');
  await store.put('enrollmentDate', value.enrollmentDate ?? '');
  await store.flush();
}

async function reopenPersistence(context: common.UIAbilityContext): Promise<ReadingPersistenceSnapshot> {
  const reopened = await preferences.getPreferences(context, 'reading_challenge');
  const lastReadDate = await reopened.get('lastReadDate', '') as string;
  const enrollmentDate = await reopened.get('enrollmentDate', '') as string;
  return {
    enrolled: await reopened.get('enrolled', false) as boolean,
    streak: await reopened.get('streak', 0) as number,
    lastReadDate: lastReadDate.length > 0 ? lastReadDate : null,
    enrollmentDate: enrollmentDate.length > 0 ? enrollmentDate : null
  };
}

async function snapshot(context: common.UIAbilityContext, date: string,
  driver: ReadingPageOwner): Promise<ReadingRuntimeSnapshot> {
  const state = driver.currentState();
  return {
    clockDate: date,
    featureAvailable: driver.featureAvailable(),
    pageOwnerId: driver.ownerId(),
    state: { name: state.name, streak: state.streak },
    persistence: await reopenPersistence(context)
  };
}

export class PreparedReadingEpisode {
  readonly clock: ChallengeClock;
  readonly effects: ChallengeEffects;
  private context: common.UIAbilityContext;
  private key: string;
  private input: ReadingFixture;
  private recorder: RecordingEffects;

  constructor(context: common.UIAbilityContext, key: string, input: ReadingFixture) {
    this.context = context;
    this.key = key;
    this.input = input;
    this.clock = new FixedClock(input.date);
    this.recorder = new RecordingEffects();
    this.effects = this.recorder;
  }

  async run(driver: ReadingPageOwner): Promise<ReadingRuntimeEpisode> {
    if (this.input.event !== 'refresh') {
      await driver.refresh();
    }
    const before = await snapshot(this.context, this.input.date, driver);
    this.recorder.clear();
    if (this.input.event === 'refresh') {
      await driver.refresh();
    } else if (this.input.event === 'enroll') {
      await driver.enroll();
    } else {
      await driver.openArticle();
    }
    const after = await snapshot(this.context, this.input.date, driver);
    after.persistence.unchanged = samePreferences(before.persistence, after.persistence);
    const observed: ReadingObserved = {
      clockDate: after.clockDate,
      featureAvailable: after.featureAvailable,
      pageOwnerId: after.pageOwnerId,
      state: after.state,
      persistence: after.persistence,
      effects: this.recorder.values.slice()
    };
    return { caseKey: this.key, before: before, after: after, observed: observed };
  }
}

export async function prepareReadingEpisode(context: common.UIAbilityContext,
  key: string): Promise<PreparedReadingEpisode> {
  const input = fixture(key);
  await seedPreferences(context, input.preferences);
  return new PreparedReadingEpisode(context, key, input);
}
