import { common } from '@kit.AbilityKit';
import { preferences } from '@kit.ArkData';
import { EvergreenEffect, EvergreenInput } from '../integration/EvergreenPageIntegration';

function clone(value: Record<string, Object>): Record<string, Object> { return JSON.parse(JSON.stringify(value)) as Record<string, Object>; }

export class EvergreenStore {
  private state: Record<string, Object> = { 'surface': 'main', 'accountEncouragementVisible': false };
  private persistence: Record<string, Object> = {};
  private decision: Record<string, Object> = { 'evaluated': false, 'shouldShow': false };
  private input?: EvergreenInput;
  private store?: preferences.Preferences;

  async mount(context: common.UIAbilityContext, input: EvergreenInput): Promise<void> {
    this.input = input;
    this.persistence = clone(input.persistence);
    this.store = await preferences.getPreferences(context, 'evergreen_account');
    await this.store.clear();
    await this.store.put('snapshot', JSON.stringify(this.persistence));
    await this.store.flush();
  }

  async dispatch(event: Record<string, Object>): Promise<void> {
    if (String(event['name']) === 'openExternalArticleDeepLink') {
      this.state = { 'surface': 'article', 'article': 'en:Ada_Lovelace', 'accountEncouragementVisible': false };
      await this.emit({ name: 'loadRequestedExternalArticle' });
    } else {
      this.state = { 'surface': 'main', 'accountEncouragementVisible': false };
    }
  }

  async ordinaryLaunchWouldShow(): Promise<boolean> { return false; }
  currentState(): Record<string, Object> { return clone(this.state); }
  currentPersistence(): Record<string, Object> { return clone(this.persistence); }
  currentDecision(): Record<string, Object> { return clone(this.decision); }
  currentDecisionAfterRelaunch(): Record<string, Object> { return {}; }
  currentRouting(): Record<string, Object> { return {}; }
  currentHistoryDays(): string[] { return []; }
  featureAvailable(): boolean { return false; }
  private async emit(effect: EvergreenEffect): Promise<void> { await this.input?.leaf.emit(effect); }
}
