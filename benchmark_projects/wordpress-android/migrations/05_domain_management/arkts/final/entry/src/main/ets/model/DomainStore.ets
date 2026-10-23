import { common } from '@kit.AbilityKit';
import { preferences } from '@kit.ArkData';
import { DomainInput } from '../integration/DomainIntegration';

function parsed(value: string): Record<string, Object> { return JSON.parse(value) as Record<string, Object>; }
function clone(value: Record<string, Object>): Record<string, Object> { return parsed(JSON.stringify(value)); }
function records(value: Object | undefined): Record<string, Object>[] { return value === undefined ? [] : value as Record<string, Object>[]; }
function names(domains: Record<string, Object>[]): string[] { return domains.map((item) => item['domain'] as string); }

export class DomainStore {
  private state: Record<string, Object> = {};
  private domains: Record<string, Object>[] = [];
  private proposals: Record<string, Object>[] = [];
  private selectedProposal: Record<string, Object> = {};
  private latestQuery: string = '';
  private latestQueryAtMs: number = 0;
  private fetchCount: number = 0;
  private cartCount: number = 0;
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
    if (name === 'openDomainManagementThenTapAddDomain') await this.openManagement(false);
    else if (name === 'openDomainManagementThenTapFindDomain') await this.openManagement(true);
    else if (name === 'openDomainManagement' || name === 'openDomainManagementWithLoadedDomains') await this.load();
    else if (name === 'tapRetry') await this.retry();
    else if (name === 'enterLocalFilter') await this.filter(event['query'] as string);
    else if (name === 'clearLocalFilter') await this.clearFilter();
    else if (name === 'enterRemoteQuery') this.enterRemoteQuery(event['query'] as string, event['atMs'] as number);
    else if (name === 'advanceControlledClockAndCompleteRequests') await this.advanceClock(event['toMs'] as number);
    else if (name === 'showProposals') this.proposals = records(event['proposals']);
    else if (name === 'tapProposedDomain') await this.tapProposal(event['domain'] as string);
    else if (name === 'openPurchaseModeFromProposal') await this.openPurchase(event['proposal'] as Record<string, Object>);
    else if (name === 'selectNewDomainMode') await this.selectDomainOnly();
    else if (name === 'acknowledgeCartErrorThenRetryNewDomain') await this.retryCart();
    else if (name === 'openCheckout') this.state = { 'purchaseScreenOpen': true, 'checkout': event['checkout'] };
    else if (name === 'returnCheckoutResult') await this.returnCheckout(event['result'] as Record<string, Object>);
    else if (name === 'openDetails') this.state = { 'managedDomain': event['managedDomain'], 'containedWebViewUrl': event['currentUrl'], 'requestedUrlLoadedInContainedWebView': false };
    else if (name === 'requestDetailsNavigation') await this.requestDetails(event['requestedUrl'] as string);
    await this.persist();
  }
  private async load(): Promise<void> {
    this.state = { 'listState': 'loading' };
    const response = await this.input.backend.fetchAllDomains(); this.fetchCount += 1;
    await this.input.leaf.emit({ name: 'fetchAllDomains', count: this.fetchCount });
    const type = response['type'] as string;
    if (type === 'success') { this.domains = records(response['domains']); this.state = { 'listState': 'complete', 'visibleDomains': names(this.domains) }; }
    else if (type === 'empty') { this.domains = []; this.state = { 'listState': 'empty', 'searchEnabled': false }; }
    else this.state = { 'listState': 'error', 'retryVisible': true };
  }
  private async openManagement(emptyAction: boolean): Promise<void> {
    await this.load(); const listState = this.state['listState'] as string;
    if (listState !== 'complete' && listState !== 'empty') return;
    await this.input.leaf.emit({ name: 'openNewDomainSearch', count: 1 });
    if (emptyAction) this.state = { 'listState': 'empty', 'searchEnabled': false, 'findDomainEnabled': true, 'destination': 'new_domain_search' };
    else this.state = { 'listState': 'complete', 'visibleDomains': names(this.domains), 'addDomainEnabled': true, 'destination': 'new_domain_search' };
  }
  private async retry(): Promise<void> {
    const before = this.state['listState'] as string; this.state = { 'listState': 'loading' };
    const response = await this.input.backend.fetchAllDomains(); this.fetchCount += 1;
    await this.input.leaf.emit({ name: 'fetchAllDomains', count: this.fetchCount });
    if (response['type'] === 'success') {
      this.domains = records(response['domains']);
      this.state = { 'statesInOrder': [before, 'loading', 'complete'], 'visibleDomains': names(this.domains), 'retryVisibleAfterSuccess': false };
    }
  }
  private async filter(query: string): Promise<void> {
    const needle = query.trim().toLowerCase();
    const visible = this.domains.filter((domain) => (domain['domain'] as string).toLowerCase().includes(needle)
      || (domain['siteSlug'] as string).toLowerCase().includes(needle)
      || (domain['blogName'] as string).toLowerCase().includes(needle));
    this.state = { 'listState': 'filtered', 'visibleDomains': names(visible), 'query': query };
    await this.input.leaf.emit({ name: 'filterLoadedDomains', normalizedQuery: query });
  }
  private async clearFilter(): Promise<void> {
    const before: Record<string, Object> = { 'listState': this.state['listState'], 'visibleDomains': this.state['visibleDomains'] };
    const after: Record<string, Object> = { 'listState': 'complete', 'visibleDomains': names(this.domains), 'query': '' };
    this.state = { 'beforeClear': before, 'afterClear': after };
    await this.input.leaf.emit({ name: 'restoreCompleteDomainList' });
  }
  private enterRemoteQuery(query: string, atMs: number): void {
    this.latestQuery = query.trim(); this.latestQueryAtMs = atMs;
    this.state = { 'normalizedQuery': this.latestQuery, 'searchState': 'waiting_for_debounce' };
  }
  private async advanceClock(toMs: number): Promise<void> {
    const dispatchAt = this.latestQueryAtMs + 250;
    if (this.latestQuery.length === 0 || toMs < dispatchAt) return;
    const found = await this.input.backend.searchForDomains(this.latestQuery);
    await this.input.leaf.emit({ name: 'searchForDomains', query: this.latestQuery, dispatchAtMs: dispatchAt, count: 1 });
    this.state = { 'normalizedQuery': this.latestQuery, 'searchState': 'populated', 'visibleDomains': found };
  }
  private async tapProposal(domain: string): Promise<void> {
    for (const proposal of this.proposals) if (proposal['domain'] === domain) { await this.openPurchase(proposal); return; }
  }
  private async openPurchase(proposal: Record<string, Object>): Promise<void> {
    this.selectedProposal = clone(proposal);
    const selected: Record<string, Object> = { 'productId': proposal['productId'], 'domain': proposal['domain'], 'supportsPrivacy': proposal['supportsPrivacy'] };
    this.state = { 'destination': 'purchase_domain', 'purchaseUiState': 'initial', 'availableModes': ['new_domain_only', 'existing_site'], 'selectedProposal': selected };
    await this.input.leaf.emit({ name: 'openPurchaseDomain', productId: proposal['productId'] as number, domain: proposal['domain'] as string, supportsPrivacy: proposal['supportsPrivacy'] as boolean });
  }
  private async submitCart(): Promise<Record<string, Object>> {
    const domain = this.selectedProposal['domain'] as string; this.cartCount += 1;
    await this.input.leaf.emit({ name: 'createCart', mode: 'domain_only', domain: domain, count: this.cartCount });
    return this.input.backend.createCart('domain_only', domain);
  }
  private async selectDomainOnly(): Promise<void> {
    this.state = { 'purchaseUiState': 'submitting_domain_only_cart' };
    const response = await this.submitCart();
    this.state = { 'purchaseUiState': response['type'] === 'error' ? 'error_submitting_cart' : 'initial' };
  }
  private async retryCart(): Promise<void> {
    const before = this.state['purchaseUiState'] as string; this.state = { 'purchaseUiState': 'initial' };
    const response = await this.submitCart();
    if (response['type'] === 'success') {
      const domain = this.selectedProposal['domain'] as string;
      await this.input.leaf.emit({ name: 'openDomainCheckout', domain: domain, count: 1 });
      this.state = { 'beforeRetry': before, 'statesAfterEvent': ['initial', 'submitting_domain_only_cart', 'initial'], 'destination': 'domain_checkout', 'checkoutDomain': domain };
    }
  }
  private async returnCheckout(result: Record<string, Object>): Promise<void> {
    const canceled = result['canceled'] as boolean;
    if (!canceled) await this.input.leaf.emit({ name: 'recordDomainPurchaseCompleted' });
    await this.input.leaf.emit({ name: 'openDomainManagement', count: 1 });
    this.state = { 'destination': 'all_domains', 'purchaseScreenOpen': false, 'checkoutError': false, 'registrationOutcome': canceled ? 'canceled' : 'completed' };
  }
  private async requestDetails(requestedUrl: string): Promise<void> {
    const managed = this.state['managedDomain'] as string;
    const allowedPrefix = 'https://wordpress.com/domains/manage/all/' + managed + '/edit/';
    if (requestedUrl.startsWith(allowedPrefix)) this.state = { 'containedWebViewUrl': requestedUrl, 'requestedUrlLoadedInContainedWebView': true };
    else {
      const current = this.state['containedWebViewUrl'];
      await this.input.leaf.emit({ name: 'redirectToExternalBrowser', url: requestedUrl, count: 1 });
      this.state = { 'containedWebViewUrl': current, 'requestedUrlLoadedInContainedWebView': false };
    }
  }
  private async persist(): Promise<void> { await this.prefs.put('state', JSON.stringify(this.state)); await this.prefs.flush(); }
}
