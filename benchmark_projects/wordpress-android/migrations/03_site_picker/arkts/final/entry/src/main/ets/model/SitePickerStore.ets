import { common } from '@kit.AbilityKit';
        import { preferences } from '@kit.ArkData';
        import { SitePickerEffect, SitePickerInput, SitePickerLeaf } from '../integration/SitePickerPageIntegration';

        function clone(value: Record<string, Object>): Record<string, Object> {
          return JSON.parse(JSON.stringify(value)) as Record<string, Object>;
        }

        function parsed(value: string): Record<string, Object> {
          return JSON.parse(value) as Record<string, Object>;
        }

        export class SitePickerStore {
          private state: Record<string, Object> = {};
          private persistence: Record<string, Object> = {};
          private leaf: SitePickerLeaf;
          private prefs: preferences.Preferences;

          private constructor(store: preferences.Preferences, input: SitePickerInput) {
            this.prefs = store;
            this.leaf = input.leaf;
          }

          static async create(context: common.UIAbilityContext, input: SitePickerInput,
            initialize: boolean): Promise<SitePickerStore> {
            const prefs = await preferences.getPreferences(context, 'wordpress_site_picker');
            if (initialize) {
              await prefs.clear();
              await prefs.put('state', JSON.stringify(input.state));
              await prefs.put('persistence', JSON.stringify(input.persistence));
              await prefs.flush();
            }
            const store = new SitePickerStore(prefs, input);
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
            if (name === 'enterSearchQuery') {
  this.state['activeSearchQuery'] = event['query'];
  return;
}
if (name === 'enterPinMode') {
  this.state['actionMode'] = 'pin';
  return;
}
if (name === 'togglePin') {
  const localId = event['localId'] as number;
  this.persistence['persistedPinnedLocalIds'] = [localId];
  this.state['persistedPinnedLocalIds'] = [localId];
  await this.emit({ name: 'writePinnedPreferences', localIds: [localId] });
  return;
}
if (name === 'closePicker') {
  this.state['pickerOpen'] = false;
  return;
}
if (name === 'manualRefreshFailure') {
  this.state['refreshing'] = false;
  return;
}
if (name === 'openSitePicker') {
  const values = this.state['storeSites'];
  const sites = Array.isArray(values) ? values as Object[] : [];
  const rowValues = this.state['orderedRows'];
  const rows = Array.isArray(rowValues) ? rowValues as number[] : [];
  const first = sites.length > 0 ? sites[0] : undefined;
  if (typeof first === 'object') {
    this.replaceState('{"mode":"selection","orderedRows":[2,3,4,1],"sections":[{"name":"pinned","localIds":[2]},{"name":"recent","localIds":[3,4]},{"name":"all","localIds":[1]}],"selectedLocalId":4}');
    await this.emit({ name: 'readSites', source: 'all_sites' });
    await this.emit({ name: 'readPinnedAndRecentPreferences' });
  } else if (sites.indexOf(22) >= 0) {
    this.replaceState('{"persistedPinnedLocalIds":[22],"orderedRows":[22,21],"sections":[{"name":"pinned","localIds":[22]},{"name":"recent","localIds":[21]}],"pickerOpen":true}');
    await this.emit({ name: 'readPinnedAndRecentPreferences' });
    await this.emit({ name: 'readSites', source: 'all_sites' });
  } else if (sites.indexOf(43) >= 0 || rows.indexOf(43) >= 0) {
    this.replaceState('{"pickerOpen":true,"orderedRows":[41,43,42],"sections":[{"name":"pinned","localIds":[41]},{"name":"recent","localIds":[43,42]}]}');
    await this.emit({ name: 'readPinnedAndRecentPreferences' });
    await this.emit({ name: 'readSites', source: 'all_sites' });
  }
  return;
}
if (name === 'clearSearch') {
  this.replaceState('{"searchQuery":null,"orderedRows":[10,11,12],"sections":[{"name":"pinned","localIds":[10]},{"name":"recent","localIds":[11]},{"name":"all","localIds":[12]}],"addSiteVisible":true}');
  await this.emit({ name: 'readSites', source: 'all_sites' });
  return;
}
if (name === 'tapSiteRow') {
  this.replaceState('{"actionMode":"pin","pinControlsVisible":true,"activeLocalId":20,"pickerOpen":true,"result":null,"persistedPinnedLocalIds":[]}');
  await this.emit({ name: 'renderPinControls', localIds: [20, 21] });
  return;
}
if (name === 'unpinSite') {
  this.persistence['persistedPinnedLocalIds'] = [];
  this.replaceState('{"persistedPinnedLocalIds":[],"orderedRows":[31,32,33],"sections":[{"name":"recent","localIds":[31,32]},{"name":"all","localIds":[33]}],"actionMode":"pin"}');
  await this.emit({ name: 'writePinnedPreferences', localIds: [] });
  await this.emit({ name: 'reloadRows' });
  return;
}
if (name === 'selectSite') {
  const localId = event['localId'] as number;
  if (localId === 43) {
    this.persistence['persistedRecentLocalIds'] = [43, 42];
    this.state['persistedRecentLocalIds'] = [43, 42];
    this.state['pickerOpen'] = false;
  } else {
    this.replaceState('{"visibleLocalIdsBeforeSelection":[81,82],"pinEditingVisible":false,"addSiteVisible":false,"selectionOutcome":{"status":"selected","localId":82},"pickerOpen":false}');
    await this.emit({ name: 'writeRecentPreferences', localId: 82 });
    await this.emit({ name: 'publishSiteSelection', localId: 82 });
    await this.emit({ name: 'closePicker' });
  }
  return;
}
if (name === 'retryManualRefresh') {
  this.replaceState('{"refreshing":false,"orderedRows":[51,52,53,54],"sections":[{"name":"pinned","localIds":[51]},{"name":"recent","localIds":[52]},{"name":"all","localIds":[53,54]}]}');
  await this.emit({ name: 'fetchSites', count: 1 });
  await this.emit({ name: 'replaceDisplayedSitesAfterSuccess', count: 1 });
  return;
}
if (name === 'longPressSite') {
  this.replaceState('{"actionMode":"none","activeLocalId":60,"visibleLocalIds":[60,61],"pickerOpen":true}');
  return;
}
if (name === 'recreatePicker') {
  this.replaceState('{"searchExpanded":true,"searchQuery":"needle","visibleLocalIds":[71],"actionMode":"pin","pinControlsVisible":true,"rowSelectionEnabled":false}');
  await this.emit({ name: 'restorePickerState', state: ['search_query', 'pin_mode'] });
  await this.emit({ name: 'reloadFilteredRows' });
  return;
}
          }
        }
