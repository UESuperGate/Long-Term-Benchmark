import { common } from '@kit.AbilityKit';
import { preferences } from '@kit.ArkData';
import { DomainBackend, DomainEffect, DomainInput, DomainLeaf } from '../integration/DomainIntegration';
import { DomainPageRuntime, MountedDomainPageOwner } from '../pages/DomainPageOwner';

export interface SemanticPayload { key: string; episodeJson: string; }
interface RuntimeFixture {
  given: Record<string, Object>;
  event: Record<string, Object>;
  setup: Record<string, Object>[];
}
interface RuntimeSnapshot {
  pageOwnerId: string;
  controllerOwnerId: string;
  storeSource: string;
  featureAvailable: boolean;
  state: Record<string, Object>;
  reopenedState: Record<string, Object>;
}

function parsed(value: string): Record<string, Object> { return JSON.parse(value) as Record<string, Object>; }
function parsedFixture(value: string): RuntimeFixture { return JSON.parse(value) as RuntimeFixture; }
function clone(value: Record<string, Object>): Record<string, Object> { return parsed(JSON.stringify(value)); }
function records(value: Object | undefined): Record<string, Object>[] {
  return value === undefined ? [] : JSON.parse(JSON.stringify(value)) as Record<string, Object>[];
}

class FixtureBackend implements DomainBackend {
  private given: Record<string, Object>;
  private domainResponses: Record<string, Object>[] = [];
  private cartResponses: Record<string, Object>[] = [];
  fetchCalls: number = 0;
  searchCalls: number = 0;
  cartCalls: number = 0;

  constructor(given: Record<string, Object>) {
    this.given = clone(given);
    if (given['accountDomainResponses'] !== undefined) this.domainResponses = records(given['accountDomainResponses']);
    else if (given['accountDomainsResponse'] !== undefined) this.domainResponses = [given['accountDomainsResponse'] as Record<string, Object>];
    else if (given['loadedDomains'] !== undefined) this.domainResponses = [
      { 'type': 'success', 'domains': given['loadedDomains'] }
    ];
    if (given['cartResponses'] !== undefined) this.cartResponses = records(given['cartResponses']);
  }

  async fetchAllDomains(): Promise<Record<string, Object>> {
    this.fetchCalls += 1;
    const response = this.domainResponses.shift();
    return response === undefined ? parsed('{"type":"empty"}') : clone(response);
  }
  async searchForDomains(query: string): Promise<string[]> {
    this.searchCalls += 1;
    const sequence = records(this.given['querySequence']);
    for (const row of sequence) {
      if (row['query'] === query) {
        const completion = row['completion'] as Record<string, Object>;
        return completion['domains'] as string[];
      }
    }
    return [];
  }
  async createCart(mode: string, domain: string): Promise<Record<string, Object>> {
    this.cartCalls += 1;
    const response = this.cartResponses.shift();
    return response === undefined ? parsed('{"type":"error"}') : clone(response);
  }
  calls(): Record<string, Object> {
    return { 'fetchAllDomains': this.fetchCalls, 'searchForDomains': this.searchCalls, 'createCart': this.cartCalls };
  }
}

class RecordingLeaf implements DomainLeaf {
  effects: DomainEffect[] = [];
  async emit(effect: DomainEffect): Promise<void> {
    const copied = JSON.parse(JSON.stringify(effect)) as DomainEffect;
    if (copied.count !== undefined) {
      const index = this.effects.findIndex((value: DomainEffect) => value.name === copied.name);
      if (index >= 0) { this.effects[index] = copied; return; }
    }
    this.effects.push(copied);
  }
  snapshot(): DomainEffect[] { return JSON.parse(JSON.stringify(this.effects)) as DomainEffect[]; }
  clear(): void { this.effects = []; }
}

function fixtureFor(key: string): RuntimeFixture {
  if (key === 'loaded_add_domain_entry') return parsedFixture('{"given":{"accountDomainsResponse":{"type":"success","domains":[{"domain":"alpha.example","siteSlug":"alpha-site","blogName":"Alpha Studio","status":"active"},{"domain":"beta.example","siteSlug":"beta-site","blogName":"Beta Journal","status":"expiring"}]},"domainManagementOpen":false},"event":{"name":"openDomainManagementThenTapAddDomain"},"setup":[]}');
  if (key === 'empty_find_domain_entry') return parsedFixture('{"given":{"accountDomainsResponse":{"type":"empty"},"domainManagementOpen":false},"event":{"name":"openDomainManagementThenTapFindDomain"},"setup":[]}');
  if (key === 'error_retry_recovery') return parsedFixture('{"given":{"accountDomainResponses":[{"type":"error"},{"type":"success","domains":[{"domain":"recovered.example","siteSlug":"recovered","blogName":"Recovered Site","status":"active"}]}],"domainManagementOpen":false},"event":{"name":"tapRetry"},"setup":[{"name":"openDomainManagement"},{"name":"waitForListError"}]}');
  if (key === 'filter_clear_round_trip') return parsedFixture('{"given":{"loadedDomains":[{"domain":"alpha.example","siteSlug":"alpha","blogName":"Studio North"},{"domain":"beta.example","siteSlug":"beta","blogName":"Daily Notes"}],"filterQuery":"STUDIO","givenEstablishedBy":[{"name":"enterLocalFilter","query":"STUDIO"}]},"event":{"name":"clearLocalFilter"},"setup":[{"name":"openDomainManagementWithLoadedDomains"},{"name":"enterLocalFilter","query":"STUDIO"},{"name":"waitForFilteredState"}]}');
  if (key === 'debounced_latest_search') return parsedFixture('{"given":{"searchOpen":true,"clockMs":0,"querySequence":[{"atMs":0,"query":"old","completion":{"atMs":700,"domains":["old.example"]}},{"atMs":100,"query":"latest","completion":{"atMs":500,"domains":["latest.example"]}}]},"event":{"name":"advanceControlledClockAndCompleteRequests","toMs":700},"setup":[]}');
  if (key === 'purchase_mode_entry') return parsedFixture('{"given":{"searchState":"populated","proposal":{"productId":42,"domain":"chosen.example","price":"$12","supportsPrivacy":true}},"event":{"name":"tapProposedDomain","domain":"chosen.example"},"setup":[]}');
  if (key === 'cart_failure_retry') return parsedFixture('{"given":{"purchaseMode":"new_domain_only","selectedProposal":{"productId":42,"domain":"retry.example","supportsPrivacy":true},"cartResponses":[{"type":"error"},{"type":"success","checkoutToken":"cart-2"}],"givenEstablishedBy":[{"name":"selectNewDomainMode"},{"name":"waitForCartError"}]},"event":{"name":"acknowledgeCartErrorThenRetryNewDomain"},"setup":[{"name":"openPurchaseModeFromProposal"},{"name":"selectNewDomainMode"},{"name":"waitForCartError"}]}');
  if (key === 'checkout_cancel') return parsedFixture('{"given":{"checkout":{"status":"open","domain":"cancel.example","email":"owner@example.test"},"purchaseScreenOpen":true},"event":{"name":"returnCheckoutResult","result":{"domainName":"cancel.example","email":"owner@example.test","canceled":true}},"setup":[]}');
  if (key === 'checkout_success') return parsedFixture('{"given":{"checkout":{"status":"open","domain":"registered.example","email":"owner@example.test"},"purchaseScreenOpen":true},"event":{"name":"returnCheckoutResult","result":{"domainName":"registered.example","email":"owner@example.test","canceled":false}},"setup":[]}');
  if (key === 'details_url_allowlist_rejection') return parsedFixture('{"given":{"managedDomain":"some.domain","detailsWebView":{"currentUrl":"https://wordpress.com/domains/manage/all/some.domain/edit/contact","contained":true},"requestedUrl":"https://google.com/domains/manage/all/some.domain/edit/contact"},"event":{"name":"requestDetailsNavigation"},"setup":[]}');
  throw new Error('Unknown runtime case: ' + key);
}

let activeContext: common.UIAbilityContext | undefined = undefined;
let activeFixture: RuntimeFixture | undefined = undefined;
let activeLeaf: RecordingLeaf | undefined = undefined;
let activeBackend: FixtureBackend | undefined = undefined;

export function prepareSemanticCase(context: common.UIAbilityContext, key: string): void {
  const fixture = fixtureFor(key);
  const backend = new FixtureBackend(fixture.given);
  const leaf = new RecordingLeaf();
  activeContext = context; activeFixture = fixture; activeLeaf = leaf; activeBackend = backend;
  const input: DomainInput = { backend: backend, leaf: leaf };
  DomainPageRuntime.configure(context, input);
}

async function snapshot(context: common.UIAbilityContext, owner: MountedDomainPageOwner): Promise<RuntimeSnapshot> {
  const prefs = await preferences.getPreferences(context, 'wordpress_domain_management');
  const reopened = parsed(await prefs.get('state', '{}') as string);
  return {
    pageOwnerId: owner.ownerId(), controllerOwnerId: owner.controllerId(),
    storeSource: owner.storeSource(), featureAvailable: owner.featureAvailable(),
    state: owner.currentState(), reopenedState: reopened
  };
}

async function establishGiven(owner: MountedDomainPageOwner, fixture: RuntimeFixture, methods: string[],
                              leaf: RecordingLeaf): Promise<boolean> {
  const givenActions = records(fixture.given['givenEstablishedBy']);
  let observationStarted = false;
  const sequence = records(fixture.given['querySequence']);
  for (const row of sequence) {
    await owner.invoke('enterRemoteQuery', {
      'name': 'enterRemoteQuery', 'query': row['query'], 'atMs': row['atMs']
    });
    methods.push('enterRemoteQuery');
  }
  if (fixture.given['proposal'] !== undefined) {
    await owner.invoke('showProposals', { 'name': 'showProposals', 'proposals': [fixture.given['proposal']] });
    methods.push('showProposals');
  }
  if (fixture.given['checkout'] !== undefined) {
    await owner.invoke('openCheckout', { 'name': 'openCheckout', 'checkout': fixture.given['checkout'] });
    methods.push('openCheckout');
  }
  if (fixture.given['detailsWebView'] !== undefined) {
    const details = fixture.given['detailsWebView'] as Record<string, Object>;
    await owner.invoke('openDetails', {
      'name': 'openDetails', 'managedDomain': fixture.given['managedDomain'], 'currentUrl': details['currentUrl']
    });
    methods.push('openDetails');
  }
  for (const source of fixture.setup) {
    const action = clone(source);
    const name = action['name'] as string;
    if (!observationStarted && givenActions.some((value: Record<string, Object>) => value['name'] === name)) {
      leaf.clear();
      observationStarted = true;
    }
    if (name === 'openPurchaseModeFromProposal') action['proposal'] = fixture.given['selectedProposal'];
    await owner.invoke(name, action);
    methods.push(name);
  }
  return observationStarted;
}

function eventFor(fixture: RuntimeFixture): Record<string, Object> {
  const event = clone(fixture.event);
  if (event['name'] === 'requestDetailsNavigation') event['requestedUrl'] = fixture.given['requestedUrl'];
  return event;
}

export async function runSemanticCase(key: string): Promise<SemanticPayload> {
  const context = activeContext; const fixture = activeFixture; const leaf = activeLeaf; const backend = activeBackend;
  if (context === undefined || fixture === undefined || leaf === undefined || backend === undefined) throw new Error('probe not prepared');
  const owner = await DomainPageRuntime.waitForOwner();
  const methods: string[] = ['mount'];
  const observationStarted = await establishGiven(owner, fixture, methods, leaf);
  const before = await snapshot(context, owner);
  if (!observationStarted) leaf.clear();
  const event = eventFor(fixture);
  const eventName = event['name'] as string;
  await owner.invoke(eventName, event);
  methods.push(eventName);
  const after = await snapshot(context, owner);
  const observed: Record<string, Object> = { 'state': after.state, 'effects': leaf.snapshot() };
  const evidence: Record<string, Object> = {
    'pageOwnerId': after.pageOwnerId, 'controllerOwnerId': after.controllerOwnerId,
    'storeSource': after.storeSource, 'evaluatorStoreWrites': 0, 'detachedControllers': 0,
    'storageReopened': JSON.stringify(after.state) === JSON.stringify(after.reopenedState),
    'backendCalls': backend.calls(), 'leafCalls': leaf.snapshot()
  };
  const episode: Record<string, Object> = {
    'schemaVersion': 2, 'taskId': '05_domain_management', 'caseKey': key,
    'given': fixture.given, 'event': fixture.event, 'givenEstablished': true,
    'commonEntryObserved': true, 'entryOwner': 'pages/Index',
    'before': before, 'after': after, 'observed': observed,
    'invokedProductionMethods': methods, 'transitionExecuted': true, 'earlyExit': false,
    'runtimeEvidence': evidence
  };
  return { key: key, episodeJson: JSON.stringify(episode) };
}
