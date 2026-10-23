import { common } from '@kit.AbilityKit';
import { preferences } from '@kit.ArkData';
import {
  FeedbackLeaf,
  FeedbackPayload,
  HybridSearchSettings,
  HybridSearchState,
  SearchHttpLeaf,
  StandardSearchLeaf
} from './HybridSearchModels';
import { HybridSearchViewModel } from './HybridSearchViewModel';

export class HybridSearchPageStore {
  readonly viewModel: HybridSearchViewModel;
  mode: string = 'standard';
  private store: preferences.Preferences;
  private settings: HybridSearchSettings;
  private feedback: FeedbackLeaf;
  private standardSearch: StandardSearchLeaf;

  private constructor(
    store: preferences.Preferences,
    settings: HybridSearchSettings,
    http: SearchHttpLeaf,
    feedback: FeedbackLeaf,
    standardSearch: StandardSearchLeaf
  ) {
    this.store = store;
    this.settings = settings;
    this.feedback = feedback;
    this.standardSearch = standardSearch;
    this.viewModel = new HybridSearchViewModel(http);
    this.mode = 'standard';
  }

  static async create(
    context: common.UIAbilityContext,
    settings: HybridSearchSettings,
    http: SearchHttpLeaf,
    feedback: FeedbackLeaf,
    standardSearch: StandardSearchLeaf
  ): Promise<HybridSearchPageStore> {
    const store = await preferences.getPreferences(context, 'hybrid_search');
    settings.hybridEnabled = await store.get('hybridEnabled', settings.hybridEnabled) as boolean;
    return new HybridSearchPageStore(store, settings, http, feedback, standardSearch);
  }

  openHybrid(): void {
    this.mode = this.eligible() ? 'hybrid' : 'standard';
  }

  async submit(): Promise<HybridSearchState> {
    if (!this.eligible()) {
      this.mode = 'standard';
      return this.viewModel.state;
    }
    this.mode = 'hybrid';
    return this.viewModel.search(this.settings.query, this.settings.language);
  }

  retry(): Promise<HybridSearchState> {
    return this.viewModel.retry();
  }

  async rate(title: string, position: number, positive: boolean): Promise<void> {
    if (!this.viewModel.state.semanticTitles.includes(title)) {
      return;
    }
    const payload: FeedbackPayload = {
      elementId: positive ? 'thumb_up' : 'thumb_down',
      query: this.settings.query,
      position: position + 1,
      title: title
    };
    await this.feedback.submit(payload);
  }

  async optOut(): Promise<void> {
    this.settings.hybridEnabled = false;
    await this.store.put('hybridEnabled', false);
    await this.store.flush();
    this.mode = 'standard';
    this.standardSearch.request(this.settings.query);
  }

  updateQuery(query: string): void {
    this.settings.query = query;
  }

  sections(): string[] {
    const result: string[] = [];
    const semanticFirst = this.settings.experimentGroup === 'semanticlexical';
    if (semanticFirst && this.viewModel.state.semanticTitles.length > 0) {
      result.push('semantic');
    }
    if (this.viewModel.state.lexicalTitles.length > 0) {
      result.push('lexical');
    }
    if (!semanticFirst && this.viewModel.state.semanticTitles.length > 0) {
      result.push('semantic');
    }
    return result;
  }

  private eligible(): boolean {
    const supported = this.settings.language === 'fr' || this.settings.language === 'el';
    return this.settings.remoteEnabled &&
      this.settings.hybridEnabled &&
      supported &&
      this.settings.experimentGroup !== 'control';
  }
}
