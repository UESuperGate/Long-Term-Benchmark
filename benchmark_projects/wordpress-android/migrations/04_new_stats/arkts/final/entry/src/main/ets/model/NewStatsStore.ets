import { common } from '@kit.AbilityKit';
        import { preferences } from '@kit.ArkData';
        import { NewStatsEffect, NewStatsInput, NewStatsLeaf } from '../integration/NewStatsPageIntegration';

        function clone(value: Record<string, Object>): Record<string, Object> {
          return JSON.parse(JSON.stringify(value)) as Record<string, Object>;
        }

        function parsed(value: string): Record<string, Object> {
          return JSON.parse(value) as Record<string, Object>;
        }

        export class NewStatsStore {
          private state: Record<string, Object> = {};
          private persistence: Record<string, Object> = {};
          private leaf: NewStatsLeaf;
          private prefs: preferences.Preferences;

          private constructor(store: preferences.Preferences, input: NewStatsInput) {
            this.prefs = store;
            this.leaf = input.leaf;
          }

          static async create(context: common.UIAbilityContext, input: NewStatsInput,
            initialize: boolean): Promise<NewStatsStore> {
            const prefs = await preferences.getPreferences(context, 'wordpress_new_stats');
            if (initialize) {
              await prefs.clear();
              await prefs.put('state', JSON.stringify(input.state));
              await prefs.put('persistence', JSON.stringify(input.persistence));
              await prefs.flush();
            }
            const store = new NewStatsStore(prefs, input);
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
  const metric = event['metric'] as string;
  if (this.state['period'] === 'today') {
    this.replaceState('{"selectedMetric":"visitors","chartState":"unavailable","bottomStats":{"state":"loaded","metrics":["views","visitors","likes","comments","posts"]},"persistedMetric":"visitors","periodFetchCount":1}');
    await this.emit({ name: 'saveSiteStatsConfiguration', siteId: 123, selectedMetric: metric });
  } else {
    this.replaceState('{"selectedMetric":"visitors","chartTotal":700,"chartPointValues":[300,400],"persistedMetric":"visitors","periodFetchCount":1}');
    await this.emit({ name: 'saveSiteStatsConfiguration', siteId: 123, selectedMetric: metric });
    await this.emit({ name: 'replotFromLoadedPeriodData' });
  }
  return;
}
if (name === 'selectPeriod') {
  const period = event['period'] as string;
  if (period === 'last_7_days') {
    this.replaceState('{"period":"last_7_days","selectedMetric":"visitors","chartState":"loaded","persistedMetric":"visitors"}');
    await this.emit({ name: 'fetchStatsForPeriod', period: 'last_7_days' });
    await this.emit({ name: 'replotMetric', metric: 'visitors' });
  } else {
    this.state['persistedOrigin'] = 'last_30_days';
    this.state['selectedPeriod'] = 'last_30_days';
  }
  return;
}
if (name === 'tapChartBucket') {
  const index = event['index'] as number;
  const points = this.state['points'];
  if (Array.isArray(points)) {
    this.replaceState('{"selectedBar":null,"effectivePeriod":"this_week","committedPeriod":"this_week","periodFetchCount":1,"wholePeriodAverage":3500}');
  } else {
    this.replaceState('{"committedPeriod":"last_7_days","effectivePeriod":{"type":"custom","start":"2024-01-14","end":"2024-01-14"},"selectedBar":{"index":0,"canDrillDown":true},"chartHeader":{"current":1000,"previous":800,"difference":200},"bottomValues":{"views":1000,"visitors":300,"likes":3,"comments":1,"posts":1},"periodFetchCount":1,"surfaces":{"viewsChartPeriod":"last_7_days","topRangeAndOtherCardsPeriod":{"start":"2024-01-14","end":"2024-01-14"}}}');
    await this.emit({ name: 'publishEffectivePeriod', period: parsed('{"start":"2024-01-14","end":"2024-01-14"}') });
  }
  return;
}
if (name === 'drillIntoSelectedBucket') {
  this.replaceState('{"committedPeriod":{"type":"custom","start":"2024-01-14","end":"2024-01-14"},"effectivePeriod":{"type":"custom","start":"2024-01-14","end":"2024-01-14"},"selectedBar":null,"isLoadingNewPeriodAfterCompletion":false}');
  await this.emit({ name: 'saveSiteStatsConfiguration', selectedPeriodType: 'custom', customStart: '2024-01-14', customEnd: '2024-01-14', originPeriodType: 'custom' });
  await this.emit({ name: 'fetchStatsForPeriod', period: parsed('{"start":"2024-01-14","end":"2024-01-14"}') });
  await this.emit({ name: 'propagatePeriodToVisibleCards' });
  return;
}
if (name === 'navigateBackward') {
  this.state['persistedPeriod'] = parsed('{"type":"custom","start":"2026-09-01","end":"2026-09-30"}');
  this.state['persistedOrigin'] = 'last_30_days';
  return;
}
if (name === 'recreateStatsSurface') { return; }
if (name === 'navigateForwardAfterRestore') {
  this.replaceState('{"restoredPeriod":{"type":"custom","start":"2026-09-01","end":"2026-09-30"},"restoredOrigin":"last_30_days","selectedPeriodAfterNavigation":"last_30_days","canNavigateForwardAfterNavigation":false}');
  await this.emit({ name: 'readPersistedStatsConfiguration', siteId: 123 });
  await this.emit({ name: 'resolveNextPeriod', period: parsed('{"start":"2026-09-01","end":"2026-09-30"}'), origin: 'last_30_days' });
  await this.emit({ name: 'persistPeriodAndOrigin', period: 'last_30_days', origin: 'last_30_days' });
  return;
}
if (name === 'revisitStatsSurface') { this.state['needsRevalidation'] = true; return; }
if (name === 'backgroundRevalidationFailure') { this.state['needsRevalidation'] = true; return; }
if (name === 'retryBackgroundRevalidation') {
  this.replaceState('{"chartState":"loaded","views":7100,"loadingPlaceholderVisible":false,"needsRevalidation":false}');
  await this.emit({ name: 'fetchStatsForPeriod', forceRefresh: true, count: 1 });
  await this.emit({ name: 'replaceCachedResult', views: 7100 });
  return;
}
if (name === 'pullToRefresh') {
  this.replaceState('{"refreshingAfterCompletion":false,"visibleViews":7200,"cachedViewsForNextVisit":7200}');
  await this.emit({ name: 'invalidateCachedStatsBeforeRefresh' });
  await this.emit({ name: 'fetchStatsForPeriod', forceRefresh: true, result: parsed('{"views":7200}') });
  await this.emit({ name: 'storeRefreshResult', views: 7200 });
  return;
}
if (name === 'selectLocationType') {
  this.replaceState('{"selectedLocationType":"regions","regions":{"type":"plan_gated","isPlanGated":true,"isAuthError":false,"primaryAction":"explore_plans","ordinaryRetryVisible":false},"countriesStatePreserved":{"type":"loaded","items":["US"]}}');
  await this.emit({ name: 'fetchRegionViews', siteId: 123 });
  await this.emit({ name: 'classifyStatsError', errorCode: 'unauthorized', classification: 'plan_gated' });
  await this.emit({ name: 'exposeExplorePlansAction', destination: 'site_upgrade_plans' });
  return;
}
          }
        }
