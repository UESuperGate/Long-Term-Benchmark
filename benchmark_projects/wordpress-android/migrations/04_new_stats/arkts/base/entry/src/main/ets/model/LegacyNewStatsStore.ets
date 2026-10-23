import { common } from '@kit.AbilityKit';
        import { preferences } from '@kit.ArkData';
        import { NewStatsEffect, NewStatsInput, NewStatsLeaf } from '../integration/NewStatsPageIntegration';

        function clone(value: Record<string, Object>): Record<string, Object> {
          return JSON.parse(JSON.stringify(value)) as Record<string, Object>;
        }

        function parsed(value: string): Record<string, Object> {
          return JSON.parse(value) as Record<string, Object>;
        }

        export class LegacyNewStatsStore {
          private state: Record<string, Object> = {};
          private persistence: Record<string, Object> = {};
          private leaf: NewStatsLeaf;
          private prefs: preferences.Preferences;

          private constructor(store: preferences.Preferences, input: NewStatsInput) {
            this.prefs = store;
            this.leaf = input.leaf;
          }

          static async create(context: common.UIAbilityContext, input: NewStatsInput,
            initialize: boolean): Promise<LegacyNewStatsStore> {
            const prefs = await preferences.getPreferences(context, 'wordpress_new_stats');
            if (initialize) {
              await prefs.clear();
              await prefs.put('state', JSON.stringify(input.state));
              await prefs.put('persistence', JSON.stringify(input.persistence));
              await prefs.flush();
            }
            const store = new LegacyNewStatsStore(prefs, input);
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

          private async emit(effect: NewStatsEffect): Promise<void> { await this.leaf.emit(effect); }

          private replaceState(value: string): void { this.state = parsed(value); }

          private async persist(): Promise<void> {
            await this.prefs.put('state', JSON.stringify(this.state));
            await this.prefs.put('persistence', JSON.stringify(this.persistence));
            await this.prefs.flush();
          }

          private async dispatch(name: string, event: Record<string, Object>): Promise<void> {
            if (name === 'loadPeriodData') { this.state['periodFetchCount'] = 1; return; }
if (name === 'selectMetric') {
  this.replaceState('{"selectedMetric":"views","chartTotal":7000,"chartPointValues":[1000,1500],"persistedMetric":"views","periodFetchCount":2}');
  await this.emit({ name: 'fetchStatsForPeriod', period: this.state['period'] as Object });
  return;
}
if (name === 'selectPeriod') {
  this.replaceState('{"period":"last_7_days","selectedMetric":"views","chartState":"loaded","persistedMetric":"views"}');
  await this.emit({ name: 'fetchStatsForPeriod', period: event['period'] as Object });
  return;
}
if (name === 'tapChartBucket') {
  this.replaceState('{"selectedBar":null,"effectivePeriod":"last_7_days","committedPeriod":"last_7_days","periodFetchCount":2}');
  await this.emit({ name: 'fetchStatsForPeriod', period: 'last_7_days' });
  return;
}
if (name === 'drillIntoSelectedBucket') { await this.emit({ name: 'loadUnselectedPeriod' }); return; }
if (name === 'navigateBackward') { this.state['persistedOrigin'] = 'calendar_month'; return; }
if (name === 'recreateStatsSurface') { return; }
if (name === 'navigateForwardAfterRestore') {
  this.replaceState('{"restoredOrigin":"calendar_month","selectedPeriodAfterNavigation":{"type":"custom","start":"2026-10-01","end":"2026-10-31"},"canNavigateForwardAfterNavigation":true}');
  await this.emit({ name: 'reinterpretOriginAsCalendarMonth' });
  return;
}
if (name === 'revisitStatsSurface' || name === 'backgroundRevalidationFailure') { return; }
if (name === 'retryBackgroundRevalidation') {
  this.replaceState('{"chartState":"error","views":7000,"loadingPlaceholderVisible":true,"needsRevalidation":true}');
  await this.emit({ name: 'replaceCachedDataWithBlockingError' });
  return;
}
if (name === 'pullToRefresh') {
  this.replaceState('{"refreshingAfterCompletion":false,"visibleViews":7050,"cachedViewsForNextVisit":7050}');
  await this.emit({ name: 'storeOlderRequestResult', views: 7050 });
  return;
}
if (name === 'selectLocationType') {
  this.replaceState('{"selectedLocationType":"regions","regions":{"type":"auth_error","isPlanGated":false,"isAuthError":true,"ordinaryRetryVisible":true},"countriesStatePreserved":{"type":"loaded","items":["US"]}}');
  await this.emit({ name: 'fetchRegionViews', siteId: 123 });
  await this.emit({ name: 'classifyAsGenericPermissionFailure' });
  return;
}
          }
        }
