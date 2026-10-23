export interface ChallengeClock {
  today(): string;
}

export class SystemChallengeClock implements ChallengeClock {
  today(): string {
    const now = new Date();
    const month = String(now.getMonth() + 1).padStart(2, '0');
    const day = String(now.getDate()).padStart(2, '0');
    return String(now.getFullYear()) + '-' + month + '-' + day;
  }
}

export interface ChallengePreferences {
  enrolled: boolean;
  streak: number;
  lastReadDate?: string;
  enrollmentDate?: string;
}

export interface ChallengePersistence {
  load(): Promise<ChallengePreferences>;
  save(value: ChallengePreferences): Promise<void>;
}

export interface ChallengeEffects {
  heartbeat(state: ChallengeViewState): void;
  updateWidget(): void;
  refreshSurface(): void;
}

export interface ChallengeViewState {
  name: string;
  streak: number;
}

export class ReadingChallengeStore {
  static readonly GOAL: number = 25;
  static readonly START_DATE: string = '2026-05-11';
  static readonly END_DATE: string = '2026-06-18';
  static readonly REMOVE_DATE: string = '2026-07-27';

  private value: ChallengePreferences = { enrolled: false, streak: 0 };
  state: ChallengeViewState = { name: 'loading', streak: 0 };
  private clock: ChallengeClock;
  private persistence: ChallengePersistence;
  private effects: ChallengeEffects;

  constructor(
    clock: ChallengeClock,
    persistence: ChallengePersistence,
    effects: ChallengeEffects
  ) {
    this.clock = clock;
    this.persistence = persistence;
    this.effects = effects;
  }

  async refresh(): Promise<ChallengeViewState> {
    this.value = await this.persistence.load();
    const changed = this.recalculateIfNeeded(this.clock.today());
    if (changed) {
      await this.persistence.save(this.value);
    }
    this.state = this.resolve(this.clock.today());
    return this.state;
  }

  async enroll(): Promise<ChallengeViewState> {
    const today = this.clock.today();
    if (today >= ReadingChallengeStore.START_DATE && today <= ReadingChallengeStore.END_DATE) {
      this.value.enrolled = true;
      this.value.enrollmentDate = today;
      await this.persistence.save(this.value);
      this.state = this.resolve(today);
      this.effects.heartbeat(this.state);
      this.effects.updateWidget();
    }
    this.state = this.resolve(today);
    return this.state;
  }

  async openArticle(): Promise<ChallengeViewState> {
    const today = this.clock.today();
    this.recalculateIfNeeded(today);
    const eligible = today >= ReadingChallengeStore.START_DATE &&
      today <= ReadingChallengeStore.REMOVE_DATE &&
      this.value.streak < ReadingChallengeStore.GOAL &&
      (!this.afterEnd(today) || this.hasActiveStreak(today));
    if (eligible && this.value.enrolled && this.value.lastReadDate !== today) {
      this.value.lastReadDate = today;
      this.value.streak += 1;
      await this.persistence.save(this.value);
      this.state = this.resolve(today);
      this.effects.heartbeat(this.state);
      this.effects.updateWidget();
      return this.state;
    }
    this.state = this.resolve(today);
    return this.state;
  }

  private recalculateIfNeeded(today: string): boolean {
    if (this.afterEnd(today) ||
      this.value.streak >= ReadingChallengeStore.GOAL ||
      !this.value.lastReadDate) {
      return false;
    }
    if (this.daysBetween(this.value.lastReadDate, today) > 1) {
      this.value.streak = 0;
      return true;
    }
    return false;
  }

  private resolve(today: string): ChallengeViewState {
    if (today > ReadingChallengeStore.REMOVE_DATE) {
      return { name: 'challenge_removed', streak: this.value.streak };
    }
    if (today < ReadingChallengeStore.START_DATE) {
      return { name: 'not_live_yet', streak: this.value.streak };
    }
    if (!this.value.enrolled) {
      return {
        name: this.afterEnd(today) ? 'challenge_concluded_no_streak' : 'not_enrolled',
        streak: this.value.streak
      };
    }
    if (this.value.streak >= ReadingChallengeStore.GOAL) {
      return { name: 'challenge_completed', streak: this.value.streak };
    }
    if (this.afterEnd(today) && !this.hasActiveStreak(today)) {
      return {
        name: this.value.streak > 0 ? 'challenge_concluded_incomplete' : 'challenge_concluded_no_streak',
        streak: this.value.streak
      };
    }
    if (this.value.streak === 0) {
      return { name: 'enrolled_not_started', streak: 0 };
    }
    return {
      name: this.value.lastReadDate === today ? 'streak_read_today' : 'streak_needs_reading',
      streak: this.value.streak
    };
  }

  private hasActiveStreak(today: string): boolean {
    return !!this.value.lastReadDate && this.daysBetween(this.value.lastReadDate, today) <= 1;
  }

  private afterEnd(today: string): boolean {
    return today > ReadingChallengeStore.END_DATE;
  }

  private daysBetween(from: string, to: string): number {
    const millis = Date.parse(to + 'T00:00:00Z') - Date.parse(from + 'T00:00:00Z');
    return Math.floor(millis / 86400000);
  }
}
