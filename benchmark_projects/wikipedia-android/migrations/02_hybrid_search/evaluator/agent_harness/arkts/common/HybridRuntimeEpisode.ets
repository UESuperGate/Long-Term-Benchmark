import { common } from '@kit.AbilityKit';
import { preferences } from '@kit.ArkData';
import {
  HybridIntegrationFeedbackLeaf as FeedbackLeaf,
  HybridIntegrationFeedbackPayload as FeedbackPayload,
  HybridIntegrationJsonTransport as SearchJsonTransport,
  HybridIntegrationSettings as HybridSearchSettings,
  HybridIntegrationState as HybridSearchState,
  HybridIntegrationStandardSearchLeaf as StandardSearchLeaf,
  HybridPageOwner
} from '../integration/HybridPageIntegration';

interface HttpCall {
  leaf: string;
  status: string;
  attempt: number;
  url: string;
}

interface RuntimeEffect {
  leaf?: string;
  status?: string;
  attempt?: number;
  name?: string;
  query?: string;
  payload?: FeedbackPayload;
}

interface HybridFixture {
  event: string;
  setupSubmit: boolean;
  settings: HybridSearchSettings;
  prefix: string[];
  fullText: string[];
  semantic: string[];
  prefixFailures: number;
  semanticFailures: number;
  held: boolean;
}

interface HybridRuntimeState {
  mode: string;
  phase: string;
  query: string;
  sections: string[];
  lexicalTitles: string[];
  semanticTitles: string[];
  retryAvailable: boolean;
  notice?: string;
}

interface HybridRuntimeSnapshot {
  featureAvailable: boolean;
  pageOwnerId: string;
  state: HybridRuntimeState;
  persistence: HybridRuntimePersistence;
}

interface HybridRuntimePersistence {
  hybridEnabled: boolean;
}

interface HybridRuntimeObserved extends HybridRuntimeSnapshot {
  effects: RuntimeEffect[];
  leafCalls: HttpCall[];
}

class WikiPagePayload {
  index: number;
  title: string;

  constructor(index: number, title: string) {
    this.index = index;
    this.title = title;
  }
}

class WikiPagesPayload {
  page1?: WikiPagePayload;
  page2?: WikiPagePayload;
  page3?: WikiPagePayload;

  put(index: number, page: WikiPagePayload): void {
    if (index === 0) {
      this.page1 = page;
    } else if (index === 1) {
      this.page2 = page;
    } else {
      this.page3 = page;
    }
  }
}

class WikiQueryPayload {
  pages: WikiPagesPayload;

  constructor(pages: WikiPagesPayload) {
    this.pages = pages;
  }
}

class WikiBodyPayload {
  query: WikiQueryPayload;

  constructor(pages: WikiPagesPayload) {
    this.query = new WikiQueryPayload(pages);
  }
}

class SemanticResultPayload {
  page_title: string;
  section_header: string;

  constructor(title: string, section: string) {
    this.page_title = title;
    this.section_header = section;
  }
}

class SemanticBodyPayload {
  semantic_search_results: SemanticResultPayload[];

  constructor(results: SemanticResultPayload[]) {
    this.semantic_search_results = results;
  }
}

export interface HybridRuntimeEpisode {
  caseKey: string;
  before: HybridRuntimeSnapshot;
  after: HybridRuntimeSnapshot;
  observed: HybridRuntimeObserved;
}

export class ControlledSearchTransport implements SearchJsonTransport {
  calls: HttpCall[] = [];
  private input: HybridFixture;
  private prefixAttempts: number = 0;
  private fullTextAttempts: number = 0;
  private semanticAttempts: number = 0;
  private releases: (() => void)[] = [];
  private heldReleased: boolean = false;

  constructor(input: HybridFixture) {
    this.input = input;
  }

  async getJson(url: string): Promise<Record<string, Object>> {
    if (url.includes('semantic-search.wmcloud.org')) {
      this.semanticAttempts += 1;
      return this.respond('semantic_http', this.semanticAttempts, url,
        this.semanticAttempts <= this.input.semanticFailures, this.semanticBody(this.input.semantic));
    }
    if (url.includes('gsrwhat=prefix')) {
      this.prefixAttempts += 1;
      return this.respond('prefix_http', this.prefixAttempts, url,
        this.prefixAttempts <= this.input.prefixFailures, this.mediaWikiBody(this.input.prefix));
    }
    this.fullTextAttempts += 1;
    return this.respond('fulltext_http', this.fullTextAttempts, url, false,
      this.mediaWikiBody(this.input.fullText));
  }

  releaseHeld(): void {
    this.heldReleased = true;
    const values = this.releases;
    this.releases = [];
    values.forEach((release: () => void) => release());
  }

  snapshotCalls(): HttpCall[] {
    return this.calls.map((call: HttpCall): HttpCall => {
      const copied: HttpCall = {
        leaf: call.leaf, status: call.status, attempt: call.attempt, url: call.url
      };
      return copied;
    });
  }

  private respond(leaf: string, attempt: number, url: string, failure: boolean,
    body: Record<string, Object>): Promise<Record<string, Object>> {
    const call: HttpCall = { leaf: leaf, status: 'started', attempt: attempt, url: url };
    this.calls.push(call);
    const complete = (): Record<string, Object> => {
      if (failure) {
        call.status = 'failed';
        throw new Error(leaf + ' failed');
      }
      call.status = 'completed';
      return body;
    };
    if (!this.input.held || this.heldReleased) {
      return Promise.resolve().then(complete);
    }
    return new Promise<Record<string, Object>>((resolve: (value: Record<string, Object>) => void,
      reject: (reason?: Error) => void) => {
      this.releases.push(() => {
        try {
          resolve(complete());
        } catch (error) {
          reject(error as Error);
        }
      });
    });
  }

  private mediaWikiBody(values: string[]): Record<string, Object> {
    const pages = new WikiPagesPayload();
    values.forEach((title: string, index: number) => {
      pages.put(index, new WikiPagePayload(index, title.replaceAll('_', ' ')));
    });
    return new WikiBodyPayload(pages) as Object as Record<string, Object>;
  }

  private semanticBody(values: string[]): Record<string, Object> {
    const results: SemanticResultPayload[] = values.map((value: string): SemanticResultPayload => {
      const separator = value.indexOf('#');
      const title = separator < 0 ? value : value.substring(0, separator);
      const section = separator < 0 ? '' : value.substring(separator + 1).replaceAll('_', ' ');
      return new SemanticResultPayload(title, section);
    });
    return new SemanticBodyPayload(results) as Object as Record<string, Object>;
  }
}

class RecordingFeedback implements FeedbackLeaf {
  effects: RuntimeEffect[] = [];

  async submit(payload: FeedbackPayload): Promise<void> {
    this.effects.push({ leaf: 'feedback_transport', payload: payload });
  }

  clear(): void {
    this.effects = [];
  }
}

class RecordingStandardSearch implements StandardSearchLeaf {
  effects: RuntimeEffect[] = [];

  request(query: string): void {
    this.effects.push({ name: 'standard_search_requested', query: query });
  }

  clear(): void {
    this.effects = [];
  }
}

function settings(group: string): HybridSearchSettings {
  return {
    language: 'fr', experimentGroup: group, remoteEnabled: true, hybridEnabled: true, query: 'Paris'
  };
}

function fixture(key: string): HybridFixture {
  if (key === 'enable_supported') {
    return { event: 'openHybrid', setupSubmit: false, settings: settings('lexicalsemantic'), prefix: [],
      fullText: [], semantic: [], prefixFailures: 0, semanticFailures: 0, held: false };
  }
  if (key === 'concurrent_dispatch') {
    return { event: 'submit', setupSubmit: false, settings: settings('lexicalsemantic'), prefix: [],
      fullText: [], semantic: [], prefixFailures: 0, semanticFailures: 0, held: true };
  }
  if (key === 'both_sources_lexical_first') {
    return { event: 'submit', setupSubmit: false, settings: settings('lexicalsemantic'),
      prefix: ['Paris', 'Paris'], fullText: ['Paris', 'Paris,_Texas'],
      semantic: ['History_of_Paris#Origins', 'Paris_agreement#Background'],
      prefixFailures: 0, semanticFailures: 0, held: false };
  }
  if (key === 'both_sources_semantic_first') {
    return { event: 'submit', setupSubmit: false, settings: settings('semanticlexical'), prefix: ['Paris'],
      fullText: [], semantic: ['History_of_Paris#Origins'], prefixFailures: 0, semanticFailures: 0, held: false };
  }
  if (key === 'lexical_failure_fallback') {
    return { event: 'submit', setupSubmit: false, settings: settings('lexicalsemantic'), prefix: [],
      fullText: [], semantic: ['History_of_Paris#Origins'], prefixFailures: 1, semanticFailures: 0, held: false };
  }
  if (key === 'semantic_failure_fallback') {
    return { event: 'submit', setupSubmit: false, settings: settings('lexicalsemantic'), prefix: ['Paris'],
      fullText: [], semantic: [], prefixFailures: 0, semanticFailures: 1, held: false };
  }
  if (key === 'both_fail') {
    return { event: 'submit', setupSubmit: false, settings: settings('lexicalsemantic'), prefix: [],
      fullText: [], semantic: [], prefixFailures: 1, semanticFailures: 1, held: false };
  }
  if (key === 'retry_recovers') {
    return { event: 'retry', setupSubmit: true, settings: settings('lexicalsemantic'), prefix: ['Paris'],
      fullText: [], semantic: ['History_of_Paris#Origins'], prefixFailures: 1, semanticFailures: 1, held: false };
  }
  if (key === 'feedback_mapping') {
    return { event: 'rate', setupSubmit: true, settings: settings('lexicalsemantic'), prefix: [],
      fullText: [], semantic: ['History_of_Paris#Origins'], prefixFailures: 0, semanticFailures: 0, held: false };
  }
  if (key === 'opt_out') {
    return { event: 'optOut', setupSubmit: true, settings: settings('lexicalsemantic'), prefix: ['Paris'],
      fullText: [], semantic: ['History_of_Paris#Origins'], prefixFailures: 0, semanticFailures: 0, held: false };
  }
  throw new Error('Unknown runtime case: ' + key);
}

async function seedPreference(context: common.UIAbilityContext): Promise<void> {
  const store = await preferences.getPreferences(context, 'hybrid_search');
  await store.clear();
  await store.put('hybridEnabled', true);
  await store.flush();
}

async function snapshot(context: common.UIAbilityContext, driver: HybridPageOwner): Promise<HybridRuntimeSnapshot> {
  const state = driver.currentState();
  const reopened = await preferences.getPreferences(context, 'hybrid_search');
  const runtimeState: HybridRuntimeState = {
    mode: driver.currentMode(),
    phase: state.phase,
    query: driver.currentQuery(),
    sections: driver.sections(),
    lexicalTitles: state.lexicalTitles.slice(),
    semanticTitles: state.semanticTitles.slice(),
    retryAvailable: state.retryAvailable,
    notice: state.notice
  };
  const persistence: HybridRuntimePersistence = {
    hybridEnabled: await reopened.get('hybridEnabled', true) as boolean
  };
  const result: HybridRuntimeSnapshot = {
    featureAvailable: driver.featureAvailable(),
    pageOwnerId: driver.ownerId(),
    state: runtimeState,
    persistence: persistence
  };
  return result;
}

function aggregateStatus(calls: HttpCall[], leaves: string[]): string {
  const selected = calls.filter((call: HttpCall) => leaves.includes(call.leaf));
  if (selected.some((call: HttpCall) => call.status === 'failed')) {
    return 'failed';
  }
  if (selected.some((call: HttpCall) => call.status === 'completed')) {
    return 'completed';
  }
  return 'started';
}

function aggregateAttempt(calls: HttpCall[], leaves: string[]): number {
  const attempts = calls.filter((call: HttpCall) => leaves.includes(call.leaf))
    .map((call: HttpCall) => call.attempt);
  return attempts.length === 0 ? 0 : Math.max(...attempts);
}

function searchEffects(calls: HttpCall[]): RuntimeEffect[] {
  const lexical = ['prefix_http', 'fulltext_http'];
  if (calls.some((call: HttpCall) => call.status === 'started')) {
    return [
      { leaf: 'lexical_http', status: aggregateStatus(calls, lexical) },
      { leaf: 'semantic_http', status: aggregateStatus(calls, ['semantic_http']) }
    ];
  }
  if (aggregateAttempt(calls, lexical) > 1 || aggregateAttempt(calls, ['semantic_http']) > 1) {
    return [
      { leaf: 'lexical_http', attempt: aggregateAttempt(calls, lexical) },
      { leaf: 'semantic_http', attempt: aggregateAttempt(calls, ['semantic_http']) }
    ];
  }
  if (calls.some((call: HttpCall) => call.status === 'failed')) {
    return [
      { leaf: 'lexical_http', status: aggregateStatus(calls, lexical) },
      { leaf: 'semantic_http', status: aggregateStatus(calls, ['semantic_http']) }
    ];
  }
  const order = ['prefix_http', 'fulltext_http', 'semantic_http'];
  return order.filter((leaf: string) => calls.some((call: HttpCall) => call.leaf === leaf))
    .map((leaf: string): RuntimeEffect => {
      const effect: RuntimeEffect = { leaf: leaf };
      return effect;
    });
}

export class PreparedHybridEpisode {
  readonly settings: HybridSearchSettings;
  readonly transport: ControlledSearchTransport;
  readonly feedback: FeedbackLeaf;
  readonly standardSearch: StandardSearchLeaf;
  private context: common.UIAbilityContext;
  private key: string;
  private input: HybridFixture;
  private feedbackRecorder: RecordingFeedback;
  private standardRecorder: RecordingStandardSearch;

  constructor(context: common.UIAbilityContext, key: string, input: HybridFixture) {
    this.context = context;
    this.key = key;
    this.input = input;
    this.settings = input.settings;
    this.transport = new ControlledSearchTransport(input);
    this.feedbackRecorder = new RecordingFeedback();
    this.standardRecorder = new RecordingStandardSearch();
    this.feedback = this.feedbackRecorder;
    this.standardSearch = this.standardRecorder;
  }

  async run(driver: HybridPageOwner): Promise<HybridRuntimeEpisode> {
    if (this.input.event !== 'openHybrid') {
      driver.openHybrid();
    }
    if (this.input.setupSubmit) {
      await driver.submit();
    }
    const before = await snapshot(this.context, driver);
    this.feedbackRecorder.clear();
    this.standardRecorder.clear();

    if (this.input.event === 'openHybrid') {
      driver.openHybrid();
    } else if (this.input.event === 'submit' && this.input.held) {
      const pending = driver.submit();
      await Promise.resolve();
      await Promise.resolve();
      const loading = await snapshot(this.context, driver);
      const calls = this.transport.snapshotCalls();
      this.transport.releaseHeld();
      await pending;
      const observed: HybridRuntimeObserved = {
        featureAvailable: loading.featureAvailable,
        pageOwnerId: loading.pageOwnerId,
        state: loading.state,
        persistence: loading.persistence,
        effects: searchEffects(calls),
        leafCalls: calls
      };
      return { caseKey: this.key, before: before, after: loading, observed: observed };
    } else if (this.input.event === 'submit') {
      await driver.submit();
    } else if (this.input.event === 'retry') {
      await driver.retry();
    } else if (this.input.event === 'rate') {
      await driver.rate('History_of_Paris#Origins', 0, false);
    } else {
      await driver.optOut();
    }

    const after = await snapshot(this.context, driver);
    const calls = this.transport.snapshotCalls();
    let effects: RuntimeEffect[] = [];
    if (this.input.event === 'submit' || this.input.event === 'retry') {
      effects = searchEffects(calls);
    } else if (this.input.event === 'rate') {
      effects = this.feedbackRecorder.effects.slice();
    } else if (this.input.event === 'optOut') {
      effects = this.standardRecorder.effects.slice();
    }
    const observed: HybridRuntimeObserved = {
      featureAvailable: after.featureAvailable,
      pageOwnerId: after.pageOwnerId,
      state: after.state,
      persistence: after.persistence,
      effects: effects,
      leafCalls: calls
    };
    return { caseKey: this.key, before: before, after: after, observed: observed };
  }
}

export async function prepareHybridEpisode(context: common.UIAbilityContext,
  key: string): Promise<PreparedHybridEpisode> {
  const input = fixture(key);
  await seedPreference(context);
  return new PreparedHybridEpisode(context, key, input);
}
