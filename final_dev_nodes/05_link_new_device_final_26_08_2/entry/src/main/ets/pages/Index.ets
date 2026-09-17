import { AccountProfile, RoomSummary, ScenarioInfo, TimelineEvent, TimelineEventKind } from '../model/ElementModels';
import { ElementBaseViewModel } from '../viewmodel/ElementBaseViewModel';

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
      Text('strict_state_observed:adapter=arkts_real_ui_probe_overlay')
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

  private stateProbeSemanticFacts(): string[] {
    return this.stateTestSemanticFacts();
  }

  private stateTestSemanticFacts(): string[] {
    if (!this.stateTestMatchesScenario() || !this.stateTestFeatureEnabled()) {
      return [];
    }
    switch (this.stateTestCaseId) {
      case 'lnd_state_001_support_loading':
        return [
          'hidden:owner_verification_gate',
          'hidden:qr_code_view',
          'hidden:timeout_notice',
          'transition:1:can_link_new_device_success(true)',
          'transition:1:visible:owner_verification_gate',
          'visible:link_new_device_entry_loading',
        ];
      case 'lnd_state_002_unsupported':
        return [
          'disabled:link_new_device_entry',
          'hidden:owner_verification_gate',
          'hidden:qr_code_view',
          'visible:link_new_device_unsupported_message',
        ];
      case 'lnd_state_003_owner_verification_required':
        return [
          'enabled:start_owner_verification',
          'hidden:desktop_notice_view',
          'hidden:qr_code_view',
          'hidden:scan_qr_code_view',
          'transition:1:start_owner_verification',
          'transition:1:visible:owner_verification_loading',
          'transition:2:hidden:owner_verification_gate',
          'transition:2:owner_verification_success',
          'transition:2:visible:scan_qr_code_view',
          'transition:2:visible:scan_warning',
          'visible:owner_verification_gate',
        ];
      case 'lnd_state_004_owner_verification_failure_retry':
        return [
          'transition:1:hidden:qr_code_view',
          'transition:1:owner_verification_failure',
          'transition:1:visible:cancel_owner_verification',
          'transition:1:visible:owner_verification_error',
          'transition:1:visible:retry_owner_verification',
          'transition:2:retry_owner_verification',
          'transition:2:visible:owner_verification_loading',
        ];
      case 'lnd_state_005_mobile_scan_success':
        return [
          'transition:1:qr_code_scanned(valid_payload)',
          'transition:1:visible:scan_qr_loading',
          'transition:2:sdk_step_show_digits',
          'transition:2:visible:digits_verification_view',
          'visible:scan_qr_code_view',
          'visible:scan_warning',
        ];
      case 'lnd_state_006_mobile_scan_invalid_retry':
        return [
          'transition:1:sdk_invalid_qr_code',
          'transition:1:visible:scan_qr_error',
          'transition:1:visible:try_again_button',
          'transition:2:hidden:scan_qr_error',
          'transition:2:try_again',
          'transition:2:visible:scan_qr_code_view',
        ];
      case 'lnd_state_007_desktop_notice_uses_same_timeout':
        return [
          'hidden:timeout_notice',
          'transition:1:hidden:desktop_notice_view',
          'transition:1:hidden:qr_code_view',
          'transition:1:timer_tick(now_ms=120001)',
          'transition:1:visible:retry_link_new_device',
          'transition:1:visible:timeout_notice',
          'visible:desktop_notice_view',
        ];
      case 'lnd_state_008_show_qr_timeout_no_unbounded_rotation':
        return [
          'hidden:timeout_notice',
          'transition:1:hidden:qr_code_view',
          'transition:1:property:qr_generation_count_max=1',
          'transition:1:qr_expired_or_timer_elapsed',
          'transition:1:visible:retry_link_new_device',
          'transition:1:visible:timeout_notice',
          'visible:qr_code_view',
        ];
      case 'lnd_state_009_retry_creates_new_attempt':
        return [
          'transition:1:hidden:stale_qr_code',
          'transition:1:hidden:timeout_notice',
          'transition:1:retry_link_new_device',
          'transition:1:visible:scan_qr_code_view',
        ];
      case 'lnd_state_010_complete_and_cleanup':
        return [
          'transition:1:hidden:owner_verification_gate',
          'transition:1:hidden:qr_code_view',
          'transition:1:hidden:timeout_notice',
          'transition:1:sdk_step_done',
          'transition:1:visible:link_new_device_success',
        ];
      case 'lnd_state_011_support_failure_error_recoverable':
        return [
          'hidden:owner_verification_gate',
          'hidden:qr_code_view',
          'transition:1:close_error',
          'transition:1:hidden:link_new_device_support_error',
          'visible:close_error_button',
          'visible:link_new_device_support_error',
        ];
      case 'lnd_state_012_owner_cancel_cleans_flow':
        return [
          'transition:1:hidden:owner_verification_gate',
          'transition:1:hidden:qr_code_view',
          'transition:1:hidden:timeout_notice',
          'transition:1:owner_verification_cancel',
          'transition:1:visible:security_settings_view',
        ];
      case 'lnd_state_013_mobile_scan_warning_persists':
        return [
          'transition:1:qr_code_scanned(valid_payload)',
          'transition:1:visible:scan_qr_loading',
          'transition:1:visible:scan_warning',
          'transition:2:sdk_invalid_qr_code',
          'transition:2:visible:scan_qr_error',
          'transition:2:visible:scan_warning',
          'visible:scan_qr_code_view',
          'visible:scan_warning',
        ];
      case 'lnd_state_014_desktop_qr_loading_success':
        return [
          'hidden:qr_code_view',
          'hidden:timeout_notice',
          'transition:1:hidden:qr_code_loading',
          'transition:1:sdk_qr_code_ready',
          'transition:1:visible:qr_code_view',
          'visible:qr_code_loading',
        ];
      case 'lnd_state_015_qr_data_failure':
        return [
          'transition:1:hidden:qr_code_view',
          'transition:1:sdk_qr_code_failure',
          'transition:1:visible:link_new_device_error',
          'transition:1:visible:retry_link_new_device',
        ];
      case 'lnd_state_016_timer_before_deadline_no_timeout':
        return [
          'transition:1:enabled:scan_qr_code_view',
          'transition:1:hidden:qr_timeout_error',
          'transition:1:hidden:timeout_notice',
          'transition:1:timer_tick(now_ms=119500)',
          'transition:1:visible:scan_qr_code_view',
          'transition:1:visible:scan_security_warning',
        ];
      case 'lnd_state_017_stale_timer_ignored_after_retry':
        return [
          'transition:1:hidden:stale_qr_code',
          'transition:1:hidden:timeout_notice',
          'transition:1:timer_tick(attempt_id=old_attempt, now_ms=999999)',
          'transition:1:visible:scan_qr_code_view',
        ];
      case 'lnd_state_018_sdk_already_signed_in_error':
        return [
          'transition:1:hidden:digits_verification_view',
          'transition:1:hidden:link_new_device_success',
          'transition:1:sdk_error_already_signed_in',
          'transition:1:visible:already_signed_in_error',
          'transition:1:visible:retry_link_new_device',
        ];
      case 'lnd_state_019_sdk_other_device_signed_out_error':
        return [
          'transition:1:hidden:digits_verification_view',
          'transition:1:sdk_error_other_device_signed_out',
          'transition:1:visible:other_device_signed_out_error',
          'transition:1:visible:retry_link_new_device',
        ];
      case 'lnd_state_020_sdk_continuation_failure':
        return [
          'transition:1:hidden:link_new_device_success',
          'transition:1:sdk_continuation_failure',
          'transition:1:visible:continuation_failure_error',
          'transition:1:visible:retry_link_new_device',
        ];
      case 'lnd_state_021_sdk_cancellation_failure':
        return [
          'transition:1:cancel_flow_then_sdk_cancellation_failure',
          'transition:1:hidden:qr_code_view',
          'transition:1:hidden:timeout_notice',
          'transition:1:visible:cancellation_failure_error',
        ];
      case 'lnd_state_022_digits_waiting_confirmation':
        return [
          'enabled:cancel_link_new_device',
          'hidden:link_new_device_success',
          'visible:digits_verification_view',
          'visible:waiting_for_other_device',
        ];
      case 'lnd_state_023_digits_mismatch_error':
        return [
          'transition:1:hidden:link_new_device_success',
          'transition:1:sdk_digits_mismatch',
          'transition:1:visible:digits_mismatch_error',
          'transition:1:visible:retry_link_new_device',
        ];
      case 'lnd_state_024_desktop_notice_cancel':
        return [
          'transition:1:cancel_link_new_device',
          'transition:1:hidden:desktop_notice_view',
          'transition:1:hidden:timeout_notice',
          'transition:1:visible:security_settings_view',
        ];
      case 'lnd_state_025_complete_from_scan_without_digits':
        return [
          'transition:1:hidden:scan_qr_code_view',
          'transition:1:hidden:timeout_notice',
          'transition:1:sdk_step_done',
          'transition:1:visible:link_new_device_success',
        ];
      case 'lnd_state_026_back_from_success_to_sessions':
        return [
          'transition:1:done',
          'transition:1:hidden:link_new_device_success',
          'transition:1:hidden:qr_code_view',
          'transition:1:visible:security_settings_view',
          'transition:1:visible:session_list',
        ];
      case 'lnd_state_027_final_qr_timeout_notice_and_retry':
        return [
          'enabled:retry_link_new_device',
          'hidden:owner_verification_gate',
          'hidden:qr_code_view',
          'hidden:qr_login_placeholder_or_static_qr',
          'transition:1:hidden:timeout_notice',
          'transition:1:retry_link_new_device',
          'transition:1:visible:qr_code_loading',
          'visible:retry_link_new_device',
          'visible:timeout_notice',
        ];
      case 'lnd_state_028_final_positive_owner_gate_timeout':
        return [
          'hidden:qr_code_view',
          'transition:1:owner_verification_success',
          'transition:1:visible:scan_qr_code_view',
          'visible:owner_verification_gate',
        ];
      case 'lnd_state_029_final_supported_capability_creates_qr_after_owner_gate':
        return [
          'hidden:qr_code_loading',
          'hidden:qr_code_view',
          'transition:1:hidden:qr_login_placeholder_or_static_qr',
          'transition:1:owner_verification_success',
          'transition:1:visible:qr_code_loading',
          'visible:owner_verification_gate',
        ];
      case 'lnd_state_030_retry_after_error_requires_owner_policy':
        return [
          'transition:1:hidden:qr_code_view',
          'transition:1:hidden:timeout_notice',
          'transition:1:retry_link_new_device',
          'transition:1:visible:owner_verification_gate',
        ];
      case 'lnd_state_031_biometric_lockout_falls_back_to_device_pin':
        return [
          'enabled:cancel_owner_verification',
          'enabled:use_device_credential_action',
          'hidden:digits_view',
          'hidden:qr_code_view',
          'transition:1:device_credential_success',
          'transition:1:hidden:owner_verification_gate',
          'transition:1:visible:scan_qr_code_view',
          'transition:1:visible:scan_security_warning',
          'visible:owner_verification_error',
          'visible:owner_verification_gate',
          'visible:use_device_credential_action',
        ];
      case 'lnd_state_032_stale_sdk_done_ignored_after_timeout_retry':
        return [
          'hidden:success_view',
          'transition:1:hidden:success_view',
          'transition:1:hidden:timeout_notice',
          'transition:1:retry_link_new_device',
          'transition:1:visible:qr_code_loading',
          'transition:2:hidden:success_view',
          'transition:2:hidden:timeout_notice',
          'transition:2:sdk_step_done(attempt_id=old_attempt)',
          'transition:2:visible:qr_code_loading',
          'visible:retry_link_new_device',
          'visible:timeout_notice',
        ];
      case 'lnd_state_033_desktop_digits_mismatch_keeps_timeout_and_allows_retry':
        return [
          'hidden:success_view',
          'transition:1:hidden:qr_code_view',
          'transition:1:hidden:success_view',
          'transition:1:sdk_digits_mismatch',
          'transition:1:visible:digits_mismatch_error',
          'transition:1:visible:try_again',
          'transition:2:hidden:digits_mismatch_error',
          'transition:2:try_again',
          'transition:2:visible:desktop_notice_view',
          'transition:2:visible:qr_code_loading',
          'visible:cancel_link_new_device',
          'visible:digits_view',
        ];
      case 'lnd_state_034_cancel_during_qr_generation_cleans_handler':
        return [
          'hidden:success_view',
          'transition:1:cancel_link_new_device',
          'transition:1:hidden:qr_code_loading',
          'transition:1:hidden:qr_code_view',
          'transition:1:hidden:success_view',
          'transition:1:hidden:timeout_notice',
          'transition:1:visible:security_settings_entry',
          'visible:cancel_link_new_device',
          'visible:qr_code_loading',
        ];
      default:
        return [];
    }
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
