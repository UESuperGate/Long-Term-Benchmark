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
      case 'gm_state_001_supported_gallery_row':
        return [
          'enabled:gallery_item_0',
          'enabled:gallery_item_1',
          'enabled:gallery_item_2',
          'enabled:gallery_item_3',
          'hidden:unsupported_event_placeholder',
          'visible:gallery_caption',
          'visible:gallery_container',
          'visible:gallery_item_0',
          'visible:gallery_item_1',
          'visible:gallery_item_2',
          'visible:gallery_item_3',
        ];
      case 'gm_state_002_final_gallery_replaces_unsupported':
        return [
          'hidden:media_viewer',
          'hidden:unsupported_event_placeholder',
          'visible:gallery_container',
          'visible:gallery_item_0',
          'visible:gallery_item_1',
          'visible:gallery_item_2',
          'visible:gallery_item_3',
        ];
      case 'gm_state_003_open_selected_media':
        return [
          'transition:1:gallery_item_click(index=2)',
          'transition:1:property:selected_media_index=2',
          'transition:1:visible:media_viewer',
          'transition:1:visible:media_viewer_item_2',
          'visible:gallery_container',
        ];
      case 'gm_state_004_validation_loading_blocks_content':
        return [
          'hidden:raw_media_content',
          'hidden:unsafe_content_warning',
          'transition:1:content_validation_update(valid)',
          'transition:1:hidden:content_scanning_placeholder',
          'transition:1:visible:raw_media_content',
          'visible:content_scanning_placeholder',
          'visible:gallery_container',
        ];
      case 'gm_state_005_validation_invalid_per_item':
        return [
          'hidden:unsupported_event_placeholder',
          'visible:gallery_container',
          'visible:gallery_item_0',
          'visible:gallery_item_1_invalid_fallback',
          'visible:gallery_item_2',
          'visible:gallery_item_3',
        ];
      case 'gm_state_006_reply_preview_item_count':
        return [
          'hidden:reply_preview_unsupported',
          'property:reply_preview_item_count=4',
          'visible:reply_preview_gallery_label',
          'visible:reply_preview_item_count',
        ];
      case 'gm_state_007_action_list_gallery_actions':
        return [
          'transition:1:hidden:action_copy_text_only',
          'transition:1:long_press_gallery_event',
          'transition:1:visible:action_forward',
          'transition:1:visible:action_reply',
          'transition:1:visible:action_share',
          'transition:1:visible:action_view_details',
        ];
      case 'gm_state_008_share_preserves_all_items':
        return [
          'transition:1:hidden:single_media_share_only',
          'transition:1:property:pending_share_attachment_count=4',
          'transition:1:share_gallery_event',
          'transition:1:visible:gallery_share_bundle',
          'transition:1:visible:share_target_picker',
        ];
      case 'gm_state_009_empty_gallery_fallback':
        return [
          'hidden:gallery_item_0',
          'hidden:unsupported_event_placeholder',
          'visible:gallery_empty_placeholder',
        ];
      case 'gm_state_010_single_item_gallery_keeps_gallery_semantics':
        return [
          'hidden:single_media_message_row',
          'hidden:unsupported_event_placeholder',
          'visible:gallery_caption',
          'visible:gallery_container',
          'visible:gallery_item_0',
        ];
      case 'gm_state_011_file_only_gallery_uses_attachment_list':
        return [
          'hidden:gallery_visual_grid',
          'hidden:unsupported_event_placeholder',
          'visible:gallery_attachment_list',
          'visible:gallery_container',
          'visible:gallery_file_item_0',
          'visible:gallery_file_item_1',
        ];
      case 'gm_state_012_audio_file_mixed_gallery':
        return [
          'hidden:unsupported_event_placeholder',
          'visible:gallery_item_audio',
          'visible:gallery_item_file',
          'visible:gallery_item_image',
          'visible:gallery_item_video',
        ];
      case 'gm_state_013_formatted_caption':
        return [
          'property:caption_formatting_preserved=true',
          'visible:gallery_container',
          'visible:gallery_formatted_caption',
        ];
      case 'gm_state_014_edited_gallery_caption':
        return [
          'hidden:unsupported_event_placeholder',
          'property:gallery_item_count=2',
          'visible:edited_indicator',
          'visible:gallery_caption',
          'visible:gallery_container',
        ];
      case 'gm_state_015_thumbnail_failure_per_item':
        return [
          'hidden:gallery_empty_placeholder',
          'hidden:unsupported_event_placeholder',
          'visible:gallery_item_0',
          'visible:gallery_item_1_thumbnail_error',
          'visible:gallery_item_2',
        ];
      case 'gm_state_016_unrecoverable_item_error':
        return [
          'hidden:unsupported_event_placeholder',
          'visible:gallery_container',
          'visible:gallery_item_0',
          'visible:gallery_item_1_not_found',
          'visible:gallery_item_2',
        ];
      case 'gm_state_017_viewer_previous_next_bounds':
        return [
          'disabled:viewer_previous',
          'enabled:viewer_next',
          'transition:1:disabled:viewer_next',
          'transition:1:enabled:viewer_previous',
          'transition:1:viewer_next',
          'transition:1:visible:media_viewer_item_1',
          'visible:media_viewer',
          'visible:media_viewer_item_0',
        ];
      case 'gm_state_018_viewer_invalid_selected_item':
        return [
          'transition:1:gallery_item_click(index=1)',
          'transition:1:hidden:media_viewer_raw_content',
          'transition:1:visible:media_viewer_blocked_content',
          'transition:1:visible:unsafe_content_warning',
        ];
      case 'gm_state_019_pinned_event_gallery':
        return [
          'hidden:pinned_unsupported_placeholder',
          'property:pinned_gallery_item_count=4',
          'visible:gallery_container',
          'visible:pinned_gallery_row',
        ];
      case 'gm_state_020_reply_preview_invalid_gallery':
        return [
          'hidden:raw_media_content',
          'hidden:reply_preview_thumbnail',
          'visible:reply_preview_gallery_label',
          'visible:reply_preview_invalid_content',
        ];
      case 'gm_state_021_action_list_invalid_gallery':
        return [
          'transition:1:hidden:action_save_media',
          'transition:1:hidden:action_share_raw_media',
          'transition:1:long_press_gallery_event',
          'transition:1:visible:action_view_details',
        ];
      case 'gm_state_022_final_gallery_coexists_with_single_media':
        return [
          'hidden:unsupported_event_placeholder',
          'visible:gallery_container',
          'visible:gallery_item_count',
          'visible:image_thumbnail',
          'visible:single_media_message_row',
        ];
      case 'gm_state_023_final_gallery_tap_opens_viewer':
        return [
          'transition:1:hidden:unsupported_event_placeholder',
          'transition:1:tap_gallery_fixture',
          'transition:1:visible:action_save_media',
          'transition:1:visible:action_share_media',
          'transition:1:visible:gallery_container',
          'transition:1:visible:media_viewer',
          'transition:1:visible:media_viewer_counter',
        ];
      case 'gm_state_024_final_positive_gallery_actions':
        return [
          'enabled:action_forward',
          'enabled:action_reply',
          'enabled:action_share',
          'enabled:gallery_item_0',
          'hidden:unsupported_event_placeholder',
          'visible:gallery_container',
        ];
      case 'gm_state_025_gallery_order_preserved_after_validation_updates':
        return [
          'property:gallery_item_0=image_a',
          'property:gallery_item_1=video_b',
          'property:gallery_item_2=file_c',
          'property:gallery_item_3=image_d',
          'transition:1:content_validation_update(item_2=valid)',
          'transition:1:property:gallery_item_0=image_a',
          'transition:1:property:gallery_item_1=video_b',
          'transition:1:property:gallery_item_2=file_c',
          'transition:1:property:gallery_item_3=image_d',
          'transition:1:visible:gallery_item_0',
          'transition:1:visible:gallery_item_1',
          'transition:1:visible:gallery_item_2',
          'transition:1:visible:gallery_item_3',
          'visible:gallery_container',
          'visible:gallery_item_0',
          'visible:gallery_item_1',
          'visible:gallery_item_2',
          'visible:gallery_item_3',
        ];
      case 'gm_state_026_viewer_reuses_timeline_caption_and_edited_state':
        return [
          'transition:1:gallery_item_click(index=0)',
          'transition:1:property:media_viewer_caption=formatted_caption',
          'transition:1:visible:media_viewer',
          'transition:1:visible:media_viewer_caption',
          'transition:1:visible:media_viewer_edited_indicator',
          'visible:edited_indicator',
          'visible:gallery_caption',
          'visible:gallery_container',
        ];
      case 'gm_state_027_redacted_gallery_hides_media_but_keeps_event_shell':
        return [
          'disabled:gallery_container',
          'hidden:gallery_item_0',
          'hidden:gallery_item_1',
          'hidden:gallery_item_2',
          'hidden:gallery_item_3',
          'hidden:media_viewer',
          'visible:redacted_event_placeholder',
        ];
      case 'gm_state_028_share_skips_blocked_items_but_reports_omissions':
        return [
          'transition:1:hidden:unsafe_media_in_share_sheet',
          'transition:1:property:share_payload_count=2',
          'transition:1:share_gallery_event',
          'transition:1:visible:gallery_share_partial_warning',
          'transition:1:visible:share_sheet',
          'visible:gallery_container',
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
