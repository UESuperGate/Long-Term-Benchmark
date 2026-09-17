import { AccountProfile, BaseFeatureFlags, RoomSummary, ScenarioInfo, TimelineEvent, TimelineEventKind } from '../model/ElementModels';

const SCENARIO_ID: string = "link_new_device_final";
const TASK_FAMILY: string = "Link New Device Flow";
const BASE_VERSION: string = "26.05.0";
const FINAL_VERSION: string = "26.08.2";
const DESCRIPTION: string = "Final development node with richer link-new-device QR flow connected. QR rotation, owner verification and timeout states are available.";
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
      liveLocationSharing: false,
      richLinkNewDevice: true
    };
  }

  getAccountProfile(): AccountProfile {
    return {
      userId: '@alice:matrix.org',
      displayName: 'Alice',
      avatarInitials: 'AL',
      avatarUrl: '',
      userStatus: 'Away',
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
        isMarkedUnread: false,
        isFavorite: false,
        isDirect: false
      },
      {
        id: 'room-design',
        name: 'Design Review',
        topic: 'Mobile UI and accessibility',
        unreadCount: 0,
        isMarkedUnread: false,
        isFavorite: false,
        isDirect: false
      },
      {
        id: 'dm-bob',
        name: 'Bob',
        topic: 'Direct message',
        unreadCount: 1,
        isMarkedUnread: false,
        isFavorite: true,
        isDirect: true
      }
    ];
  }

  getTimelineEvents(): TimelineEvent[] {
    const baseEvents: TimelineEvent[] = [
      {
        id: 'evt-001',
        roomId: 'room-general',
        sender: 'Alice',
        timestamp: '09:20',
        kind: TimelineEventKind.Text,
        body: 'Morning! The Android and iOS base snapshots are aligned.',
        supported: true
      },
      {
        id: 'evt-002',
        roomId: 'room-general',
        sender: 'Bob',
        timestamp: '09:23',
        kind: TimelineEventKind.Image,
        body: 'Single image attachment',
        mediaCount: 1,
        mediaUri: 'file:///storage/media/base-image.jpg',
        mimeType: 'image/jpeg',
        mediaSize: 0,
        mediaItems: [
          {
            uri: 'file:///storage/media/base-image.jpg',
            mimeType: 'image/jpeg',
            size: 0
          }
        ],
        supported: true
      },
      {
        id: 'evt-003',
        roomId: 'room-general',
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
        roomId: 'room-general',
        sender: 'Dana',
        timestamp: '09:31',
        kind: TimelineEventKind.Gallery,
        body: 'Gallery message fixture: unsupported in this base',
        mediaCount: 4,
        mediaUri: 'file:///storage/media/gallery-1.jpg',
        mimeType: 'image/jpeg',
        mediaItems: [
          {
            uri: 'file:///storage/media/gallery-1.jpg',
            mimeType: 'image/jpeg',
            size: 0
          },
          {
            uri: 'file:///storage/media/gallery-2.jpg',
            mimeType: 'image/jpeg',
            size: 0
          },
          {
            uri: 'file:///storage/media/gallery-3.jpg',
            mimeType: 'image/jpeg',
            size: 0
          },
          {
            uri: 'file:///storage/media/gallery-4.jpg',
            mimeType: 'image/jpeg',
            size: 0
          }
        ],
        supported: false
      });
    }

    if (SCENARIO_ID === 'active_call_timeline_base' || SCENARIO_ID === 'active_call_timeline_final') {
      baseEvents.push({
        id: 'evt-call-fixture',
        roomId: 'room-general',
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
        roomId: 'room-general',
        sender: 'Bob',
        timestamp: '09:41',
        kind: TimelineEventKind.LiveLocation,
        body: 'Live location fixture: unsupported in this base',
        supported: false
      });
    }

    return baseEvents;
  }

  getSecurityRows(): string[] {
    if (SCENARIO_ID === 'link_new_device_base' || SCENARIO_ID === 'link_new_device_final') {
      return [
        'Session verification: available',
        'Manual recovery key: available',
        'QR link: rotating and refreshable',
        'Owner verification: available',
        'Timeout handling: available'
      ];
    }

    return [
      'Session verification: available',
      'Recovery: available',
      'Device list: available'
    ];
  }
}
