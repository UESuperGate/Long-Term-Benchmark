import { common } from '@kit.AbilityKit';
import {
  ChallengeClock,
  ChallengeEffects,
  ChallengeViewState,
  ReadingChallengeStore,
  SystemChallengeClock
} from '../model/ReadingChallengeStore';
import { ReadingChallengePreferences } from '../model/ReadingChallengePreferences';
import {
  CallbackReadingPageOwner,
  ReadingIntegrationInput,
  ReadingIntegrationState,
  ReadingPageOwner
} from '../integration/ReadingPageIntegration';

class PageEffects implements ChallengeEffects {
  private record: (effect: string) => void;

  constructor(record: (effect: string) => void) {
    this.record = record;
  }

  heartbeat(state: ChallengeViewState): void {
    this.record('heartbeat:' + state.name);
  }

  updateWidget(): void {
    this.record('widget_update');
  }

  refreshSurface(): void {
    this.record('challenge_surface_refreshed');
  }
}

@Entry
@Component
struct Index {
  @State challengeName: string = 'loading';
  @State streak: number = 0;
  @State articleOpen: boolean = false;
  @State effectSummary: string = '';
  private store?: ReadingChallengeStore;
  private runtimeOwnerId: string = 'Index:' + String(Date.now());

  async aboutToAppear(): Promise<void> {
    const context = getContext(this) as common.UIAbilityContext;
    await this.initialize(context, new SystemChallengeClock(), new PageEffects((effect: string) => {
      this.effectSummary = effect;
    }));
    await this.refreshChallengeSurface();
  }

  private async initialize(context: common.UIAbilityContext, clock: ChallengeClock,
    effects: ChallengeEffects): Promise<void> {
    const persistence = await ReadingChallengePreferences.create(context);
    this.store = new ReadingChallengeStore(
      clock,
      persistence,
      effects
    );
  }

  private async refreshChallengeSurface(): Promise<void> {
    if (this.store) {
      this.apply(await this.store.refresh());
    }
  }

  private async joinChallenge(): Promise<void> {
    if (this.store) {
      this.apply(await this.store.enroll());
    }
  }

  private async openArticle(): Promise<void> {
    this.articleOpen = true;
    if (this.store) {
      this.apply(await this.store.openArticle());
    }
  }

  private apply(state: ChallengeViewState): void {
    this.challengeName = state.name;
    this.streak = state.streak;
  }

  createRuntimeOwner(): ReadingPageOwner {
    return new CallbackReadingPageOwner(
      async (context: common.UIAbilityContext, input: ReadingIntegrationInput): Promise<void> => {
        await this.initialize(context, input.clock as ChallengeClock, input.effects as ChallengeEffects);
      },
      async (): Promise<void> => { await this.refreshChallengeSurface(); },
      async (): Promise<void> => { await this.joinChallenge(); },
      async (): Promise<void> => { await this.openArticle(); },
      (): ReadingIntegrationState => this.store ? this.store.state : {
        name: this.challengeName, streak: this.streak
      },
      (): boolean => this.articleOpen,
      (): boolean => this.store !== undefined,
      (): string => this.runtimeOwnerId
    );
  }

  build() {
    Column({ space: 16 }) {
      Text('Wikipedia Reading Challenge')
        .fontSize(26)
        .fontWeight(FontWeight.Bold)
      Text('State: ' + this.challengeName)
      Text('Streak: ' + this.streak)
      Button('Join challenge')
        .onClick(async () => {
          await this.joinChallenge();
        })
      Button(this.articleOpen ? 'Article open' : 'Open article')
        .onClick(async () => {
          await this.openArticle();
        })
      Button('Refresh')
        .onClick(async () => {
          await this.refreshChallengeSurface();
        })
      Text(this.effectSummary)
        .fontSize(12)
        .fontColor('#54595D')
    }
    .width('100%')
    .height('100%')
    .padding(24)
    .justifyContent(FlexAlign.Center)
  }
}
