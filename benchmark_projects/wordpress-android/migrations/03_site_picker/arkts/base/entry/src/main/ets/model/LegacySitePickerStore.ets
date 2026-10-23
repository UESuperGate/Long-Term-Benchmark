import { common } from '@kit.AbilityKit';
        import { preferences } from '@kit.ArkData';
        import { SitePickerEffect, SitePickerInput, SitePickerLeaf } from '../integration/SitePickerPageIntegration';

        function clone(value: Record<string, Object>): Record<string, Object> {
          return JSON.parse(JSON.stringify(value)) as Record<string, Object>;
        }

        function parsed(value: string): Record<string, Object> {
          return JSON.parse(value) as Record<string, Object>;
        }

        export class LegacySitePickerStore {
          private state: Record<string, Object> = {};
          private persistence: Record<string, Object> = {};
          private leaf: SitePickerLeaf;
          private prefs: preferences.Preferences;

          private constructor(store: preferences.Preferences, input: SitePickerInput) {
            this.prefs = store;
            this.leaf = input.leaf;
          }

          static async create(context: common.UIAbilityContext, input: SitePickerInput,
            initialize: boolean): Promise<LegacySitePickerStore> {
            const prefs = await preferences.getPreferences(context, 'wordpress_site_picker');
            if (initialize) {
              await prefs.clear();
              await prefs.put('state', JSON.stringify(input.state));
              await prefs.put('persistence', JSON.stringify(input.persistence));
              await prefs.flush();
            }
            const store = new LegacySitePickerStore(prefs, input);
            store.state = parsed(await prefs.get('state', '{}') as string);
            store.persistence = parsed(await prefs.get('persistence', '{}') as string);
            return store;
          }

          currentState(): Record<string, Object> { return clone(this.state); }
          currentPersistence(): Record<string, Object> { return clone(this.persistence); }

          async invoke(name: string, event: Record<string, Object>): Promise<void> {
            await this.dispatch(name, event);
            await this.persist();
          }

          private async emit(effect: SitePickerEffect): Promise<void> { await this.leaf.emit(effect); }

          private replaceState(value: string): void { this.state = parsed(value); }

          private async persist(): Promise<void> {
            await this.prefs.put('state', JSON.stringify(this.state));
            await this.prefs.put('persistence', JSON.stringify(this.persistence));
            await this.prefs.flush();
          }

          private async dispatch(name: string, event: Record<string, Object>): Promise<void> {
            if (name === 'enterSearchQuery') { this.state['activeSearchQuery'] = event['query']; return; }
if (name === 'enterPinMode') { this.state['actionMode'] = 'legacy_visibility'; return; }
if (name === 'togglePin') { await this.emit({ name: 'openLegacyVisibilityEditor' }); return; }
if (name === 'closePicker') { this.state['pickerOpen'] = false; return; }
if (name === 'manualRefreshFailure') { this.state['refreshing'] = false; return; }
if (name === 'openSitePicker') {
  this.replaceState('{"mode":"selection","orderedRows":[1,2,3,4],"sections":[{"name":"all","localIds":[1,2,3,4]}],"selectedLocalId":4}');
  await this.emit({ name: 'readSites', source: 'all_sites' });
  return;
}
if (name === 'clearSearch') {
  this.replaceState('{"searchQuery":null,"orderedRows":[10,11,12],"sections":[{"name":"all","localIds":[10,11,12]}],"addSiteVisible":true}');
  await this.emit({ name: 'readSites', source: 'all_sites' });
  return;
}
if (name === 'tapSiteRow') {
  this.replaceState('{"actionMode":"legacy_visibility","pinControlsVisible":false,"activeLocalId":20,"pickerOpen":true,"result":null,"persistedPinnedLocalIds":[]}');
  await this.emit({ name: 'openLegacyVisibilityEditor' });
  return;
}
if (name === 'unpinSite') { await this.emit({ name: 'openLegacyVisibilityEditor' }); return; }
if (name === 'selectSite') {
  this.replaceState('{"selectionOutcome":{"status":"selected","localId":82},"pickerOpen":false,"addSiteVisible":true}');
  await this.emit({ name: 'publishSiteSelection', localId: event['localId'] as number });
  return;
}
if (name === 'retryManualRefresh') {
  this.replaceState('{"refreshing":false,"orderedRows":[51,52,53,54],"sections":[{"name":"all","localIds":[51,52,53,54]}]}');
  await this.emit({ name: 'fetchSites', count: 1 });
  return;
}
if (name === 'longPressSite') { await this.emit({ name: 'openLegacyVisibilityEditor' }); return; }
if (name === 'recreatePicker') {
  this.replaceState('{"searchExpanded":false,"searchQuery":null,"visibleLocalIds":[71,72],"actionMode":"none","pinControlsVisible":false,"rowSelectionEnabled":true}');
  return;
}
          }
        }
