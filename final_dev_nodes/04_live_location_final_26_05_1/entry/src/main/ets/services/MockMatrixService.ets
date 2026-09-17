import { AccountProfile, BaseFeatureFlags, RoomSummary, ScenarioInfo, TimelineEvent, TimelineEventKind } from '../model/ElementModels';

const SCENARIO_ID: string = "live_location_final";
const TASK_FAMILY: string = "Live Location Sharing";
const BASE_VERSION: string = "26.04.0";
const FINAL_VERSION: string = "26.05.1";
const DESCRIPTION: string = "Final development node with active live location sharing connected. Timeline, banner-like status and start/stop side effects are represented.";
const INTENTIONALLY_ABSENT: string[] = [];

export class MockMatrixService {
  getScenarioInfo(): ScenarioInfo {
    return {
      scenarioId: SCENARIO_ID,
      taskFamily: TASK_FAMILY,
      baseVersion: BASE_VERSION,
      finalVersion: FINAL_VERSION,
      description: DESCRIPTION,
      intentionallyAbsent: INTENTIONALLY_ABSENT,
      flags: this.getFeatureFlags()
    };
  }

  getFeatureFlags(): BaseFeatureFlags {
    return {
      userStatus: false,
      galleryMessages: false,
      activeCallTimeline: false,
      liveLocationSharing: true,
      richLinkNewDevice: false
    };
  }

  getAccountProfile(): AccountProfile {
    return {
      userId: '@alice:matrix.org',
      displayName: 'Alice',
      avatarInitials: 'AL',
      canSetUserStatus: false
    };
  }

  getRooms(): RoomSummary[] {
    return [
      {
        id: 'room-general',
        name: 'Element X General',
        topic: 'Cross-platform product discussion',
        unreadCount: 3,
        isDirect: false
      },
      {
        id: 'room-design',
        name: 'Design Review',
        topic: 'Mobile UI and accessibility',
        unreadCount: 0,
        isDirect: false
      },
      {
        id: 'dm-bob',
        name: 'Bob',
        topic: 'Direct message',
        unreadCount: 1,
        isDirect: true
      }
    ];
  }

  getTimelineEvents(): TimelineEvent[] {
    const baseEvents: TimelineEvent[] = [
      {
        id: 'evt-001',
        sender: 'Alice',
        timestamp: '09:20',
        kind: TimelineEventKind.Text,
        body: 'Morning! The Android and iOS base snapshots are aligned.',
        supported: true
      },
      {
        id: 'evt-002',
        sender: 'Bob',
        timestamp: '09:23',
        kind: TimelineEventKind.Image,
        body: 'Single image attachment',
        mediaCount: 1,
        supported: true
      },
      {
        id: 'evt-003',
        sender: 'Chen',
        timestamp: '09:25',
        kind: TimelineEventKind.Text,
        body: 'Please keep existing room and timeline behavior stable.',
        supported: true
      }
    ];

    if (SCENARIO_ID === 'gallery_messages_base' || SCENARIO_ID === 'gallery_messages_final') {
      baseEvents.push({
        id: 'evt-gallery-fixture',
        sender: 'Dana',
        timestamp: '09:31',
        kind: TimelineEventKind.Gallery,
        body: 'Gallery message fixture: unsupported in this base',
        mediaCount: 4,
        supported: false
      });
    }

    if (SCENARIO_ID === 'active_call_timeline_base' || SCENARIO_ID === 'active_call_timeline_final') {
      baseEvents.push({
        id: 'evt-call-fixture',
        sender: 'Element Call',
        timestamp: '09:35',
        kind: TimelineEventKind.ActiveCall,
        body: 'Active call fixture: unsupported timeline item in this base',
        supported: false
      });
    }

    if (SCENARIO_ID === 'live_location_base' || SCENARIO_ID === 'live_location_final') {
      baseEvents.push({
        id: 'evt-live-location-fixture',
        sender: 'Bob',
        timestamp: '09:41',
        kind: TimelineEventKind.LiveLocation,
        body: 'Live location sharing active',
        supported: true
      });
    }

    return baseEvents;
  }

  getSecurityRows(): string[] {
    if (SCENARIO_ID === 'link_new_device_base' || SCENARIO_ID === 'link_new_device_final') {
      return [
        'Session verification: available',
        'Manual recovery key: available',
        'QR link placeholder: visible but non-rotating',
        'Owner verification: not available',
        'Timeout handling: not available'
      ];
    }

    return [
      'Session verification: available',
      'Recovery: available',
      'Device list: available'
    ];
  }
}
