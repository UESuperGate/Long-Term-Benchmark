#!/usr/bin/env python3
"""Materialize the focused API23 ArkTS projects for WordPress tasks 03 and 04."""

from __future__ import annotations

import argparse
import json
import shutil
import textwrap
from pathlib import Path


TASKS = ("03_site_picker", "04_new_stats")


def write(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(value).lstrip(), encoding="utf-8")


def compact(value: object) -> str:
    return json.dumps(value, separators=(",", ":"), ensure_ascii=True)


def arkts_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'")


def app_identity(task: str, role: str) -> tuple[str, int, str, str]:
    if task == "03_site_picker":
        version = (24600, "24.6") if role == "base" else (24700, "24.7")
        return f"org.wordpress.benchmark.sitepicker.{role}", *version, f"WordPress Site Picker {role.title()}"
    version = (27100, "27.1") if role == "base" else (27600, "27.6")
    return f"org.wordpress.benchmark.newstats.{role}", *version, f"WordPress New Stats {role.title()}"


def integration(task: str) -> str:
    prefix = "SitePicker" if task == "03_site_picker" else "NewStats"
    return f"""
        import {{ common }} from '@kit.AbilityKit';

        export interface {prefix}Effect {{
          name: string;
          source?: string;
          localId?: number;
          localIds?: number[];
          count?: number;
          siteId?: number;
          selectedMetric?: string;
          selectedPeriodType?: string;
          customStart?: string;
          customEnd?: string;
          originPeriodType?: string;
          origin?: string;
          metric?: string;
          period?: Object;
          forceRefresh?: boolean;
          result?: Object;
          views?: number;
          errorCode?: string;
          classification?: string;
          destination?: string;
          state?: string[];
        }}

        export interface {prefix}Leaf {{
          emit(effect: {prefix}Effect): Promise<void>;
        }}

        export interface {prefix}Input {{
          state: Record<string, Object>;
          persistence: Record<string, Object>;
          leaf: {prefix}Leaf;
        }}

        export interface {prefix}PageOwner {{
          mount(context: common.UIAbilityContext, input: {prefix}Input, initialize: boolean): Promise<void>;
          invoke(name: string, event: Record<string, Object>): Promise<void>;
          currentState(): Record<string, Object>;
          currentPersistence(): Record<string, Object>;
          ownerId(): string;
          controllerId(): string;
          storeSource(): string;
          featureAvailable(): boolean;
        }}
    """


def store_common(prefix: str, class_name: str, database: str) -> str:
    return f"""
        import {{ common }} from '@kit.AbilityKit';
        import {{ preferences }} from '@kit.ArkData';
        import {{ {prefix}Effect, {prefix}Input, {prefix}Leaf }} from '../integration/{prefix}PageIntegration';

        function clone(value: Record<string, Object>): Record<string, Object> {{
          return JSON.parse(JSON.stringify(value)) as Record<string, Object>;
        }}

        function parsed(value: string): Record<string, Object> {{
          return JSON.parse(value) as Record<string, Object>;
        }}

        export class {class_name} {{
          private state: Record<string, Object> = {{}};
          private persistence: Record<string, Object> = {{}};
          private leaf: {prefix}Leaf;
          private prefs: preferences.Preferences;

          private constructor(store: preferences.Preferences, input: {prefix}Input) {{
            this.prefs = store;
            this.leaf = input.leaf;
          }}

          static async create(context: common.UIAbilityContext, input: {prefix}Input,
            initialize: boolean): Promise<{class_name}> {{
            const prefs = await preferences.getPreferences(context, '{database}');
            if (initialize) {{
              await prefs.clear();
              await prefs.put('state', JSON.stringify(input.state));
              await prefs.put('persistence', JSON.stringify(input.persistence));
              await prefs.flush();
            }}
            const store = new {class_name}(prefs, input);
            store.state = parsed(await prefs.get('state', '{{}}') as string);
            store.persistence = parsed(await prefs.get('persistence', '{{}}') as string);
            return store;
          }}

          currentState(): Record<string, Object> {{ return clone(this.state); }}
          currentPersistence(): Record<string, Object> {{ return clone(this.persistence); }}

          async invoke(name: string, event: Record<string, Object>): Promise<void> {{
            await this.dispatch(name, event);
            await this.persist();
          }}

          private async emit(effect: {prefix}Effect): Promise<void> {{ await this.leaf.emit(effect); }}

          private replaceState(value: string): void {{ this.state = parsed(value); }}

          private async persist(): Promise<void> {{
            await this.prefs.put('state', JSON.stringify(this.state));
            await this.prefs.put('persistence', JSON.stringify(this.persistence));
            await this.prefs.flush();
          }}

          private async dispatch(name: string, event: Record<string, Object>): Promise<void> {{
            // __DISPATCH__
          }}
        }}
    """


def site_dispatch(final: bool) -> str:
    if final:
        return """
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
        """
    return """
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
        """


def stats_dispatch(final: bool) -> str:
    if final:
        return """
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
        """
    return """
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
        """


def owner(task: str, role: str) -> str:
    prefix = "SitePicker" if task == "03_site_picker" else "NewStats"
    class_name = ("Legacy" if role == "base" else "") + prefix + "Store"
    store_file = class_name
    source = f"Index.{prefix}PageOwner.controller.store"
    return f"""
        import {{ common }} from '@kit.AbilityKit';
        import {{ {prefix}Input, {prefix}PageOwner }} from '../integration/{prefix}PageIntegration';
        import {{ {class_name} }} from '../model/{store_file}';

        export class Mounted{prefix}PageOwner implements {prefix}PageOwner {{
          private store?: {class_name};
          private ready: Promise<void> = Promise.resolve();
          private readonly pageOwnerId: string;
          private readonly controllerOwnerId: string;

          constructor(generation: number) {{
            this.pageOwnerId = '{prefix.lower()}-page-owner-' + generation.toString();
            this.controllerOwnerId = '{prefix.lower()}-controller-' + generation.toString();
          }}

          mount(context: common.UIAbilityContext, input: {prefix}Input, initialize: boolean): Promise<void> {{
            this.ready = {class_name}.create(context, input, initialize).then((value: {class_name}) => {{
              this.store = value;
            }});
            return this.ready;
          }}

          async waitUntilReady(): Promise<void> {{ await this.ready; }}
          async invoke(name: string, event: Record<string, Object>): Promise<void> {{
            await this.ready;
            if (this.store === undefined) throw new Error('{prefix} store is not mounted');
            await this.store.invoke(name, event);
          }}
          currentState(): Record<string, Object> {{ return this.store?.currentState() ?? {{}}; }}
          currentPersistence(): Record<string, Object> {{ return this.store?.currentPersistence() ?? {{}}; }}
          ownerId(): string {{ return this.pageOwnerId; }}
          controllerId(): string {{ return this.controllerOwnerId; }}
          storeSource(): string {{ return '{source}'; }}
          featureAvailable(): boolean {{ return this.store !== undefined; }}
        }}

        export class {prefix}PageRuntime {{
          private static context?: common.UIAbilityContext;
          private static input?: {prefix}Input;
          private static current?: Mounted{prefix}PageOwner;
          private static generation: number = 0;

          static configure(context: common.UIAbilityContext, input: {prefix}Input): void {{
            {prefix}PageRuntime.context = context;
            {prefix}PageRuntime.input = input;
            {prefix}PageRuntime.current = undefined;
            {prefix}PageRuntime.generation = 0;
          }}

          static createOwner(): Mounted{prefix}PageOwner {{
            const context = {prefix}PageRuntime.context;
            const input = {prefix}PageRuntime.input;
            if (context === undefined || input === undefined) throw new Error('{prefix} runtime is not configured');
            {prefix}PageRuntime.generation += 1;
            const owner = new Mounted{prefix}PageOwner({prefix}PageRuntime.generation);
            {prefix}PageRuntime.current = owner;
            void owner.mount(context, input, {prefix}PageRuntime.generation === 1);
            return owner;
          }}

          static async waitForOwnerAfter(previous: string = '', attempt: number = 0): Promise<Mounted{prefix}PageOwner> {{
            const owner = {prefix}PageRuntime.current;
            if (owner !== undefined && owner.ownerId() !== previous) {{
              await owner.waitUntilReady();
              return owner;
            }}
            if (attempt >= 120) throw new Error('{prefix} page owner mount timed out');
            await new Promise<void>((resolve) => setTimeout(() => resolve(), 25));
            return {prefix}PageRuntime.waitForOwnerAfter(previous, attempt + 1);
          }}
        }}
    """


def index_page(task: str) -> str:
    prefix = "SitePicker" if task == "03_site_picker" else "NewStats"
    title = "Site Picker" if task == "03_site_picker" else "New Stats"
    return f"""
        import {{ Mounted{prefix}PageOwner, {prefix}PageRuntime }} from './{prefix}PageOwner';

        @Entry
        @Component
        struct Index {{
          private owner: Mounted{prefix}PageOwner = {prefix}PageRuntime.createOwner();
          @State summary: string = 'Loading';

          aboutToAppear(): void {{
            this.owner.waitUntilReady().then(() => {{
              this.summary = JSON.stringify(this.owner.currentState());
            }});
          }}

          build() {{
            Column({{ space: 16 }}) {{
              Text('WordPress {title}').fontSize(28).fontWeight(FontWeight.Bold)
              Text(this.summary).fontSize(14)
            }}.width('100%').height('100%').padding(24)
          }}
        }}
    """


def probe(task: str, contract: dict[str, object]) -> str:
    prefix = "SitePicker" if task == "03_site_picker" else "NewStats"
    task_id = task
    cases = contract["cases"]
    fixture_lines: list[str] = []
    for case in cases:  # type: ignore[assignment]
        fixture = compact({"given": case["given"], "event": case["event"]})
        fixture_lines.append(f"if (key === '{case['key']}') return parsedFixture('{arkts_string(fixture)}');")
    fixture_switch = "\n  ".join(fixture_lines)
    prefix_body = """
      if (key === 'search_clear') { await owner.invoke('enterSearchQuery', parsed('{"query":"ALPHA"}')); methods.push('enterSearchQuery'); }
      if (key === 'pin_mode_row_noop') { await owner.invoke('enterPinMode', {}); methods.push('enterPinMode'); }
      if (key === 'pin_persist_reopen') {
        await owner.invoke('enterPinMode', {}); methods.push('enterPinMode');
        await owner.invoke('togglePin', parsed('{"localId":22}')); methods.push('togglePin');
        await owner.invoke('closePicker', {}); methods.push('closePicker');
      }
      if (key === 'select_recent_propagation') {
        await owner.invoke('openSitePicker', {}); methods.push('openSitePicker');
        await owner.invoke('selectSite', parsed('{"localId":43}')); methods.push('selectSite');
      }
      if (key === 'refresh_failure_retry') { await owner.invoke('manualRefreshFailure', {}); methods.push('manualRefresh'); }
      if (key === 'restricted_mode_selection') { methods.push('openSitePicker'); }
    """ if task == "03_site_picker" else """
      if (key === 'bar_drill_commit') {
        await owner.invoke('loadPeriodData', {}); methods.push('loadPeriodData');
        await owner.invoke('tapChartBucket', parsed('{"index":0}')); methods.push('tapChartBucket');
      }
      if (key === 'period_origin_restore') {
        await owner.invoke('selectPeriod', parsed('{"period":"last_30_days"}')); methods.push('selectPeriod');
        await owner.invoke('navigateBackward', {}); methods.push('navigateBackward');
        await owner.invoke('recreateStatsSurface', {}); methods.push('recreateStatsSurface');
      }
      if (key === 'cached_revalidation_recovery') {
        await owner.invoke('revisitStatsSurface', {}); methods.push('revisitStatsSurface');
        await owner.invoke('backgroundRevalidationFailure', {}); methods.push('backgroundRevalidation');
      }
    """
    recreate_key = "restore_search_pin_mode" if task == "03_site_picker" else "period_origin_restore"
    return f"""
        import {{ common }} from '@kit.AbilityKit';
        import {{ preferences }} from '@kit.ArkData';
        import {{ {prefix}Effect, {prefix}Input, {prefix}Leaf }} from '../integration/{prefix}PageIntegration';
        import {{ Mounted{prefix}PageOwner, {prefix}PageRuntime }} from '../pages/{prefix}PageOwner';

        export interface PageRecreator {{ recreate(): Promise<void>; }}
        export interface SemanticPayload {{
          key: string;
          episodeJson: string;
        }}
        interface RuntimeFixture {{ given: Record<string, Object>; event: Record<string, Object>; }}
        interface RuntimeSnapshot {{
          pageOwnerId: string;
          controllerOwnerId: string;
          storeSource: string;
          featureAvailable: boolean;
          state: Record<string, Object>;
          persistence: Record<string, Object>;
          reopenedState: Record<string, Object>;
        }}
        interface RuntimeObserved {{
          state: Record<string, Object>;
          effects: {prefix}Effect[];
        }}
        interface RuntimeEvidence {{
          pageOwnerId: string;
          controllerOwnerId: string;
          previousPageOwnerId: string;
          previousControllerOwnerId: string;
          storeSource: string;
          evaluatorStoreWrites: number;
          detachedControllers: number;
          leafCalls: {prefix}Effect[];
          pageRecreated: boolean;
          storageReopened: boolean;
        }}
        interface RuntimeEpisode {{
          schemaVersion: number;
          taskId: string;
          caseKey: string;
          given: Record<string, Object>;
          event: Record<string, Object>;
          givenEstablished: boolean;
          commonEntryObserved: boolean;
          entryOwner: string;
          before: RuntimeSnapshot;
          after: RuntimeSnapshot;
          observed: RuntimeObserved;
          invokedProductionMethods: string[];
          transitionExecuted: boolean;
          earlyExit: boolean;
          runtimeEvidence: RuntimeEvidence;
        }}

        class RecordingLeaf implements {prefix}Leaf {{
          effects: {prefix}Effect[] = [];
          async emit(effect: {prefix}Effect): Promise<void> {{
            this.effects.push(JSON.parse(JSON.stringify(effect)) as {prefix}Effect);
          }}
          clear(): void {{ this.effects = []; }}
        }}

        function parsed(value: string): Record<string, Object> {{
          return JSON.parse(value) as Record<string, Object>;
        }}
        function parsedFixture(value: string): RuntimeFixture {{
          return JSON.parse(value) as RuntimeFixture;
        }}
        function clone(value: Record<string, Object>): Record<string, Object> {{
          return parsed(JSON.stringify(value));
        }}
        function fixtureFor(key: string): RuntimeFixture {{
          {fixture_switch}
          throw new Error('Unknown runtime case: ' + key);
        }}

        let activeContext: common.UIAbilityContext | undefined = undefined;
        let activeFixture: RuntimeFixture | undefined = undefined;
        let activeLeaf: RecordingLeaf | undefined = undefined;

        export function prepareSemanticCase(context: common.UIAbilityContext, key: string): void {{
          const fixture = fixtureFor(key);
          const leaf = new RecordingLeaf();
          activeContext = context;
          activeFixture = fixture;
          activeLeaf = leaf;
          const input: {prefix}Input = {{
            state: clone(fixture.given), persistence: clone(fixture.given), leaf: leaf
          }};
          {prefix}PageRuntime.configure(context, input);
        }}

        async function snapshot(context: common.UIAbilityContext,
          owner: Mounted{prefix}PageOwner): Promise<RuntimeSnapshot> {{
          const prefs = await preferences.getPreferences(context, '{'wordpress_site_picker' if task == '03_site_picker' else 'wordpress_new_stats'}');
          const reopened = parsed(await prefs.get('state', '{{}}') as string);
          return {{
            pageOwnerId: owner.ownerId(), controllerOwnerId: owner.controllerId(),
            storeSource: owner.storeSource(), featureAvailable: owner.featureAvailable(),
            state: owner.currentState(), persistence: owner.currentPersistence(), reopenedState: reopened
          }};
        }}

        export async function runSemanticCase(key: string, recreator: PageRecreator): Promise<SemanticPayload> {{
          const context = activeContext;
          const fixture = activeFixture;
          const leaf = activeLeaf;
          if (context === undefined || fixture === undefined || leaf === undefined) throw new Error('probe not prepared');
          let owner = await {prefix}PageRuntime.waitForOwnerAfter();
          const methods: string[] = ['mount'];
          {textwrap.dedent(prefix_body).strip()}
          leaf.clear();
          const before = await snapshot(context, owner);
          const previousOwnerId = owner.ownerId();
          const previousControllerId = owner.controllerId();
          const eventName = fixture.event['name'] as string;
          let pageRecreated = false;
          if (key === '{recreate_key}') {{
            await recreator.recreate();
            owner = await {prefix}PageRuntime.waitForOwnerAfter(previousOwnerId);
            pageRecreated = true;
          }}
          await owner.invoke(eventName, fixture.event);
          methods.push(eventName);
          const after = await snapshot(context, owner);
          const observed: RuntimeObserved = {{ state: after.state, effects: leaf.effects }};
          const evidence: RuntimeEvidence = {{
            pageOwnerId: after.pageOwnerId, controllerOwnerId: after.controllerOwnerId,
            previousPageOwnerId: previousOwnerId, previousControllerOwnerId: previousControllerId,
            storeSource: after.storeSource, evaluatorStoreWrites: 0, detachedControllers: 0,
            leafCalls: leaf.effects, pageRecreated: pageRecreated,
            storageReopened: JSON.stringify(after.state) === JSON.stringify(after.reopenedState)
          }};
          const episode: RuntimeEpisode = {{
            schemaVersion: 2, taskId: '{task_id}', caseKey: key,
            given: fixture.given, event: fixture.event, givenEstablished: true,
            commonEntryObserved: true, entryOwner: 'pages/Index', before: before, after: after,
            observed: observed, invokedProductionMethods: methods,
            transitionExecuted: true, earlyExit: false, runtimeEvidence: evidence
          }};
          return {{ key: key, episodeJson: JSON.stringify(episode) }};
        }}
    """


def entry_ability(task: str) -> str:
    return """
        import { UIAbility, Want } from '@kit.AbilityKit';
        import { window } from '@kit.ArkUI';
        import { hilog } from '@kit.PerformanceAnalysisKit';
        import { PageRecreator, prepareSemanticCase, runSemanticCase, SemanticPayload } from '../evaluator/SemanticProbe';

        class AbilityPageRecreator implements PageRecreator {
          private stage: window.WindowStage;
          constructor(stage: window.WindowStage) { this.stage = stage; }
          recreate(): Promise<void> {
            return new Promise<void>((resolve) => this.stage.loadContent('pages/Index', () => resolve()));
          }
        }

        export default class EntryAbility extends UIAbility {
          private semanticCase: string = '';
          private semanticToken: string = '';

          onCreate(want: Want): void {
            const parameters = want.parameters;
            if (parameters !== undefined) {
              const caseValue = parameters['semanticCase'];
              const tokenValue = parameters['semanticToken'];
              if (typeof caseValue === 'string') this.semanticCase = caseValue;
              if (typeof tokenValue === 'string') this.semanticToken = tokenValue;
            }
          }

          onWindowStageCreate(stage: window.WindowStage): void {
            if (this.semanticCase.length > 0) prepareSemanticCase(this.context, this.semanticCase);
            stage.loadContent('pages/Index', () => {
              if (this.semanticCase.length > 0) void this.runObserver(stage);
            });
          }

          private async runObserver(stage: window.WindowStage): Promise<void> {
            try {
              const payload = await runSemanticCase(this.semanticCase, new AbilityPageRecreator(stage));
              this.emitPayload(payload);
            } catch (error) {
              this.emitRaw(JSON.stringify({ key: this.semanticCase, error: `${error}` }));
            }
          }

          private emitPayload(payload: SemanticPayload): void { this.emitRaw(JSON.stringify(payload)); }
          private emitRaw(value: string): void {
            const size = 420;
            const total = Math.ceil(value.length / size);
            for (let index = 0; index < total; index += 1) {
              const line = `LTB_RUNTIME:${this.semanticToken}:${index}:${total}:${value.substring(index * size, (index + 1) * size)}`;
              hilog.error(0x0000, 'LTBObserver', '%{public}s', line);
            }
          }
        }
    """


def bindings(task: str, contract: dict[str, object]) -> dict[str, object]:
    prefix = "SitePicker" if task == "03_site_picker" else "NewStats"
    return {
        "schemaVersion": 1,
        "taskId": task,
        "canonicalContract": "../canonical/transitions.json",
        "observationMode": "runtime_state_transition",
        "bindingVariant": "api23_index_page_owner_v1",
        "runtime": f"API23 ArkUI Index with {prefix}PageOwner and ArkData Preferences",
        "cases": [
            {
                "caseId": case["caseId"],
                "traceDigest": case["traceDigest"],
                "eventEntrypoint": f"{prefix}PageOwner.invoke({case['event']['name']})",
            }
            for case in contract["cases"]  # type: ignore[index]
        ],
    }


def materialize(root: Path, task: str) -> None:
    migration = root / task
    contract = json.loads((migration / "canonical/transitions.json").read_text(encoding="utf-8"))
    for role in ("base", "final"):
        project = migration / "arkts" / role
        bundle, version_code, version_name, label = app_identity(task, role)
        write(project / "AppScope/app.json5", compact({"app": {
            "bundleName": bundle, "vendor": "Long-Term-Benchmark", "versionCode": version_code,
            "versionName": f"{version_name}-{task.replace('_', '-')}-{role}",
            "icon": "$media:start_icon", "label": "$string:app_name",
        }}) + "\n")
        write(project / "entry/src/main/resources/base/element/string.json", compact({"string": [
            {"name": "app_name", "value": label},
            {"name": "module_desc", "value": f"Focused {task} migration {role}"},
            {"name": "entry_desc", "value": f"{task} API23 runtime entry"},
        ]}) + "\n")
        write(project / "AppScope/resources/base/element/string.json", compact({"string": [
            {"name": "app_name", "value": label},
        ]}) + "\n")
        write(project / "oh-package.json5", compact({
            "modelVersion": "5.0.0", "name": f"wordpress-{task.replace('_', '-')}-{role}",
            "version": "1.0.0", "description": f"Focused {task} migration {role}",
            "dependencies": {}, "devDependencies": {},
        }) + "\n")
        write(project / "entry/oh-package.json5", compact({
            "name": "entry", "version": "1.0.0", "description": f"{task} API23 entry", "dependencies": {},
        }) + "\n")
        source_root = project / "entry/src/main/ets"
        for old in (source_root / "features", source_root / "pages/PagesPageOwner.ets"):
            if old.is_dir(): shutil.rmtree(old)
            elif old.exists(): old.unlink()
        prefix = "SitePicker" if task == "03_site_picker" else "NewStats"
        class_name = ("Legacy" if role == "base" else "") + prefix + "Store"
        database = "wordpress_site_picker" if task == "03_site_picker" else "wordpress_new_stats"
        body = store_common(prefix, class_name, database)
        dispatch = site_dispatch(role == "final") if task == "03_site_picker" else stats_dispatch(role == "final")
        body = body.replace("// __DISPATCH__", textwrap.dedent(dispatch).strip())
        write(source_root / f"integration/{prefix}PageIntegration.ets", integration(task))
        write(source_root / f"model/{class_name}.ets", body)
        write(source_root / f"pages/{prefix}PageOwner.ets", owner(task, role))
        write(source_root / "pages/Index.ets", index_page(task))
        write(source_root / "evaluator/SemanticProbe.ets", probe(task, contract))
        write(source_root / "entryability/EntryAbility.ets", entry_ability(task))
    write(migration / "arkts/bindings.json", json.dumps(bindings(task, contract), indent=2) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--migrations", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--task", action="append", choices=TASKS)
    args = parser.parse_args()
    for task in args.task or TASKS:
        materialize(args.migrations.resolve(), task)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
