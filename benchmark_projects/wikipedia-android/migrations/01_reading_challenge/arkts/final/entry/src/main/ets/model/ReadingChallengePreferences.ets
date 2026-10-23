import { common } from '@kit.AbilityKit';
import { preferences } from '@kit.ArkData';
import { ChallengePersistence, ChallengePreferences } from './ReadingChallengeStore';

export class ReadingChallengePreferences implements ChallengePersistence {
  private store: preferences.Preferences;

  private constructor(store: preferences.Preferences) {
    this.store = store;
  }

  static async create(context: common.UIAbilityContext): Promise<ReadingChallengePreferences> {
    const store = await preferences.getPreferences(context, 'reading_challenge');
    return new ReadingChallengePreferences(store);
  }

  async load(): Promise<ChallengePreferences> {
    return {
      enrolled: await this.store.get('enrolled', false) as boolean,
      streak: await this.store.get('streak', 0) as number,
      lastReadDate: await this.store.get('lastReadDate', '') as string || undefined,
      enrollmentDate: await this.store.get('enrollmentDate', '') as string || undefined
    };
  }

  async save(value: ChallengePreferences): Promise<void> {
    await this.store.put('enrolled', value.enrolled);
    await this.store.put('streak', value.streak);
    await this.store.put('lastReadDate', value.lastReadDate ?? '');
    await this.store.put('enrollmentDate', value.enrollmentDate ?? '');
    await this.store.flush();
  }
}
