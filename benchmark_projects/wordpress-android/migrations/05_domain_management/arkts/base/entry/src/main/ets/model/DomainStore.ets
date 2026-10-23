import { common } from '@kit.AbilityKit';
import { preferences } from '@kit.ArkData';
import { DomainInput } from '../integration/DomainIntegration';

function parsed(value: string): Record<string, Object> { return JSON.parse(value) as Record<string, Object>; }
function clone(value: Record<string, Object>): Record<string, Object> { return parsed(JSON.stringify(value)); }
function records(value: Object | undefined): Record<string, Object>[] {
  return value === undefined ? [] : value as Record<string, Object>[];
}
function names(domains: Record<string, Object>[]): string[] { return domains.map((item) => item['domain'] as string); }

export class DomainStore {
  private state: Record<string, Object> = {};
  private domains: Record<string, Object>[] = [];
  private input: DomainInput;
  private prefs: preferences.Preferences;
  private constructor(store: preferences.Preferences, input: DomainInput) { this.prefs = store; this.input = input; }
  static async create(context: common.UIAbilityContext, input: DomainInput, initialize: boolean): Promise<DomainStore> {
    const prefs = await preferences.getPreferences(context, 'wordpress_domain_management');
    if (initialize) { await prefs.clear(); await prefs.put('state', '{}'); await prefs.flush(); }
    const store = new DomainStore(prefs, input);
    store.state = parsed(await prefs.get('state', '{}') as string);
    return store;
  }
  currentState(): Record<string, Object> { return clone(this.state); }
  async invoke(name: string, event: Record<string, Object>): Promise<void> {
    if (name === 'openDomainManagementThenTapAddDomain') { await this.load(); this.state['addDomainEnabled'] = true; this.state['destination'] = 'legacy_unwired'; }
    else if (name === 'openDomainManagementThenTapFindDomain') { await this.load(); this.state['findDomainEnabled'] = true; this.state['destination'] = 'legacy_unwired'; }
    else if (name === 'openDomainManagement' || name === 'openDomainManagementWithLoadedDomains') await this.load();
    else if (name === 'enterLocalFilter') await this.filter(event['query'] as string);
    else if (name === 'clearLocalFilter') await this.clearFilter();
    else if (name === 'showProposals' || name === 'openPurchaseModeFromProposal') this.state['proposal'] = event['proposal'] ?? event['proposals'];
    else if (name === 'openCheckout') this.state = parsed('{"purchaseScreenOpen":true}');
    else if (name === 'returnCheckoutResult') this.state = parsed('{"purchaseScreenOpen":true,"registrationOutcome":"unsupported"}');
    else if (name === 'openDetails') this.state = { 'containedWebViewUrl': event['currentUrl'] };
    else if (name === 'requestDetailsNavigation') this.state = { 'containedWebViewUrl': event['requestedUrl'], 'requestedUrlLoadedInContainedWebView': true };
    await this.persist();
  }
  private async load(): Promise<void> {
    const response = await this.input.backend.fetchAllDomains();
    await this.input.leaf.emit({ name: 'fetchAllDomains', count: 1 });
    const type = response['type'] as string;
    if (type === 'success') { this.domains = records(response['domains']); this.state = { 'listState': 'complete', 'visibleDomains': names(this.domains) }; }
    else if (type === 'empty') { this.domains = []; this.state = { 'listState': 'empty', 'searchEnabled': false }; }
    else this.state = { 'listState': 'error' };
  }
  private async filter(query: string): Promise<void> {
    const needle = query.toLowerCase();
    const visible = this.domains.filter((domain) => (domain['domain'] as string).toLowerCase().includes(needle) || (domain['siteSlug'] as string).toLowerCase().includes(needle));
    this.state = { 'listState': 'filtered', 'visibleDomains': names(visible), 'query': query };
    await this.input.leaf.emit({ name: 'filterLoadedDomains', normalizedQuery: query });
  }
  private async clearFilter(): Promise<void> {
    const before: Record<string, Object> = { 'listState': this.state['listState'], 'visibleDomains': this.state['visibleDomains'] };
    const after: Record<string, Object> = { 'listState': 'complete', 'visibleDomains': names(this.domains), 'query': '' };
    this.state = { 'beforeClear': before, 'afterClear': after };
    await this.input.leaf.emit({ name: 'restoreCompleteDomainList' });
  }
  private async persist(): Promise<void> { await this.prefs.put('state', JSON.stringify(this.state)); await this.prefs.flush(); }
}
