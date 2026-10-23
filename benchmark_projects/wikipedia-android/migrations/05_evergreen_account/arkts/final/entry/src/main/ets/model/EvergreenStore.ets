import { common } from '@kit.AbilityKit';
import { preferences } from '@kit.ArkData';
import { EvergreenEffect, EvergreenInput } from '../integration/EvergreenPageIntegration';

function clone(value: Record<string, Object>): Record<string, Object> { return JSON.parse(JSON.stringify(value)) as Record<string, Object>; }
function epochDay(value: string): number { return Math.floor(new Date(value + 'T00:00:00Z').getTime() / 86400000); }

export class EvergreenStore {
  private state: Record<string, Object> = {};
  private persistence: Record<string, Object> = {};
  private decision: Record<string, Object> = { 'evaluated': false, 'shouldShow': false };
  private decisionAfterRelaunch: Record<string, Object> = {};
  private routing: Record<string, Object> = {};
  private readingHistoryDays: string[] = [];
  private input?: EvergreenInput;
  private store?: preferences.Preferences;

  async mount(context: common.UIAbilityContext, input: EvergreenInput): Promise<void> {
    this.input = input;
    this.state = clone(input.state);
    this.persistence = clone(input.persistence);
    this.readingHistoryDays = this.collectHistoryDays(this.state);
    if (this.state['surface'] !== 'account_encouragement') {
      this.state['surface'] = 'main';
      this.state['accountEncouragementVisible'] = false;
    } else {
      this.state['visible'] = true;
      this.state['pageIndex'] = 0;
    }
    this.store = await preferences.getPreferences(context, 'evergreen_account');
    await this.store.clear();
    await this.persist();
  }

  async dispatch(event: Record<string, Object>): Promise<void> {
    const name = String(event['name']);
    if (name === 'resumeApplication') {
      await this.resumeApplication(false);
    } else if (name === 'openExternalArticleDeepLink') {
      await this.openExternalArticleDeepLink();
    } else if (name === 'pressPermanentCloseAndRelaunch') {
      await this.permanentCloseAndRelaunch();
    } else if (name === 'createAccountAndCompleteSuccessfully') {
      await this.createAccountAndComplete(String(event['authenticationLeafResult']));
    } else if (name === 'maybeLater') {
      this.state = { 'surface': 'main', 'accountEncouragementVisible': false };
      await this.emit({ name: 'finishAccountEncouragement' });
    }
  }

  async ordinaryLaunchWouldShow(): Promise<boolean> {
    const probe = await this.evaluateEligibility();
    return probe['shouldShow'] === true;
  }

  private async resumeApplication(afterAction: boolean): Promise<void> {
    const result = await this.evaluateEligibility();
    if (afterAction) this.decisionAfterRelaunch = result; else this.decision = result;
    if (result['shouldShow'] === true) await this.showEncouragement(); else this.showMain();
  }

  private async evaluateEligibility(): Promise<Record<string, Object>> {
    if (String(this.state['account'] ?? 'logged_out') === 'registered') {
      await this.emit({ name: 'readPermanentAccountState' });
      return { 'evaluated': true, 'shouldShow': false };
    }
    const impressions = Number(this.persistence['impressions'] ?? 0);
    if (impressions >= 2) {
      await this.emit({ name: 'applyMaximumOrdinaryImpressions', maximum: 2 });
      return { 'evaluated': true, 'shouldShow': false };
    }
    if (impressions === 1) {
      const raw = String(this.persistence['lastImpressionDate'] ?? '');
      const last = epochDay(raw);
      if (Number.isNaN(last)) {
        await this.emit({ name: 'parsePersistedLastImpressionDate', result: 'invalid' });
        return { 'evaluated': true, 'shouldShow': false, 'completedWithoutException': true };
      }
      const count = this.historyDays().filter((day: string) => epochDay(day) > last).length;
      await this.emit({ name: 'countDistinctReturnReadingDays', count: count });
      return { 'evaluated': true, 'shouldShow': count >= 2 };
    }
    const clock = epochDay(String(this.state['clockDate'] ?? '2026-09-02'));
    const recent = this.historyDays().filter((day: string) => {
      const value = epochDay(day);
      return value >= clock - 365 && value <= clock;
    });
    await this.emit({ name: 'queryDistinctReadingDaysWithinHistoryCutoff', historyCutoffDays: 365, qualifyingDays: recent.length });
    let eligible = false;
    recent.forEach((earlier: string) => {
      const first = epochDay(earlier);
      if (clock - first >= 7 && recent.some((later: string) => epochDay(later) > first && epochDay(later) - first < 14)) eligible = true;
    });
    return { 'evaluated': true, 'shouldShow': eligible };
  }

  private async showEncouragement(): Promise<void> {
    const next = Number(this.persistence['impressions'] ?? 0) + 1;
    this.persistence['impressions'] = next;
    this.persistence['lastImpressionDate'] = String(this.state['clockDate'] ?? '2026-09-02');
    this.state['surface'] = 'account_encouragement';
    this.state['visible'] = true;
    this.state['pageIndex'] = 0;
    this.state['accountEncouragementVisible'] = true;
    await this.emit({ name: 'loadPersonalizedCountsFromApplicationData' });
    await this.emit({ name: 'startAuthenticationEncouragementFunnel', interaction: 'impression' });
    await this.persist();
  }

  private showMain(): void {
    const account = this.state['account'];
    this.state = { 'surface': 'main', 'accountEncouragementVisible': false };
    if (account === 'registered') this.state['account'] = 'registered';
  }

  private async permanentCloseAndRelaunch(): Promise<void> {
    this.persistence['impressions'] = 100;
    await this.persist();
    await this.emit({ name: 'finishAccountEncouragement' });
    this.decisionAfterRelaunch = { 'evaluated': true, 'shouldShow': false };
    this.showMain();
  }

  private async createAccountAndComplete(result: string): Promise<void> {
    await this.emit({ name: 'launchRegistrationFirstAuthentication', source: 'encourage', createAccountFirst: true });
    if (result === 'success_permanent_account') {
      this.state['account'] = 'registered';
      await this.emit({ name: 'finishAccountEncouragementAfterLoginResult', result: 'success' });
    }
    this.decisionAfterRelaunch = await this.evaluateEligibility();
    this.showMain();
  }

  private async openExternalArticleDeepLink(): Promise<void> {
    this.routing = { 'externalArticleLinkDetected': true, 'encouragementConsidered': false };
    this.state = { 'surface': 'article', 'article': 'en:Ada_Lovelace', 'accountEncouragementVisible': false };
    await this.emit({ name: 'loadRequestedExternalArticle' });
  }

  private collectHistoryDays(source: Record<string, Object>): string[] {
    const result: string[] = [];
    ['distinctReadingDays', 'distinctReadingDaysAfterLastImpression', 'distinctRecentReadingDays'].forEach((key: string) => {
      const values = source[key] as string[] | undefined;
      values?.forEach((day: string) => { if (!result.includes(day)) result.push(day); });
    });
    return result.sort();
  }

  private historyDays(): string[] { return [...this.readingHistoryDays]; }

  currentState(): Record<string, Object> { return clone(this.state); }
  currentPersistence(): Record<string, Object> { return clone(this.persistence); }
  currentDecision(): Record<string, Object> { return clone(this.decision); }
  currentDecisionAfterRelaunch(): Record<string, Object> { return clone(this.decisionAfterRelaunch); }
  currentRouting(): Record<string, Object> { return clone(this.routing); }
  currentHistoryDays(): string[] { return this.historyDays(); }
  featureAvailable(): boolean { return true; }
  private async emit(effect: EvergreenEffect): Promise<void> { await this.input?.leaf.emit(effect); }
  private async persist(): Promise<void> { await this.store?.put('snapshot', JSON.stringify(this.persistence)); await this.store?.flush(); }
}
