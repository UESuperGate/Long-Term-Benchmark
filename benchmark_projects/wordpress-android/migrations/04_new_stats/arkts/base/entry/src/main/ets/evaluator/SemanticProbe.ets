import { common } from '@kit.AbilityKit';
        import { preferences } from '@kit.ArkData';
        import { NewStatsEffect, NewStatsInput, NewStatsLeaf } from '../integration/NewStatsPageIntegration';
        import { MountedNewStatsPageOwner, NewStatsPageRuntime } from '../pages/NewStatsPageOwner';

        export interface PageRecreator { recreate(): Promise<void>; }
        export interface SemanticPayload {
          key: string;
          episodeJson: string;
        }
        interface RuntimeFixture { given: Record<string, Object>; event: Record<string, Object>; }
        interface RuntimeSnapshot {
          pageOwnerId: string;
          controllerOwnerId: string;
          storeSource: string;
          featureAvailable: boolean;
          state: Record<string, Object>;
          persistence: Record<string, Object>;
          reopenedState: Record<string, Object>;
        }
        interface RuntimeObserved {
          state: Record<string, Object>;
          effects: NewStatsEffect[];
        }
        interface RuntimeEvidence {
          pageOwnerId: string;
          controllerOwnerId: string;
          previousPageOwnerId: string;
          previousControllerOwnerId: string;
          storeSource: string;
          evaluatorStoreWrites: number;
          detachedControllers: number;
          leafCalls: NewStatsEffect[];
          pageRecreated: boolean;
          storageReopened: boolean;
        }
        interface RuntimeEpisode {
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
        }

        class RecordingLeaf implements NewStatsLeaf {
          effects: NewStatsEffect[] = [];
          async emit(effect: NewStatsEffect): Promise<void> {
            this.effects.push(JSON.parse(JSON.stringify(effect)) as NewStatsEffect);
          }
          clear(): void { this.effects = []; }
        }

        function parsed(value: string): Record<string, Object> {
          return JSON.parse(value) as Record<string, Object>;
        }
        function parsedFixture(value: string): RuntimeFixture {
          return JSON.parse(value) as RuntimeFixture;
        }
        function clone(value: Record<string, Object>): Record<string, Object> {
          return parsed(JSON.stringify(value));
        }
        function fixtureFor(key: string): RuntimeFixture {
          if (key === 'metric_replot_persist') return parsedFixture('{"given":{"siteId":123,"period":"last_7_days","selectedMetric":"views","loadedPeriodData":{"totals":{"views":7000,"visitors":700,"likes":50,"comments":25,"posts":5},"points":[{"period":"2024-01-14","views":1000,"visitors":300},{"period":"2024-01-15","views":1500,"visitors":400}]},"periodFetchCount":1},"event":{"name":"selectMetric","metric":"visitors"}}');
  if (key === 'hourly_fallback_restore') return parsedFixture('{"given":{"siteId":123,"period":"today","persistedMetric":"visitors","displayedMetric":"views","chartState":"loaded","hourlySeriesMetrics":["views"],"metricPickedOnCurrentPeriod":false},"event":{"name":"selectPeriod","period":"last_7_days"}}');
  if (key === 'explicit_hourly_unavailable') return parsedFixture('{"given":{"siteId":123,"period":"today","selectedMetric":"views","chartState":"loaded","bottomStats":{"state":"loaded","metrics":["views","visitors","likes","comments","posts"]},"periodFetchCount":1},"event":{"name":"selectMetric","metric":"visitors"}}');
  if (key === 'bar_soft_select') return parsedFixture('{"given":{"committedPeriod":"last_7_days","selectedMetric":"views","selectedBar":null,"chartType":"bar","periodFetchCount":1,"currentPoints":[{"period":"2024-01-14","views":1000,"visitors":300,"likes":3,"comments":1,"posts":1},{"period":"2024-01-15","views":1500,"visitors":400,"likes":4,"comments":2,"posts":1}],"previousPoints":[{"period":"2024-01-07","views":800,"visitors":250,"likes":2,"comments":0,"posts":1},{"period":"2024-01-08","views":1200,"visitors":350,"likes":3,"comments":1,"posts":1}]},"event":{"name":"tapChartBucket","index":0}}');
  if (key === 'bar_drill_commit') return parsedFixture('{"given":{"committedPeriod":"last_7_days","effectivePeriod":{"type":"custom","start":"2024-01-14","end":"2024-01-14"},"selectedBar":{"index":0,"rawPeriod":"2024-01-14","canDrillDown":true},"givenEstablishedBy":[{"name":"loadPeriodData"},{"name":"tapChartBucket","index":0}]},"event":{"name":"drillIntoSelectedBucket"}}');
  if (key === 'future_bucket_noop') return parsedFixture('{"given":{"period":"this_week","chartType":"bar","selectedBar":null,"periodFetchCount":1,"points":[{"period":"2024-01-14","views":1000,"isUpcoming":false},{"period":"2024-01-15","views":1500,"isUpcoming":false},{"period":"2024-01-16","views":0,"isUpcoming":true}],"wholePeriodAverage":3500},"event":{"name":"tapChartBucket","index":2}}');
  if (key === 'period_origin_restore') return parsedFixture('{"given":{"siteId":123,"clockDate":"2026-10-30","persistedPeriod":{"type":"custom","start":"2026-09-01","end":"2026-09-30"},"persistedOrigin":"last_30_days","processState":"recreated","givenEstablishedBy":[{"name":"selectPeriod","period":"last_30_days"},{"name":"navigateBackward"},{"name":"recreateStatsSurface"}]},"event":{"name":"navigateForwardAfterRestore"}}');
  if (key === 'cached_revalidation_recovery') return parsedFixture('{"given":{"siteId":123,"today":"2026-10-23","period":"last_7_days","requestIdentity":{"surface":"views_chart","siteId":123,"today":"2026-10-23","period":"last_7_days","variant":null},"displayedCachedResult":{"views":7000},"loadingPlaceholderVisible":false,"needsRevalidation":true,"nextRevalidationOutcome":{"views":7100},"givenEstablishedBy":[{"name":"revisitStatsSurface"},{"name":"backgroundRevalidation","outcome":"network_error","observableResult":"cached_content_preserved"}]},"event":{"name":"retryBackgroundRevalidation"}}');
  if (key === 'pull_refresh_inflight_isolation') return parsedFixture('{"given":{"siteId":123,"period":"last_7_days","displayedCachedResult":{"views":7000},"olderRequest":{"status":"in_flight","resultWhenReleased":{"views":7050}},"refreshRequestResult":{"views":7200},"completionOrder":["refresh_request","older_request"]},"event":{"name":"pullToRefresh"}}');
  if (key === 'plan_gate_presentation') return parsedFixture('{"given":{"siteId":123,"period":"last_7_days","userCanViewStats":true,"selectedLocationType":"countries","countriesState":{"type":"loaded","items":["US"]},"regionResponse":{"httpStatus":403,"body":"{\\"error\\":\\"unauthorized\\",\\"message\\":\\"localized\\"}"},"planActionDestination":"site_upgrade_plans"},"event":{"name":"selectLocationType","locationType":"regions"}}');
          throw new Error('Unknown runtime case: ' + key);
        }

        let activeContext: common.UIAbilityContext | undefined = undefined;
        let activeFixture: RuntimeFixture | undefined = undefined;
        let activeLeaf: RecordingLeaf | undefined = undefined;

        export function prepareSemanticCase(context: common.UIAbilityContext, key: string): void {
          const fixture = fixtureFor(key);
          const leaf = new RecordingLeaf();
          activeContext = context;
          activeFixture = fixture;
          activeLeaf = leaf;
          const input: NewStatsInput = {
            state: clone(fixture.given), persistence: clone(fixture.given), leaf: leaf
          };
          NewStatsPageRuntime.configure(context, input);
        }

        async function snapshot(context: common.UIAbilityContext,
          owner: MountedNewStatsPageOwner): Promise<RuntimeSnapshot> {
          const prefs = await preferences.getPreferences(context, 'wordpress_new_stats');
          const reopened = parsed(await prefs.get('state', '{}') as string);
          return {
            pageOwnerId: owner.ownerId(), controllerOwnerId: owner.controllerId(),
            storeSource: owner.storeSource(), featureAvailable: owner.featureAvailable(),
            state: owner.currentState(), persistence: owner.currentPersistence(), reopenedState: reopened
          };
        }

        export async function runSemanticCase(key: string, recreator: PageRecreator): Promise<SemanticPayload> {
          const context = activeContext;
          const fixture = activeFixture;
          const leaf = activeLeaf;
          if (context === undefined || fixture === undefined || leaf === undefined) throw new Error('probe not prepared');
          let owner = await NewStatsPageRuntime.waitForOwnerAfter();
          const methods: string[] = ['mount'];
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
          leaf.clear();
          const before = await snapshot(context, owner);
          const previousOwnerId = owner.ownerId();
          const previousControllerId = owner.controllerId();
          const eventName = fixture.event['name'] as string;
          let pageRecreated = false;
          if (key === 'period_origin_restore') {
            await recreator.recreate();
            owner = await NewStatsPageRuntime.waitForOwnerAfter(previousOwnerId);
            pageRecreated = true;
          }
          await owner.invoke(eventName, fixture.event);
          methods.push(eventName);
          const after = await snapshot(context, owner);
          const observed: RuntimeObserved = { state: after.state, effects: leaf.effects };
          const evidence: RuntimeEvidence = {
            pageOwnerId: after.pageOwnerId, controllerOwnerId: after.controllerOwnerId,
            previousPageOwnerId: previousOwnerId, previousControllerOwnerId: previousControllerId,
            storeSource: after.storeSource, evaluatorStoreWrites: 0, detachedControllers: 0,
            leafCalls: leaf.effects, pageRecreated: pageRecreated,
            storageReopened: JSON.stringify(after.state) === JSON.stringify(after.reopenedState)
          };
          const episode: RuntimeEpisode = {
            schemaVersion: 2, taskId: '04_new_stats', caseKey: key,
            given: fixture.given, event: fixture.event, givenEstablished: true,
            commonEntryObserved: true, entryOwner: 'pages/Index', before: before, after: after,
            observed: observed, invokedProductionMethods: methods,
            transitionExecuted: true, earlyExit: false, runtimeEvidence: evidence
          };
          return { key: key, episodeJson: JSON.stringify(episode) };
        }
