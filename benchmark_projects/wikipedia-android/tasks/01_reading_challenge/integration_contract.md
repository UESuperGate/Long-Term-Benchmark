# Reading Challenge Integration Contract

This document contains only stable production API shape and integration boundaries. Evaluator-owned data is intentionally excluded.

## Runtime integration rule

Semantic tests must execute a real application-owned entry path. On Android, every event enters `ReadingChallengePageActionPrefix`; article reads then pass through `PageLoadCompleteActionPrefix`, and state resolution, streak maintenance, persistence access, and effect dispatch run through `ReadingChallengeWidgetRepository`. Enrollment passes through `ReadingChallengeEnrollmentAction`. An evaluator adapter may control only the external leaves listed below. On ArkTS, the page must own a real `ReadingChallengeStore`, and user actions must reach `refresh`, `enroll`, or `openArticle` through that store. A harness implementation of the business rules is not a valid substitute.

## Android production sources

- `app/src/main/java/org/wikipedia/widgets/readingchallenge/ReadingChallengeWidgetRepository.kt`
- `app/src/main/java/org/wikipedia/widgets/readingchallenge/ReadingChallengeState.kt`
- `app/src/main/java/org/wikipedia/widgets/readingchallenge/ReadingChallengeWidget.kt`
- `app/src/main/java/org/wikipedia/widgets/readingchallenge/ReadingChallengeAnalyticsHelper.kt`
- `app/src/main/java/org/wikipedia/widgets/readingchallenge/ReadingChallengeOnboardingActivity.kt` for the enrollment entry
- `app/src/main/java/org/wikipedia/widgets/readingchallenge/ReadingChallengeEnrollmentAction.kt`, the focused executable extraction of the eligible Join branch
- `app/src/main/java/org/wikipedia/settings/Prefs.kt`
- `app/src/main/java/org/wikipedia/page/PageActivity.kt` for the article page lifecycle entry that dispatches the qualifying-read update

Package: `org.wikipedia.widgets.readingchallenge`

```kotlin
sealed interface ReadingChallengeState {
    object Loading : ReadingChallengeState
    object NotLiveYet : ReadingChallengeState
    object NotEnrolled : ReadingChallengeState
    object EnrolledNotStarted : ReadingChallengeState
    data class StreakOngoingNeedsReading(val streak: Int) : ReadingChallengeState
    data class StreakOngoingReadToday(val streak: Int) : ReadingChallengeState
    object ChallengeCompleted : ReadingChallengeState
    data class ChallengeConcludedIncomplete(val streak: Int) : ReadingChallengeState
    object ChallengeConcludedNoStreak : ReadingChallengeState
    object ChallengeRemoved : ReadingChallengeState
}

data class ReadingChallengeUserData(
    val currentDate: LocalDate,
    val enabled: Boolean,
    val currentStreak: Int,
    val hasReadToday: Boolean,
    val hasActiveStreak: Boolean
)

class ReadingChallengeWidgetRepository(context: Context) {
    fun observeState(): Flow<ReadingChallengeState>
    fun hasReadToday(currentDate: LocalDate): Boolean
    fun resolveState(userData: ReadingChallengeUserData): ReadingChallengeState
    fun hasActiveStreak(currentDate: LocalDate): Boolean
    fun recalculateStreakIfNeeded(currentDate: LocalDate): Unit
    suspend fun updateWidgetsAndSendAnalytics(): Unit
    suspend fun updateOnArticleRead(currentDate: LocalDate): Unit

    companion object {
        const val READING_STREAK_GOAL: Int
        const val INTENT_EXTRA_READING_CHALLENGE_JOIN: String
        const val INTENT_EXTRA_READING_CHALLENGE_REWARD: String
        const val READING_CHALLENGE_START_DATE: String
        const val READING_CHALLENGE_END_DATE: String
        val START_DATE: LocalDate
        val END_DATE: LocalDate
        fun isWidgetInstalled(): Boolean
        fun shouldShowOnboardingDialog(): Boolean
        fun shouldShowWidgetInstallDialog(): Boolean
        fun shouldShowReward(intent: Intent): Boolean
    }
}

class ReadingChallengeEnrollmentAction(context: Context) {
    suspend fun enroll(currentDate: LocalDate): Unit
}

class ReadingChallengePageActionPrefix(context: Context) {
    fun refreshChallengeSurface(currentDate: LocalDate): Unit
    suspend fun enroll(currentDate: LocalDate): Unit
    suspend fun openArticle(currentDate: LocalDate): Unit
    fun snapshot(currentDate: LocalDate): ReadingChallengePageSnapshot
}

class PageLoadCompleteActionPrefix(context: Context) {
    suspend fun onPageLoadComplete(currentDate: LocalDate): Unit
}
```

Package: `org.wikipedia.settings`

```kotlin
object Prefs {
    var readingChallengeStreak: Int
    var readingChallengeEnrolled: Boolean
    var readingChallengeLastReadDate: String
    var readingChallengeEnrollmentDate: String
    var readingChallengeStartDate: String
    var readingChallengeEndDate: String
    var readingChallengeOnboardingShown: Boolean
    var readingChallengeInstallPromptShown: Boolean
}
```

The native episode strongly links the application-owned action prefix and observes its snapshot, reopened preference storage, and external effect log. Missing owner APIs are compile/runtime binding failures, never base-like verdicts. Direct preference writes may establish the initial fixture only; a scored enrollment event must pass through `ReadingChallengeEnrollmentAction`, and a scored read must pass through `PageLoadCompleteActionPrefix`.

## Android external leaf boundaries

- Clock input: tests supply a `java.time.LocalDate` only to public methods that accept it. Production preference dates remain ISO local-date strings.
- Persistence transport: Android preferences and `SharedPreferences` notification plumbing are controllable storage leaves. The repository must still read and write the production `Prefs` properties.
- Widget delivery: `suspend fun ReadingChallengeWidget.updateAll(context: Context): Unit` is an external delivery leaf. The production repository must decide when to call it.
- Analytics delivery: `ReadingChallengeAnalyticsHelper.sendHeartbeatEvent(state: ReadingChallengeState): Unit` is an external transport leaf. The production repository must create and dispatch the state.
- Android framework and account/widget-host queries are leaves for focused runtime execution. They must not replace enrollment, eligibility, streak, persistence, or state-resolution logic.

## ArkTS production sources

- `entry/src/main/ets/pages/Index.ets`
- `entry/src/main/ets/model/ReadingChallengeStore.ets`
- `entry/src/main/ets/model/ReadingChallengePreferences.ets`

### Model API

```ts
export interface ChallengeClock {
  today(): string;
}

export class SystemChallengeClock implements ChallengeClock {
  today(): string;
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
  static readonly GOAL: number;
  static readonly START_DATE: string;
  static readonly END_DATE: string;
  static readonly REMOVE_DATE: string;

  state: ChallengeViewState;

  constructor(
    clock: ChallengeClock,
    persistence: ChallengePersistence,
    effects: ChallengeEffects
  );

  refresh(): Promise<ChallengeViewState>;
  enroll(): Promise<ChallengeViewState>;
  openArticle(): Promise<ChallengeViewState>;
}

export class ReadingChallengePreferences implements ChallengePersistence {
  static create(context: common.UIAbilityContext): Promise<ReadingChallengePreferences>;
  load(): Promise<ChallengePreferences>;
  save(value: ChallengePreferences): Promise<void>;
}
```

`Index.aboutToAppear()` is the ArkUI production composition entry. It creates `ReadingChallengePreferences`, `SystemChallengeClock`, page-owned `ChallengeEffects`, and `ReadingChallengeStore`, then calls `refresh()`. The rendered Join, Open article, and Refresh controls call the corresponding store methods. Deterministic tests may provide controlled implementations of `ChallengeClock`, `ChallengePersistence`, and `ChallengeEffects`, but must execute the production store methods and observe their returned state, persistence calls, and leaf effects.
