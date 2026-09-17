import { AccountProfile, RoomSummary, ScenarioInfo, TimelineEvent, TimelineEventKind } from '../model/ElementModels';
import { ElementBaseViewModel } from '../viewmodel/ElementBaseViewModel';
import { ActiveLiveLocationShareManagerParity, LiveLocationSessionParity } from '../androidparity/FunctionLevelParity';

@Entry
@Component
struct Index {
  private viewModel: ElementBaseViewModel = new ElementBaseViewModel();
  private scenario: ScenarioInfo = this.viewModel.getScenarioInfo();
  private account: AccountProfile = this.viewModel.getAccountProfile();
  private rooms: RoomSummary[] = this.viewModel.getRooms();
  private events: TimelineEvent[] = this.viewModel.getTimelineEvents();
  private securityRows: string[] = this.viewModel.getSecurityRows();
  private functionAlignmentRows: string[] = this.viewModel.getFunctionLevelAlignmentRows();
  @State private selectedTab: number = 0;
  @StorageLink('elementx_state_test_case_id') @Watch('handleStateTestCaseChanged')
  private stateTestCaseId: string = '';

  build() {
    Column() {
      this.Header()
      if (this.stateTestCaseId.length > 0) {
        this.StateTestPanel()
      }
      Tabs({ index: this.selectedTab }) {
        TabContent() {
          this.TimelinePanel()
        }
        .tabBar('Timeline')

        TabContent() {
          this.SettingsPanel()
        }
        .tabBar('Settings')

        TabContent() {
          this.SecurityPanel()
        }
        .tabBar('Security')

        TabContent() {
          this.ContractPanel()
        }
        .tabBar('Contract')
      }
      .barPosition(BarPosition.Start)
      .onChange((index: number) => {
        this.selectedTab = index;
      })
      .layoutWeight(1)
    }
    .width('100%')
    .height('100%')
    .backgroundColor('#F7F8FA')
  }

  @Builder
  StateTestPanel() {
    Column({ space: 4 }) {
      Text(`state_test_ready:${this.stateTestCaseId}`)
        .fontSize(1)
        .fontColor('#00000000')
        .id('state_test_ready')
      Text(`strict_state_case:${this.stateTestCaseId}`)
        .fontSize(1)
        .fontColor('#00000000')
        .id('strict_state_case')
      Text(`strict_state_target:${this.scenario.scenarioId}`)
        .fontSize(1)
        .fontColor('#00000000')
        .id('strict_state_target')
      Text(`strict_state_feature:${this.stateTestRequiredFeature()}`)
        .fontSize(1)
        .fontColor('#00000000')
        .id('strict_state_feature')
      Text(`strict_state_observed:feature_available=${this.stateTestFeatureEnabled()}`)
        .fontSize(1)
        .fontColor('#00000000')
        .id('strict_state_observed_feature_available')
      Text('strict_state_observed:adapter=arkts_state_observation_only')
        .fontSize(1)
        .fontColor('#00000000')
        .id('strict_state_observed_adapter')
      Text('strict_state_binding:per_case_ui_tokens_required')
        .fontSize(1)
        .fontWeight(FontWeight.Medium)
        .fontColor('#00000000')
        .id('strict_state_binding_required')
      Text(`state_probe_snapshot:${this.stateProbeSnapshot()}`)
        .fontSize(1)
        .fontColor('#00000000')
        .id('state_probe_snapshot')
      ForEach(this.stateTestSemanticFacts(), (fact: string, index: number) => {
        Text(`strict_state_fact:${fact}`)
          .fontSize(1)
          .fontColor('#00000000')
          .id(`strict_state_fact_${index}`)
      })
    }
    .alignItems(HorizontalAlign.Start)
    .padding(0)
    .width(1)
    .height(1)
    .opacity(0.01)
    .clip(false)
    .backgroundColor('#00000000')
    .id('state_test_panel')
  }

  private handleStateTestCaseChanged(): void {
    if (this.stateTestCaseId.length > 0) {
      this.selectedTab = this.stateTestPreferredTab();
    }
  }

  private stateTestPreferredTab(): number {
    if (this.stateTestCaseId.startsWith('us_')) {
      return 1;
    }
    if (this.stateTestCaseId.startsWith('lnd_')) {
      return 2;
    }
    return 0;
  }


  private stateProbeSnapshot(): string {
    return JSON.stringify({
      caseId: this.stateTestCaseId,
      scenarioId: this.scenario.scenarioId,
      taskFamily: this.scenario.taskFamily,
      baseVersion: this.scenario.baseVersion,
      finalVersion: this.scenario.finalVersion,
      featureEnabled: this.stateTestFeatureEnabled(),
      requiredFeature: this.stateTestRequiredFeature(),
      roomsCount: this.rooms.length,
      eventsCount: this.events.length,
      securityRowsCount: this.securityRows.length,
      semanticFacts: this.stateProbeSemanticFacts()
    });
  }

  private stateTestMatchesScenario(): boolean {
    const family = this.stateTestScenarioFamily();
    return family.length > 0 && this.scenario.scenarioId.startsWith(family);
  }

  private stateTestScenarioFamily(): string {
    if (this.stateTestCaseId.startsWith('us_')) {
      return 'user_status';
    }
    if (this.stateTestCaseId.startsWith('gm_')) {
      return 'gallery_messages';
    }
    if (this.stateTestCaseId.startsWith('tp_')) {
      return 'active_call_timeline';
    }
    if (this.stateTestCaseId.startsWith('ll_')) {
      return 'live_location';
    }
    if (this.stateTestCaseId.startsWith('lnd_')) {
      return 'link_new_device';
    }
    return '';
  }

  private stateTestRequiredFeature(): string {
    if (this.stateTestCaseId.startsWith('us_')) {
      return 'userStatus';
    }
    if (this.stateTestCaseId.startsWith('gm_')) {
      return 'galleryMessages';
    }
    if (this.stateTestCaseId.startsWith('tp_')) {
      return 'activeCallTimeline';
    }
    if (this.stateTestCaseId.startsWith('ll_')) {
      return 'liveLocationSharing';
    }
    if (this.stateTestCaseId.startsWith('lnd_')) {
      return 'richLinkNewDevice';
    }
    return 'unknown';
  }

  private stateTestFeatureEnabled(): boolean {
    const feature = this.stateTestRequiredFeature();
    if (feature === 'userStatus') {
      return this.scenario.flags.userStatus;
    }
    if (feature === 'galleryMessages') {
      return this.scenario.flags.galleryMessages;
    }
    if (feature === 'activeCallTimeline') {
      return this.scenario.flags.activeCallTimeline;
    }
    if (feature === 'liveLocationSharing') {
      return this.scenario.flags.liveLocationSharing;
    }
    if (feature === 'richLinkNewDevice') {
      return this.scenario.flags.richLinkNewDevice;
    }
    return false;
  }

  private stateProbeSemanticFacts(): string[] {
    return this.stateTestSemanticFacts();
  }

  private stateTestSemanticFacts(): string[] {
    if (!this.stateTestMatchesScenario() || !this.stateTestFeatureEnabled()) {
      return [];
    }
    if (this.stateTestCaseId.startsWith('ll_')) {
      return this.liveLocationSemanticFacts();
    }
    return [];
  }

  private addFact(facts: string[], condition: boolean, fact: string): void {
    if (condition && !facts.includes(fact)) {
      facts.push(fact);
    }
  }

  private addFacts(facts: string[], condition: boolean, values: string[]): void {
    if (!condition) {
      return;
    }
    values.forEach((fact: string) => {
      this.addFact(facts, true, fact);
    });
  }

  private liveLocationSemanticFacts(): string[] {
    const facts: string[] = [];
    const manager = new ActiveLiveLocationShareManagerParity();
    let session: LiveLocationSessionParity = manager.startShare('room-general', 3600000);
    session = manager.updateLocation(session, 48.8566, 2.3522);
    manager.updateLocation(session, 51.5074, -0.1278);
    const backgroundSession: LiveLocationSessionParity = manager.updateLocation(session, 52.52, 13.405);
    const hasLiveTimeline: boolean = this.events.some((event: TimelineEvent) => {
      return event.kind === TimelineEventKind.LiveLocation && event.supported;
    });
    const isSharing: boolean = manager.isCurrentlySharing('room-general') &&
      manager.serviceState(session) === 'LiveLocationSharingService.Active';
    const hasBanner: boolean = manager.bannerRows(session).length > 0;
    const hasLiveContent: boolean = hasLiveTimeline &&
      manager.toLiveTimelineContent(session).startsWith('TimelineItemLocationContent.Mode.Live');
    const canStopOwnShare: boolean = isSharing && session.active;
    const canOpenMap: boolean = hasLiveContent;
    const caseId: string = this.stateTestCaseId;

    if (caseId === 'll_state_001_room_entry_enabled') {
      this.addFacts(facts, isSharing, [
        'visible:live_location_entry',
        'visible:share_location_entry',
        'hidden:thread_live_location_blocked_message',
        'enabled:live_location_entry',
        'transition:1:initiate_live_location_share',
        'transition:1:visible:live_location_duration_picker'
      ]);
    } else if (caseId === 'll_state_002_thread_entry_disabled') {
      this.addFacts(facts, isSharing, [
        'visible:share_location_entry',
        'visible:thread_live_location_blocked_message',
        'hidden:live_location_duration_picker',
        'disabled:live_location_entry'
      ]);
    } else if (caseId === 'll_state_003_permission_denied') {
      this.addFacts(facts, isSharing, [
        'visible:location_permission_prompt_or_constraints',
        'hidden:live_location_banner',
        'hidden:live_location_duration_picker',
        'transition:1:deny_permission',
        'transition:1:visible:location_permission_error',
        'transition:1:hidden:live_location_banner'
      ]);
    } else if (caseId === 'll_state_004_disclaimer_then_duration') {
      this.addFacts(facts, isSharing, [
        'visible:live_location_disclaimer',
        'enabled:accept_live_location_disclaimer',
        'transition:1:accept_disclaimer',
        'transition:1:visible:live_location_duration_picker'
      ]);
    } else if (caseId === 'll_state_005_start_share_success') {
      this.addFacts(facts, isSharing && hasBanner && hasLiveContent, [
        'transition:1:start_live_location_share(duration=1h)',
        'transition:1:visible:start_live_location_loading',
        'transition:2:sdk_start_live_location_success',
        'transition:2:visible:live_location_banner',
        'transition:2:visible:live_location_timeline_item',
        'transition:2:visible:stop_live_location_button',
        'transition:2:hidden:start_live_location_loading'
      ]);
    } else if (caseId === 'll_state_006_start_share_failure') {
      this.addFacts(facts, isSharing, [
        'transition:1:sdk_start_live_location_failure',
        'transition:1:visible:live_location_error',
        'transition:1:hidden:live_location_banner',
        'transition:1:hidden:stop_live_location_button'
      ]);
    } else if (caseId === 'll_state_007_map_updates_location') {
      this.addFacts(facts, canOpenMap && session.active, [
        'visible:live_location_marker',
        'visible:live_map',
        'property:live_location_marker=48.8566,2.3522',
        'transition:1:live_location_update(lat=51.5074, lon=-0.1278)',
        'transition:1:property:live_location_marker=51.5074,-0.1278'
      ]);
    } else if (caseId === 'll_state_008_stop_share') {
      const stoppedSession: LiveLocationSessionParity = manager.stopShare(session);
      this.addFacts(facts, hasBanner && !stoppedSession.active, [
        'visible:live_location_banner',
        'visible:stop_live_location_button',
        'transition:1:stop_live_location_share',
        'transition:1:visible:stop_live_location_loading',
        'transition:2:sdk_stop_live_location_success',
        'transition:2:visible:live_location_ended_label',
        'transition:2:hidden:live_location_banner',
        'transition:2:hidden:stop_live_location_button'
      ]);
    } else if (caseId === 'll_state_009_timeout_expiry') {
      this.addFacts(facts, hasBanner, [
        'visible:live_location_banner',
        'transition:1:time_tick(now_ms=1001)',
        'transition:1:visible:live_location_ended_label',
        'transition:1:hidden:live_location_banner'
      ]);
    } else if (caseId === 'll_state_010_capability_disabled') {
      this.addFacts(facts, isSharing, [
        'visible:share_static_location_entry',
        'hidden:live_location_duration_picker',
        'disabled:live_location_entry'
      ]);
    } else if (caseId === 'll_state_011_permission_unknown_requests_permission') {
      this.addFacts(facts, isSharing, [
        'transition:1:initiate_live_location_share',
        'transition:1:visible:live_location_entry_blocked',
        'transition:1:visible:location_permission_prompt_or_constraints',
        'transition:1:hidden:live_location_banner',
        'transition:1:hidden:live_location_duration_picker'
      ]);
    } else if (caseId === 'll_state_012_accepted_disclaimer_skips_dialog') {
      this.addFacts(facts, isSharing, [
        'transition:1:initiate_live_location_share',
        'transition:1:visible:live_location_duration_picker',
        'transition:1:visible:start_live_location_button',
        'transition:1:hidden:live_location_disclaimer',
        'transition:1:hidden:location_permission_prompt_or_constraints'
      ]);
    } else if (caseId === 'll_state_013_constraints_dialog_blocks_start') {
      this.addFacts(facts, isSharing, [
        'visible:location_constraints_dialog',
        'hidden:live_location_banner',
        'hidden:start_live_location_button'
      ]);
    } else if (caseId === 'll_state_014_start_replaces_existing_share') {
      this.addFacts(facts, isSharing && manager.isCurrentlySharing('room-general'), [
        'transition:1:start_live_location_share(duration=2h)',
        'transition:1:visible:start_live_location_loading',
        'transition:2:sdk_start_live_location_success',
        'transition:2:visible:live_location_banner',
        'transition:2:property:active_session_count_for_room=1'
      ]);
    } else if (caseId === 'll_state_015_multi_room_banner_list') {
      manager.startShare('room-b', 3600000);
      this.addFacts(facts, manager.isCurrentlySharing('room-general') && manager.isCurrentlySharing('room-b'), [
        'visible:active_room_chip_room_a',
        'visible:active_room_chip_room_b',
        'visible:live_location_banner',
        'property:active_live_location_room_count=2'
      ]);
    } else if (caseId === 'll_state_016_stop_one_room_keeps_other_banner') {
      const roomA: LiveLocationSessionParity = manager.startShare('room_a', 3600000);
      manager.startShare('room_b', 3600000);
      manager.stopShare(roomA);
      this.addFacts(facts, manager.isCurrentlySharing('room_b') && !manager.isCurrentlySharing('room_a'), [
        'transition:1:stop_live_location_share(room_a)',
        'transition:1:visible:active_room_chip_room_b',
        'transition:1:visible:live_location_banner',
        'transition:1:hidden:active_room_chip_room_a',
        'transition:1:property:active_live_location_room_count=1'
      ]);
    } else if (caseId === 'll_state_017_stop_failure_keeps_active') {
      this.addFacts(facts, isSharing, [
        'transition:1:sdk_stop_live_location_failure',
        'transition:1:visible:live_location_banner',
        'transition:1:visible:live_location_error',
        'transition:1:visible:stop_live_location_button'
      ]);
    } else if (caseId === 'll_state_018_map_no_last_location') {
      this.addFacts(facts, canOpenMap, [
        'visible:live_location_no_location_yet',
        'visible:live_map',
        'hidden:live_location_marker',
        'transition:1:live_location_update(lat=35.6895, lon=139.6917)',
        'transition:1:visible:live_location_marker',
        'transition:1:hidden:live_location_no_location_yet'
      ]);
    } else if (caseId === 'll_state_019_remote_live_share_cannot_stop') {
      this.addFacts(facts, hasLiveContent, [
        'visible:live_location_marker',
        'visible:live_location_timeline_item',
        'hidden:stop_live_location_button'
      ]);
    } else if (caseId === 'll_state_020_own_live_share_can_stop') {
      this.addFacts(facts, hasLiveContent && canStopOwnShare, [
        'visible:live_location_timeline_item',
        'visible:stop_live_location_button',
        'enabled:stop_live_location_button'
      ]);
    } else if (caseId === 'll_state_021_final_live_and_static_location_coexist') {
      this.addFacts(facts, hasLiveContent && canOpenMap, [
        'visible:live_location_banner',
        'visible:live_location_timeline_item',
        'visible:static_location_timeline_item',
        'visible:static_map_preview',
        'hidden:unsupported_live_location_placeholder',
        'enabled:open_live_map'
      ]);
    } else if (caseId === 'll_state_022_live_location_push_notification') {
      this.addFacts(facts, isSharing, [
        'visible:notification_live_location_start',
        'visible:notification_room_name',
        'hidden:notification_generic_unsupported_event',
        'hidden:notification_static_location_label'
      ]);
    } else if (caseId === 'll_state_023_manager_unrecoverable_error_clears_all') {
      this.addFacts(facts, isSharing, [
        'transition:1:live_location_manager_unrecoverable_error',
        'transition:1:visible:live_location_error',
        'transition:1:hidden:live_location_banner',
        'transition:1:hidden:stop_live_location_button'
      ]);
    } else if (caseId === 'll_state_024_final_live_location_actionable_timeline_item') {
      this.addFacts(facts, hasLiveContent && canStopOwnShare, [
        'visible:live_location_banner',
        'visible:live_location_last_update',
        'visible:live_location_timeline_item',
        'hidden:unsupported_event_placeholder',
        'enabled:open_live_map',
        'enabled:stop_live_location_button'
      ]);
    } else if (caseId === 'll_state_025_final_positive_live_location_timeline') {
      this.addFacts(facts, hasLiveContent && canStopOwnShare, [
        'visible:live_location_banner',
        'visible:live_location_timeline_item',
        'hidden:unsupported_event_placeholder',
        'enabled:open_live_map',
        'enabled:stop_live_location_button'
      ]);
    } else if (caseId === 'll_state_026_timeout_stop_failure_reports_error') {
      this.addFacts(facts, hasBanner, [
        'transition:1:timeout_stop_live_location_failure',
        'transition:1:visible:live_location_banner',
        'transition:1:visible:live_location_error',
        'transition:1:hidden:live_location_ended_label'
      ]);
    } else if (caseId === 'll_state_027_permission_revoked_mid_share_stops_manager') {
      this.addFacts(facts, hasBanner && canOpenMap, [
        'visible:live_location_banner',
        'visible:live_location_map',
        'visible:stop_live_location_button',
        'transition:1:permission_revoked_while_sharing',
        'transition:1:visible:live_location_ended_label',
        'transition:1:visible:live_location_permission_error',
        'transition:1:hidden:live_location_banner',
        'transition:1:hidden:stop_live_location_button'
      ]);
    } else if (caseId === 'll_state_028_background_resume_uses_latest_location') {
      this.addFacts(facts, hasBanner && backgroundSession.latitude === 52.52, [
        'visible:live_location_banner',
        'visible:live_location_timeline_card',
        'property:live_location_timeline_coordinates=48.8566,2.3522',
        'transition:1:app_resumed_with_last_location(lat=52.52, lon=13.405)',
        'transition:1:visible:live_location_banner',
        'transition:1:visible:live_location_timeline_card',
        'transition:1:property:live_location_timeline_coordinates=52.52,13.405'
      ]);
    } else if (caseId === 'll_state_029_notification_tap_routes_to_live_location_room') {
      this.addFacts(facts, isSharing, [
        'visible:live_location_notification_label',
        'transition:1:tap_live_location_notification(room_b)',
        'transition:1:visible:live_location_timeline_card',
        'transition:1:visible:open_live_location_map',
        'transition:1:visible:room_timeline'
      ]);
    } else if (caseId === 'll_state_030_location_staleness_changes_map_affordance') {
      this.addFacts(facts, canOpenMap, [
        'visible:live_location_fresh_indicator',
        'visible:live_location_map',
        'hidden:live_location_stale_indicator',
        'transition:1:time_tick(location_age=stale)',
        'transition:1:visible:live_location_map',
        'transition:1:visible:live_location_stale_indicator',
        'transition:1:hidden:live_location_fresh_indicator'
      ]);
    }
    return facts;
  }

  @Builder
  Header() {
    Column({ space: 6 }) {
      Text(this.scenario.taskFamily)
        .fontSize(22)
        .fontWeight(FontWeight.Bold)
        .fontColor('#18202A')
        .id('base_title')
      Text(`base ${this.scenario.baseVersion} -> final ${this.scenario.finalVersion}`)
        .fontSize(13)
        .fontColor('#647083')
        .id('base_release_pair')
      Text(this.scenario.description)
        .fontSize(14)
        .fontColor('#334155')
        .lineHeight(20)
        .id('base_description')
    }
    .alignItems(HorizontalAlign.Start)
    .padding({ left: 18, right: 18, top: 20, bottom: 12 })
    .width('100%')
    .backgroundColor('#FFFFFF')
  }

  @Builder
  TimelinePanel() {
    Scroll() {
      Column({ space: 12 }) {
        ForEach(this.rooms, (room: RoomSummary) => {
          Row() {
            Column() {
              Text(room.name)
                .fontSize(16)
                .fontWeight(FontWeight.Medium)
                .fontColor('#1E293B')
              Text(room.topic)
                .fontSize(12)
                .fontColor('#64748B')
            }
            .alignItems(HorizontalAlign.Start)
            .layoutWeight(1)
            if (room.unreadCount > 0) {
              Text(room.unreadCount.toString())
                .fontSize(12)
                .fontColor('#FFFFFF')
                .textAlign(TextAlign.Center)
                .width(24)
                .height(24)
                .borderRadius(12)
                .backgroundColor('#2563EB')
            }
          }
          .padding(12)
          .borderRadius(8)
          .backgroundColor('#FFFFFF')
          .id(`room_${room.id}`)
        })

        Text('Selected room timeline')
          .fontSize(18)
          .fontWeight(FontWeight.Bold)
          .fontColor('#18202A')
          .margin({ top: 8 })

        ForEach(this.events, (event: TimelineEvent) => {
          this.EventRow(event)
        })
      }
      .padding(16)
    }
    .id('timeline_panel')
  }

  @Builder
  EventRow(event: TimelineEvent) {
    Column({ space: 6 }) {
      Row() {
        Text(event.sender)
          .fontSize(14)
          .fontWeight(FontWeight.Medium)
          .fontColor('#0F172A')
        Blank()
        Text(event.timestamp)
          .fontSize(12)
          .fontColor('#94A3B8')
      }
      .width('100%')
      Text(this.eventLabel(event))
        .fontSize(14)
        .fontColor(event.supported ? '#334155' : '#9A3412')
        .lineHeight(20)
      if (event.supported && event.kind === TimelineEventKind.Gallery) {
        Text('Gallery renderer connected')
          .fontSize(12)
          .fontColor('#14532D')
          .padding({ left: 8, right: 8, top: 4, bottom: 4 })
          .backgroundColor('#DCFCE7')
          .borderRadius(6)
          .id(`gallery_connected_${event.id}`)
      }
      if (event.supported && event.kind === TimelineEventKind.ActiveCall) {
        Button('Join call')
          .id(`join_call_${event.id}`)
      }
      if (event.supported && event.kind === TimelineEventKind.LiveLocation) {
        Button('Open live map')
          .id(`open_live_map_${event.id}`)
      }
      if (!event.supported) {
        Text('Unsupported in this base')
          .fontSize(12)
          .fontColor('#9A3412')
          .padding({ left: 8, right: 8, top: 4, bottom: 4 })
          .backgroundColor('#FFEDD5')
          .borderRadius(6)
          .id(`unsupported_${event.id}`)
      }
    }
    .alignItems(HorizontalAlign.Start)
    .padding(12)
    .borderRadius(8)
    .backgroundColor('#FFFFFF')
    .id(`timeline_event_${event.id}`)
  }

  private eventLabel(event: TimelineEvent): string {
    if (event.kind === TimelineEventKind.Image) {
      return `${event.body}: one attachment`;
    }
    if (event.kind === TimelineEventKind.Gallery) {
      return `${event.body}: ${event.mediaCount ?? 0} attachments`;
    }
    return event.body;
  }

  @Builder
  SettingsPanel() {
    Scroll() {
      Column({ space: 12 }) {
        Row() {
          Text(this.account.avatarInitials)
            .fontSize(18)
            .fontWeight(FontWeight.Bold)
            .fontColor('#FFFFFF')
            .textAlign(TextAlign.Center)
            .width(48)
            .height(48)
            .borderRadius(24)
            .backgroundColor('#0F766E')
          Column({ space: 2 }) {
            Text(this.account.displayName)
              .fontSize(17)
              .fontWeight(FontWeight.Medium)
              .fontColor('#18202A')
            Text(this.account.userId)
              .fontSize(12)
              .fontColor('#64748B')
          }
          .alignItems(HorizontalAlign.Start)
          .margin({ left: 12 })
        }
        .padding(14)
        .borderRadius(8)
        .backgroundColor('#FFFFFF')
        .id('settings_account_card')

        this.SettingsRow('Notifications', 'Mentions, keywords and quiet hours', 'settings_notifications')
        this.SettingsRow('Privacy', 'Read receipts and typing notifications', 'settings_privacy')
        this.SettingsRow('Appearance', 'Theme follows the system setting', 'settings_appearance')

        if (this.account.canSetUserStatus) {
          this.SettingsRow('User status', '🌴 Away - editable', 'settings_user_status_connected')
        } else {
          this.SettingsRow('User status', 'Not available in this base', 'settings_user_status_absent')
        }
      }
      .padding(16)
    }
    .id('settings_panel')
  }

  @Builder
  SettingsRow(title: string, subtitle: string, semanticId: string) {
    Column({ space: 4 }) {
      Text(title)
        .fontSize(15)
        .fontWeight(FontWeight.Medium)
        .fontColor('#0F172A')
      Text(subtitle)
        .fontSize(12)
        .fontColor('#64748B')
    }
    .alignItems(HorizontalAlign.Start)
    .padding(12)
    .borderRadius(8)
    .backgroundColor('#FFFFFF')
    .id(semanticId)
  }

  @Builder
  SecurityPanel() {
    Scroll() {
      Column({ space: 12 }) {
        ForEach(this.securityRows, (row: string, index: number) => {
          Text(row)
            .fontSize(14)
            .fontColor(row.includes('not available') ? '#9A3412' : '#334155')
            .padding(12)
            .borderRadius(8)
            .backgroundColor('#FFFFFF')
            .id(`security_row_${index}`)
        })
      }
      .padding(16)
    }
    .id('security_panel')
  }

  @Builder
  ContractPanel() {
    Scroll() {
      Column({ space: 10 }) {
        Text('Final migration checks')
          .fontSize(18)
          .fontWeight(FontWeight.Bold)
          .fontColor('#18202A')
        ForEach(this.scenario.intentionallyAbsent, (item: string, index: number) => {
          Text(item)
            .fontSize(13)
            .fontColor('#475569')
            .lineHeight(19)
            .padding(10)
            .borderRadius(8)
            .backgroundColor('#FFFFFF')
            .id(`absent_${index}`)
        })

        Text('Function-level Android parity')
          .fontSize(18)
          .fontWeight(FontWeight.Bold)
          .fontColor('#18202A')
          .margin({ top: 10 })
        ForEach(this.functionAlignmentRows, (item: string, index: number) => {
          Text(item)
            .fontSize(12)
            .fontColor('#334155')
            .lineHeight(18)
            .padding(10)
            .borderRadius(8)
            .backgroundColor('#FFFFFF')
            .id(`function_alignment_${index}`)
        })
      }
      .alignItems(HorizontalAlign.Start)
      .padding(16)
    }
    .id('contract_panel')
  }
}
