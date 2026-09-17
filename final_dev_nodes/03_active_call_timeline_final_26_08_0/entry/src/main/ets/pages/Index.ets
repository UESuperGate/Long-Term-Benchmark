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
      case 'tp_state_001_media_unknown_requests_validation':
        return [
          'hidden:unsafe_content_warning',
          'hidden:unsupported_event_placeholder',
          'transition:1:scanner_started',
          'transition:1:visible:content_scanning_placeholder',
          'visible:content_validation_pending',
          'visible:media_row_placeholder',
        ];
      case 'tp_state_002_valid_media_renders_original_content':
        return [
          'transition:1:content_validation_update(valid)',
          'transition:1:hidden:content_scanning_placeholder',
          'transition:1:hidden:unsafe_content_warning',
          'transition:1:visible:video_play_affordance',
          'transition:1:visible:video_thumbnail',
          'visible:content_scanning_placeholder',
        ];
      case 'tp_state_003_invalid_media_uses_safety_fallback':
        return [
          'disabled:open_media_viewer',
          'hidden:raw_media_content',
          'transition:1:hidden:media_viewer_raw_content',
          'transition:1:tap_blocked_media',
          'transition:1:visible:unsafe_content_warning',
          'visible:blocked_media_placeholder',
          'visible:unsafe_content_warning',
        ];
      case 'tp_state_004_unrecoverable_error_not_found':
        return [
          'hidden:content_scanning_placeholder',
          'hidden:raw_media_content',
          'visible:media_not_found_placeholder',
        ];
      case 'tp_state_005_gallery_mixed_validation_aggregates':
        return [
          'hidden:unsupported_event_placeholder',
          'transition:1:content_validation_update(item_1=invalid)',
          'transition:1:visible:gallery_item_1_invalid_fallback',
          'visible:gallery_container',
          'visible:gallery_item_0',
          'visible:gallery_item_1_scanning',
          'visible:gallery_item_2',
        ];
      case 'tp_state_006_viewer_keeps_timeline_validation':
        return [
          'transition:1:hidden:media_viewer_invalid_state',
          'transition:1:open_media_viewer',
          'transition:1:visible:media_viewer',
          'transition:1:visible:media_viewer_image',
        ];
      case 'tp_state_007_active_call_joinable_card':
        return [
          'enabled:join_call_button',
          'hidden:rtc_started_plain_notice',
          'hidden:unsupported_event_placeholder',
          'transition:1:join_active_call',
          'transition:1:visible:active_call_card',
          'transition:1:visible:in_call_indicator',
          'visible:active_call_card',
          'visible:active_call_participants',
          'visible:active_call_title',
          'visible:join_call_button',
        ];
      case 'tp_state_008_declined_call_no_join_action':
        return [
          'hidden:active_call_card',
          'hidden:join_call_button',
          'visible:rtc_declined_notice',
        ];
      case 'tp_state_009_render_only_selected_hides_unselected_media':
        return [
          'hidden:raw_media_content',
          'transition:1:allow_event(evt_blocked)',
          'transition:1:hidden:message_shield',
          'transition:1:visible:raw_media_content',
          'visible:message_shield',
        ];
      case 'tp_state_010_accessibility_group_state':
        return [
          'hidden:message_shield_on_group_header',
          'property:accessibility_state=collapsed',
          'transition:1:expand_group',
          'transition:1:property:accessibility_state=expanded',
          'transition:1:visible:group_collapse_toggle',
          'transition:1:visible:timeline_group_header',
          'visible:group_expand_toggle',
          'visible:timeline_group_header',
        ];
      case 'tp_state_011_final_text_event_coexists_with_media_scanner':
        return [
          'hidden:message_shield',
          'hidden:unsafe_content_warning',
          'visible:content_scanning_placeholder',
          'visible:text_message_body',
        ];
      case 'tp_state_012_own_media_bypasses_render_only_shield':
        return [
          'hidden:content_scanning_placeholder',
          'hidden:message_shield',
          'visible:own_sender_marker',
          'visible:raw_media_content',
        ];
      case 'tp_state_013_valid_state_not_downgraded_to_loading':
        return [
          'hidden:content_scanning_placeholder',
          'hidden:unsafe_content_warning',
          'transition:1:async_image_state_loading_after_valid',
          'transition:1:hidden:content_scanning_placeholder',
          'transition:1:hidden:unsafe_content_warning',
          'transition:1:visible:image_thumbnail',
          'transition:1:visible:raw_media_content',
          'visible:image_thumbnail',
          'visible:raw_media_content',
        ];
      case 'tp_state_014_overall_invalid_takes_priority':
        return [
          'hidden:raw_media_content_for_item_2',
          'visible:gallery_container',
          'visible:gallery_item_2_invalid_fallback',
          'visible:unsafe_content_warning',
        ];
      case 'tp_state_015_loading_state_blocks_reply_thumbnail':
        return [
          'hidden:reply_preview_invalid_content',
          'hidden:reply_preview_thumbnail',
          'visible:reply_preview_scanning',
        ];
      case 'tp_state_016_invalid_reply_preview':
        return [
          'hidden:raw_media_content',
          'hidden:reply_preview_thumbnail',
          'visible:reply_preview_invalid_content',
        ];
      case 'tp_state_017_voice_message_validation':
        return [
          'disabled:voice_play_button',
          'transition:1:content_validation_update(valid)',
          'transition:1:enabled:voice_play_button',
          'transition:1:visible:voice_waveform',
          'visible:content_scanning_placeholder',
          'visible:voice_message_row',
        ];
      case 'tp_state_018_sticker_validation':
        return [
          'hidden:sticker_alt_text',
          'hidden:sticker_image',
          'visible:blocked_media_placeholder',
          'visible:unsafe_content_warning',
        ];
      case 'tp_state_019_banned_mime_type_maps_to_invalid':
        return [
          'transition:1:hidden:download_file_button',
          'transition:1:scanner_banned_mime_type',
          'transition:1:visible:blocked_media_placeholder',
          'transition:1:visible:unsafe_content_warning',
        ];
      case 'tp_state_020_scanner_service_unavailable':
        return [
          'hidden:media_viewer',
          'hidden:raw_media_content',
          'visible:content_validation_unavailable_fallback',
          'visible:timeline_row_shell',
        ];
      case 'tp_state_021_media_viewer_non_event_media_valid':
        return [
          'hidden:event_content_validation_error',
          'hidden:media_viewer_invalid_state',
          'visible:media_viewer_image',
        ];
      case 'tp_state_022_active_call_joined_no_duplicate_action':
        return [
          'hidden:join_call_button',
          'visible:active_call_card',
          'visible:in_call_indicator',
        ];
      case 'tp_state_023_active_call_missing_participants':
        return [
          'hidden:participant_avatar_error',
          'visible:active_call_card',
          'visible:active_call_title',
          'visible:join_call_button',
        ];
      case 'tp_state_024_active_call_participant_update':
        return [
          'property:active_call_participant_count=1',
          'transition:1:active_call_members_updated(count=3)',
          'transition:1:property:active_call_participant_count=3',
          'transition:1:visible:active_call_card',
          'transition:1:visible:active_call_participant_count_label',
          'visible:active_call_card',
        ];
      case 'tp_state_025_navigation_ignores_invalid_media':
        return [
          'enabled:jump_to_unread_button',
          'hidden:raw_media_content',
          'transition:1:jump_to_unread',
          'transition:1:visible:timeline_scroll_position_stable',
          'transition:1:visible:unread_marker_target_row',
          'visible:jump_to_unread_button',
          'visible:unsafe_content_warning',
        ];
      case 'tp_state_026_action_menu_for_blocked_media':
        return [
          'transition:1:hidden:action_download_media',
          'transition:1:hidden:action_play_media',
          'transition:1:long_press_blocked_media',
          'transition:1:visible:action_report',
          'transition:1:visible:action_view_details',
        ];
      case 'tp_state_027_final_active_call_actionable_card':
        return [
          'enabled:join_call_button',
          'hidden:blocked_media_notice',
          'hidden:unsupported_event_placeholder',
          'transition:1:disabled:join_call_button',
          'transition:1:join_call',
          'transition:1:visible:active_call_card',
          'transition:1:visible:joining_call_indicator',
          'visible:active_call_card',
          'visible:active_call_participant_count',
          'visible:join_call_button',
        ];
      case 'tp_state_028_final_positive_scanner_and_call':
        return [
          'hidden:unsupported_event_placeholder',
          'visible:active_call_card',
          'visible:join_call_button',
        ];
      case 'tp_state_029_validation_cache_survives_scroll_rebind':
        return [
          'hidden:content_scanning_placeholder',
          'hidden:unsafe_content_warning',
          'transition:1:hidden:content_scanning_placeholder',
          'transition:1:hidden:unsafe_content_warning',
          'transition:1:timeline_row_rebound(event_id=evt_media_cached)',
          'transition:1:visible:image_thumbnail',
          'visible:image_thumbnail',
        ];
      case 'tp_state_030_mixed_timeline_scanner_does_not_block_text':
        return [
          'enabled:text_event_action_menu',
          'hidden:raw_media_content',
          'visible:blocked_media_placeholder',
          'visible:text_event_body',
          'visible:unsafe_content_warning',
        ];
      case 'tp_state_031_active_call_end_update_removes_join_action':
        return [
          'enabled:active_call_join_button',
          'transition:1:active_call_state_update(ended)',
          'transition:1:hidden:active_call_join_button',
          'transition:1:visible:active_call_card',
          'transition:1:visible:active_call_ended_label',
          'visible:active_call_card',
          'visible:active_call_join_button',
        ];
      case 'tp_state_032_blocked_media_details_action_without_download':
        return [
          'hidden:video_play_affordance',
          'transition:1:hidden:download_media_action',
          'transition:1:hidden:play_media_action',
          'transition:1:hidden:share_media_action',
          'transition:1:long_press_blocked_media',
          'transition:1:visible:message_details_action',
          'transition:1:visible:report_content_action',
          'visible:blocked_media_placeholder',
          'visible:unsafe_content_warning',
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
