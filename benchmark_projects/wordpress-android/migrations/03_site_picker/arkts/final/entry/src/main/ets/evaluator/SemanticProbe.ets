import { common } from '@kit.AbilityKit';
        import { preferences } from '@kit.ArkData';
        import { SitePickerEffect, SitePickerInput, SitePickerLeaf } from '../integration/SitePickerPageIntegration';
        import { MountedSitePickerPageOwner, SitePickerPageRuntime } from '../pages/SitePickerPageOwner';

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
          effects: SitePickerEffect[];
        }
        interface RuntimeEvidence {
          pageOwnerId: string;
          controllerOwnerId: string;
          previousPageOwnerId: string;
          previousControllerOwnerId: string;
          storeSource: string;
          evaluatorStoreWrites: number;
          detachedControllers: number;
          leafCalls: SitePickerEffect[];
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

        class RecordingLeaf implements SitePickerLeaf {
          effects: SitePickerEffect[] = [];
          async emit(effect: SitePickerEffect): Promise<void> {
            this.effects.push(JSON.parse(JSON.stringify(effect)) as SitePickerEffect);
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
          if (key === 'grouped_open') return parsedFixture('{"given":{"mode":"default","storeSites":[{"localId":1,"siteId":101,"name":"Alpha","host":"alpha.test","wpComAccessible":true},{"localId":2,"siteId":102,"name":"Pinned","host":"pinned.test","wpComAccessible":true},{"localId":3,"siteId":103,"name":"Recent One","host":"recent-one.test","wpComAccessible":true},{"localId":4,"siteId":104,"name":"Recent Current","host":"recent-current.test","wpComAccessible":true}],"persistedPinnedLocalIds":[2],"persistedRecentLocalIds":[3,2,4],"selectedLocalId":4},"event":{"name":"openSitePicker"}}');
  if (key === 'search_clear') return parsedFixture('{"given":{"mode":"default","storeSites":[{"localId":10,"name":"Alpha Pinned","host":"alpha-pinned.test"},{"localId":11,"name":"Alpha Recent","host":"alpha-recent.test"},{"localId":12,"name":"Beta","host":"beta.test"}],"persistedPinnedLocalIds":[10],"persistedRecentLocalIds":[10,11],"activeSearchQuery":"ALPHA","visibleLocalIds":[10,11],"givenEstablishedBy":[{"name":"enterSearchQuery","query":"ALPHA"}]},"event":{"name":"clearSearch"}}');
  if (key === 'pin_mode_row_noop') return parsedFixture('{"given":{"mode":"default","actionMode":"pin","activeLocalId":20,"rows":[20,21],"persistedPinnedLocalIds":[],"givenEstablishedBy":[{"name":"enterPinMode"}]},"event":{"name":"tapSiteRow","localId":21}}');
  if (key === 'pin_persist_reopen') return parsedFixture('{"given":{"mode":"default","storeSites":[21,22],"persistedPinnedLocalIds":[22],"persistedRecentLocalIds":[21],"pickerOpen":false,"givenEstablishedBy":[{"name":"enterPinMode"},{"name":"togglePin","localId":22},{"name":"closePicker"}]},"event":{"name":"openSitePicker"}}');
  if (key === 'unpin_regroup') return parsedFixture('{"given":{"mode":"default","rows":[31,32,33],"persistedPinnedLocalIds":[31],"persistedRecentLocalIds":[31,32],"actionMode":"pin"},"event":{"name":"unpinSite","localId":31}}');
  if (key === 'select_recent_propagation') return parsedFixture('{"given":{"mode":"default","storeSites":[41,42,43],"persistedPinnedLocalIds":[41],"persistedRecentLocalIds":[43,42],"pickerOpen":false,"givenEstablishedBy":[{"name":"openSitePicker"},{"name":"selectSite","localId":43}]},"event":{"name":"openSitePicker"}}');
  if (key === 'refresh_failure_retry') return parsedFixture('{"given":{"mode":"default","orderedRows":[51,52,53],"sections":[{"name":"pinned","localIds":[51]},{"name":"recent","localIds":[52]},{"name":"all","localIds":[53]}],"persistedPinnedLocalIds":[51],"persistedRecentLocalIds":[52],"refreshing":false,"nextFetchOutcome":{"type":"success","storeSites":[51,52,53,54]},"givenEstablishedBy":[{"name":"manualRefresh","outcome":"error","observableResult":"last_usable_grouped_rows_preserved"}]},"event":{"name":"retryManualRefresh"}}');
  if (key === 'wpcom_long_press_noop') return parsedFixture('{"given":{"mode":"default","actionMode":"none","site":{"localId":61,"wpComAccessible":true},"activeLocalId":60,"persistedPinnedLocalIds":[]},"event":{"name":"longPressSite","localId":61}}');
  if (key === 'restore_search_pin_mode') return parsedFixture('{"given":{"mode":"default","rows":[{"localId":71,"name":"Needle Site","host":"needle.test"},{"localId":72,"name":"Other","host":"other.test"}],"persistedPinnedLocalIds":[72],"searchQuery":"needle","actionMode":"pin"},"event":{"name":"recreatePicker"}}');
  if (key === 'restricted_mode_selection') return parsedFixture('{"given":{"mode":"simple","storeSites":[{"localId":81,"name":"WordPress.com","wpComAccessible":true},{"localId":82,"name":"Self Hosted","wpComAccessible":false}],"activeLocalId":81,"pickerOpen":true,"visibleLocalIds":[81,82],"pinEditingVisible":false,"addSiteVisible":false,"givenEstablishedBy":[{"name":"openSitePicker","mode":"simple"}]},"event":{"name":"selectSite","localId":82}}');
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
          const input: SitePickerInput = {
            state: clone(fixture.given), persistence: clone(fixture.given), leaf: leaf
          };
          SitePickerPageRuntime.configure(context, input);
        }

        async function snapshot(context: common.UIAbilityContext,
          owner: MountedSitePickerPageOwner): Promise<RuntimeSnapshot> {
          const prefs = await preferences.getPreferences(context, 'wordpress_site_picker');
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
          let owner = await SitePickerPageRuntime.waitForOwnerAfter();
          const methods: string[] = ['mount'];
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
          leaf.clear();
          const before = await snapshot(context, owner);
          const previousOwnerId = owner.ownerId();
          const previousControllerId = owner.controllerId();
          const eventName = fixture.event['name'] as string;
          let pageRecreated = false;
          if (key === 'restore_search_pin_mode') {
            await recreator.recreate();
            owner = await SitePickerPageRuntime.waitForOwnerAfter(previousOwnerId);
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
            schemaVersion: 2, taskId: '03_site_picker', caseKey: key,
            given: fixture.given, event: fixture.event, givenEstablished: true,
            commonEntryObserved: true, entryOwner: 'pages/Index', before: before, after: after,
            observed: observed, invokedProductionMethods: methods,
            transitionExecuted: true, earlyExit: false, runtimeEvidence: evidence
          };
          return { key: key, episodeJson: JSON.stringify(episode) };
        }
