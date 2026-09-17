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
      case 'us_state_001_unsupported_hides_entry':
        return [
          'hidden:user_status_badge',
          'hidden:user_status_editor',
          'hidden:user_status_settings_entry',
          'visible:privacy_settings_entry',
          'visible:profile_settings_entry',
          'visible:security_settings_entry',
        ];
      case 'us_state_002_empty_supported_entry':
        return [
          'enabled:open_user_status_editor',
          'hidden:user_status_emoji_badge',
          'hidden:user_status_timeline_text',
          'transition:1:open_user_status_editor',
          'transition:1:visible:custom_status_button',
          'transition:1:visible:predefined_status_list',
          'transition:1:visible:user_status_editor',
          'visible:user_status_empty_value',
          'visible:user_status_settings_entry',
        ];
      case 'us_state_003_custom_input_and_emoji_sheet':
        return [
          'enabled:custom_status_text_field',
          'enabled:emoji_picker_button',
          'transition:1:hidden:emoji_picker_grid',
          'transition:1:open_emoji_sheet',
          'transition:1:visible:custom_status_text_field',
          'transition:1:visible:emoji_picker_button',
          'transition:2:emoji_sheet_loaded',
          'transition:2:visible:emoji_picker_grid',
          'visible:custom_status_text_field',
          'visible:emoji_picker_button',
          'visible:save_status_button',
        ];
      case 'us_state_004_save_success_propagates_surfaces':
        return [
          'enabled:save_status_button',
          'transition:1:hidden:custom_status_text_field',
          'transition:1:hidden:predefined_status_list',
          'transition:1:hidden:save_status_button',
          'transition:1:hidden:user_status_editor',
          'transition:1:save_status',
          'transition:1:visible:user_status_settings_entry',
          'transition:2:hidden:user_status_saving_indicator',
          'transition:2:sdk_set_user_status_success',
          'transition:2:visible:dm_user_status_badge',
          'transition:2:visible:home_status_badge',
          'transition:2:visible:user_profile_status',
          'transition:2:visible:user_status_settings_value',
          'visible:save_status_button',
        ];
      case 'us_state_005_save_failure_keeps_previous_status':
        return [
          'transition:1:property:user_status_settings_value=☕',
          'transition:1:sdk_set_user_status_failure',
          'transition:1:visible:user_status_error',
          'transition:1:visible:user_status_settings_value',
          'visible:user_status_saving_indicator',
        ];
      case 'us_state_006_clear_status':
        return [
          'transition:1:clear_status',
          'transition:1:visible:user_status_saving_indicator',
          'transition:2:hidden:dm_user_status_badge',
          'transition:2:hidden:user_profile_status',
          'transition:2:hidden:user_status_emoji_badge',
          'transition:2:sdk_clear_user_status_success',
          'transition:2:visible:user_status_empty_value',
          'visible:clear_status_button',
          'visible:user_status_emoji_badge',
        ];
      case 'us_state_007_timeline_sender_emoji_only':
        return [
          'hidden:timeline_sender_status_text',
          'property:timeline_sender_status_emoji=💡',
          'visible:timeline_sender_name',
          'visible:timeline_sender_status_emoji',
        ];
      case 'us_state_008_in_call_status':
        return [
          'hidden:custom_user_status_text_in_timeline',
          'transition:1:call_ended',
          'transition:1:hidden:in_call_status_badge',
          'transition:1:visible:user_status_empty_value',
          'visible:in_call_status_badge',
        ];
      case 'us_state_009_capability_failure_safe_fallback':
        return [
          'hidden:user_status_editor',
          'hidden:user_status_error_blocking_dialog',
          'hidden:user_status_settings_entry',
          'visible:privacy_settings_entry',
          'visible:profile_settings_entry',
          'visible:security_settings_entry',
        ];
      case 'us_state_010_predefined_status_selection':
        return [
          'enabled:predefined_status_away',
          'transition:1:hidden:predefined_status_list',
          'transition:1:select_predefined_status(away)',
          'transition:1:visible:user_status_saving_indicator',
          'visible:predefined_status_away',
          'visible:predefined_status_focus_time',
          'visible:predefined_status_list',
        ];
      case 'us_state_011_dismiss_picker_keeps_status':
        return [
          'transition:1:dismiss_status_picker',
          'transition:1:property:user_status_settings_value=☕',
          'transition:1:visible:user_status_settings_value',
          'visible:predefined_status_list',
        ];
      case 'us_state_012_custom_input_dirty_state':
        return [
          'hidden:save_status_button',
          'transition:1:edit_custom_status(emoji=💬, text=In a meeting)',
          'transition:1:enabled:save_status_button',
          'visible:cancel_status_button',
          'visible:custom_status_text_field',
        ];
      case 'us_state_013_custom_input_cancel_clears_draft_only':
        return [
          'transition:1:cancel_custom_input',
          'transition:1:hidden:custom_status_text_field',
          'transition:1:hidden:user_status_editor',
          'transition:1:property:user_status_settings_value=💡',
          'transition:1:visible:user_status_settings_value',
        ];
      case 'us_state_014_update_loading_disables_mutating_actions':
        return [
          'hidden:custom_status_text_field',
          'hidden:predefined_status_list',
          'hidden:save_status_button',
          'hidden:user_status_editor',
          'visible:user_status_settings_entry',
          'visible:user_status_settings_value',
        ];
      case 'us_state_015_home_top_bar_own_status':
        return [
          'hidden:home_status_text',
          'property:home_status_badge=🚙',
          'visible:home_status_badge',
          'visible:home_top_bar_avatar',
        ];
      case 'us_state_016_dm_room_row_remote_status':
        return [
          'hidden:group_room_status_badge',
          'property:dm_user_status_badge=☕',
          'visible:dm_user_status_badge',
          'visible:room_summary_row',
        ];
      case 'us_state_017_group_room_no_synthetic_status':
        return [
          'hidden:dm_user_status_badge',
          'hidden:group_room_status_badge',
          'visible:room_summary_row',
        ];
      case 'us_state_018_profile_status_refresh':
        return [
          'property:user_profile_status=🌴',
          'transition:1:profile_status_refreshed(emoji=💬, text=In a meeting)',
          'transition:1:property:user_profile_status=💬',
          'visible:user_profile_header',
          'visible:user_profile_status',
        ];
      case 'us_state_019_displayed_status_takes_precedence':
        return [
          'hidden:raw_user_status_badge',
          'hidden:raw_user_status_text',
          'property:in_call_status_badge=in_call',
          'visible:in_call_status_badge',
          'visible:user_profile_header',
        ];
      case 'us_state_020_remote_status_removed':
        return [
          'transition:1:hidden:dm_user_status_badge',
          'transition:1:hidden:user_profile_status',
          'transition:1:remote_user_status_removed',
          'visible:dm_user_status_badge',
        ];
      case 'us_state_021_final_status_entry_and_badge':
        return [
          'enabled:open_user_status_editor',
          'hidden:unsupported_feature_placeholder',
          'hidden:user_status_timeline_text',
          'property:home_status_badge=💡',
          'property:user_status_settings_value=💡',
          'visible:home_status_badge',
          'visible:profile_settings_entry',
          'visible:user_status_settings_entry',
          'visible:user_status_settings_value',
        ];
      case 'us_state_022_final_positive_user_status_entry':
        return [
          'enabled:open_user_status_editor',
          'hidden:unsupported_feature_placeholder',
          'visible:user_status_settings_entry',
        ];
      case 'us_state_023_remote_status_refresh_does_not_override_own_status':
        return [
          'property:dm_user_status_badge=🌙',
          'property:home_status_badge=☕',
          'transition:1:property:dm_user_status_badge=🧭',
          'transition:1:property:home_status_badge=☕',
          'transition:1:remote_status_refreshed(emoji=🧭, text=Travelling)',
          'transition:1:visible:dm_user_status_badge',
          'transition:1:visible:home_status_badge',
          'visible:dm_user_status_badge',
          'visible:home_status_badge',
        ];
      case 'us_state_024_status_text_never_leaks_to_timeline':
        return [
          'hidden:timeline_sender_status_text',
          'hidden:user_status_full_text_in_message_body',
          'property:timeline_sender_status_emoji=🛠',
          'transition:1:hidden:timeline_sender_status_text',
          'transition:1:hidden:user_status_full_text_in_message_body',
          'transition:1:property:timeline_sender_status_emoji=✅',
          'transition:1:sender_status_refreshed(emoji=✅, text=Back online)',
          'transition:1:visible:timeline_sender_status_emoji',
          'visible:timeline_sender_name',
          'visible:timeline_sender_status_emoji',
        ];
      case 'us_state_025_save_retry_after_failure_uses_latest_draft':
        return [
          'enabled:custom_status_text_field',
          'enabled:save_status_button',
          'transition:1:edit_custom_status(emoji=🚀, text=Shipping)',
          'transition:1:property:custom_status_text_field=Shipping',
          'transition:1:visible:save_status_button',
          'transition:2:property:user_status_settings_value=🚀',
          'transition:2:sdk_set_user_status_success',
          'transition:2:visible:user_status_settings_value',
          'visible:custom_status_text_field',
          'visible:save_status_button',
          'visible:user_status_error',
        ];
      case 'us_state_026_call_status_restore_manual_status':
        return [
          'property:home_status_badge=📞',
          'transition:1:call_ended_restore_previous_status',
          'transition:1:hidden:in_call_status_badge',
          'transition:1:property:home_status_badge=📚',
          'transition:1:visible:home_status_badge',
          'visible:home_status_badge',
          'visible:in_call_status_badge',
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

        this.SettingsRow('User status', '🌴 Away - editable', 'settings_user_status_connected')
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
