import { ClientAuthState, ClientSnapshot } from '../model/ClientModels';
import { ReadReceiptSummary, RoomSummary, TimelineEvent, TimelineEventKind, TimelineMediaItem } from '../model/ElementModels';
import common from '@ohos.app.ability.common';
import Want from '@ohos.app.ability.Want';
import picker from '@ohos.file.picker';
import fs from '@ohos.file.fs';
import fileUri from '@ohos.file.fileuri';
import http from '@ohos.net.http';
import pasteboard from '@ohos.pasteboard';
import { TimelineMediaPreviewMode } from '../model/ClientRuntimeModels';
import { ElementClientViewModel, ForegroundSyncResult, JoinRoomResult, MarkRoomReadResult, RoomPreviewResult, SendMessageResult, SignInResult, UpdateIgnoredUserResult, UpdateProfileResult, UpdateReadReceiptPreferenceResult, UpdateRoomMembershipResult, UpdateRoomMetadataResult, UpdateTimelineMediaPreviewModeResult, UserProfileResult } from '../viewmodel/ElementClientViewModel';
import { ElementNotificationService, PublishRoomNotificationResult } from '../services/ElementNotificationService';
import { LaunchIntentPayload, LaunchIntentStore } from '../services/LaunchIntentStore';
import { SharedMediaFileReader, SharedMediaReadResult } from '../services/SharedMediaFileReader';

interface MediaDownloadHeaders {
  'Accept': string;
  'Authorization'?: string;
  'User-Agent': string;
}

interface MediaActionContent {
  ok: boolean;
  uri: string;
  filename: string;
  errorMessage: string;
}

interface MediaActionCacheEntry {
  path: string;
  mtime: number;
}

const MEDIA_ACTION_CACHE_MAX_AGE_SECONDS = 24 * 60 * 60;
const MEDIA_ACTION_CACHE_MAX_FILES = 24;

@Entry
@Component
struct Index {
  private viewModel: ElementClientViewModel = new ElementClientViewModel();
  private notificationService: ElementNotificationService = new ElementNotificationService();
  private sharedMediaFileReader: SharedMediaFileReader = new SharedMediaFileReader();
  @State private authState: ClientAuthState = ClientAuthState.SignedOut;
  @State private selectedTab: number = 0;
  @State private visibleTimelineRoomTitle: string = '';
  @State private homeserver: string = 'matrix.org';
  @State private username: string = 'Alice';
  @State private password: string = '';
  @State private signInError: string = '';
  @State private isSigningIn: boolean = false;
  @State private messageDraft: string = '';
  @State private sendStatus: string = '';
  @State private sendError: string = '';
  @State private isSendingMessage: boolean = false;
  @State private readError: string = '';
  @State private isMarkingRead: boolean = false;
  @State private isMarkingUnread: boolean = false;
  @State private isAutoMarkingRead: boolean = false;
  @State private homeReadError: string = '';
  @State private isMarkingAllRead: boolean = false;
  @State private displayNameDraft: string = '';
  @State private userStatusDraft: string = '';
  @State private profileError: string = '';
  @State private isUpdatingProfile: boolean = false;
  @State private privacyError: string = '';
  @State private isUpdatingReadReceiptPreference: boolean = false;
  @State private mediaPreviewError: string = '';
  @State private isUpdatingMediaPreviewPreference: boolean = false;
  @State private notificationStatus: string = '';
  @State private isPublishingNotification: boolean = false;
  @State private selectedReadReceiptEventId: string = '';
  @State private mediaViewerEventId: string = '';
  @State private mediaViewerItemIndex: number = 0;
  @State private mediaViewerActionStatus: string = '';
  @State private isMediaViewerDetailsVisible: boolean = false;
  @State private pendingShareAttachmentRows: string[] = [];
  @State private isShareTargetPickerVisible: boolean = false;
  @State private pendingPermalinkUri: string = '';
  @State private pendingPermalinkMessage: string = '';
  @State private focusedPermalinkEventId: string = '';
  @State private focusedPermalinkThreadId: string = '';
  @State private jumpToUnreadRoomId: string = '';
  @State private jumpToUnreadEventId: string = '';
  @State private unreadMarkerBeforeEventId: string = '';
  @State private jumpToUnreadCount: number = 0;
  @State private pendingUserProfileUserId: string = '';
  @State private pendingUserProfileName: string = '';
  @State private pendingUserProfileStatus: string = '';
  @State private pendingUserProfileError: string = '';
  @State private pendingUserProfileActionStatus: string = '';
  @State private pendingUserProfileIgnored: boolean = false;
  @State private isUpdatingIgnoredUser: boolean = false;
  @State private isStartingPermalinkDm: boolean = false;
  @State private isBlockedUsersSheetVisible: boolean = false;
  @State private blockedUsersPendingUnblockUserId: string = '';
  @State private blockedUsersStatus: string = '';
  @State private blockedUsersError: string = '';
  @State private isUnblockingBlockedUser: boolean = false;
  @State private roomListContextMenuRoomId: string = '';
  @State private roomListContextMenuError: string = '';
  @State private isUpdatingRoomListContextMenu: boolean = false;
  @State private isRoomListContextMenuConfirmingLeave: boolean = false;
  @State private roomDetailsRoomId: string = '';
  @State private roomDetailsError: string = '';
  @State private isUpdatingRoomDetails: boolean = false;
  @State private isRoomDetailsConfirmingLeave: boolean = false;
  @State private reportRoomId: string = '';
  @State private reportRoomReason: string = '';
  @State private reportRoomLeaveRoom: boolean = false;
  @State private reportRoomAlreadySubmitted: boolean = false;
  @State private reportRoomError: string = '';
  @State private isReportingRoom: boolean = false;
  @State private pendingRoomPreviewId: string = '';
  @State private pendingRoomPreviewName: string = '';
  @State private pendingRoomPreviewTopic: string = '';
  @State private pendingRoomPreviewServers: string[] = [];
  @State private pendingRoomPreviewError: string = '';
  @State private isJoiningPermalinkRoom: boolean = false;
  @State private foregroundSyncStatus: string = '';
  @State private isForegroundSyncing: boolean = false;
  @State private snapshot: ClientSnapshot = this.viewModel.getSignedOutSnapshot();
  private foregroundSyncTimerId: number = -1;
  @StorageLink('elementx_launch_intent_payload')
  @Watch('handleStoredLaunchIntentChanged')
  private storedLaunchIntentPayload: string = '';

  build() {
    Column() {
      if (this.authState === ClientAuthState.SignedIn) {
        this.SignedInShell()
      } else if (this.authState === ClientAuthState.ManualLogin) {
        this.ManualLoginScreen()
      } else if (this.authState === ClientAuthState.QrLogin) {
        this.QrLoginScreen()
      } else if (this.authState === ClientAuthState.CreateAccount) {
        this.CreateAccountScreen()
      } else {
        this.OnboardingScreen()
      }
    }
    .width('100%')
    .height('100%')
    .backgroundColor('#F7F8FA')
    .onAppear(() => {
      const restored = this.viewModel.restoreLatestSession();
      this.snapshot = restored;
      if (restored.session !== null) {
        this.authState = ClientAuthState.SignedIn;
        this.syncProfileDrafts();
      }
      this.restorePersistedSession();
    })
    .onDisAppear(() => {
      this.stopForegroundSyncLoop();
    })
  }

  @Builder
  OnboardingScreen() {
    Column() {
      Row() {
        Button('Dev')
          .fontSize(14)
          .backgroundColor('#00000000')
          .fontColor('#20242C')
          .id('developer_options')
        Blank()
      }
      .width('100%')
      .padding({ left: 18, right: 18, top: 58 })

      Blank()

      Column({ space: 22 }) {
        Text('Element')
          .fontSize(42)
          .fontWeight(FontWeight.Bold)
          .fontColor('#13BF9D')
          .textAlign(TextAlign.Center)
          .width(220)
          .height(220)
          .borderRadius(48)
          .backgroundColor('#DFF4FA')
          .id('element_brand_mark')
        Text('Be in your element')
          .fontSize(30)
          .fontWeight(FontWeight.Bold)
          .fontColor('#20242C')
          .textAlign(TextAlign.Center)
          .id('onboarding_title')
        Text('Welcome to the fastest Element ever. Supercharged for speed and simplicity.')
          .fontSize(18)
          .fontColor('#20242C')
          .lineHeight(27)
          .textAlign(TextAlign.Center)
          .padding({ left: 26, right: 26 })
          .id('onboarding_subtitle')
      }

      Blank()

      Column({ space: 18 }) {
        Button('Sign in with QR code')
          .width('88%')
          .height(56)
          .fontSize(18)
          .fontWeight(FontWeight.Medium)
          .backgroundColor('#191B21')
          .fontColor('#FFFFFF')
          .borderRadius(28)
          .onClick(() => {
            this.authState = ClientAuthState.QrLogin;
          })
          .id('onboarding_qr_sign_in')
        Button('Sign in manually')
          .width('88%')
          .height(56)
          .fontSize(18)
          .fontWeight(FontWeight.Medium)
          .backgroundColor('#191B21')
          .fontColor('#FFFFFF')
          .borderRadius(28)
          .onClick(() => {
            this.authState = ClientAuthState.ManualLogin;
          })
          .id('onboarding_manual_sign_in')
        Button('Create account')
          .width('88%')
          .height(56)
          .fontSize(18)
          .fontWeight(FontWeight.Medium)
          .backgroundColor('#00000000')
          .fontColor('#20242C')
          .onClick(() => {
            this.authState = ClientAuthState.CreateAccount;
          })
          .id('onboarding_create_account')
        Text(`Version ${this.snapshot.versionName}`)
          .fontSize(15)
          .fontColor('#717887')
          .margin({ top: 20, bottom: 38 })
          .id('onboarding_version')
      }
      .width('100%')
      .alignItems(HorizontalAlign.Center)
    }
    .width('100%')
    .height('100%')
    .backgroundColor('#DFF4FA')
  }

  @Builder
  ManualLoginScreen() {
    Column({ space: 18 }) {
      this.AuthHeader('Sign in manually', 'Continue with your Matrix account.')
      TextInput({ text: this.homeserver, placeholder: 'Homeserver' })
        .onChange((value: string) => {
          this.homeserver = value;
        })
        .id('login_homeserver')
      TextInput({ text: this.username, placeholder: 'Username' })
        .onChange((value: string) => {
          this.username = value;
        })
        .id('login_username')
      TextInput({ text: this.password, placeholder: 'Password' })
        .onChange((value: string) => {
          this.password = value;
        })
        .id('login_password')
      if (this.signInError.length > 0) {
        Text(this.signInError)
          .fontSize(13)
          .fontColor('#B42318')
          .lineHeight(19)
          .width('100%')
          .id('login_error')
      }
      Button(this.isSigningIn ? 'Signing in' : 'Sign in')
        .width('100%')
        .height(52)
        .backgroundColor('#191B21')
        .fontColor('#FFFFFF')
        .borderRadius(26)
        .onClick(() => {
          this.handleManualSignIn();
        })
        .id('login_submit')
      Button('Back')
        .width('100%')
        .height(44)
        .backgroundColor('#00000000')
        .fontColor('#20242C')
        .onClick(() => {
          this.authState = ClientAuthState.SignedOut;
        })
        .id('login_back')
    }
    .padding(24)
    .width('100%')
    .height('100%')
    .backgroundColor('#FFFFFF')
  }

  @Builder
  QrLoginScreen() {
    Column({ space: 18 }) {
      this.AuthHeader('Sign in with QR code', 'Scan the code from your other device.')
      Text('QR scanner surface')
        .fontSize(28)
        .fontWeight(FontWeight.Bold)
        .textAlign(TextAlign.Center)
        .width('100%')
        .height(220)
        .borderRadius(8)
        .backgroundColor('#E7F7F2')
        .id('qr_scanner_surface')
      Button('Continue')
        .width('100%')
        .height(52)
        .backgroundColor('#191B21')
        .fontColor('#FFFFFF')
        .borderRadius(26)
        .onClick(() => {
          this.snapshot = this.viewModel.signInWithFixture(this.homeserver, this.username);
          this.selectedTab = 0;
          this.authState = ClientAuthState.SignedIn;
        })
        .id('qr_continue_sign_in')
      Button('Back')
        .width('100%')
        .height(44)
        .backgroundColor('#00000000')
        .fontColor('#20242C')
        .onClick(() => {
          this.authState = ClientAuthState.SignedOut;
        })
        .id('qr_back')
    }
    .padding(24)
    .width('100%')
    .height('100%')
    .backgroundColor('#FFFFFF')
  }

  @Builder
  CreateAccountScreen() {
    Column({ space: 18 }) {
      this.AuthHeader('Create account', 'Start with a Matrix homeserver.')
      Button('Create account')
        .width('100%')
        .height(52)
        .backgroundColor('#191B21')
        .fontColor('#FFFFFF')
        .borderRadius(26)
        .onClick(() => {
          this.snapshot = this.viewModel.signInWithFixture(this.homeserver, this.username);
          this.selectedTab = 0;
          this.authState = ClientAuthState.SignedIn;
        })
        .id('create_account_submit')
      Button('Back')
        .width('100%')
        .height(44)
        .backgroundColor('#00000000')
        .fontColor('#20242C')
        .onClick(() => {
          this.authState = ClientAuthState.SignedOut;
        })
        .id('create_back')
    }
    .padding(24)
    .width('100%')
    .height('100%')
    .backgroundColor('#FFFFFF')
  }

  @Builder
  AuthHeader(title: string, subtitle: string) {
    Column({ space: 8 }) {
      Text(title)
        .fontSize(28)
        .fontWeight(FontWeight.Bold)
        .fontColor('#20242C')
        .id('auth_title')
      Text(subtitle)
        .fontSize(15)
        .fontColor('#647083')
        .lineHeight(22)
        .id('auth_subtitle')
    }
    .alignItems(HorizontalAlign.Start)
    .width('100%')
    .margin({ top: 56, bottom: 18 })
  }

  @Builder
  SignedInShell() {
    Stack() {
      Column() {
        this.TopBar()
        Tabs({ index: this.selectedTab }) {
          TabContent() {
            this.HomePanel()
          }
          .tabBar('Home')

          TabContent() {
            this.TimelinePanel()
          }
          .tabBar('Timeline')

          TabContent() {
            this.SettingsPanel()
          }
          .tabBar('Settings')

          TabContent() {
            this.DevicesPanel()
          }
          .tabBar('Devices')
        }
        .barPosition(BarPosition.End)
        .onChange((index: number) => {
          this.selectedTab = index;
        })
        .layoutWeight(1)
      }
      .width('100%')
      .height('100%')
      .backgroundColor('#F7F8FA')
      if (this.selectedReadReceiptEventId.length > 0) {
        this.ReadReceiptSheet()
      }
      if (this.mediaViewerEventId.length > 0) {
        this.MediaViewerSheet()
      }
      if (this.isShareTargetPickerVisible) {
        this.ShareTargetSheet()
      }
      if (this.pendingPermalinkUri.length > 0) {
        this.PermalinkSheet()
      }
      if (this.pendingUserProfileUserId.length > 0) {
        this.UserProfileSheet()
      }
      if (this.roomListContextMenuRoomId.length > 0) {
        this.RoomListContextMenuSheet()
      }
      if (this.roomDetailsRoomId.length > 0) {
        this.RoomDetailsSheet()
      }
      if (this.reportRoomId.length > 0) {
        this.ReportRoomSheet()
      }
      if (this.isBlockedUsersSheetVisible) {
        this.BlockedUsersSheet()
      }
      if (this.pendingRoomPreviewId.length > 0) {
        this.RoomPreviewSheet()
      }
    }
    .width('100%')
    .height('100%')
  }

  @Builder
  TopBar() {
    Row() {
      Text(this.snapshot.session?.account.avatarInitials ?? 'EX')
        .fontSize(16)
        .fontWeight(FontWeight.Bold)
        .fontColor('#FFFFFF')
        .textAlign(TextAlign.Center)
        .width(42)
        .height(42)
        .borderRadius(21)
        .backgroundColor('#0F766E')
      Column({ space: 2 }) {
        Text(this.snapshot.appName)
          .fontSize(20)
          .fontWeight(FontWeight.Bold)
          .fontColor('#18202A')
        Text(this.snapshot.session?.account.userId ?? 'Signed out')
          .fontSize(12)
          .fontColor('#64748B')
      }
      .alignItems(HorizontalAlign.Start)
      .margin({ left: 12 })
      Blank()
      if (this.syncChipText().length > 0) {
        this.SyncChip()
        Blank()
          .width(8)
      }
      Button('Sign out')
        .height(36)
        .fontSize(13)
        .backgroundColor('#EEF2F7')
        .fontColor('#20242C')
        .onClick(() => {
          this.handleSignOut();
        })
        .id('client_sign_out')
    }
    .padding({ left: 16, right: 16, top: 58, bottom: 12 })
    .width('100%')
    .backgroundColor('#FFFFFF')
    .id('client_top_bar')
  }

  @Builder
  HomePanel() {
    Scroll() {
      Column({ space: 12 }) {
        this.SectionTitle('Rooms')
        this.HomeReadActions()
        ForEach(this.snapshot.rooms, (room: RoomSummary) => {
          this.RoomRow(room)
        })
        this.SectionTitle('Activity')
        ForEach(this.snapshot.featureStatusRows, (row: string) => {
          this.StatusRow(row)
        })
        this.SectionTitle('System')
        ForEach(this.snapshot.runtimeRows, (row: string) => {
          this.StatusRow(row)
        })
        if (this.foregroundSyncStatus.length > 0) {
          this.StatusRow(this.foregroundSyncStatus)
        }
      }
      .padding(16)
    }
    .id('home_panel')
  }

  @Builder
  HomeReadActions() {
    Column({ space: 8 }) {
      Row() {
        Text('Unread')
          .fontSize(14)
          .fontWeight(FontWeight.Medium)
          .fontColor('#1E293B')
        Blank()
        Button(this.isMarkingAllRead ? 'Marking all' : 'Mark all read')
          .height(36)
          .backgroundColor('#EEF2F7')
          .fontColor('#0F172A')
          .borderRadius(18)
          .onClick(() => {
            this.handleMarkAllRoomsRead();
          })
          .id('home_mark_all_read_button')
      }
      .width('100%')
      if (this.homeReadError.length > 0) {
        Text(this.homeReadError)
          .fontSize(13)
          .fontColor('#B42318')
          .lineHeight(18)
          .width('100%')
          .id('home_mark_all_read_error')
      }
    }
    .alignItems(HorizontalAlign.Start)
    .padding(12)
    .borderRadius(8)
    .backgroundColor('#FFFFFF')
    .id('home_read_actions')
  }

  @Builder
  RoomRow(room: RoomSummary) {
    Row() {
      Column({ space: 4 }) {
        Text(room.name)
          .fontSize(16)
          .fontWeight(FontWeight.Medium)
          .fontColor('#1E293B')
        Text(room.topic)
          .fontSize(12)
          .fontColor('#64748B')
        if (room.isFavorite) {
          Text('Favourited')
            .fontSize(11)
            .fontColor('#7C3AED')
            .lineHeight(16)
            .id(`room_favorite_${room.id}`)
        }
      }
      .alignItems(HorizontalAlign.Start)
      .layoutWeight(1)
      if (room.unreadCount > 0 || room.isMarkedUnread) {
        Text(this.roomUnreadBadgeLabel(room))
          .fontSize(12)
          .fontColor('#FFFFFF')
          .textAlign(TextAlign.Center)
          .width(24)
          .height(24)
          .borderRadius(12)
          .backgroundColor(room.isMarkedUnread && room.unreadCount === 0 ? '#7C3AED' : '#2563EB')
      }
    }
    .padding(12)
    .borderRadius(8)
    .backgroundColor(room.id === this.snapshot.selectedRoomId ? '#E7F7F2' : '#FFFFFF')
    .onClick(() => {
      this.handleSelectRoom(room.id);
    })
    .gesture(
      LongPressGesture({ repeat: false })
        .onAction(() => {
          this.openRoomListContextMenu(room.id);
        })
    )
    .id(`room_${room.id}`)
  }

  @Builder
  RoomListContextMenuSheet() {
    if (this.roomListContextMenuRoomId.length > 0) {
      Column() {
        Blank()
          .layoutWeight(1)
        Column({ space: 12 }) {
          Row() {
            Column({ space: 2 }) {
              Text(this.roomListContextMenuRoomName())
                .fontSize(18)
                .fontWeight(FontWeight.Bold)
                .fontColor('#0F172A')
              Text(this.roomListContextMenuRoomTopic())
                .fontSize(12)
                .fontColor('#64748B')
            }
            .alignItems(HorizontalAlign.Start)
            .layoutWeight(1)
            Button('Close')
              .height(38)
              .backgroundColor('#EEF2F7')
              .fontColor('#0F172A')
              .borderRadius(19)
              .onClick(() => {
                this.closeRoomListContextMenu();
              })
              .id('room_list_context_close')
          }
          .width('100%')
          if (this.isRoomListContextMenuConfirmingLeave) {
            Text(`Leave ${this.roomListContextMenuRoomName()}?`)
              .fontSize(15)
              .fontWeight(FontWeight.Medium)
              .fontColor('#0F172A')
              .width('100%')
              .id('room_list_context_leave_confirm_title')
            Row({ space: 8 }) {
              Button('Cancel')
                .height(44)
                .layoutWeight(1)
                .backgroundColor('#EEF2F7')
                .fontColor('#0F172A')
                .borderRadius(22)
                .enabled(!this.isUpdatingRoomListContextMenu)
                .onClick(() => {
                  this.cancelRoomListContextMenuLeave();
                })
                .id('room_list_context_leave_cancel')
              Button(this.isUpdatingRoomListContextMenu ? 'Leaving' : 'Leave')
                .height(44)
                .layoutWeight(1)
                .backgroundColor('#B42318')
                .fontColor('#FFFFFF')
                .borderRadius(22)
                .enabled(!this.isUpdatingRoomListContextMenu)
                .onClick(() => {
                  this.confirmRoomListContextMenuLeave();
                })
                .id('room_list_context_leave_confirm')
            }
            .width('100%')
          } else {
            Button(this.roomListContextMenuReadLabel())
              .height(44)
              .width('100%')
              .backgroundColor('#0F766E')
              .fontColor('#FFFFFF')
              .borderRadius(22)
              .enabled(!this.isUpdatingRoomListContextMenu)
              .onClick(() => {
                this.handleRoomListContextMenuReadAction();
              })
              .id(this.roomListContextMenuReadButtonId())
            Button(this.roomListContextMenuFavoriteLabel())
              .height(44)
              .width('100%')
              .backgroundColor('#EEF2F7')
              .fontColor('#334155')
              .borderRadius(22)
              .enabled(!this.isUpdatingRoomListContextMenu)
              .onClick(() => {
                this.handleRoomListContextMenuFavoriteToggle();
              })
              .id(this.roomListContextMenuFavoriteButtonId())
            Button('Settings')
              .height(44)
              .width('100%')
              .backgroundColor('#EEF2F7')
              .fontColor('#334155')
              .borderRadius(22)
              .enabled(!this.isUpdatingRoomListContextMenu)
              .onClick(() => {
                this.openRoomDetailsFromRoomListContextMenu();
              })
              .id('room_list_context_settings')
            if (this.roomListContextMenuCanReportRoom()) {
              Button('Report room')
                .height(44)
                .width('100%')
                .backgroundColor('#FFF4ED')
                .fontColor('#B54708')
                .borderRadius(22)
                .enabled(!this.isUpdatingRoomListContextMenu)
                .onClick(() => {
                  this.openReportRoomFromRoomListContextMenu();
                })
                .id('room_list_context_report_room')
            }
            Button('Leave room')
              .height(44)
              .width('100%')
              .backgroundColor('#FEE4E2')
              .fontColor('#B42318')
              .borderRadius(22)
              .enabled(!this.isUpdatingRoomListContextMenu)
              .onClick(() => {
                this.requestRoomListContextMenuLeave();
              })
              .id('room_list_context_leave_room')
          }
          if (this.roomListContextMenuError.length > 0) {
            Text(this.roomListContextMenuError)
              .fontSize(13)
              .fontColor('#B42318')
              .lineHeight(18)
              .width('100%')
              .id('room_list_context_error')
          }
        }
        .width('100%')
        .padding(20)
        .borderRadius({ topLeft: 8, topRight: 8 })
        .backgroundColor('#FFFFFF')
        .offset({ y: -120 })
      }
      .width('100%')
      .height('100%')
      .backgroundColor('#66000000')
      .zIndex(34)
      .id('room_list_context_menu_sheet')
    }
  }

  @Builder
  RoomDetailsSheet() {
    if (this.roomDetailsRoomId.length > 0) {
      Column() {
        Blank()
          .layoutWeight(1)
        Column({ space: 12 }) {
          Row() {
            Column({ space: 2 }) {
              Text('Room details')
                .fontSize(18)
                .fontWeight(FontWeight.Bold)
                .fontColor('#0F172A')
              Text(this.roomDetailsRoomName())
                .fontSize(14)
                .fontColor('#334155')
            }
            .alignItems(HorizontalAlign.Start)
            .layoutWeight(1)
            Button('Close')
              .height(38)
              .backgroundColor('#EEF2F7')
              .fontColor('#0F172A')
              .borderRadius(19)
              .onClick(() => {
                this.closeRoomDetails();
              })
              .id('room_details_close')
          }
          .width('100%')
          Text(this.roomDetailsRoomTopic())
            .fontSize(13)
            .fontColor('#64748B')
            .lineHeight(18)
            .width('100%')
            .id('room_details_topic')
          Text(this.roomDetailsRoomIdLabel())
            .fontSize(12)
            .fontColor('#64748B')
            .lineHeight(18)
            .width('100%')
            .id('room_details_room_id')
          if (this.isRoomDetailsConfirmingLeave) {
            Text(`Leave ${this.roomDetailsRoomName()}?`)
              .fontSize(15)
              .fontWeight(FontWeight.Medium)
              .fontColor('#0F172A')
              .width('100%')
              .id('room_details_leave_confirm_title')
            Row({ space: 8 }) {
              Button('Cancel')
                .height(44)
                .layoutWeight(1)
                .backgroundColor('#EEF2F7')
                .fontColor('#0F172A')
                .borderRadius(22)
                .enabled(!this.isUpdatingRoomDetails)
                .onClick(() => {
                  this.cancelRoomDetailsLeave();
                })
                .id('room_details_leave_cancel')
              Button(this.isUpdatingRoomDetails ? 'Leaving' : 'Leave')
                .height(44)
                .layoutWeight(1)
                .backgroundColor('#B42318')
                .fontColor('#FFFFFF')
                .borderRadius(22)
                .enabled(!this.isUpdatingRoomDetails)
                .onClick(() => {
                  this.confirmRoomDetailsLeave();
                })
                .id('room_details_leave_confirm')
            }
            .width('100%')
          } else {
            Button(this.roomDetailsReadLabel())
              .height(44)
              .width('100%')
              .backgroundColor('#0F766E')
              .fontColor('#FFFFFF')
              .borderRadius(22)
              .enabled(!this.isUpdatingRoomDetails)
              .onClick(() => {
                this.handleRoomDetailsReadAction();
              })
              .id(this.roomDetailsReadButtonId())
            Button(this.roomDetailsFavoriteLabel())
              .height(44)
              .width('100%')
              .backgroundColor('#EEF2F7')
              .fontColor('#334155')
              .borderRadius(22)
              .enabled(!this.isUpdatingRoomDetails)
              .onClick(() => {
                this.handleRoomDetailsFavoriteToggle();
              })
              .id(this.roomDetailsFavoriteButtonId())
            if (this.roomDetailsCanReportRoom()) {
              Button('Report room')
                .height(44)
                .width('100%')
                .backgroundColor('#FFF4ED')
                .fontColor('#B54708')
                .borderRadius(22)
                .enabled(!this.isUpdatingRoomDetails)
                .onClick(() => {
                  this.openReportRoomFromRoomDetails();
                })
                .id('room_details_report_room')
            }
            Button('Leave room')
              .height(44)
              .width('100%')
              .backgroundColor('#FEE4E2')
              .fontColor('#B42318')
              .borderRadius(22)
              .enabled(!this.isUpdatingRoomDetails)
              .onClick(() => {
                this.requestRoomDetailsLeave();
              })
              .id('room_details_leave_room')
          }
          if (this.roomDetailsError.length > 0) {
            Text(this.roomDetailsError)
              .fontSize(13)
              .fontColor('#B42318')
              .lineHeight(18)
              .width('100%')
              .id('room_details_error')
          }
        }
        .width('100%')
        .padding(20)
        .borderRadius({ topLeft: 8, topRight: 8 })
        .backgroundColor('#FFFFFF')
        .offset({ y: -120 })
      }
      .width('100%')
      .height('100%')
      .backgroundColor('#66000000')
      .zIndex(36)
      .id('room_details_sheet')
    }
  }

  @Builder
  ReportRoomSheet() {
    if (this.reportRoomId.length > 0) {
      Column() {
        Blank()
          .layoutWeight(1)
        Column({ space: 12 }) {
          Row() {
            Column({ space: 2 }) {
              Text('Report room')
                .fontSize(18)
                .fontWeight(FontWeight.Bold)
                .fontColor('#0F172A')
              Text(this.reportRoomName())
                .fontSize(14)
                .fontColor('#334155')
            }
            .alignItems(HorizontalAlign.Start)
            .layoutWeight(1)
            Button('Close')
              .height(38)
              .backgroundColor('#EEF2F7')
              .fontColor('#0F172A')
              .borderRadius(19)
              .enabled(!this.isReportingRoom)
              .onClick(() => {
                this.closeReportRoom();
              })
              .id('report_room_close')
          }
          .width('100%')
          TextInput({ text: this.reportRoomReason, placeholder: 'Describe reason...' })
            .height(92)
            .width('100%')
            .backgroundColor('#F8FAFC')
            .borderRadius(8)
            .padding(12)
            .fontSize(14)
            .fontColor('#0F172A')
            .enabled(!this.isReportingRoom)
            .onChange((value: string) => {
              this.reportRoomReason = value;
            })
            .id('report_room_reason')
          Text('This reports the room to the homeserver administrator. Encrypted message content may not be visible to the administrator.')
            .fontSize(12)
            .fontColor('#64748B')
            .lineHeight(17)
            .width('100%')
            .id('report_room_footer')
          Button(this.reportRoomLeaveRoom ? 'Leave room: on' : 'Leave room: off')
            .height(44)
            .width('100%')
            .backgroundColor(this.reportRoomLeaveRoom ? '#FEF3F2' : '#EEF2F7')
            .fontColor(this.reportRoomLeaveRoom ? '#B42318' : '#334155')
            .borderRadius(22)
            .enabled(!this.isReportingRoom)
            .onClick(() => {
              if (this.reportRoomAlreadySubmitted) {
                return;
              }
              this.reportRoomLeaveRoom = !this.reportRoomLeaveRoom;
            })
            .id('report_room_leave_toggle')
          Row({ space: 8 }) {
            Button('Cancel')
              .height(44)
              .layoutWeight(1)
              .backgroundColor('#EEF2F7')
              .fontColor('#0F172A')
              .borderRadius(22)
              .enabled(!this.isReportingRoom)
              .onClick(() => {
                this.closeReportRoom();
              })
              .id('report_room_cancel')
            Button(this.reportRoomSubmitLabel())
              .height(44)
              .layoutWeight(1)
              .backgroundColor('#B42318')
              .fontColor('#FFFFFF')
              .borderRadius(22)
              .enabled(!this.isReportingRoom)
              .onClick(() => {
                this.handleReportRoomSubmit();
              })
              .id('report_room_submit')
          }
          .width('100%')
          if (this.reportRoomError.length > 0) {
            Text(this.reportRoomError)
              .fontSize(13)
              .fontColor('#B42318')
              .lineHeight(18)
              .width('100%')
              .id('report_room_error')
          }
        }
        .width('100%')
        .padding(20)
        .borderRadius({ topLeft: 8, topRight: 8 })
        .backgroundColor('#FFFFFF')
        .offset({ y: -120 })
      }
      .width('100%')
      .height('100%')
      .backgroundColor('#66000000')
      .zIndex(38)
      .id('report_room_sheet')
    }
  }

  @Builder
  TimelinePanel() {
    Scroll() {
      Column({ space: 12 }) {
        Text(this.timelineRoomTitle())
          .fontSize(18)
          .fontWeight(FontWeight.Bold)
          .fontColor('#18202A')
          .width('100%')
          .margin({ top: 8, bottom: 2 })
        this.TimelineActions()
        this.MessageComposer()
        ForEach(this.snapshot.timeline, (event: TimelineEvent) => {
          if (this.shouldRenderUnreadMarkerBefore(event)) {
            this.TimelineUnreadMarker()
          }
          this.EventRow(event)
        })
      }
      .padding(16)
      .width('100%')
      .constraintSize({ minHeight: '100%' })
    }
    .width('100%')
    .height('100%')
    .id('timeline_panel')
    .onAppear(() => {
      this.handleTimelineVisibleForRead();
    })
  }

  @Builder
  TimelineActions() {
    Column({ space: 8 }) {
      Row({ space: 8 }) {
        Text('Read state')
          .fontSize(14)
          .fontWeight(FontWeight.Medium)
          .fontColor('#1E293B')
        Blank()
        Button(this.isMarkingRead ? 'Marking read' : 'Mark read')
          .height(36)
          .backgroundColor('#0F766E')
          .fontColor('#FFFFFF')
          .borderRadius(18)
          .onClick(() => {
            this.handleMarkRoomRead();
          })
          .id('timeline_mark_read_button')
        Button(this.isMarkingUnread ? 'Marking unread' : 'Mark unread')
          .height(36)
          .backgroundColor('#EEF2F7')
          .fontColor('#334155')
          .borderRadius(18)
          .onClick(() => {
            this.handleMarkRoomUnread();
          })
          .id('timeline_mark_unread_button')
      }
      .width('100%')
      if (this.isTimelineMarkedUnread()) {
        Text('Marked unread')
          .fontSize(13)
          .fontColor('#7C3AED')
          .lineHeight(18)
          .width('100%')
          .id('timeline_marked_unread_state')
      }
      if (this.readError.length > 0) {
        Text(this.readError)
          .fontSize(13)
          .fontColor('#B42318')
          .lineHeight(18)
          .width('100%')
          .id('timeline_mark_read_error')
      }
      if (this.shouldShowJumpToUnread()) {
        Row({ space: 8 }) {
          Text(this.jumpToUnreadLabel())
            .fontSize(13)
            .fontColor('#0F766E')
            .lineHeight(18)
            .layoutWeight(1)
          Button('Jump unread')
            .height(32)
            .backgroundColor('#E7F7F2')
            .fontColor('#0F766E')
            .borderRadius(16)
            .onClick(() => {
              this.handleJumpToUnread();
            })
            .id('timeline_jump_to_unread_button')
        }
        .alignItems(VerticalAlign.Center)
        .width('100%')
        .padding({ left: 8, right: 8, top: 6, bottom: 6 })
        .borderRadius(6)
        .backgroundColor('#F0FDFA')
        .id('timeline_jump_to_unread_state')
      }
      if (this.focusedPermalinkEventId.length > 0) {
        Text(this.focusedPermalinkLabel())
          .fontSize(13)
          .fontColor('#92400E')
          .lineHeight(18)
          .width('100%')
          .padding({ left: 8, right: 8, top: 6, bottom: 6 })
          .borderRadius(6)
          .backgroundColor('#FEF3C7')
          .id('timeline_focus_banner')
      }
      if (this.focusedPermalinkThreadId.length > 0) {
        Text(`Thread focus: ${this.focusedPermalinkThreadId}`)
          .fontSize(13)
          .fontColor('#1D4ED8')
          .lineHeight(18)
          .width('100%')
          .padding({ left: 8, right: 8, top: 6, bottom: 6 })
          .borderRadius(6)
          .backgroundColor('#DBEAFE')
          .id('timeline_thread_banner')
      }
    }
    .alignItems(HorizontalAlign.Start)
    .padding(12)
    .borderRadius(8)
    .backgroundColor('#FFFFFF')
    .id('timeline_read_state')
  }

  @Builder
  TimelineUnreadMarker() {
    Column({ space: 4 }) {
      Text('UNREAD MESSAGES')
        .fontSize(12)
        .fontWeight(FontWeight.Medium)
        .fontColor('#0F766E')
        .textAlign(TextAlign.End)
        .width('100%')
      Row()
        .height(1)
        .width('100%')
        .backgroundColor('#0F766E')
    }
    .alignItems(HorizontalAlign.End)
    .width('100%')
    .padding({ left: 18, right: 18, top: 12, bottom: 12 })
    .id('timeline_unread_marker')
  }

  @Builder
  EventRow(event: TimelineEvent) {
    Column({ space: 8 }) {
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
        .fontColor('#334155')
        .lineHeight(20)
      if (this.isMediaTimelineEvent(event)) {
        this.MediaAttachmentPreview(event)
      }
      if (event.kind === TimelineEventKind.ActiveCall) {
        Button('Join call')
          .height(40)
          .id(`join_call_${event.id}`)
      }
      if (event.kind === TimelineEventKind.LiveLocation) {
        Button('Open live map')
          .height(40)
          .id(`open_live_map_${event.id}`)
      }
      if (this.shouldRenderReadReceipts(event)) {
        this.ReadReceiptStrip(event)
      }
    }
    .alignItems(HorizontalAlign.Start)
    .padding(12)
    .borderRadius(8)
    .backgroundColor(this.isFocusedPermalinkEvent(event) ? '#FFF7ED' : '#FFFFFF')
    .id(`timeline_event_${event.id}`)
  }

  @Builder
  MediaAttachmentPreview(event: TimelineEvent) {
    Column({ space: 8 }) {
      if (event.kind === TimelineEventKind.Gallery) {
        Column({ space: 8 }) {
          Row({ space: 8 }) {
            ForEach(this.galleryRowItems(event, 0), (item: TimelineMediaItem) => {
              this.GalleryMediaTile(event, item)
            }, (item: TimelineMediaItem) => item.uri + item.mimeType)
          }
          .width('100%')
          Row({ space: 8 }) {
            ForEach(this.galleryRowItems(event, 2), (item: TimelineMediaItem) => {
              this.GalleryMediaTile(event, item)
            }, (item: TimelineMediaItem) => item.uri + item.mimeType)
          }
          .width('100%')
        }
        .width('100%')
      } else {
        Column({ space: 6 }) {
          if (this.canRenderVisualThumbnail(event.kind, event.mediaUri ?? '')) {
            Image(this.renderableVisualThumbnailUri(event.kind, event.mediaUri ?? '', 800, 600))
              .width('100%')
              .height(150)
              .objectFit(ImageFit.Cover)
              .borderRadius(8)
              .id(`media_image_${event.id}`)
          }
          Text(this.mediaEventKindTitle(event))
            .fontSize(12)
            .fontWeight(FontWeight.Medium)
            .fontColor('#0F172A')
          Text(this.mediaMetaLabel(event))
            .fontSize(11)
            .fontColor('#64748B')
            .lineHeight(16)
            .maxLines(2)
            .textOverflow({ overflow: TextOverflow.Ellipsis })
        }
        .alignItems(HorizontalAlign.Start)
        .width('100%')
        .padding(10)
        .borderRadius(8)
        .backgroundColor('#F1F5F9')
        .onClick(() => {
          this.openMediaViewer(event, 0);
        })
        .id(`media_preview_${event.id}`)
      }
      Text(this.mediaRendererLabel(event))
        .fontSize(12)
        .fontColor('#14532D')
        .padding({ left: 8, right: 8, top: 4, bottom: 4 })
        .backgroundColor('#DCFCE7')
        .borderRadius(6)
    }
    .alignItems(HorizontalAlign.Start)
    .width('100%')
  }

  @Builder
  GalleryMediaTile(event: TimelineEvent, item: TimelineMediaItem) {
    Column({ space: 4 }) {
      if (this.canRenderVisualMediaItem(item)) {
        Image(this.renderableMediaItemThumbnailUri(item, 800, 600))
          .width('100%')
          .height(50)
          .objectFit(ImageFit.Cover)
          .borderRadius(6)
      }
      Text(this.mediaItemKindLabel(item))
        .fontSize(12)
        .fontWeight(FontWeight.Medium)
        .fontColor('#0F172A')
        .textAlign(TextAlign.Center)
        .maxLines(1)
        .textOverflow({ overflow: TextOverflow.Ellipsis })
      Text(item.mimeType)
        .fontSize(10)
        .fontColor('#64748B')
        .textAlign(TextAlign.Center)
        .maxLines(1)
        .textOverflow({ overflow: TextOverflow.Ellipsis })
    }
    .justifyContent(FlexAlign.Center)
    .width('48%')
    .height(96)
    .padding(8)
    .borderRadius(8)
    .backgroundColor('#F1F5F9')
    .onClick(() => {
      this.openMediaViewer(event, this.mediaItemIndex(event, item));
    })
    .id(`media_item_${this.shareAttachmentKey(item.uri + item.mimeType)}`)
  }

  @Builder
  ReadReceiptStrip(event: TimelineEvent) {
    Row({ space: 6 }) {
      ForEach(this.eventReadReceipts(event), (receipt: ReadReceiptSummary) => {
        Text(receipt.avatarInitials)
          .fontSize(9)
          .fontWeight(FontWeight.Bold)
          .fontColor('#FFFFFF')
          .textAlign(TextAlign.Center)
          .width(22)
          .height(22)
          .borderRadius(11)
          .backgroundColor('#0F766E')
      }, (receipt: ReadReceiptSummary) => receipt.userId)
      Text(this.readReceiptLabel(event))
        .fontSize(12)
        .fontColor('#64748B')
        .lineHeight(18)
    }
    .width('100%')
    .justifyContent(FlexAlign.End)
    .padding({ top: 2, right: 2 })
    .onClick(() => {
      this.openReadReceiptSheet(event.id);
    })
    .id(`read_receipts_${event.id}`)
  }

  @Builder
  ReadReceiptSheet() {
    Column() {
      Blank()
        .layoutWeight(1)
      Column({ space: 12 }) {
        Row() {
          Text('Seen by')
            .fontSize(18)
            .fontWeight(FontWeight.Bold)
            .fontColor('#0F172A')
          Blank()
          Button('Close')
            .height(38)
            .backgroundColor('#EEF2F7')
            .fontColor('#0F172A')
            .borderRadius(19)
            .onClick(() => {
              this.closeReadReceiptSheet();
            })
            .id('read_receipts_close_button')
        }
        .width('100%')
        ForEach(this.selectedReadReceiptItems(), (receipt: ReadReceiptSummary) => {
          Row({ space: 12 }) {
            Text(receipt.avatarInitials)
              .fontSize(13)
              .fontWeight(FontWeight.Bold)
              .fontColor('#FFFFFF')
              .textAlign(TextAlign.Center)
              .width(36)
              .height(36)
              .borderRadius(18)
              .backgroundColor('#0F766E')
            Column({ space: 2 }) {
              Text(receipt.displayName)
                .fontSize(15)
                .fontWeight(FontWeight.Medium)
                .fontColor('#0F172A')
              Text(receipt.userId)
                .fontSize(12)
                .fontColor('#64748B')
            }
            .alignItems(HorizontalAlign.Start)
            Blank()
            Text(receipt.timestamp)
              .fontSize(12)
              .fontColor('#64748B')
          }
          .width('100%')
          .padding({ top: 8, bottom: 8 })
          .id(`read_receipt_item_${receipt.userId}`)
        }, (receipt: ReadReceiptSummary) => receipt.userId)
      }
      .width('100%')
      .padding(20)
      .borderRadius({ topLeft: 8, topRight: 8 })
      .backgroundColor('#FFFFFF')
      .offset({ y: -120 })
      Blank()
        .height(100)
    }
    .width('100%')
    .height('100%')
    .backgroundColor('#66000000')
    .id('read_receipts_sheet')
  }

  @Builder
  MediaViewerSheet() {
    Column() {
      Column({ space: 12 }) {
        Row() {
          Column({ space: 2 }) {
            Text('Media viewer')
              .fontSize(18)
              .fontWeight(FontWeight.Bold)
              .fontColor('#F8FAFC')
            Text(this.mediaViewerPositionLabel())
              .fontSize(12)
              .fontColor('#CBD5E1')
          }
          .alignItems(HorizontalAlign.Start)
          Blank()
          Button('Close')
            .height(38)
            .backgroundColor('#334155')
            .fontColor('#F8FAFC')
            .borderRadius(19)
            .onClick(() => {
              this.closeMediaViewer();
            })
            .id('media_viewer_close_button')
        }
        .width('100%')
        Column({ space: 10 }) {
          if (this.mediaViewerRenderableUri().length > 0) {
            Image(this.mediaViewerRenderableUri())
              .width('100%')
              .height(360)
              .objectFit(ImageFit.Contain)
              .borderRadius(8)
              .backgroundColor('#020617')
              .id('media_viewer_image')
          } else {
            Column({ space: 8 }) {
              Text(this.mediaViewerItemKindLabel())
                .fontSize(24)
                .fontWeight(FontWeight.Bold)
                .fontColor('#F8FAFC')
              Text('Preview unavailable')
                .fontSize(13)
                .fontColor('#CBD5E1')
            }
            .justifyContent(FlexAlign.Center)
            .width('100%')
            .height(360)
            .borderRadius(8)
            .backgroundColor('#020617')
            .id('media_viewer_fallback')
          }
          Text(this.mediaViewerEventLabel())
            .fontSize(16)
            .fontWeight(FontWeight.Medium)
            .fontColor('#F8FAFC')
            .width('100%')
            .maxLines(2)
            .textOverflow({ overflow: TextOverflow.Ellipsis })
          Text(this.mediaViewerMetadataLabel())
            .fontSize(12)
            .fontColor('#CBD5E1')
            .lineHeight(18)
            .width('100%')
            .maxLines(3)
            .textOverflow({ overflow: TextOverflow.Ellipsis })
          Row({ space: 8 }) {
            Button('Share')
              .height(36)
              .layoutWeight(1)
              .backgroundColor('#334155')
              .fontColor('#F8FAFC')
              .borderRadius(18)
              .onClick(() => {
                this.handleMediaViewerShare();
              })
              .id('media_viewer_share_button')
            Button('Save')
              .height(36)
              .layoutWeight(1)
              .backgroundColor('#334155')
              .fontColor('#F8FAFC')
              .borderRadius(18)
              .onClick(() => {
                this.handleMediaViewerSave();
              })
              .id('media_viewer_save_button')
            Button('Info')
              .height(36)
              .layoutWeight(1)
              .backgroundColor(this.isMediaViewerDetailsVisible ? '#0F766E' : '#334155')
              .fontColor('#F8FAFC')
              .borderRadius(18)
              .onClick(() => {
                this.handleMediaViewerInfo();
              })
              .id('media_viewer_info_button')
          }
          .width('100%')
          Row({ space: 8 }) {
            Button('Open')
              .height(36)
              .layoutWeight(1)
              .backgroundColor('#334155')
              .fontColor('#F8FAFC')
              .borderRadius(18)
              .onClick(() => {
                this.handleMediaViewerOpenWith();
              })
              .id('media_viewer_open_with_button')
            Button('Timeline')
              .height(36)
              .layoutWeight(1)
              .backgroundColor('#334155')
              .fontColor('#F8FAFC')
              .borderRadius(18)
              .onClick(() => {
                this.handleMediaViewerViewInTimeline();
              })
              .id('media_viewer_view_timeline_button')
            Button('Forward')
              .height(36)
              .layoutWeight(1)
              .backgroundColor('#334155')
              .fontColor('#F8FAFC')
              .borderRadius(18)
              .onClick(() => {
                this.handleMediaViewerForward();
              })
              .id('media_viewer_forward_button')
          }
          .width('100%')
          if (this.mediaViewerActionStatus.length > 0) {
            Text(this.mediaViewerActionStatus)
              .fontSize(12)
              .fontColor('#A7F3D0')
              .lineHeight(18)
              .width('100%')
              .maxLines(2)
              .textOverflow({ overflow: TextOverflow.Ellipsis })
              .id('media_viewer_action_status')
          }
          if (this.isMediaViewerDetailsVisible) {
            Column({ space: 4 }) {
              Text('Details')
                .fontSize(13)
                .fontWeight(FontWeight.Bold)
                .fontColor('#F8FAFC')
              Text(this.mediaViewerDetailsLabel())
                .fontSize(12)
                .fontColor('#CBD5E1')
                .lineHeight(18)
                .width('100%')
            }
            .width('100%')
            .padding(10)
            .borderRadius(8)
            .backgroundColor('#1E293B')
            .id('media_viewer_details_panel')
          }
        }
        .alignItems(HorizontalAlign.Start)
        .width('100%')
        .id('media_viewer_content')
        if (this.selectedMediaViewerItems().length > 1) {
          Row({ space: 12 }) {
            Button('Previous')
              .height(42)
              .layoutWeight(1)
              .backgroundColor('#334155')
              .fontColor('#F8FAFC')
              .borderRadius(21)
              .onClick(() => {
                this.showPreviousMediaViewerItem();
              })
              .id('media_viewer_previous_button')
            Button('Next')
              .height(42)
              .layoutWeight(1)
              .backgroundColor('#334155')
              .fontColor('#F8FAFC')
              .borderRadius(21)
              .onClick(() => {
                this.showNextMediaViewerItem();
              })
              .id('media_viewer_next_button')
          }
          .width('100%')
        }
      }
      .width('100%')
      .padding(20)
      .backgroundColor('#0F172A')
    }
    .width('100%')
    .height('100%')
    .justifyContent(FlexAlign.Center)
    .backgroundColor('#CC000000')
    .zIndex(20)
    .id('media_viewer_sheet')
  }

  @Builder
  ShareTargetSheet() {
    Column() {
      Blank()
        .layoutWeight(1)
      Column({ space: 12 }) {
        Row() {
          Text('Share to')
            .fontSize(18)
            .fontWeight(FontWeight.Bold)
            .fontColor('#0F172A')
          Blank()
          Button('Close')
            .height(38)
            .backgroundColor('#EEF2F7')
            .fontColor('#0F172A')
            .borderRadius(19)
            .onClick(() => {
              this.closeShareTargetPicker();
            })
            .id('share_target_close_button')
        }
        .width('100%')
        ForEach(this.snapshot.rooms, (room: RoomSummary) => {
          Row({ space: 10 }) {
            Column({ space: 2 }) {
              Text(room.name)
                .fontSize(15)
                .fontWeight(FontWeight.Medium)
                .fontColor('#0F172A')
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
            Button('Select')
              .height(36)
              .backgroundColor('#EEF2F7')
              .fontColor('#0F172A')
              .borderRadius(18)
              .onClick(() => {
                this.handleShareTargetRoom(room.id);
              })
              .id(`share_target_select_${room.id}`)
          }
          .alignItems(VerticalAlign.Center)
          .width('100%')
          .padding({ left: 12, right: 12, top: 10, bottom: 10 })
          .borderRadius(8)
          .backgroundColor('#FFFFFF')
          .onClick(() => {
            this.handleShareTargetRoom(room.id);
          })
          .id(`share_target_${room.id}`)
        }, (room: RoomSummary) => room.id)
      }
      .width('100%')
      .padding(20)
      .borderRadius({ topLeft: 8, topRight: 8 })
      .backgroundColor('#FFFFFF')
      .offset({ y: -120 })
      Blank()
        .height(100)
    }
    .width('100%')
    .height('100%')
    .backgroundColor('#66000000')
    .zIndex(30)
    .id('share_target_sheet')
  }

  @Builder
  PermalinkSheet() {
    Column() {
      Blank()
        .layoutWeight(1)
      Column({ space: 12 }) {
        Row() {
          Text('Open link')
            .fontSize(18)
            .fontWeight(FontWeight.Bold)
            .fontColor('#0F172A')
          Blank()
          Button('Close')
            .height(38)
            .backgroundColor('#EEF2F7')
            .fontColor('#0F172A')
            .borderRadius(19)
            .onClick(() => {
              this.closePermalinkSheet();
            })
            .id('permalink_close_button')
        }
        .width('100%')
        Text(this.pendingPermalinkMessage)
          .fontSize(15)
          .fontColor('#1E293B')
          .lineHeight(22)
          .width('100%')
          .id('permalink_message')
        Text(this.pendingPermalinkUri)
          .fontSize(12)
          .fontColor('#64748B')
          .lineHeight(18)
          .width('100%')
          .id('permalink_uri')
      }
      .width('100%')
      .padding(20)
      .borderRadius({ topLeft: 8, topRight: 8 })
      .backgroundColor('#FFFFFF')
      .offset({ y: -120 })
    }
    .width('100%')
    .height('100%')
    .backgroundColor('#66000000')
    .zIndex(20)
    .id('permalink_sheet')
  }

  @Builder
  UserProfileSheet() {
    Column() {
      Blank()
        .layoutWeight(1)
      Column({ space: 12 }) {
        Row() {
          Text(this.profileInitials())
            .fontSize(15)
            .fontWeight(FontWeight.Bold)
            .fontColor('#FFFFFF')
            .textAlign(TextAlign.Center)
            .width(40)
            .height(40)
            .borderRadius(20)
            .backgroundColor('#0F766E')
          Column({ space: 2 }) {
            Text(this.pendingUserProfileName)
              .fontSize(18)
              .fontWeight(FontWeight.Bold)
              .fontColor('#0F172A')
            Text(this.pendingUserProfileUserId)
              .fontSize(12)
              .fontColor('#64748B')
          }
          .alignItems(HorizontalAlign.Start)
          .margin({ left: 10 })
          Blank()
          Button('Close')
            .height(38)
            .backgroundColor('#EEF2F7')
            .fontColor('#0F172A')
            .borderRadius(19)
            .onClick(() => {
              this.closeUserProfileSheet();
            })
            .id('user_profile_close_button')
        }
        .width('100%')
        Text(this.pendingUserProfileStatus.length > 0 ? this.pendingUserProfileStatus : 'Matrix user')
          .fontSize(14)
          .fontColor('#334155')
          .lineHeight(20)
          .width('100%')
          .id('user_profile_status')
        if (this.pendingUserProfileError.length > 0) {
          Text(this.pendingUserProfileError)
            .fontSize(13)
            .fontColor('#B42318')
            .lineHeight(18)
            .width('100%')
            .id('user_profile_error')
        }
        if (this.pendingUserProfileActionStatus.length > 0) {
          Text(this.pendingUserProfileActionStatus)
            .fontSize(13)
            .fontColor('#475569')
            .lineHeight(18)
            .width('100%')
            .id('user_profile_action_status')
        }
        Button(this.isStartingPermalinkDm ? 'Starting chat' : 'Start chat')
          .height(44)
          .width('100%')
          .backgroundColor('#191B21')
          .fontColor('#FFFFFF')
          .borderRadius(22)
          .onClick(() => {
            this.handleStartPermalinkDm();
          })
          .id('user_profile_start_chat_button')
        Button(this.ignoredUserActionLabel())
          .height(44)
          .width('100%')
          .backgroundColor(this.pendingUserProfileIgnored ? '#EEF2F7' : '#FFF1F2')
          .fontColor(this.pendingUserProfileIgnored ? '#0F172A' : '#BE123C')
          .borderRadius(22)
          .enabled(!this.isUpdatingIgnoredUser)
          .onClick(() => {
            this.handleToggleIgnoredUser();
          })
          .id('user_profile_block_toggle_button')
      }
      .width('100%')
      .padding(20)
      .borderRadius({ topLeft: 8, topRight: 8 })
      .backgroundColor('#FFFFFF')
      .offset({ y: -120 })
    }
    .width('100%')
    .height('100%')
    .backgroundColor('#66000000')
    .zIndex(30)
    .id('user_profile_sheet')
  }

  @Builder
  RoomPreviewSheet() {
    Column() {
      Blank()
        .layoutWeight(1)
      Column({ space: 12 }) {
        Row() {
          Column({ space: 2 }) {
            Text(this.pendingRoomPreviewName)
              .fontSize(18)
              .fontWeight(FontWeight.Bold)
              .fontColor('#0F172A')
            Text(this.pendingRoomPreviewId)
              .fontSize(12)
              .fontColor('#64748B')
          }
          .alignItems(HorizontalAlign.Start)
          Blank()
          Button('Close')
            .height(38)
            .backgroundColor('#EEF2F7')
            .fontColor('#0F172A')
            .borderRadius(19)
            .onClick(() => {
              this.closeRoomPreviewSheet();
            })
            .id('room_preview_close_button')
        }
        .width('100%')
        Text(this.pendingRoomPreviewTopic)
          .fontSize(14)
          .fontColor('#334155')
          .lineHeight(20)
          .width('100%')
          .id('room_preview_topic')
        if (this.pendingRoomPreviewServers.length > 0) {
          Text(`Via ${this.pendingRoomPreviewServers.join(', ')}`)
            .fontSize(12)
            .fontColor('#64748B')
            .lineHeight(18)
            .width('100%')
            .id('room_preview_servers')
        }
        if (this.pendingRoomPreviewError.length > 0) {
          Text(this.pendingRoomPreviewError)
            .fontSize(13)
            .fontColor('#B42318')
            .lineHeight(18)
            .width('100%')
            .id('room_preview_error')
        }
        Button(this.isJoiningPermalinkRoom ? 'Joining' : 'Join room')
          .height(44)
          .width('100%')
          .backgroundColor('#191B21')
          .fontColor('#FFFFFF')
          .borderRadius(22)
          .onClick(() => {
            this.handleJoinPermalinkRoom();
          })
          .id('room_preview_join_button')
      }
      .width('100%')
      .padding(20)
      .borderRadius({ topLeft: 8, topRight: 8 })
      .backgroundColor('#FFFFFF')
      .offset({ y: -120 })
    }
    .width('100%')
    .height('100%')
    .backgroundColor('#66000000')
    .zIndex(30)
    .id('room_preview_sheet')
  }

  @Builder
  MessageComposer() {
    Column({ space: 10 }) {
      if (this.pendingShareAttachmentRows.length > 0) {
        this.PendingShareAttachments()
      }
      TextInput({ text: this.messageDraft, placeholder: 'Message' })
        .onChange((value: string) => {
          this.messageDraft = value;
          if (value.length > 0) {
            this.sendStatus = '';
          }
          if (value.length > 0 && this.sendError.length > 0 && this.isSlashCommandCandidate(value)) {
            this.sendError = '';
          }
        })
        .id('timeline_message_input')
      this.SlashCommandSuggestions()
      if (this.sendStatus.length > 0) {
        Text(this.sendStatus)
          .fontSize(13)
          .fontColor('#475569')
          .lineHeight(18)
          .width('100%')
          .id('timeline_send_status')
      }
      if (this.sendError.length > 0) {
        Text(this.sendError)
          .fontSize(13)
          .fontColor('#B42318')
          .lineHeight(18)
          .width('100%')
          .id('timeline_send_error')
      }
      Button(this.isSendingMessage ? 'Sending' : 'Send')
        .height(44)
        .width('100%')
        .backgroundColor('#191B21')
        .fontColor('#FFFFFF')
        .borderRadius(22)
        .onClick(() => {
          this.handleSendMessage();
        })
        .id('timeline_send_button')
    }
    .alignItems(HorizontalAlign.Start)
    .padding(12)
    .borderRadius(8)
    .backgroundColor('#FFFFFF')
    .id('timeline_composer')
  }

  @Builder
  SlashCommandSuggestions() {
    if (this.shouldShowSlashCommandSuggestions()) {
      Scroll() {
        Column({ space: 0 }) {
          if (this.isSlashSuggestionCandidate('/ignore')) {
            this.SlashCommandSuggestionRow('/ignore', '<user-id> [reason]', 'Ignore a user', 'slash_suggestion_ignore')
          }
          if (this.isSlashSuggestionCandidate('/unignore')) {
            this.SlashCommandSuggestionRow('/unignore', '<user-id>', 'Unignore a user', 'slash_suggestion_unignore')
          }
          if (this.isSlashSuggestionCandidate('/plain')) {
            this.SlashCommandSuggestionRow('/plain', '<message>', 'Send plain text', 'slash_suggestion_plain')
          }
          if (this.isSlashSuggestionCandidate('/me')) {
            this.SlashCommandSuggestionRow('/me', '<message>', 'Send emote', 'slash_suggestion_me')
          }
          if (this.isSlashSuggestionCandidate('/rainbow')) {
            this.SlashCommandSuggestionRow('/rainbow', '<message>', 'Send rainbow text', 'slash_suggestion_rainbow')
          }
          if (this.isSlashSuggestionCandidate('/rainbowme')) {
            this.SlashCommandSuggestionRow('/rainbowme', '<message>', 'Send rainbow emote', 'slash_suggestion_rainbowme')
          }
          if (this.isSlashSuggestionCandidate('/spoiler')) {
            this.SlashCommandSuggestionRow('/spoiler', '<message>', 'Send spoiler text', 'slash_suggestion_spoiler')
          }
          if (this.isSlashSuggestionCandidate('/nick')) {
            this.SlashCommandSuggestionRow('/nick', '<display-name>', 'Change display name', 'slash_suggestion_nick')
          }
          if (this.isSlashSuggestionCandidate('/myroomnick')) {
            this.SlashCommandSuggestionRow('/myroomnick', '<display-name>', 'Change room nickname', 'slash_suggestion_myroomnick')
          }
          if (this.isSlashSuggestionCandidate('/roomnick')) {
            this.SlashCommandSuggestionRow('/roomnick', '<display-name>', 'Change room nickname', 'slash_suggestion_roomnick')
          }
          if (this.isSlashSuggestionCandidate('/whois')) {
            this.SlashCommandSuggestionRow('/whois', '<user-id>', 'Open user profile', 'slash_suggestion_whois')
          }
          if (this.isSlashSuggestionCandidate('/roomname')) {
            this.SlashCommandSuggestionRow('/roomname', '<name>', 'Change room name', 'slash_suggestion_roomname')
          }
          if (this.isSlashSuggestionCandidate('/topic')) {
            this.SlashCommandSuggestionRow('/topic', '<topic>', 'Change room topic', 'slash_suggestion_topic')
          }
          if (this.isSlashSuggestionCandidate('/invite')) {
            this.SlashCommandSuggestionRow('/invite', '<user-id> [reason]', 'Invite user', 'slash_suggestion_invite')
          }
          if (this.isSlashSuggestionCandidate('/remove')) {
            this.SlashCommandSuggestionRow('/remove', '<user-id> [reason]', 'Remove user', 'slash_suggestion_remove')
          }
          if (this.isSlashSuggestionCandidate('/ban')) {
            this.SlashCommandSuggestionRow('/ban', '<user-id> [reason]', 'Ban user', 'slash_suggestion_ban')
          }
          if (this.isSlashSuggestionCandidate('/unban')) {
            this.SlashCommandSuggestionRow('/unban', '<user-id> [reason]', 'Unban user', 'slash_suggestion_unban')
          }
          if (this.isSlashSuggestionCandidate('/shrug')) {
            this.SlashCommandSuggestionRow('/shrug', '<message>', 'Prefix with shrug', 'slash_suggestion_shrug')
          }
          if (this.isSlashSuggestionCandidate('/lenny')) {
            this.SlashCommandSuggestionRow('/lenny', '<message>', 'Prefix with lenny', 'slash_suggestion_lenny')
          }
          if (this.isSlashSuggestionCandidate('/tableflip')) {
            this.SlashCommandSuggestionRow('/tableflip', '<message>', 'Prefix with table flip', 'slash_suggestion_tableflip')
          }
          if (this.isSlashSuggestionCandidate('/unflip')) {
            this.SlashCommandSuggestionRow('/unflip', '<message>', 'Prefix with unflip', 'slash_suggestion_unflip')
          }
        }
        .alignItems(HorizontalAlign.Start)
        .width('100%')
      }
      .height(260)
      .width('100%')
      .id('slash_suggestions_panel')
    }
  }

  @Builder
  SlashCommandSuggestionRow(command: string, parameters: string, description: string, rowId: string) {
    Row({ space: 8 }) {
      Text(command)
        .fontSize(13)
        .fontWeight(FontWeight.Medium)
        .fontColor('#191B21')
      Text(parameters)
        .fontSize(12)
        .fontColor('#64748B')
        .layoutWeight(1)
      Text(description)
        .fontSize(12)
        .fontColor('#475569')
    }
    .height(34)
    .padding({ left: 2, right: 2 })
    .width('100%')
    .onClick(() => {
      this.selectSlashCommandSuggestion(command);
    })
    .id(rowId)
  }

  @Builder
  PendingShareAttachments() {
    Column({ space: 6 }) {
      Text('Shared content')
        .fontSize(13)
        .fontWeight(FontWeight.Medium)
        .fontColor('#1E293B')
      ForEach(this.pendingShareAttachmentRows, (row: string) => {
        Text(row)
          .fontSize(12)
          .fontColor('#64748B')
          .lineHeight(18)
          .width('100%')
          .id(`pending_share_${this.shareAttachmentKey(row)}`)
      }, (row: string) => row)
    }
    .alignItems(HorizontalAlign.Start)
    .padding(10)
    .width('100%')
    .borderRadius(8)
    .backgroundColor('#F8FAFC')
    .id('pending_share_attachments')
  }

  private eventLabel(event: TimelineEvent): string {
    if (event.kind === TimelineEventKind.Gallery) {
      return `${event.body}: ${event.mediaCount ?? 0} attachments`;
    }
    if (this.isMediaTimelineEvent(event)) {
      const mimeType = event.mimeType ?? '';
      if (mimeType.length > 0) {
        return `${event.body} (${mimeType})`;
      }
      return event.body;
    }
    if (event.kind === TimelineEventKind.Emote) {
      return `* ${event.sender} ${event.body}`;
    }
    return event.body;
  }

  private isMediaTimelineEvent(event: TimelineEvent): boolean {
    return event.kind === TimelineEventKind.Image ||
      event.kind === TimelineEventKind.Video ||
      event.kind === TimelineEventKind.Audio ||
      event.kind === TimelineEventKind.File ||
      event.kind === TimelineEventKind.Gallery;
  }

  private mediaRendererLabel(event: TimelineEvent): string {
    if (event.kind === TimelineEventKind.Image) {
      return 'Image renderer connected';
    }
    if (event.kind === TimelineEventKind.Video) {
      return 'Video renderer connected';
    }
    if (event.kind === TimelineEventKind.Audio) {
      return 'Audio renderer connected';
    }
    if (event.kind === TimelineEventKind.File) {
      return 'File renderer connected';
    }
    return 'Gallery renderer connected';
  }

  private mediaEventKindTitle(event: TimelineEvent): string {
    if (event.kind === TimelineEventKind.Image) {
      return 'Image';
    }
    if (event.kind === TimelineEventKind.Video) {
      return 'Video';
    }
    if (event.kind === TimelineEventKind.Audio) {
      return 'Audio';
    }
    if (event.kind === TimelineEventKind.File) {
      return 'File';
    }
    return 'Gallery';
  }

  private eventMediaItems(event: TimelineEvent): TimelineMediaItem[] {
    const items = event.mediaItems ?? [];
    if (items.length > 0) {
      return items;
    }
    const uri = event.mediaUri ?? '';
    const mimeType = event.mimeType ?? '';
    if (uri.length === 0 && mimeType.length === 0) {
      return [];
    }
    return [
      {
        uri: uri,
        mimeType: mimeType,
        size: event.mediaSize ?? 0
      }
    ];
  }

  private visibleMediaItems(event: TimelineEvent): TimelineMediaItem[] {
    const items = this.eventMediaItems(event);
    const result: TimelineMediaItem[] = [];
    const count = items.length > 4 ? 4 : items.length;
    for (let index = 0; index < count; index += 1) {
      result.push(items[index]);
    }
    return result;
  }

  private galleryRowItems(event: TimelineEvent, startIndex: number): TimelineMediaItem[] {
    const items = this.visibleMediaItems(event);
    const result: TimelineMediaItem[] = [];
    for (let index = startIndex; index < startIndex + 2 && index < items.length; index += 1) {
      result.push(items[index]);
    }
    return result;
  }

  private mediaItemIndex(event: TimelineEvent, item: TimelineMediaItem): number {
    const items = this.eventMediaItems(event);
    const index = items.findIndex((candidate: TimelineMediaItem) => {
      return candidate.uri === item.uri && candidate.mimeType === item.mimeType;
    });
    return index >= 0 ? index : 0;
  }

  private mediaItemKindLabel(item: TimelineMediaItem): string {
    if (item.mimeType.indexOf('image/') === 0) {
      return 'Image';
    }
    if (item.mimeType.indexOf('video/') === 0) {
      return 'Video';
    }
    if (item.mimeType.indexOf('audio/') === 0) {
      return 'Audio';
    }
    return 'File';
  }

  private mediaMetaLabel(event: TimelineEvent): string {
    const mimeType = event.mimeType ?? '';
    const uri = event.mediaUri ?? '';
    const parts: string[] = [];
    if (mimeType.length > 0) {
      parts.push(mimeType);
    }
    if (event.mediaSize !== undefined && event.mediaSize > 0) {
      parts.push(`${event.mediaSize} bytes`);
    }
    if (uri.length > 0) {
      parts.push(this.compactUri(uri));
    }
    return parts.length > 0 ? parts.join(' · ') : 'Media attachment';
  }

  private compactUri(uri: string): string {
    if (uri.length <= 48) {
      return uri;
    }
    return `${uri.substring(0, 24)}...${uri.substring(uri.length - 18)}`;
  }

  private canRenderImageUri(uri: string): boolean {
    return this.renderableVisualThumbnailUri(TimelineEventKind.Image, uri, 800, 600).length > 0;
  }

  private canRenderVisualThumbnail(kind: TimelineEventKind, uri: string): boolean {
    if (!this.shouldShowTimelineMediaPreview()) {
      return false;
    }
    return this.renderableVisualThumbnailUri(kind, uri, 800, 600).length > 0;
  }

  private canRenderVisualMediaItem(item: TimelineMediaItem): boolean {
    if (!this.shouldShowTimelineMediaPreview()) {
      return false;
    }
    if (item.mimeType.indexOf('image/') === 0) {
      return this.renderableMediaItemThumbnailUri(item, 800, 600).length > 0;
    }
    if (item.mimeType.indexOf('video/') === 0) {
      return item.uri.indexOf('mxc://') === 0 && this.renderableMediaItemThumbnailUri(item, 800, 600).length > 0;
    }
    return false;
  }

  private renderableMediaItemThumbnailUri(item: TimelineMediaItem, width: number, height: number): string {
    const kind = item.mimeType.indexOf('video/') === 0 ? TimelineEventKind.Video : TimelineEventKind.Image;
    return this.renderableVisualThumbnailUri(kind, item.uri, width, height);
  }

  private renderableVisualThumbnailUri(kind: TimelineEventKind, uri: string, width: number, height: number): string {
    if (kind === TimelineEventKind.Image &&
      (uri.indexOf('file://') === 0 || uri.indexOf('http://') === 0 || uri.indexOf('https://') === 0)) {
      return uri;
    }
    if (uri.indexOf('mxc://') === 0) {
      return this.resolveMxcThumbnailUri(uri, width, height);
    }
    return '';
  }

  private renderableImageContentUri(uri: string): string {
    if (uri.indexOf('file://') === 0 || uri.indexOf('http://') === 0 || uri.indexOf('https://') === 0) {
      return uri;
    }
    if (uri.indexOf('mxc://') === 0) {
      return this.resolveMxcDownloadUri(uri);
    }
    return '';
  }

  private mediaViewerRenderableUri(): string {
    const item = this.selectedMediaViewerItem();
    if (item === null) {
      return '';
    }
    if (item.mimeType.indexOf('image/') === 0) {
      return this.renderableImageContentUri(item.uri);
    }
    if (item.mimeType.indexOf('video/') === 0) {
      return this.renderableMediaItemThumbnailUri(item, 800, 600);
    }
    return '';
  }

  private mediaViewerItemKindLabel(): string {
    const item = this.selectedMediaViewerItem();
    if (item === null) {
      return 'Media';
    }
    return this.mediaItemKindLabel(item);
  }

  private mediaViewerPositionLabel(): string {
    const items = this.selectedMediaViewerItems();
    if (items.length <= 1) {
      return this.mediaViewerItemKindLabel();
    }
    return `${this.mediaViewerItemIndex + 1} of ${items.length}`;
  }

  private mediaViewerEventLabel(): string {
    const event = this.selectedMediaViewerEvent();
    if (event === null) {
      return 'Media attachment';
    }
    return this.eventLabel(event);
  }

  private mediaViewerMetadataLabel(): string {
    const item = this.selectedMediaViewerItem();
    if (item === null) {
      return '';
    }
    const parts: string[] = [];
    if (item.mimeType.length > 0) {
      parts.push(item.mimeType);
    }
    if (item.size !== undefined && item.size > 0) {
      parts.push(`${item.size} bytes`);
    }
    if (item.uri.length > 0) {
      parts.push(item.uri);
    }
    return parts.join(' · ');
  }

  private mediaViewerDetailsLabel(): string {
    const item = this.selectedMediaViewerItem();
    const event = this.selectedMediaViewerEvent();
    if (item === null) {
      return 'No media selected';
    }
    const eventId = event === null ? this.mediaViewerEventId : event.id;
    const caption = event === null ? '' : event.body;
    const parts: string[] = [
      `Filename: ${this.mediaViewerFilename()}`,
      `MIME: ${item.mimeType.length > 0 ? item.mimeType : 'unknown'}`,
      `Event: ${eventId.length > 0 ? eventId : 'unknown'}`
    ];
    if (item.size !== undefined && item.size > 0) {
      parts.push(`Size: ${item.size} bytes`);
    }
    if (caption.length > 0) {
      parts.push(`Caption: ${caption}`);
    }
    if (item.uri.length > 0) {
      parts.push(`Source: ${item.uri}`);
    }
    return parts.join('\n');
  }

  private mediaViewerFilename(): string {
    const item = this.selectedMediaViewerItem();
    if (item === null || item.uri.length === 0) {
      return 'media';
    }
    const withoutQuery = item.uri.split('?')[0].split('#')[0];
    const slashIndex = withoutQuery.lastIndexOf('/');
    if (slashIndex >= 0 && slashIndex < withoutQuery.length - 1) {
      return withoutQuery.substring(slashIndex + 1);
    }
    return withoutQuery.length > 0 ? withoutQuery : 'media';
  }

  private mediaViewerActionSubject(): string {
    const item = this.selectedMediaViewerItem();
    if (item === null) {
      return 'media';
    }
    const filename = this.mediaViewerFilename();
    if (item.mimeType.length > 0) {
      return `${filename} (${item.mimeType})`;
    }
    return filename;
  }

  private mediaViewerAttachmentRow(): string {
    const item = this.selectedMediaViewerItem();
    if (item === null) {
      return '';
    }
    const mimeType = item.mimeType.length > 0 ? item.mimeType : 'application/octet-stream';
    return `${mimeType} ${item.uri}`;
  }

  private mediaViewerShareWant(item: TimelineMediaItem, uri: string): Want | null {
    const mimeType = item.mimeType.length > 0 ? item.mimeType : '*/*';
    const filename = this.mediaViewerFilename();
    const want: Want = {
      action: 'ohos.want.action.sendData',
      uri: uri,
      type: mimeType,
      parameters: {
        'ability.params.stream': [uri],
        'ohos.extra.param.key.contentTitle': filename,
        'ohos.extra.param.key.shareAbstract': this.mediaViewerEventLabel(),
        'ohos.extra.param.key.shareUrl': uri
      }
    };
    return want;
  }

  private mediaViewerOpenWant(item: TimelineMediaItem, uri: string): Want | null {
    const mimeType = item.mimeType.length > 0 ? item.mimeType : '*/*';
    const want: Want = {
      action: 'ohos.want.action.viewData',
      uri: uri,
      type: mimeType,
      parameters: {
        'ability.params.stream': [uri]
      }
    };
    return want;
  }

  private selectedMediaViewerEvent(): TimelineEvent | null {
    const event = this.snapshot.timeline.find((candidate: TimelineEvent) => candidate.id === this.mediaViewerEventId);
    return event === undefined ? null : event;
  }

  private selectedMediaViewerItems(): TimelineMediaItem[] {
    const event = this.selectedMediaViewerEvent();
    if (event === null) {
      return [];
    }
    return this.eventMediaItems(event);
  }

  private selectedMediaViewerItem(): TimelineMediaItem | null {
    const items = this.selectedMediaViewerItems();
    if (items.length === 0) {
      return null;
    }
    const index = this.normalizedMediaViewerIndex(items.length);
    return items[index];
  }

  private normalizedMediaViewerIndex(itemCount: number): number {
    if (itemCount <= 0) {
      return 0;
    }
    if (this.mediaViewerItemIndex < 0) {
      return 0;
    }
    if (this.mediaViewerItemIndex >= itemCount) {
      return itemCount - 1;
    }
    return this.mediaViewerItemIndex;
  }

  private resolveMxcThumbnailUri(uri: string, width: number, height: number): string {
    const path = this.mxcMediaPath(uri);
    if (path.length === 0) {
      return '';
    }
    const safeWidth = this.clampThumbnailDimension(width, 800);
    const safeHeight = this.clampThumbnailDimension(height, 600);
    return `${this.matrixMediaBaseUrl()}/_matrix/media/v3/thumbnail/${path}?width=${safeWidth}&height=${safeHeight}&method=scale`;
  }

  private resolveMxcDownloadUri(uri: string): string {
    const path = this.mxcMediaPath(uri);
    if (path.length === 0) {
      return '';
    }
    return `${this.matrixMediaBaseUrl()}/_matrix/media/v3/download/${path}`;
  }

  private mxcMediaPath(uri: string): string {
    const mediaBaseUrl = this.matrixMediaBaseUrl();
    if (mediaBaseUrl.length === 0 || uri.indexOf('mxc://') !== 0) {
      return '';
    }
    const safeUri = uri.split('#')[0].split('?')[0];
    const rest = safeUri.substring(6);
    const slashIndex = rest.indexOf('/');
    if (slashIndex <= 0 || slashIndex >= rest.length - 1) {
      return '';
    }
    const serverName = rest.substring(0, slashIndex);
    const mediaId = rest.substring(slashIndex + 1);
    return `${encodeURIComponent(serverName)}/${encodeURIComponent(mediaId)}`;
  }

  private clampThumbnailDimension(value: number, maxValue: number): number {
    if (value <= 0) {
      return maxValue;
    }
    if (value > maxValue) {
      return maxValue;
    }
    return Math.floor(value);
  }

  private matrixMediaBaseUrl(): string {
    const homeserver = this.snapshot.session?.homeserver ?? '';
    if (homeserver.length === 0) {
      return '';
    }
    let baseUrl = homeserver.trim();
    while (baseUrl.endsWith('/')) {
      baseUrl = baseUrl.substring(0, baseUrl.length - 1);
    }
    if (baseUrl.indexOf('http://') === 0 || baseUrl.indexOf('https://') === 0) {
      return baseUrl;
    }
    return `https://${baseUrl}`;
  }

  private shouldRenderReadReceipts(event: TimelineEvent): boolean {
    if (this.snapshot.session === null || !this.snapshot.session.renderReadReceipts) {
      return false;
    }
    return this.eventReadReceipts(event).length > 0;
  }

  private eventReadReceipts(event: TimelineEvent): ReadReceiptSummary[] {
    return event.readReceipts ?? [];
  }

  private readReceiptLabel(event: TimelineEvent): string {
    const receipts = this.eventReadReceipts(event);
    if (receipts.length === 0) {
      return '';
    }
    if (receipts.length === 1) {
      return `Read by ${receipts[0].displayName}`;
    }
    return `Read by ${receipts[0].displayName} +${receipts.length - 1}`;
  }

  private openReadReceiptSheet(eventId: string): void {
    this.selectedReadReceiptEventId = eventId;
  }

  private closeReadReceiptSheet(): void {
    this.selectedReadReceiptEventId = '';
  }

  private openMediaViewer(event: TimelineEvent, itemIndex: number): void {
    if (!this.isMediaTimelineEvent(event)) {
      return;
    }
    const items = this.eventMediaItems(event);
    if (items.length === 0) {
      return;
    }
    this.mediaViewerEventId = event.id;
    this.mediaViewerItemIndex = this.normalizedRequestedMediaViewerIndex(itemIndex, items.length);
    this.resetMediaViewerTransientState();
  }

  private closeMediaViewer(): void {
    this.mediaViewerEventId = '';
    this.mediaViewerItemIndex = 0;
    this.resetMediaViewerTransientState();
  }

  private resetMediaViewerTransientState(): void {
    this.mediaViewerActionStatus = '';
    this.isMediaViewerDetailsVisible = false;
  }

  private showPreviousMediaViewerItem(): void {
    const itemCount = this.selectedMediaViewerItems().length;
    if (itemCount <= 1) {
      return;
    }
    if (this.mediaViewerItemIndex <= 0) {
      this.mediaViewerItemIndex = itemCount - 1;
      this.resetMediaViewerTransientState();
      return;
    }
    this.mediaViewerItemIndex -= 1;
    this.resetMediaViewerTransientState();
  }

  private showNextMediaViewerItem(): void {
    const itemCount = this.selectedMediaViewerItems().length;
    if (itemCount <= 1) {
      return;
    }
    if (this.mediaViewerItemIndex >= itemCount - 1) {
      this.mediaViewerItemIndex = 0;
      this.resetMediaViewerTransientState();
      return;
    }
    this.mediaViewerItemIndex += 1;
    this.resetMediaViewerTransientState();
  }

  private handleMediaViewerShare(): void {
    this.isMediaViewerDetailsVisible = false;
    const item = this.selectedMediaViewerItem();
    if (item === null || item.uri.length === 0) {
      this.mediaViewerActionStatus = 'Share unavailable: no selected media';
      return;
    }
    const subject = this.mediaViewerActionSubject();
    this.mediaViewerActionStatus = `Share preparing: ${subject}`;
    this.prepareMediaActionContent(item).then((content: MediaActionContent) => {
      if (!content.ok) {
        this.mediaViewerActionStatus = `Share unavailable: ${subject} (${content.errorMessage})`;
        return;
      }
      const want = this.mediaViewerShareWant(item, content.uri);
      if (want === null) {
        this.mediaViewerActionStatus = 'Share unavailable: no selected media';
        return;
      }
      this.mediaViewerActionStatus = `Share launching: ${subject} from cached media`;
      this.abilityContext().startAbility(want).then(() => {
        this.mediaViewerActionStatus = `Share launched: ${subject} from cached media`;
      }).catch((error: Error) => {
        this.mediaViewerActionStatus = `Share ready: ${subject} from cached media (${error.message})`;
      });
    }).catch((error: Error) => {
      this.mediaViewerActionStatus = `Share unavailable: ${subject} (${error.message})`;
    });
  }

  private handleMediaViewerSave(): void {
    this.isMediaViewerDetailsVisible = false;
    const item = this.selectedMediaViewerItem();
    if (item === null || item.uri.length === 0) {
      this.mediaViewerActionStatus = 'Save unavailable: no selected media';
      return;
    }
    const subject = this.mediaViewerActionSubject();
    const filename = this.mediaViewerFilename();
    this.mediaViewerActionStatus = `Save choosing location: ${subject}`;
    const documentPicker = new picker.DocumentViewPicker(this.abilityContext());
    const options: picker.DocumentSaveOptions = {
      newFileNames: [filename],
      autoCreateEmptyFile: true
    };
    documentPicker.save(options).then((saveUris: Array<string>) => {
      if (saveUris.length === 0) {
        this.mediaViewerActionStatus = `Save cancelled: ${subject}`;
        return;
      }
      const targetUri = saveUris[0];
      this.mediaViewerActionStatus = `Save reading: ${subject}`;
      this.readSavableMedia(item).then((mediaFile: SharedMediaReadResult) => {
        if (!mediaFile.ok) {
          this.mediaViewerActionStatus = `Save unavailable: ${subject} (${mediaFile.errorMessage})`;
          return;
        }
        this.writeSavedMedia(targetUri, mediaFile.data, mediaFile.size, subject);
      }).catch((error: Error) => {
        this.mediaViewerActionStatus = `Save unavailable: ${subject} (${error.message})`;
      });
    }).catch((error: Error) => {
      this.mediaViewerActionStatus = `Save unavailable: ${subject} (${error.message})`;
    });
  }

  private async readSavableMedia(item: TimelineMediaItem): Promise<SharedMediaReadResult> {
    if (this.isReadableSharedMediaUri(item.uri)) {
      return this.sharedMediaFileReader.readFileUri(item.uri);
    }
    const remoteUrl = this.remoteMediaDownloadUrl(item.uri);
    if (remoteUrl.length === 0) {
      return this.createSharedMediaResult(false, new ArrayBuffer(0), 0, this.mediaViewerFilename(), 'Only file, fd, content, datashare, http(s) and Matrix MXC media can be saved');
    }
    return this.downloadSavableMedia(remoteUrl, this.mediaViewerFilename());
  }

  private isReadableSharedMediaUri(uri: string): boolean {
    return uri.indexOf('file://') === 0 ||
      uri.indexOf('fd://') === 0 ||
      uri.indexOf('content://') === 0 ||
      uri.indexOf('datashare://') === 0;
  }

  private async downloadSavableMedia(url: string, filename: string): Promise<SharedMediaReadResult> {
    const request = http.createHttp();
    try {
      const response = await request.request(url, {
        method: http.RequestMethod.GET,
        header: this.mediaDownloadHeaders(),
        readTimeout: 60000,
        connectTimeout: 60000,
        expectDataType: http.HttpDataType.ARRAY_BUFFER,
        maxLimit: 104857600
      });
      const statusCode = response.responseCode as number;
      if (statusCode < 200 || statusCode >= 300) {
        return this.createSharedMediaResult(false, new ArrayBuffer(0), 0, filename, `HTTP ${statusCode}`);
      }
      if (!(response.result instanceof ArrayBuffer)) {
        return this.createSharedMediaResult(false, new ArrayBuffer(0), 0, filename, 'Downloaded media was not binary');
      }
      return this.createSharedMediaResult(true, response.result, response.result.byteLength, filename, '');
    } catch (error) {
      return this.createSharedMediaResult(false, new ArrayBuffer(0), 0, filename, `${error}`);
    } finally {
      request.destroy();
    }
  }

  private remoteMediaDownloadUrl(uri: string): string {
    if (uri.indexOf('http://') === 0 || uri.indexOf('https://') === 0) {
      return uri;
    }
    if (uri.indexOf('mxc://') === 0) {
      return this.resolveMxcDownloadUri(uri);
    }
    return '';
  }

  private mediaDownloadHeaders(): MediaDownloadHeaders {
    const accessToken = this.snapshot.session?.accessToken ?? '';
    if (accessToken.length === 0) {
      return {
        'Accept': '*/*',
        'User-Agent': 'ElementXHarmony/26.08.4'
      };
    }
    return {
      'Accept': '*/*',
      'Authorization': `Bearer ${accessToken}`,
      'User-Agent': 'ElementXHarmony/26.08.4'
    };
  }

  private createSharedMediaResult(ok: boolean, data: ArrayBuffer, size: number, filename: string, errorMessage: string): SharedMediaReadResult {
    return {
      ok: ok,
      data: data,
      size: size,
      filename: filename,
      errorMessage: errorMessage
    };
  }

  private writeSavedMedia(targetUri: string, data: ArrayBuffer, size: number, subject: string): void {
    let targetFile: fs.File | null = null;
    try {
      targetFile = fs.openSync(targetUri, fs.OpenMode.WRITE_ONLY | fs.OpenMode.CREATE | fs.OpenMode.TRUNC);
      const bytesWritten = fs.writeSync(targetFile.fd, data, { offset: 0, length: size });
      if (bytesWritten !== size) {
        this.mediaViewerActionStatus = `Save incomplete: ${subject} (${bytesWritten}/${size} bytes)`;
        return;
      }
      this.mediaViewerActionStatus = `Saved: ${subject}`;
    } catch (error) {
      this.mediaViewerActionStatus = `Save failed: ${subject} (${error})`;
    } finally {
      if (targetFile !== null) {
        try {
          fs.closeSync(targetFile);
        } catch (error) {
        }
      }
    }
  }

  private async prepareMediaActionContent(item: TimelineMediaItem): Promise<MediaActionContent> {
    const mediaFile = await this.readSavableMedia(item);
    if (!mediaFile.ok) {
      return this.createMediaActionContent(false, '', mediaFile.filename, mediaFile.errorMessage);
    }
    return this.writeMediaActionCache(mediaFile);
  }

  private writeMediaActionCache(mediaFile: SharedMediaReadResult): MediaActionContent {
    const filename = mediaFile.filename.length > 0 ? mediaFile.filename : this.mediaViewerFilename();
    const cacheDir = `${this.abilityContext().tempDir}/elementx-media-actions`;
    const cachePath = `${cacheDir}/${new Date().getTime()}-${this.safeCacheFilename(filename)}`;
    let cacheFile: fs.File | null = null;
    try {
      try {
        fs.mkdirSync(cacheDir, true);
      } catch (error) {
      }
      cacheFile = fs.openSync(cachePath, fs.OpenMode.WRITE_ONLY | fs.OpenMode.CREATE | fs.OpenMode.TRUNC);
      const bytesWritten = fs.writeSync(cacheFile.fd, mediaFile.data, { offset: 0, length: mediaFile.size });
      if (bytesWritten !== mediaFile.size) {
        return this.createMediaActionContent(false, '', filename, `Cached media write incomplete (${bytesWritten}/${mediaFile.size} bytes)`);
      }
      this.pruneMediaActionCache(cacheDir, cachePath);
      return this.createMediaActionContent(true, fileUri.getUriFromPath(cachePath), filename, '');
    } catch (error) {
      return this.createMediaActionContent(false, '', filename, `${error}`);
    } finally {
      if (cacheFile !== null) {
        try {
          fs.closeSync(cacheFile);
        } catch (error) {
        }
      }
    }
  }

  private safeCacheFilename(filename: string): string {
    const raw = filename.length > 0 ? filename : 'media';
    return raw.replace(/[^A-Za-z0-9._-]/g, '_');
  }

  private pruneMediaActionCache(cacheDir: string, currentPath: string): void {
    try {
      const nowSeconds = Math.floor(new Date().getTime() / 1000);
      const entries: MediaActionCacheEntry[] = [];
      const names = fs.listFileSync(cacheDir);
      for (let index = 0; index < names.length; index++) {
        const path = `${cacheDir}/${names[index]}`;
        const stat = fs.statSync(path);
        if (!stat.isFile()) {
          continue;
        }
        if (path !== currentPath && nowSeconds - stat.mtime > MEDIA_ACTION_CACHE_MAX_AGE_SECONDS) {
          fs.unlinkSync(path);
          continue;
        }
        entries.push({
          path: path,
          mtime: stat.mtime
        });
      }
      entries.sort((left: MediaActionCacheEntry, right: MediaActionCacheEntry): number => right.mtime - left.mtime);
      for (let index = MEDIA_ACTION_CACHE_MAX_FILES; index < entries.length; index++) {
        if (entries[index].path !== currentPath) {
          fs.unlinkSync(entries[index].path);
        }
      }
    } catch (error) {
    }
  }

  private createMediaActionContent(ok: boolean, uri: string, filename: string, errorMessage: string): MediaActionContent {
    return {
      ok: ok,
      uri: uri,
      filename: filename,
      errorMessage: errorMessage
    };
  }

  private handleMediaViewerOpenWith(): void {
    this.isMediaViewerDetailsVisible = false;
    const item = this.selectedMediaViewerItem();
    if (item === null || item.uri.length === 0) {
      this.mediaViewerActionStatus = 'Open with unavailable: no selected media';
      return;
    }
    const subject = this.mediaViewerActionSubject();
    this.mediaViewerActionStatus = `Open with preparing: ${subject}`;
    this.prepareMediaActionContent(item).then((content: MediaActionContent) => {
      if (!content.ok) {
        this.mediaViewerActionStatus = `Open with unavailable: ${subject} (${content.errorMessage})`;
        return;
      }
      const want = this.mediaViewerOpenWant(item, content.uri);
      if (want === null) {
        this.mediaViewerActionStatus = 'Open with unavailable: no selected media';
        return;
      }
      this.mediaViewerActionStatus = `Open with launching: ${subject} from cached media`;
      this.abilityContext().startAbility(want).then(() => {
        this.mediaViewerActionStatus = `Open with launched: ${subject} from cached media`;
      }).catch((error: Error) => {
        this.mediaViewerActionStatus = `Open with ready: ${subject} from cached media (${error.message})`;
      });
    }).catch((error: Error) => {
      this.mediaViewerActionStatus = `Open with unavailable: ${subject} (${error.message})`;
    });
  }

  private handleMediaViewerInfo(): void {
    this.isMediaViewerDetailsVisible = !this.isMediaViewerDetailsVisible;
    this.mediaViewerActionStatus = this.isMediaViewerDetailsVisible ? `Details shown: ${this.mediaViewerActionSubject()}` : '';
  }

  private handleMediaViewerViewInTimeline(): void {
    const event = this.selectedMediaViewerEvent();
    if (event === null) {
      this.mediaViewerActionStatus = 'Timeline event unavailable';
      return;
    }
    this.focusedPermalinkEventId = event.id;
    this.selectedTab = 1;
    this.closeMediaViewer();
  }

  private handleMediaViewerForward(): void {
    const row = this.mediaViewerAttachmentRow();
    if (row.length === 0) {
      this.mediaViewerActionStatus = 'Forward unavailable: no selected media';
      return;
    }
    const event = this.selectedMediaViewerEvent();
    this.messageDraft = event === null ? '' : event.body;
    this.pendingShareAttachmentRows = [row];
    this.isShareTargetPickerVisible = true;
    this.closeMediaViewer();
  }

  private normalizedRequestedMediaViewerIndex(index: number, itemCount: number): number {
    if (itemCount <= 0 || index < 0) {
      return 0;
    }
    if (index >= itemCount) {
      return itemCount - 1;
    }
    return index;
  }

  private selectedReadReceiptItems(): ReadReceiptSummary[] {
    const selected = this.snapshot.timeline.find((event: TimelineEvent) => event.id === this.selectedReadReceiptEventId);
    if (selected === undefined) {
      return [];
    }
    return this.eventReadReceipts(selected);
  }

  @Builder
  SettingsPanel() {
    Scroll() {
      Column({ space: 12 }) {
        this.SectionTitle('Settings')
        this.ProfileEditor()
        this.StatusRow('Notifications: mentions, keywords and quiet hours')
        this.NotificationPreview()
        this.ReadReceiptPreference()
        this.TimelineMediaPreviewPreference()
        this.BlockedUsersPreference()
        this.StatusRow('Privacy: typing notifications follow read receipt privacy')
        this.StatusRow('Appearance: follows system setting')
        this.SectionTitle('Connection')
        this.StatusRow(`Sync: ${this.snapshot.loggedInState?.sync.serviceState ?? 'idle'}`)
        this.StatusRow(`Push: ${this.snapshot.loggedInState?.pusherRegistrationState.message ?? 'Not registered'}`)
        this.StatusRow(`Network: ${this.snapshot.loggedInState?.networkStatus ?? 'disconnected'}`)
        this.SectionTitle('Security')
        ForEach(this.snapshot.securityRows, (row: string) => {
          this.StatusRow(row)
        })
      }
      .padding(16)
    }
    .id('settings_panel')
  }

  @Builder
  NotificationPreview() {
    Column({ space: 10 }) {
      Row() {
        Column({ space: 2 }) {
          Text('Message notification')
            .fontSize(16)
            .fontWeight(FontWeight.Medium)
            .fontColor('#1E293B')
          Text(this.notificationStatus.length > 0 ? this.notificationStatus : 'Bob DM with mark-read action')
            .fontSize(12)
            .fontColor(this.notificationStatus.indexOf('failed') >= 0 ? '#B42318' : '#64748B')
        }
        .alignItems(HorizontalAlign.Start)
        Blank()
        Button(this.isPublishingNotification ? 'Publishing' : 'Test')
          .height(40)
          .backgroundColor('#EEF2F7')
          .fontColor('#0F172A')
          .borderRadius(20)
          .onClick(() => {
            this.handlePublishNotification();
          })
          .id('settings_publish_notification_button')
      }
      .width('100%')
    }
    .alignItems(HorizontalAlign.Start)
    .padding(12)
    .borderRadius(8)
    .backgroundColor('#FFFFFF')
    .id('settings_notification_preview')
  }

  @Builder
  ReadReceiptPreference() {
    Column({ space: 10 }) {
      Row() {
        Column({ space: 2 }) {
          Text(`Read receipts: ${this.isPresenceSharingEnabled() ? 'public' : 'private'}`)
            .fontSize(16)
            .fontWeight(FontWeight.Medium)
            .fontColor('#1E293B')
          Text(`Timeline receipts: ${this.snapshot.session?.renderReadReceipts ? 'shown' : 'hidden'}`)
            .fontSize(12)
            .fontColor('#64748B')
        }
        .alignItems(HorizontalAlign.Start)
        Blank()
        Button(this.isPresenceSharingEnabled() ? 'Use private' : 'Use public')
          .height(40)
          .backgroundColor('#EEF2F7')
          .fontColor('#0F172A')
          .borderRadius(20)
          .onClick(() => {
            this.handleToggleReadReceiptPreference();
          })
          .id('settings_read_receipt_toggle')
      }
      .width('100%')
      if (this.privacyError.length > 0) {
        Text(this.privacyError)
          .fontSize(13)
          .fontColor('#B42318')
          .lineHeight(18)
          .width('100%')
          .id('settings_privacy_error')
      }
    }
    .alignItems(HorizontalAlign.Start)
    .padding(12)
    .borderRadius(8)
    .backgroundColor('#FFFFFF')
    .id('settings_read_receipt_preference')
  }

  @Builder
  TimelineMediaPreviewPreference() {
    Column({ space: 10 }) {
      Column({ space: 2 }) {
        Text(`Timeline media: ${this.timelineMediaPreviewModeLabel(this.currentTimelineMediaPreviewMode())}`)
          .fontSize(16)
          .fontWeight(FontWeight.Medium)
          .fontColor('#1E293B')
        Text(`Current room: ${this.shouldShowTimelineMediaPreview() ? 'previews shown' : 'previews hidden'}`)
          .fontSize(12)
          .fontColor('#64748B')
      }
      .alignItems(HorizontalAlign.Start)
      Row({ space: 8 }) {
        Button('Always')
          .height(40)
          .backgroundColor(this.currentTimelineMediaPreviewMode() === TimelineMediaPreviewMode.AlwaysShow ? '#0F766E' : '#EEF2F7')
          .fontColor(this.currentTimelineMediaPreviewMode() === TimelineMediaPreviewMode.AlwaysShow ? '#FFFFFF' : '#0F172A')
          .borderRadius(20)
          .onClick(() => {
            this.handleSetTimelineMediaPreviewMode(TimelineMediaPreviewMode.AlwaysShow);
          })
          .id('settings_media_preview_always')
        Button('Private')
          .height(40)
          .backgroundColor(this.currentTimelineMediaPreviewMode() === TimelineMediaPreviewMode.PrivateRooms ? '#0F766E' : '#EEF2F7')
          .fontColor(this.currentTimelineMediaPreviewMode() === TimelineMediaPreviewMode.PrivateRooms ? '#FFFFFF' : '#0F172A')
          .borderRadius(20)
          .onClick(() => {
            this.handleSetTimelineMediaPreviewMode(TimelineMediaPreviewMode.PrivateRooms);
          })
          .id('settings_media_preview_private')
        Button('Hide')
          .height(40)
          .backgroundColor(this.currentTimelineMediaPreviewMode() === TimelineMediaPreviewMode.AlwaysHide ? '#0F766E' : '#EEF2F7')
          .fontColor(this.currentTimelineMediaPreviewMode() === TimelineMediaPreviewMode.AlwaysHide ? '#FFFFFF' : '#0F172A')
          .borderRadius(20)
          .onClick(() => {
            this.handleSetTimelineMediaPreviewMode(TimelineMediaPreviewMode.AlwaysHide);
          })
          .id('settings_media_preview_hide')
      }
      .width('100%')
      if (this.mediaPreviewError.length > 0) {
        Text(this.mediaPreviewError)
          .fontSize(13)
          .fontColor('#B42318')
          .lineHeight(18)
          .width('100%')
          .id('settings_media_preview_error')
      }
    }
    .alignItems(HorizontalAlign.Start)
    .padding(12)
    .borderRadius(8)
    .backgroundColor('#FFFFFF')
    .id('settings_timeline_media_preview')
  }

  @Builder
  BlockedUsersPreference() {
    if (this.blockedUserIds().length > 0) {
      Row() {
        Column({ space: 2 }) {
          Text('Blocked users')
            .fontSize(16)
            .fontWeight(FontWeight.Medium)
            .fontColor('#1E293B')
            .maxLines(1)
            .textOverflow({ overflow: TextOverflow.Ellipsis })
          Text('Messages from blocked users are hidden')
            .fontSize(12)
            .fontColor('#64748B')
            .maxLines(1)
            .textOverflow({ overflow: TextOverflow.Ellipsis })
        }
        .alignItems(HorizontalAlign.Start)
        .layoutWeight(1)
        Text(`${this.blockedUserIds().length}`)
          .fontSize(14)
          .fontWeight(FontWeight.Bold)
          .fontColor('#FFFFFF')
          .textAlign(TextAlign.Center)
          .width(32)
          .height(32)
          .borderRadius(16)
          .backgroundColor('#0F766E')
          .margin({ left: 10 })
      }
      .width('100%')
      .padding(12)
      .borderRadius(8)
      .backgroundColor('#FFFFFF')
      .onClick(() => {
        this.openBlockedUsersSheet();
      })
      .id('settings_blocked_users_entry')
    }
  }

  @Builder
  BlockedUsersSheet() {
    Column() {
      Blank()
        .layoutWeight(1)
      Column({ space: 12 }) {
        Row() {
          Column({ space: 2 }) {
            Text('Blocked users')
              .fontSize(18)
              .fontWeight(FontWeight.Bold)
              .fontColor('#0F172A')
            Text(`${this.blockedUserIds().length} blocked`)
              .fontSize(12)
              .fontColor('#64748B')
          }
          .alignItems(HorizontalAlign.Start)
          Blank()
          Button('Close')
            .height(38)
            .backgroundColor('#EEF2F7')
            .fontColor('#0F172A')
            .borderRadius(19)
            .onClick(() => {
              this.closeBlockedUsersSheet();
            })
            .id('blocked_users_close_button')
        }
        .width('100%')
        if (this.blockedUserIds().length === 0) {
          Text('You have no blocked users')
            .fontSize(14)
            .fontColor('#64748B')
            .lineHeight(20)
            .width('100%')
            .id('blocked_users_empty')
        } else {
          ForEach(this.blockedUserIds(), (userId: string) => {
            this.BlockedUserRow(userId)
          }, (userId: string) => userId)
        }
        if (this.blockedUsersPendingUnblockUserId.length > 0) {
          Column({ space: 10 }) {
            Text(`Unblock ${this.displayNameFromUserId(this.blockedUsersPendingUnblockUserId)}?`)
              .fontSize(15)
              .fontWeight(FontWeight.Medium)
              .fontColor('#0F172A')
              .width('100%')
            Text('Their messages will be shown again.')
              .fontSize(13)
              .fontColor('#64748B')
              .width('100%')
            Row({ space: 8 }) {
              Button('Cancel')
                .height(40)
                .layoutWeight(1)
                .backgroundColor('#EEF2F7')
                .fontColor('#0F172A')
                .borderRadius(20)
                .onClick(() => {
                  this.cancelBlockedUsersUnblock();
                })
                .id('blocked_users_cancel_unblock')
              Button(this.isUnblockingBlockedUser ? 'Unblocking' : 'Unblock')
                .height(40)
                .layoutWeight(1)
                .backgroundColor('#0F766E')
                .fontColor('#FFFFFF')
                .borderRadius(20)
                .enabled(!this.isUnblockingBlockedUser)
                .onClick(() => {
                  this.confirmBlockedUsersUnblock();
                })
                .id('blocked_users_confirm_unblock')
            }
            .width('100%')
          }
          .width('100%')
          .padding(12)
          .borderRadius(8)
          .backgroundColor('#F8FAFC')
          .id('blocked_users_confirm_panel')
        }
        if (this.blockedUsersStatus.length > 0) {
          Text(this.blockedUsersStatus)
            .fontSize(13)
            .fontColor('#475569')
            .lineHeight(18)
            .width('100%')
            .id('blocked_users_status')
        }
        if (this.blockedUsersError.length > 0) {
          Text(this.blockedUsersError)
            .fontSize(13)
            .fontColor('#B42318')
            .lineHeight(18)
            .width('100%')
            .id('blocked_users_error')
        }
      }
      .width('100%')
      .padding(20)
      .borderRadius({ topLeft: 8, topRight: 8 })
      .backgroundColor('#FFFFFF')
      .offset({ y: -120 })
    }
    .width('100%')
    .height('100%')
    .backgroundColor('#66000000')
    .zIndex(35)
    .id('blocked_users_sheet')
  }

  @Builder
  BlockedUserRow(userId: string) {
    Row() {
      Text(this.initialsFromUserId(userId))
        .fontSize(14)
        .fontWeight(FontWeight.Bold)
        .fontColor('#FFFFFF')
        .textAlign(TextAlign.Center)
        .width(36)
        .height(36)
        .borderRadius(18)
        .backgroundColor('#0F766E')
      Column({ space: 2 }) {
        Text(this.displayNameFromUserId(userId))
          .fontSize(15)
          .fontWeight(FontWeight.Medium)
          .fontColor('#1E293B')
        Text(userId)
          .fontSize(12)
          .fontColor('#64748B')
      }
      .alignItems(HorizontalAlign.Start)
      .margin({ left: 10 })
      Blank()
      Button('Unblock')
        .height(38)
        .backgroundColor('#EEF2F7')
        .fontColor('#0F172A')
        .borderRadius(19)
        .onClick(() => {
          this.requestBlockedUsersUnblock(userId);
        })
        .id(`blocked_user_unblock_${this.safeId(userId)}`)
    }
    .width('100%')
    .padding(12)
    .borderRadius(8)
    .backgroundColor('#F8FAFC')
    .gesture(
      LongPressGesture({ repeat: false })
        .onAction(() => {
          this.copyBlockedUserIdToClipboard(userId);
        })
    )
    .id(`blocked_user_row_${this.safeId(userId)}`)
  }

  @Builder
  ProfileEditor() {
    Column({ space: 10 }) {
      Row() {
        Text(this.snapshot.session?.account.avatarInitials ?? 'EX')
          .fontSize(14)
          .fontWeight(FontWeight.Bold)
          .fontColor('#FFFFFF')
          .textAlign(TextAlign.Center)
          .width(36)
          .height(36)
          .borderRadius(18)
          .backgroundColor('#0F766E')
        Column({ space: 2 }) {
          Text(this.snapshot.session?.account.displayName ?? 'Signed out')
            .fontSize(16)
            .fontWeight(FontWeight.Medium)
            .fontColor('#1E293B')
          Text(this.snapshot.session?.account.userId ?? '')
            .fontSize(12)
            .fontColor('#64748B')
        }
        .alignItems(HorizontalAlign.Start)
        .margin({ left: 10 })
      }
      .width('100%')
      TextInput({ text: this.displayNameDraft, placeholder: 'Display name' })
        .onChange((value: string) => {
          this.displayNameDraft = value;
        })
        .id('settings_display_name_input')
      TextInput({ text: this.userStatusDraft, placeholder: 'Status' })
        .onChange((value: string) => {
          this.userStatusDraft = value;
        })
        .id('settings_user_status_input')
      if (this.profileError.length > 0) {
        Text(this.profileError)
          .fontSize(13)
          .fontColor('#B42318')
          .lineHeight(18)
          .width('100%')
          .id('settings_profile_error')
      }
      Button(this.isUpdatingProfile ? 'Saving' : 'Save profile')
        .height(44)
        .width('100%')
        .backgroundColor('#191B21')
        .fontColor('#FFFFFF')
        .borderRadius(22)
        .onClick(() => {
          this.handleUpdateProfile();
        })
        .id('settings_save_profile')
    }
    .alignItems(HorizontalAlign.Start)
    .padding(12)
    .borderRadius(8)
    .backgroundColor('#FFFFFF')
    .id('settings_profile_editor')
  }

  @Builder
  DevicesPanel() {
    Scroll() {
      Column({ space: 12 }) {
        this.SectionTitle('Link new device')
        ForEach(this.snapshot.deviceRows, (row: string) => {
          this.StatusRow(row)
        })
        this.SectionTitle('Incoming links')
        ForEach(this.snapshot.intentRows, (row: string) => {
          this.StatusRow(row)
        })
      }
      .padding(16)
    }
    .id('devices_panel')
  }

  @Builder
  SectionTitle(title: string) {
    Text(title)
      .fontSize(18)
      .fontWeight(FontWeight.Bold)
      .fontColor('#18202A')
      .width('100%')
      .margin({ top: 8, bottom: 2 })
  }

  @Builder
  StatusRow(text: string) {
    Text(text)
      .fontSize(14)
      .fontColor('#334155')
      .textAlign(TextAlign.Start)
      .lineHeight(20)
      .padding(12)
      .width('100%')
      .borderRadius(8)
      .backgroundColor('#FFFFFF')
  }

  @Builder
  SyncChip() {
    Text(this.syncChipText())
      .fontSize(12)
      .fontColor('#0F5132')
      .textAlign(TextAlign.Center)
      .height(28)
      .padding({ left: 10, right: 10 })
      .borderRadius(14)
      .backgroundColor('#D1FAE5')
      .id('sync_indicator_chip')
  }

  private syncChipText(): string {
    const state = this.snapshot.loggedInState?.sync.indicatorState ?? 'hidden';
    if (state === 'syncing') {
      return 'Syncing';
    }
    if (state === 'server_unreachable') {
      return 'Server unreachable';
    }
    return '';
  }

  private selectedRoomName(): string {
    const roomId = this.visibleTimelineRoomId();
    return this.roomNameForRoomId(roomId);
  }

  private timelineRoomTitle(): string {
    if (this.visibleTimelineRoomTitle.length > 0) {
      return this.visibleTimelineRoomTitle;
    }
    return this.selectedRoomName();
  }

  private roomNameForRoomId(roomId: string): string {
    const room = this.snapshot.rooms.find((item: RoomSummary) => item.id === roomId);
    if (room === undefined) {
      return 'Timeline';
    }
    return room.name;
  }

  private refreshVisibleTimelineRoomTitle(roomId: string): void {
    this.visibleTimelineRoomTitle = this.roomNameForRoomId(roomId);
  }

  private visibleTimelineRoomId(): string {
    if (this.snapshot.timeline.length > 0) {
      return this.snapshot.timeline[0].roomId;
    }
    return this.snapshot.selectedRoomId;
  }

  private selectedTimelineRoom(): RoomSummary | null {
    const roomId = this.visibleTimelineRoomId();
    const room = this.snapshot.rooms.find((item: RoomSummary) => item.id === roomId);
    return room === undefined ? null : room;
  }

  private roomUnreadBadgeLabel(room: RoomSummary): string {
    if (room.unreadCount > 0) {
      return room.unreadCount.toString();
    }
    return room.isMarkedUnread ? '!' : '';
  }

  private roomHasNewContent(room: RoomSummary): boolean {
    return room.unreadCount > 0 || room.isMarkedUnread;
  }

  private roomListContextMenuRoom(): RoomSummary | null {
    const room = this.snapshot.rooms.find((item: RoomSummary) => item.id === this.roomListContextMenuRoomId);
    return room === undefined ? null : room;
  }

  private roomListContextMenuRoomName(): string {
    const room = this.roomListContextMenuRoom();
    return room === null ? 'Room' : room.name;
  }

  private roomListContextMenuRoomTopic(): string {
    const room = this.roomListContextMenuRoom();
    return room === null ? '' : room.topic;
  }

  private roomListContextMenuHasNewContent(): boolean {
    const room = this.roomListContextMenuRoom();
    return room !== null && this.roomHasNewContent(room);
  }

  private roomListContextMenuReadLabel(): string {
    if (this.isUpdatingRoomListContextMenu) {
      return this.roomListContextMenuHasNewContent() ? 'Marking read' : 'Marking unread';
    }
    return this.roomListContextMenuHasNewContent() ? 'Mark as read' : 'Mark as unread';
  }

  private roomListContextMenuReadButtonId(): string {
    return this.roomListContextMenuHasNewContent() ? 'room_list_context_mark_read' : 'room_list_context_mark_unread';
  }

  private roomListContextMenuIsFavorite(): boolean {
    const room = this.roomListContextMenuRoom();
    return room !== null && room.isFavorite;
  }

  private roomListContextMenuFavoriteLabel(): string {
    if (this.isUpdatingRoomListContextMenu) {
      return this.roomListContextMenuIsFavorite() ? 'Updating favourite' : 'Updating favourite';
    }
    return this.roomListContextMenuIsFavorite() ? 'Favourited' : 'Favourite';
  }

  private roomListContextMenuFavoriteButtonId(): string {
    return this.roomListContextMenuIsFavorite() ? 'room_list_context_favourited' : 'room_list_context_favourite';
  }

  private roomListContextMenuCanReportRoom(): boolean {
    return this.snapshot.session !== null && this.roomListContextMenuRoom() !== null;
  }

  private roomDetailsRoom(): RoomSummary | null {
    const room = this.snapshot.rooms.find((item: RoomSummary) => item.id === this.roomDetailsRoomId);
    return room === undefined ? null : room;
  }

  private roomDetailsRoomName(): string {
    const room = this.roomDetailsRoom();
    return room === null ? 'Room' : room.name;
  }

  private roomDetailsRoomTopic(): string {
    const room = this.roomDetailsRoom();
    return room === null ? '' : room.topic;
  }

  private roomDetailsRoomIdLabel(): string {
    return this.roomDetailsRoomId.length === 0 ? '' : `Room ID: ${this.roomDetailsRoomId}`;
  }

  private roomDetailsHasNewContent(): boolean {
    const room = this.roomDetailsRoom();
    return room !== null && this.roomHasNewContent(room);
  }

  private roomDetailsReadLabel(): string {
    if (this.isUpdatingRoomDetails) {
      return this.roomDetailsHasNewContent() ? 'Marking read' : 'Marking unread';
    }
    return this.roomDetailsHasNewContent() ? 'Mark as read' : 'Mark as unread';
  }

  private roomDetailsReadButtonId(): string {
    return this.roomDetailsHasNewContent() ? 'room_details_mark_read' : 'room_details_mark_unread';
  }

  private roomDetailsIsFavorite(): boolean {
    const room = this.roomDetailsRoom();
    return room !== null && room.isFavorite;
  }

  private roomDetailsFavoriteLabel(): string {
    if (this.isUpdatingRoomDetails) {
      return 'Updating favourite';
    }
    return this.roomDetailsIsFavorite() ? 'Favourited' : 'Favourite';
  }

  private roomDetailsFavoriteButtonId(): string {
    return this.roomDetailsIsFavorite() ? 'room_details_favourited' : 'room_details_favourite';
  }

  private roomDetailsCanReportRoom(): boolean {
    const room = this.roomDetailsRoom();
    return this.snapshot.session !== null && room !== null && !room.isDirect;
  }

  private reportRoom(): RoomSummary | null {
    const room = this.snapshot.rooms.find((item: RoomSummary) => item.id === this.reportRoomId);
    return room === undefined ? null : room;
  }

  private reportRoomName(): string {
    const room = this.reportRoom();
    return room === null ? 'Room' : room.name;
  }

  private reportRoomSubmitLabel(): string {
    if (this.isReportingRoom) {
      return this.reportRoomAlreadySubmitted ? 'Retrying leave' : 'Reporting';
    }
    return this.reportRoomAlreadySubmitted ? 'Retry leave' : 'Report';
  }

  private isTimelineMarkedUnread(): boolean {
    const room = this.selectedTimelineRoom();
    return room !== null && room.isMarkedUnread;
  }

  private currentTimelineMediaPreviewMode(): TimelineMediaPreviewMode {
    return this.snapshot.session?.timelineMediaPreviewMode ?? TimelineMediaPreviewMode.AlwaysShow;
  }

  private timelineMediaPreviewModeLabel(mode: TimelineMediaPreviewMode): string {
    if (mode === TimelineMediaPreviewMode.PrivateRooms) {
      return 'private rooms';
    }
    if (mode === TimelineMediaPreviewMode.AlwaysHide) {
      return 'hidden';
    }
    return 'always shown';
  }

  private shouldShowTimelineMediaPreview(): boolean {
    const mode = this.currentTimelineMediaPreviewMode();
    if (mode === TimelineMediaPreviewMode.AlwaysShow) {
      return true;
    }
    if (mode === TimelineMediaPreviewMode.AlwaysHide) {
      return false;
    }
    const room = this.selectedTimelineRoom();
    return room !== null && room.isDirect;
  }

  private restorePersistedSession(): void {
    const context = this.abilityContext();
    this.viewModel.restorePersistedLatestSession(context).then((restored: ClientSnapshot) => {
      this.snapshot = restored;
      if (restored.session !== null) {
        this.authState = ClientAuthState.SignedIn;
        this.syncProfileDrafts();
      }
      this.consumeLaunchIntent();
    }).catch(() => {
      this.snapshot = this.viewModel.restoreLatestSession();
      this.consumeLaunchIntent();
    });
  }

  private consumeLaunchIntent(): void {
    const payload: LaunchIntentPayload = LaunchIntentStore.consume();
    if (payload.action.length === 0 && payload.uri.length === 0 && payload.command.length === 0) {
      return;
    }
    if (payload.command === 'mark_room_read' && payload.roomId.length > 0) {
      this.clearPermalinkFocus();
      this.clearPermalinkSheets();
      this.snapshot = this.viewModel.selectRoom(this.snapshot, payload.roomId);
      this.refreshVisibleTimelineRoomTitle(payload.roomId);
      this.viewModel.markSelectedRoomAsRead(this.snapshot).then((result: MarkRoomReadResult) => {
        if (result.ok) {
          this.snapshot = result.snapshot;
        }
      }).catch(() => {
      });
      return;
    }
    if (payload.command === 'open_room' && payload.roomId.length > 0) {
      this.clearPermalinkFocus();
      this.clearPermalinkSheets();
      this.snapshot = this.viewModel.selectRoom(this.snapshot, payload.roomId);
      this.refreshVisibleTimelineRoomTitle(payload.roomId);
      this.selectedTab = 1;
      if (this.snapshot.session !== null) {
        this.authState = ClientAuthState.SignedIn;
        this.syncProfileDrafts();
      }
      this.handleTimelineVisibleForRead();
      return;
    }
    if (payload.command === 'incoming_share') {
      this.clearPermalinkFocus();
      this.clearPermalinkSheets();
      this.snapshot = this.viewModel.handleIntent(payload.action, payload.uri);
      const sharedDraft = this.sharedMessageDraft(payload);
      const sharedAttachmentRows = this.sharedAttachmentRows(payload);
      if (sharedDraft.length > 0 || sharedAttachmentRows.length > 0) {
        this.messageDraft = sharedDraft;
        this.pendingShareAttachmentRows = sharedAttachmentRows;
        this.isShareTargetPickerVisible = this.snapshot.session !== null;
        if (!this.isShareTargetPickerVisible) {
          this.selectedTab = 1;
        }
      }
      if (this.snapshot.session !== null) {
        this.authState = ClientAuthState.SignedIn;
        this.syncProfileDrafts();
      }
      return;
    }
    if (payload.command === 'login_link') {
      this.snapshot = this.viewModel.handleIntent(payload.action, payload.uri);
      const accountProvider = this.queryParameter(payload.uri, 'account_provider');
      const loginHint = this.queryParameter(payload.uri, 'login_hint');
      if (accountProvider.length > 0) {
        this.homeserver = accountProvider;
      }
      const hintedUsername = this.usernameFromLoginHint(loginHint);
      if (hintedUsername.length > 0) {
        this.username = hintedUsername;
      }
      this.signInError = '';
      this.pendingPermalinkUri = '';
      this.pendingPermalinkMessage = '';
      this.clearPermalinkFocus();
      this.clearPermalinkSheets();
      if (this.snapshot.session !== null) {
        this.authState = ClientAuthState.SignedIn;
        this.selectedTab = 3;
        this.syncProfileDrafts();
      } else {
        this.authState = ClientAuthState.ManualLogin;
      }
      return;
    }
    if (payload.command === 'oauth') {
      this.snapshot = this.viewModel.handleIntent(payload.action, payload.uri);
      const oauthError = this.queryParameter(payload.uri, 'error');
      const loginToken = this.oauthLoginToken(payload.uri);
      const oauthCode = this.queryParameter(payload.uri, 'code');
      this.pendingPermalinkUri = '';
      this.pendingPermalinkMessage = '';
      this.clearPermalinkFocus();
      this.clearJumpToUnread();
      this.clearPermalinkSheets();
      if (this.snapshot.session !== null) {
        this.authState = ClientAuthState.SignedIn;
        this.selectedTab = 3;
        this.syncProfileDrafts();
      } else if (loginToken.length > 0) {
        this.handleOAuthTokenSignIn(payload.uri, loginToken);
      } else if (oauthCode.length > 0) {
        this.signInError = 'OAuth authorization code callback received; Matrix SDK OIDC exchange is still pending';
        this.authState = ClientAuthState.ManualLogin;
      } else {
        this.signInError = oauthError.length > 0 ? `OAuth returned ${oauthError}` : 'OAuth callback received';
        this.authState = ClientAuthState.ManualLogin;
      }
      return;
    }
    if (payload.command === 'permalink') {
      this.snapshot = this.viewModel.handleIntent(payload.action, payload.uri);
      if (this.snapshot.session !== null) {
        this.authState = ClientAuthState.SignedIn;
        this.syncProfileDrafts();
      }
      const roomId = this.roomIdFromPermalink(payload.uri);
      const eventId = this.eventIdFromPermalink(payload.uri);
      const threadId = this.threadIdFromPermalink(payload.uri);
      const userId = this.userIdFromPermalink(payload.uri);
      const roomIdOrAlias = this.roomIdOrAliasFromPermalink(payload.uri);
      const serverNames = this.serverNamesFromPermalink(payload.uri);
      if (roomId.length > 0 && this.snapshot.session !== null) {
        this.clearPermalinkSheets();
        this.snapshot = this.viewModel.selectRoom(this.snapshot, roomId);
        this.refreshVisibleTimelineRoomTitle(roomId);
        const focusedEventId = threadId.length > 0 ? threadId : eventId;
        if (focusedEventId.length > 0) {
          this.snapshot = this.viewModel.ensureFocusedPermalinkEvent(this.snapshot, roomId, focusedEventId);
        }
        this.selectedTab = 1;
        this.pendingPermalinkUri = '';
        this.pendingPermalinkMessage = '';
        this.focusedPermalinkThreadId = threadId;
        this.focusedPermalinkEventId = focusedEventId;
        this.handleTimelineVisibleForRead();
        return;
      }
      if (userId.length > 0 && this.snapshot.session !== null) {
        this.showPermalinkUserProfile(userId);
        return;
      }
      if (roomIdOrAlias.length > 0 && this.snapshot.session !== null) {
        this.showPermalinkRoomPreview(roomIdOrAlias, serverNames);
        return;
      }
      this.pendingPermalinkUri = payload.uri;
      this.pendingPermalinkMessage = this.permalinkMessage(payload.uri);
      this.clearPermalinkFocus();
      this.clearPermalinkSheets();
      if (this.snapshot.session !== null) {
        this.selectedTab = 3;
      }
      return;
    }
    this.snapshot = this.viewModel.handleIntent(payload.action, payload.uri);
    if (this.snapshot.session !== null) {
      this.authState = ClientAuthState.SignedIn;
      this.syncProfileDrafts();
    }
  }

  private handleStoredLaunchIntentChanged(): void {
    if (this.storedLaunchIntentPayload.length === 0) {
      return;
    }
    this.consumeLaunchIntent();
  }

  private sharedMessageDraft(payload: LaunchIntentPayload): string {
    if (payload.shareText.length > 0) {
      return payload.shareText;
    }
    return '';
  }

  private sharedAttachmentRows(payload: LaunchIntentPayload): string[] {
    const rows: string[] = [];
    for (let index = 0; index < payload.shareUris.length; index += 1) {
      const mimeType = index < payload.shareMimeTypes.length && payload.shareMimeTypes[index].length > 0
        ? payload.shareMimeTypes[index]
        : 'application/octet-stream';
      rows.push(`${mimeType} ${payload.shareUris[index]}`);
    }
    return rows;
  }

  private shareAttachmentKey(row: string): string {
    return row.replace(/[^a-zA-Z0-9]/g, '_');
  }

  private handleShareTargetRoom(roomId: string): void {
    this.clearPermalinkFocus();
    this.snapshot = this.viewModel.selectRoom(this.snapshot, roomId);
    this.refreshVisibleTimelineRoomTitle(roomId);
    this.selectedTab = 1;
    this.isShareTargetPickerVisible = false;
    this.handleTimelineVisibleForRead();
  }

  private closeShareTargetPicker(): void {
    this.isShareTargetPickerVisible = false;
    this.messageDraft = '';
    this.pendingShareAttachmentRows = [];
  }

  private roomIdFromPermalink(uri: string): string {
    const haystack = this.normalizedPermalink(uri);
    for (let index = 0; index < this.snapshot.rooms.length; index += 1) {
      const room = this.snapshot.rooms[index];
      if (this.permalinkMatchesRoom(haystack, room)) {
        return room.id;
      }
    }
    if (haystack.indexOf('@bob:') >= 0 || haystack.indexOf('/bob') >= 0) {
      return 'dm-bob';
    }
    return '';
  }

  private userIdFromPermalink(uri: string): string {
    const segments = this.permalinkPathSegments(uri);
    if (segments.length === 0) {
      return '';
    }
    if (segments[0] === 'user' && segments.length > 1) {
      return segments[1];
    }
    if (segments[0].startsWith('@')) {
      return segments[0];
    }
    return '';
  }

  private roomIdOrAliasFromPermalink(uri: string): string {
    const segments = this.permalinkPathSegments(uri);
    if (segments.length === 0) {
      return '';
    }
    if (segments[0] === 'room' && segments.length > 1) {
      return segments[1];
    }
    if (segments[0].startsWith('@') || segments[0] === 'user') {
      return '';
    }
    return segments[0];
  }

  private eventIdFromPermalink(uri: string): string {
    const segments = this.permalinkPathSegments(uri);
    if (segments.length < 2) {
      return '';
    }
    if (segments[0] === 'room' && segments.length >= 3) {
      return segments[2];
    }
    if (segments[0] === 'user') {
      return '';
    }
    return segments[1];
  }

  private threadIdFromPermalink(uri: string): string {
    const threadId = this.queryParameter(uri, 'thread_id');
    if (threadId.length > 0) {
      return threadId;
    }
    const camelThreadId = this.queryParameter(uri, 'threadId');
    if (camelThreadId.length > 0) {
      return camelThreadId;
    }
    return this.queryParameter(uri, 'thread');
  }

  private serverNamesFromPermalink(uri: string): string[] {
    return this.queryParameters(uri, 'via');
  }

  private permalinkMatchesRoom(haystack: string, room: RoomSummary): boolean {
    const roomId = room.id.toLowerCase();
    const roomName = room.name.toLowerCase();
    const roomSlug = this.slug(room.name);
    if (haystack.indexOf(roomId) >= 0 || haystack.indexOf(roomName) >= 0 || haystack.indexOf(roomSlug) >= 0) {
      return true;
    }
    if (room.id === 'room-general' && haystack.indexOf('element-x-general') >= 0) {
      return true;
    }
    return room.isDirect && haystack.indexOf(`/${roomSlug}`) >= 0;
  }

  private normalizedPermalink(uri: string): string {
    const decoded = this.safeDecode(uri).toLowerCase();
    return decoded.replace(/%23/g, '#').replace(/\+/g, ' ');
  }

  private permalinkMessage(uri: string): string {
    const normalized = this.normalizedPermalink(uri);
    if (normalized.indexOf('/@') >= 0 || normalized.indexOf('#/@') >= 0) {
      return 'User permalink is ready, but this client has not opened the member profile flow yet.';
    }
    if (normalized.indexOf('/!') >= 0 || normalized.indexOf('/#') >= 0) {
      return 'Room permalink is not in the joined-room list on this fixture session.';
    }
    return 'Permalink was received and is pending a matching client route.';
  }

  private closePermalinkSheet(): void {
    this.pendingPermalinkUri = '';
    this.pendingPermalinkMessage = '';
    this.clearPermalinkFocus();
    this.snapshot = this.viewModel.clearIntent();
  }

  private showPermalinkUserProfile(userId: string): void {
    this.clearPermalinkFocus();
    this.clearRoomPreviewSheet();
    this.pendingPermalinkUri = '';
    this.pendingPermalinkMessage = '';
    const profileResult: UserProfileResult = this.viewModel.getUserProfile(this.snapshot, userId);
    if (profileResult.ok && profileResult.profile !== null) {
      this.pendingUserProfileUserId = profileResult.profile.userId;
      this.pendingUserProfileName = profileResult.profile.displayName;
      this.pendingUserProfileStatus = profileResult.profile.status;
      this.pendingUserProfileError = '';
    } else {
      this.pendingUserProfileUserId = userId;
      this.pendingUserProfileName = this.displayNameFromUserId(userId);
      this.pendingUserProfileStatus = '';
      this.pendingUserProfileError = profileResult.errorMessage;
    }
    this.pendingUserProfileActionStatus = '';
    this.pendingUserProfileIgnored = this.isPendingUserIgnored();
    this.selectedTab = 3;
  }

  private showPermalinkRoomPreview(roomIdOrAlias: string, serverNames: string[]): void {
    this.clearPermalinkFocus();
    this.clearUserProfileSheet();
    this.pendingPermalinkUri = '';
    this.pendingPermalinkMessage = '';
    const previewResult: RoomPreviewResult = this.viewModel.getRoomPreview(this.snapshot, roomIdOrAlias, serverNames);
    this.pendingRoomPreviewId = roomIdOrAlias;
    this.pendingRoomPreviewServers = serverNames;
    if (previewResult.ok && previewResult.preview !== null) {
      this.pendingRoomPreviewName = previewResult.preview.name;
      this.pendingRoomPreviewTopic = previewResult.preview.topic;
      this.pendingRoomPreviewError = previewResult.preview.canJoin ? '' : 'Room cannot be joined from this preview';
    } else {
      this.pendingRoomPreviewName = roomIdOrAlias;
      this.pendingRoomPreviewTopic = 'Room preview unavailable';
      this.pendingRoomPreviewError = previewResult.errorMessage;
    }
    this.selectedTab = 3;
  }

  private handleStartPermalinkDm(): void {
    if (this.isStartingPermalinkDm) {
      return;
    }
    this.isStartingPermalinkDm = true;
    this.pendingUserProfileError = '';
    this.viewModel.createDirectRoom(this.snapshot, this.pendingUserProfileUserId).then((result: JoinRoomResult) => {
      this.isStartingPermalinkDm = false;
      if (!result.ok) {
        this.pendingUserProfileError = result.errorMessage;
        return;
      }
      this.snapshot = result.snapshot;
      this.selectedTab = 1;
      this.clearUserProfileSheet();
      this.handleTimelineVisibleForRead();
    }).catch((error: Error) => {
      this.isStartingPermalinkDm = false;
      this.pendingUserProfileError = `${error}`;
    });
  }

  private handleToggleIgnoredUser(): void {
    if (this.isUpdatingIgnoredUser) {
      return;
    }
    this.isUpdatingIgnoredUser = true;
    this.pendingUserProfileError = '';
    this.pendingUserProfileActionStatus = this.pendingUserProfileIgnored ? 'Unblocking user' : 'Blocking user';
    const nextIgnored = !this.pendingUserProfileIgnored;
    this.viewModel.updateIgnoredUser(this.snapshot, this.pendingUserProfileUserId, nextIgnored, this.abilityContext()).then((result: UpdateIgnoredUserResult) => {
      this.isUpdatingIgnoredUser = false;
      if (!result.ok) {
        this.pendingUserProfileIgnored = result.ignored;
        this.pendingUserProfileActionStatus = '';
        this.pendingUserProfileError = result.errorMessage;
        return;
      }
      this.snapshot = result.snapshot;
      this.pendingUserProfileIgnored = result.ignored;
      this.pendingUserProfileActionStatus = result.ignored ? 'User blocked' : 'User unblocked';
    }).catch((error: Error) => {
      this.isUpdatingIgnoredUser = false;
      this.pendingUserProfileActionStatus = '';
      this.pendingUserProfileError = `${error}`;
    });
  }

  private openBlockedUsersSheet(): void {
    if (this.blockedUserIds().length === 0) {
      return;
    }
    this.clearPermalinkSheets();
    this.blockedUsersPendingUnblockUserId = '';
    this.blockedUsersStatus = '';
    this.blockedUsersError = '';
    this.isUnblockingBlockedUser = false;
    this.isBlockedUsersSheetVisible = true;
  }

  private openRoomListContextMenu(roomId: string): void {
    this.clearPermalinkSheets();
    this.roomListContextMenuRoomId = roomId;
    this.roomListContextMenuError = '';
    this.isUpdatingRoomListContextMenu = false;
    this.isRoomListContextMenuConfirmingLeave = false;
  }

  private closeRoomListContextMenu(): void {
    this.roomListContextMenuRoomId = '';
    this.roomListContextMenuError = '';
    this.isUpdatingRoomListContextMenu = false;
    this.isRoomListContextMenuConfirmingLeave = false;
  }

  private requestRoomListContextMenuLeave(): void {
    this.isRoomListContextMenuConfirmingLeave = true;
    this.roomListContextMenuError = '';
  }

  private cancelRoomListContextMenuLeave(): void {
    this.isRoomListContextMenuConfirmingLeave = false;
    this.roomListContextMenuError = '';
  }

  private openRoomDetails(roomId: string): void {
    if (roomId.length === 0) {
      return;
    }
    this.clearPermalinkSheets();
    this.roomDetailsRoomId = roomId;
    this.roomDetailsError = '';
    this.isUpdatingRoomDetails = false;
    this.isRoomDetailsConfirmingLeave = false;
  }

  private openRoomDetailsFromRoomListContextMenu(): void {
    const roomId = this.roomListContextMenuRoomId;
    this.closeRoomListContextMenu();
    this.openRoomDetails(roomId);
  }

  private openReportRoom(roomId: string): void {
    if (roomId.length === 0) {
      return;
    }
    this.clearPermalinkSheets();
    this.reportRoomId = roomId;
    this.reportRoomReason = '';
    this.reportRoomLeaveRoom = false;
    this.reportRoomAlreadySubmitted = false;
    this.reportRoomError = '';
    this.isReportingRoom = false;
  }

  private openReportRoomFromRoomListContextMenu(): void {
    const roomId = this.roomListContextMenuRoomId;
    this.closeRoomListContextMenu();
    this.openReportRoom(roomId);
  }

  private openReportRoomFromRoomDetails(): void {
    const roomId = this.roomDetailsRoomId;
    this.closeRoomDetails();
    this.openReportRoom(roomId);
  }

  private closeRoomDetails(): void {
    this.roomDetailsRoomId = '';
    this.roomDetailsError = '';
    this.isUpdatingRoomDetails = false;
    this.isRoomDetailsConfirmingLeave = false;
  }

  private requestRoomDetailsLeave(): void {
    this.isRoomDetailsConfirmingLeave = true;
    this.roomDetailsError = '';
  }

  private cancelRoomDetailsLeave(): void {
    this.isRoomDetailsConfirmingLeave = false;
    this.roomDetailsError = '';
  }

  private closeReportRoom(): void {
    this.reportRoomId = '';
    this.reportRoomReason = '';
    this.reportRoomLeaveRoom = false;
    this.reportRoomAlreadySubmitted = false;
    this.reportRoomError = '';
    this.isReportingRoom = false;
  }

  private closeBlockedUsersSheet(): void {
    this.isBlockedUsersSheetVisible = false;
    this.blockedUsersPendingUnblockUserId = '';
    this.blockedUsersStatus = '';
    this.blockedUsersError = '';
    this.isUnblockingBlockedUser = false;
  }

  private requestBlockedUsersUnblock(userId: string): void {
    this.blockedUsersPendingUnblockUserId = userId;
    this.blockedUsersStatus = '';
    this.blockedUsersError = '';
  }

  private cancelBlockedUsersUnblock(): void {
    if (this.isUnblockingBlockedUser) {
      return;
    }
    this.blockedUsersPendingUnblockUserId = '';
    this.blockedUsersStatus = '';
    this.blockedUsersError = '';
  }

  private copyBlockedUserIdToClipboard(userId: string): void {
    this.blockedUsersPendingUnblockUserId = '';
    this.blockedUsersError = '';
    try {
      const systemPasteboard = pasteboard.getSystemPasteboard();
      systemPasteboard.setDataSync(pasteboard.createData(pasteboard.MIMETYPE_TEXT_PLAIN, userId));
      this.blockedUsersStatus = 'Copied to clipboard';
    } catch (error) {
      this.blockedUsersStatus = '';
      this.blockedUsersError = `${error}`;
    }
  }

  private confirmBlockedUsersUnblock(): void {
    if (this.isUnblockingBlockedUser || this.blockedUsersPendingUnblockUserId.length === 0) {
      return;
    }
    const userId = this.blockedUsersPendingUnblockUserId;
    this.isUnblockingBlockedUser = true;
    this.blockedUsersStatus = `Unblocking ${this.displayNameFromUserId(userId)}`;
    this.blockedUsersError = '';
    this.viewModel.updateIgnoredUser(this.snapshot, userId, false, this.abilityContext()).then((result: UpdateIgnoredUserResult) => {
      this.isUnblockingBlockedUser = false;
      if (!result.ok) {
        this.blockedUsersError = result.errorMessage;
        this.blockedUsersStatus = '';
        return;
      }
      this.snapshot = result.snapshot;
      this.blockedUsersPendingUnblockUserId = '';
      this.blockedUsersStatus = `Unblocked ${this.displayNameFromUserId(userId)}`;
    }).catch((error: Error) => {
      this.isUnblockingBlockedUser = false;
      this.blockedUsersStatus = '';
      this.blockedUsersError = `${error}`;
    });
  }

  private handleJoinPermalinkRoom(): void {
    if (this.isJoiningPermalinkRoom) {
      return;
    }
    this.isJoiningPermalinkRoom = true;
    this.pendingRoomPreviewError = '';
    this.viewModel.joinRoomByIdOrAlias(this.snapshot, this.pendingRoomPreviewId, this.pendingRoomPreviewServers).then((result: JoinRoomResult) => {
      this.isJoiningPermalinkRoom = false;
      if (!result.ok) {
        this.pendingRoomPreviewError = result.errorMessage;
        return;
      }
      this.snapshot = result.snapshot;
      this.selectedTab = 1;
      this.clearRoomPreviewSheet();
      this.handleTimelineVisibleForRead();
    }).catch((error: Error) => {
      this.isJoiningPermalinkRoom = false;
      this.pendingRoomPreviewError = `${error}`;
    });
  }

  private closeUserProfileSheet(): void {
    this.clearUserProfileSheet();
    this.snapshot = this.viewModel.clearIntent();
  }

  private closeRoomPreviewSheet(): void {
    this.clearRoomPreviewSheet();
    this.snapshot = this.viewModel.clearIntent();
  }

  private clearPermalinkSheets(): void {
    this.clearUserProfileSheet();
    this.clearRoomPreviewSheet();
  }

  private clearUserProfileSheet(): void {
    this.pendingUserProfileUserId = '';
    this.pendingUserProfileName = '';
    this.pendingUserProfileStatus = '';
    this.pendingUserProfileError = '';
    this.pendingUserProfileActionStatus = '';
    this.pendingUserProfileIgnored = false;
    this.isUpdatingIgnoredUser = false;
    this.isStartingPermalinkDm = false;
  }

  private clearRoomPreviewSheet(): void {
    this.pendingRoomPreviewId = '';
    this.pendingRoomPreviewName = '';
    this.pendingRoomPreviewTopic = '';
    this.pendingRoomPreviewServers = [];
    this.pendingRoomPreviewError = '';
    this.isJoiningPermalinkRoom = false;
  }

  private permalinkPathSegments(uri: string): string[] {
    const fragmentIndex = uri.indexOf('#');
    let rawPath = fragmentIndex >= 0 ? uri.substring(fragmentIndex + 1) : uri;
    if (fragmentIndex < 0) {
      const schemeIndex = rawPath.indexOf('://');
      if (schemeIndex >= 0) {
        const afterHost = rawPath.substring(schemeIndex + 3);
        const slashIndex = afterHost.indexOf('/');
        rawPath = slashIndex >= 0 ? afterHost.substring(slashIndex + 1) : '';
      }
    }
    const path = rawPath.split('?')[0].replace(/^\/+/, '');
    if (path.length === 0) {
      return [];
    }
    const parts = path.split('/');
    const result: string[] = [];
    for (let index = 0; index < parts.length; index += 1) {
      const part = this.safeDecode(parts[index]).trim();
      if (part.length > 0) {
        result.push(part);
      }
    }
    return result;
  }

  private queryParameter(uri: string, key: string): string {
    const values = this.queryParameters(uri, key);
    if (values.length === 0) {
      return '';
    }
    return values[0];
  }

  private oauthLoginToken(uri: string): string {
    const loginToken = this.queryParameter(uri, 'loginToken');
    if (loginToken.length > 0) {
      return loginToken;
    }
    const snakeLoginToken = this.queryParameter(uri, 'login_token');
    if (snakeLoginToken.length > 0) {
      return snakeLoginToken;
    }
    return this.queryParameter(uri, 'token');
  }

  private oauthHomeserverFromCallback(uri: string): string {
    const accountProvider = this.queryParameter(uri, 'account_provider');
    if (accountProvider.length > 0) {
      this.homeserver = accountProvider;
      return accountProvider;
    }
    const homeserverParam = this.queryParameter(uri, 'homeserver');
    if (homeserverParam.length > 0) {
      this.homeserver = homeserverParam;
      return homeserverParam;
    }
    const serverName = this.queryParameter(uri, 'server_name');
    if (serverName.length > 0) {
      this.homeserver = serverName;
      return serverName;
    }
    return this.homeserver.length > 0 ? this.homeserver : 'matrix.org';
  }

  private queryParameters(uri: string, key: string): string[] {
    const prefix = `${key}=`;
    const queryIndex = uri.indexOf('?');
    if (queryIndex < 0) {
      return [];
    }
    const query = uri.substring(queryIndex + 1).split('#')[0];
    const parts = query.split('&');
    const values: string[] = [];
    for (let index = 0; index < parts.length; index += 1) {
      if (parts[index].startsWith(prefix)) {
        values.push(this.safeDecode(parts[index].substring(prefix.length).replace(/\+/g, '%20')));
      }
    }
    return values;
  }

  private usernameFromLoginHint(loginHint: string): string {
    const normalized = loginHint.startsWith('mxid:') ? loginHint.substring(5) : loginHint;
    const withoutAt = normalized.startsWith('@') ? normalized.substring(1) : normalized;
    const localpart = withoutAt.split(':')[0];
    if (localpart.length === 0) {
      return '';
    }
    return `${localpart.substring(0, 1).toUpperCase()}${localpart.substring(1)}`;
  }

  private focusedPermalinkLabel(): string {
    if (this.snapshot.timeline.find((event: TimelineEvent) => event.id === this.focusedPermalinkEventId) !== undefined) {
      return `Focused event: ${this.focusedPermalinkEventId}`;
    }
    return `Focused event not loaded: ${this.focusedPermalinkEventId}`;
  }

  private isFocusedPermalinkEvent(event: TimelineEvent): boolean {
    return this.focusedPermalinkEventId.length > 0 && event.id === this.focusedPermalinkEventId;
  }

  private clearPermalinkFocus(): void {
    this.focusedPermalinkEventId = '';
    this.focusedPermalinkThreadId = '';
  }

  private clearJumpToUnread(): void {
    this.jumpToUnreadRoomId = '';
    this.jumpToUnreadEventId = '';
    this.unreadMarkerBeforeEventId = '';
    this.jumpToUnreadCount = 0;
  }

  private shouldShowJumpToUnread(): boolean {
    return this.jumpToUnreadRoomId === this.snapshot.selectedRoomId &&
      this.jumpToUnreadEventId.length > 0 &&
      this.snapshot.timeline.length > 0;
  }

  private shouldRenderUnreadMarkerBefore(event: TimelineEvent): boolean {
    return this.shouldShowJumpToUnread() &&
      this.unreadMarkerBeforeEventId.length > 0 &&
      event.id === this.unreadMarkerBeforeEventId;
  }

  private jumpToUnreadLabel(): string {
    const count = this.jumpToUnreadCount > 0 ? this.jumpToUnreadCount : 1;
    return `${count} unread message${count === 1 ? '' : 's'}`;
  }

  private handleJumpToUnread(): void {
    if (!this.shouldShowJumpToUnread()) {
      return;
    }
    this.focusedPermalinkEventId = this.jumpToUnreadEventId;
    this.focusedPermalinkThreadId = '';
  }

  private captureJumpToUnreadState(): void {
    const roomId = this.snapshot.selectedRoomId;
    if (roomId.length === 0) {
      this.clearJumpToUnread();
      return;
    }
    const room = this.snapshot.rooms.find((item: RoomSummary) => item.id === roomId);
    if (room === undefined || room.unreadCount <= 0 || this.snapshot.timeline.length === 0) {
      if (this.jumpToUnreadRoomId !== roomId) {
        this.clearJumpToUnread();
      }
      return;
    }
    const targetIndex = Math.min(Math.max(room.unreadCount - 1, 0), this.snapshot.timeline.length - 1);
    const markerIndex = Math.min(Math.max(room.unreadCount, 0), this.snapshot.timeline.length - 1);
    const targetEvent = this.snapshot.timeline[targetIndex];
    const markerEvent = this.snapshot.timeline[markerIndex];
    if (targetEvent === undefined || markerEvent === undefined) {
      return;
    }
    this.jumpToUnreadRoomId = roomId;
    this.jumpToUnreadEventId = targetEvent.id;
    this.unreadMarkerBeforeEventId = markerEvent.id;
    this.jumpToUnreadCount = room.unreadCount;
  }

  private profileInitials(): string {
    if (this.pendingUserProfileName.length >= 2) {
      return this.pendingUserProfileName.substring(0, 2).toUpperCase();
    }
    if (this.pendingUserProfileName.length === 1) {
      return this.pendingUserProfileName.toUpperCase();
    }
    return 'MX';
  }

  private ignoredUserActionLabel(): string {
    if (this.isUpdatingIgnoredUser) {
      return this.pendingUserProfileIgnored ? 'Unblocking user' : 'Blocking user';
    }
    return this.pendingUserProfileIgnored ? 'Unblock user' : 'Block user';
  }

  private isPendingUserIgnored(): boolean {
    if (this.snapshot.session === null || this.pendingUserProfileUserId.length === 0) {
      return false;
    }
    return this.snapshot.session.ignoredUsers.includes(this.pendingUserProfileUserId);
  }

  private blockedUserIds(): string[] {
    if (this.snapshot.session === null) {
      return [];
    }
    return this.snapshot.session.ignoredUsers;
  }

  private initialsFromUserId(userId: string): string {
    const name = this.displayNameFromUserId(userId);
    if (name.length >= 2) {
      return name.substring(0, 2).toUpperCase();
    }
    if (name.length === 1) {
      return name.toUpperCase();
    }
    return 'MX';
  }

  private safeId(value: string): string {
    return value.replace(/[^A-Za-z0-9_-]/g, '_');
  }

  private displayNameFromUserId(userId: string): string {
    const withoutAt = userId.startsWith('@') ? userId.substring(1) : userId;
    const localpart = withoutAt.split(':')[0];
    if (localpart.length === 0) {
      return 'Matrix user';
    }
    return `${localpart.substring(0, 1).toUpperCase()}${localpart.substring(1)}`;
  }

  private slug(value: string): string {
    return value.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
  }

  private safeDecode(value: string): string {
    try {
      return decodeURIComponent(value);
    } catch (error) {
      return value;
    }
  }

  private handleManualSignIn(): void {
    if (this.isSigningIn) {
      return;
    }
    this.isSigningIn = true;
    this.signInError = '';
    const context = this.abilityContext();
    this.viewModel.signIn(this.homeserver, this.username, this.password, context).then((result: SignInResult) => {
      this.isSigningIn = false;
      if (!result.ok) {
        this.signInError = result.errorMessage;
        return;
      }
      this.snapshot = result.snapshot;
      this.syncProfileDrafts();
      this.selectedTab = 0;
      this.authState = ClientAuthState.SignedIn;
    }).catch((error: Error) => {
      this.isSigningIn = false;
      this.signInError = `${error}`;
    });
  }

  private handleOAuthTokenSignIn(callbackUri: string, loginToken: string): void {
    if (this.isSigningIn) {
      return;
    }
    this.isSigningIn = true;
    this.signInError = 'Signing in with OAuth callback';
    const context = this.abilityContext();
    const oauthHomeserver = this.oauthHomeserverFromCallback(callbackUri);
    this.viewModel.signInWithLoginToken(oauthHomeserver, loginToken, context).then((result: SignInResult) => {
      this.isSigningIn = false;
      if (!result.ok) {
        this.signInError = result.errorMessage;
        this.authState = ClientAuthState.ManualLogin;
        return;
      }
      this.snapshot = result.snapshot;
      this.syncProfileDrafts();
      this.selectedTab = 0;
      this.authState = ClientAuthState.SignedIn;
      this.signInError = '';
    }).catch((error: Error) => {
      this.isSigningIn = false;
      this.signInError = `${error}`;
      this.authState = ClientAuthState.ManualLogin;
    });
  }

  private handleSignOut(): void {
    this.stopForegroundSyncLoop();
    const context = this.abilityContext();
    this.viewModel.signOutPersisted(this.snapshot, context).then((signedOut: ClientSnapshot) => {
      this.snapshot = signedOut;
      this.password = '';
      this.displayNameDraft = '';
      this.userStatusDraft = '';
      this.pendingShareAttachmentRows = [];
      this.isShareTargetPickerVisible = false;
      this.pendingPermalinkUri = '';
      this.pendingPermalinkMessage = '';
      this.clearPermalinkFocus();
      this.clearJumpToUnread();
      this.clearPermalinkSheets();
      this.authState = ClientAuthState.SignedOut;
    }).catch(() => {
      this.snapshot = this.viewModel.signOut(this.snapshot);
      this.password = '';
      this.displayNameDraft = '';
      this.userStatusDraft = '';
      this.pendingShareAttachmentRows = [];
      this.isShareTargetPickerVisible = false;
      this.pendingPermalinkUri = '';
      this.pendingPermalinkMessage = '';
      this.clearPermalinkFocus();
      this.clearJumpToUnread();
      this.clearPermalinkSheets();
      this.authState = ClientAuthState.SignedOut;
    });
  }

  private handleSendMessage(): void {
    if (this.isSendingMessage) {
      return;
    }
    if (this.handleSlashCommandBeforeSend(this.messageDraft)) {
      return;
    }
    this.isSendingMessage = true;
    this.sendStatus = '';
    this.sendError = '';
    const sendTask = this.pendingShareAttachmentRows.length > 0
      ? this.viewModel.sendSharedAttachmentMessage(this.snapshot, this.messageDraft, this.pendingShareAttachmentRows)
      : this.viewModel.sendTextMessage(this.snapshot, this.messageDraft);
    sendTask.then((result: SendMessageResult) => {
      this.isSendingMessage = false;
      if (!result.ok) {
        this.sendError = result.errorMessage;
        return;
      }
      this.snapshot = result.snapshot;
      this.messageDraft = '';
      this.pendingShareAttachmentRows = [];
      this.isShareTargetPickerVisible = false;
      this.clearPermalinkFocus();
      this.captureJumpToUnreadState();
    }).catch((error: Error) => {
      this.isSendingMessage = false;
      this.sendStatus = '';
      this.sendError = `${error}`;
    });
  }

  private handleSlashCommandBeforeSend(message: string): boolean {
    const trimmed = message.trim();
    if (!this.isSlashCommandCandidate(trimmed)) {
      return false;
    }
    this.sendStatus = '';
    this.sendError = '';
    if (trimmed === '/') {
      this.sendError = 'Unrecognized command /';
      return true;
    }
    const command = this.slashCommandName(trimmed);
    if (this.handleRichMessageSlashCommand(command, trimmed)) {
      return true;
    }
    if (this.handleTextSlashCommand(command, trimmed)) {
      return true;
    }
    if (this.handleProfileSlashCommand(command, trimmed)) {
      return true;
    }
    if (this.handleNavigationSlashCommand(command, trimmed)) {
      return true;
    }
    if (this.handleRoomMetadataSlashCommand(command, trimmed)) {
      return true;
    }
    if (this.handleRoomNickSlashCommand(command, trimmed)) {
      return true;
    }
    if (this.handleRoomMembershipSlashCommand(command, trimmed)) {
      return true;
    }
    if (this.handleRoomLeaveSlashCommand(command, trimmed)) {
      return true;
    }
    if (this.handleRoomJoinSlashCommand(command, trimmed)) {
      return true;
    }
    if (this.handleRemainingSlashCommandSurface(command, trimmed)) {
      return true;
    }
    if (command !== '/ignore' && command !== '/unignore') {
      this.sendError = `Unrecognized command ${command}`;
      return true;
    }
    const userId = this.slashCommandFirstArgument(trimmed);
    if (!this.isMatrixUserId(userId)) {
      this.sendError = `${command} syntax: ${this.slashCommandUsage(command)}`;
      return true;
    }
    const shouldIgnore = command === '/ignore';
    this.isSendingMessage = true;
    this.sendStatus = `${shouldIgnore ? 'Ignoring' : 'Unignoring'} ${this.displayNameFromUserId(userId)}`;
    this.viewModel.updateIgnoredUser(this.snapshot, userId, shouldIgnore, this.abilityContext()).then((result: UpdateIgnoredUserResult) => {
      this.isSendingMessage = false;
      if (!result.ok) {
        this.sendStatus = '';
        this.sendError = result.errorMessage;
        return;
      }
      this.snapshot = result.snapshot;
      this.messageDraft = '';
      this.pendingShareAttachmentRows = [];
      this.isShareTargetPickerVisible = false;
      this.sendStatus = `${shouldIgnore ? 'Ignored' : 'Unignored'} ${this.displayNameFromUserId(userId)}`;
      this.clearPermalinkFocus();
      this.captureJumpToUnreadState();
    }).catch((error: Error) => {
      this.isSendingMessage = false;
      this.sendStatus = '';
      this.sendError = `${error}`;
    });
    return true;
  }

  private handleProfileSlashCommand(command: string, trimmed: string): boolean {
    if (command !== '/nick') {
      return false;
    }
    const displayName = this.slashCommandMessage(trimmed);
    if (displayName.length === 0) {
      this.sendError = `${command} syntax: ${this.slashCommandUsage(command)}`;
      return true;
    }
    if (this.snapshot.session === null) {
      this.sendError = 'No signed-in session';
      return true;
    }
    this.isSendingMessage = true;
    this.sendStatus = 'Updating display name';
    this.sendError = '';
    const context = this.abilityContext();
    this.viewModel.updateOwnProfile(this.snapshot, displayName, this.snapshot.session.account.userStatus, context).then((result: UpdateProfileResult) => {
      this.isSendingMessage = false;
      if (!result.ok) {
        this.sendStatus = '';
        this.sendError = result.errorMessage;
        return;
      }
      this.snapshot = result.snapshot;
      this.messageDraft = '';
      this.pendingShareAttachmentRows = [];
      this.isShareTargetPickerVisible = false;
      this.sendStatus = 'Display name updated';
      this.syncProfileDrafts();
      this.clearPermalinkFocus();
    }).catch((error: Error) => {
      this.isSendingMessage = false;
      this.sendStatus = '';
      this.sendError = `${error}`;
    });
    return true;
  }

  private handleNavigationSlashCommand(command: string, trimmed: string): boolean {
    if (command !== '/whois' && command !== '/devtools') {
      return false;
    }
    if (command === '/devtools') {
      if (this.slashCommandMessage(trimmed).length > 0) {
        this.sendError = `${command} syntax: ${this.slashCommandUsage(command)}`;
        return true;
      }
      this.messageDraft = '';
      this.pendingShareAttachmentRows = [];
      this.isShareTargetPickerVisible = false;
      this.sendStatus = '';
      this.sendError = '';
      this.selectedTab = 2;
      return true;
    }
    const userId = this.slashCommandFirstArgument(trimmed);
    if (!this.isMatrixUserId(userId)) {
      this.sendError = `${command} syntax: ${this.slashCommandUsage(command)}`;
      return true;
    }
    this.messageDraft = '';
    this.pendingShareAttachmentRows = [];
    this.isShareTargetPickerVisible = false;
    this.sendStatus = '';
    this.sendError = '';
    this.showPermalinkUserProfile(userId);
    this.selectedTab = 1;
    return true;
  }

  private handleRemainingSlashCommandSurface(command: string, trimmed: string): boolean {
    if (this.isUnsupportedMxcSlashCommand(command)) {
      const mxcUrl = this.slashCommandFirstArgument(trimmed);
      if (this.slashCommandParts(trimmed).length !== 2 || !this.isMxcUrl(mxcUrl)) {
        this.sendError = `${command} syntax: ${this.slashCommandUsage(command)}`;
        return true;
      }
      this.sendError = 'Not yet implemented';
      return true;
    }
    if (command === '/op') {
      const parts = this.slashCommandParts(trimmed);
      if (parts.length !== 3 || !this.isMatrixUserId(parts[1]) || !this.isIntegerString(parts[2])) {
        this.sendError = `${command} syntax: ${this.slashCommandUsage(command)}`;
        return true;
      }
      this.sendError = 'Not yet implemented';
      return true;
    }
    if (command === '/deop') {
      const parts = this.slashCommandParts(trimmed);
      if (parts.length !== 2 || !this.isMatrixUserId(parts[1])) {
        this.sendError = `${command} syntax: ${this.slashCommandUsage(command)}`;
        return true;
      }
      this.sendError = 'Not yet implemented';
      return true;
    }
    if (command === '/discardsession') {
      if (this.slashCommandMessage(trimmed).length > 0) {
        this.sendError = `${command} syntax: ${this.slashCommandUsage(command)}`;
        return true;
      }
      this.sendError = 'Not yet implemented';
      return true;
    }
    if (command === '/upgraderoom') {
      if (this.slashCommandMessage(trimmed).length === 0) {
        this.sendError = `${command} syntax: ${this.slashCommandUsage(command)}`;
        return true;
      }
      this.sendError = 'Not yet implemented';
      return true;
    }
    if (command === '/confetti' || command === '/snowfall') {
      this.sendError = 'Not yet implemented';
      return true;
    }
    return false;
  }

  private handleRoomMembershipSlashCommand(command: string, trimmed: string): boolean {
    if (!this.isRoomMembershipSlashCommand(command)) {
      return false;
    }
    const userId = this.slashCommandFirstArgument(trimmed);
    if (!this.isMatrixUserId(userId)) {
      this.sendError = `${command} syntax: ${this.slashCommandUsage(command)}`;
      return true;
    }
    const action = command === '/remove' || command === '/kick' ? 'kick' : command.substring(1);
    const reason = this.slashCommandMessageAfterFirstArgument(trimmed);
    this.isSendingMessage = true;
    this.sendStatus = this.roomMembershipStatus(command, userId, false);
    this.sendError = '';
    this.viewModel.updateSelectedRoomMembership(this.snapshot, action, userId, reason).then((result: UpdateRoomMembershipResult) => {
      this.isSendingMessage = false;
      if (!result.ok) {
        this.sendStatus = '';
        this.sendError = result.errorMessage;
        return;
      }
      this.snapshot = result.snapshot;
      this.messageDraft = '';
      this.pendingShareAttachmentRows = [];
      this.isShareTargetPickerVisible = false;
      this.sendStatus = this.roomMembershipStatus(command, userId, true);
      this.clearPermalinkFocus();
    }).catch((error: Error) => {
      this.isSendingMessage = false;
      this.sendStatus = '';
      this.sendError = `${error}`;
    });
    return true;
  }

  private handleRoomMetadataSlashCommand(command: string, trimmed: string): boolean {
    if (command !== '/roomname' && command !== '/topic') {
      return false;
    }
    const value = this.slashCommandMessage(trimmed);
    if (value.length === 0) {
      this.sendError = `${command} syntax: ${this.slashCommandUsage(command)}`;
      return true;
    }
    this.isSendingMessage = true;
    this.sendStatus = command === '/roomname' ? 'Updating room name' : 'Updating room topic';
    this.sendError = '';
    const updateTask = command === '/roomname'
      ? this.viewModel.updateSelectedRoomName(this.snapshot, value)
      : this.viewModel.updateSelectedRoomTopic(this.snapshot, value);
    updateTask.then((result: UpdateRoomMetadataResult) => {
      this.isSendingMessage = false;
      if (!result.ok) {
        this.sendStatus = '';
        this.sendError = result.errorMessage;
        return;
      }
      this.snapshot = result.snapshot;
      this.messageDraft = '';
      this.pendingShareAttachmentRows = [];
      this.isShareTargetPickerVisible = false;
      this.sendStatus = command === '/roomname' ? 'Room name updated' : 'Room topic updated';
      this.refreshVisibleTimelineRoomTitle(result.snapshot.selectedRoomId);
      this.clearPermalinkFocus();
    }).catch((error: Error) => {
      this.isSendingMessage = false;
      this.sendStatus = '';
      this.sendError = `${error}`;
    });
    return true;
  }

  private handleRoomNickSlashCommand(command: string, trimmed: string): boolean {
    if (command !== '/myroomnick' && command !== '/roomnick') {
      return false;
    }
    const displayName = this.slashCommandMessage(trimmed);
    if (displayName.length === 0) {
      this.sendError = `${command} syntax: ${this.slashCommandUsage(command)}`;
      return true;
    }
    this.isSendingMessage = true;
    this.sendStatus = 'Updating room nickname';
    this.sendError = '';
    this.viewModel.updateSelectedRoomOwnDisplayName(this.snapshot, displayName).then((result: UpdateRoomMetadataResult) => {
      this.isSendingMessage = false;
      if (!result.ok) {
        this.sendStatus = '';
        this.sendError = result.errorMessage;
        return;
      }
      this.snapshot = result.snapshot;
      this.messageDraft = '';
      this.pendingShareAttachmentRows = [];
      this.isShareTargetPickerVisible = false;
      this.sendStatus = 'Room nickname updated';
      this.clearPermalinkFocus();
    }).catch((error: Error) => {
      this.isSendingMessage = false;
      this.sendStatus = '';
      this.sendError = `${error}`;
    });
    return true;
  }

  private handleRoomLeaveSlashCommand(command: string, trimmed: string): boolean {
    if (command !== '/leave' && command !== '/part') {
      return false;
    }
    if (this.slashCommandMessage(trimmed).length > 0) {
      this.sendError = `${command} syntax: ${this.slashCommandUsage(command)}`;
      return true;
    }
    this.isSendingMessage = true;
    this.sendStatus = 'Leaving room';
    this.sendError = '';
    this.viewModel.leaveSelectedRoom(this.snapshot).then((result: UpdateRoomMetadataResult) => {
      this.isSendingMessage = false;
      if (!result.ok) {
        this.sendStatus = '';
        this.sendError = result.errorMessage;
        return;
      }
      this.snapshot = result.snapshot;
      this.messageDraft = '';
      this.pendingShareAttachmentRows = [];
      this.isShareTargetPickerVisible = false;
      this.selectedTab = 0;
      this.sendStatus = 'Left room';
      this.clearPermalinkFocus();
      this.refreshVisibleTimelineRoomTitle(result.snapshot.selectedRoomId);
    }).catch((error: Error) => {
      this.isSendingMessage = false;
      this.sendStatus = '';
      this.sendError = `${error}`;
    });
    return true;
  }

  private handleRoomJoinSlashCommand(command: string, trimmed: string): boolean {
    if (command !== '/join' && command !== '/j' && command !== '/goto') {
      return false;
    }
    const roomIdOrAlias = this.slashCommandFirstArgument(trimmed);
    if (!this.isMatrixRoomAddress(roomIdOrAlias)) {
      this.sendError = `${command} syntax: ${this.slashCommandUsage(command)}`;
      return true;
    }
    this.isSendingMessage = true;
    this.sendStatus = 'Joining room';
    this.sendError = '';
    this.viewModel.joinRoomByIdOrAlias(this.snapshot, roomIdOrAlias, []).then((result: JoinRoomResult) => {
      this.isSendingMessage = false;
      if (!result.ok) {
        this.sendStatus = '';
        this.sendError = result.errorMessage;
        return;
      }
      this.snapshot = result.snapshot;
      this.messageDraft = '';
      this.pendingShareAttachmentRows = [];
      this.isShareTargetPickerVisible = false;
      this.selectedTab = 1;
      this.sendStatus = 'Joined room';
      this.clearPermalinkFocus();
      this.clearRoomPreviewSheet();
      this.refreshVisibleTimelineRoomTitle(result.snapshot.selectedRoomId);
    }).catch((error: Error) => {
      this.isSendingMessage = false;
      this.sendStatus = '';
      this.sendError = `${error}`;
    });
    return true;
  }

  private handleTextSlashCommand(command: string, trimmed: string): boolean {
    if (command === '/plain') {
      const message = this.slashCommandMessage(trimmed);
      if (message.length === 0) {
        this.sendError = `${command} syntax: ${this.slashCommandUsage(command)}`;
        return true;
      }
      this.sendSlashTextMessage(message);
      return true;
    }
    if (this.isPrefixSlashCommand(command)) {
      const prefix = this.slashCommandPrefix(command);
      const message = this.slashCommandMessage(trimmed);
      this.sendSlashTextMessage(message.length > 0 ? `${prefix} ${message}` : prefix);
      return true;
    }
    return false;
  }

  private handleRichMessageSlashCommand(command: string, trimmed: string): boolean {
    if (!this.isRichMessageSlashCommand(command)) {
      return false;
    }
    const message = this.slashCommandMessage(trimmed);
    if (message.length === 0) {
      this.sendError = `${command} syntax: ${this.slashCommandUsage(command)}`;
      return true;
    }
    if (command === '/me') {
      this.sendSlashEmoteMessage(message);
      return true;
    }
    if (command === '/rainbowme') {
      this.sendSlashFormattedMessage(message, this.createRainbowFormattedBody(message), 'm.emote', TimelineEventKind.Emote);
      return true;
    }
    if (command === '/rainbow') {
      this.sendSlashFormattedMessage(message, this.createRainbowFormattedBody(message), 'm.text', TimelineEventKind.Text);
      return true;
    }
    const spoilerBody = `[Spoiler](${message})`;
    const spoilerFormattedBody = `<span data-mx-spoiler>${this.escapeHtml(message)}</span>`;
    this.sendSlashFormattedMessage(spoilerBody, spoilerFormattedBody, 'm.text', TimelineEventKind.Text);
    return true;
  }

  private sendSlashTextMessage(body: string): void {
    this.isSendingMessage = true;
    this.sendStatus = '';
    this.sendError = '';
    this.viewModel.sendTextMessage(this.snapshot, body).then((result: SendMessageResult) => {
      this.isSendingMessage = false;
      if (!result.ok) {
        this.sendError = result.errorMessage;
        return;
      }
      this.snapshot = result.snapshot;
      this.messageDraft = '';
      this.pendingShareAttachmentRows = [];
      this.isShareTargetPickerVisible = false;
      this.clearPermalinkFocus();
      this.captureJumpToUnreadState();
    }).catch((error: Error) => {
      this.isSendingMessage = false;
      this.sendStatus = '';
      this.sendError = `${error}`;
    });
  }

  private sendSlashEmoteMessage(body: string): void {
    this.isSendingMessage = true;
    this.sendStatus = '';
    this.sendError = '';
    this.viewModel.sendEmoteMessage(this.snapshot, body).then((result: SendMessageResult) => {
      this.isSendingMessage = false;
      if (!result.ok) {
        this.sendError = result.errorMessage;
        return;
      }
      this.snapshot = result.snapshot;
      this.messageDraft = '';
      this.pendingShareAttachmentRows = [];
      this.isShareTargetPickerVisible = false;
      this.clearPermalinkFocus();
      this.captureJumpToUnreadState();
    }).catch((error: Error) => {
      this.isSendingMessage = false;
      this.sendStatus = '';
      this.sendError = `${error}`;
    });
  }

  private sendSlashFormattedMessage(body: string, formattedBody: string, msgtype: string, localKind: TimelineEventKind): void {
    this.isSendingMessage = true;
    this.sendStatus = '';
    this.sendError = '';
    this.viewModel.sendFormattedMessage(this.snapshot, body, formattedBody, msgtype, localKind).then((result: SendMessageResult) => {
      this.isSendingMessage = false;
      if (!result.ok) {
        this.sendError = result.errorMessage;
        return;
      }
      this.snapshot = result.snapshot;
      this.messageDraft = '';
      this.pendingShareAttachmentRows = [];
      this.isShareTargetPickerVisible = false;
      this.clearPermalinkFocus();
      this.captureJumpToUnreadState();
    }).catch((error: Error) => {
      this.isSendingMessage = false;
      this.sendStatus = '';
      this.sendError = `${error}`;
    });
  }

  private isSlashCommandCandidate(value: string): boolean {
    const trimmed = value.trim();
    return trimmed.startsWith('/') && !trimmed.startsWith('//');
  }

  private shouldShowSlashCommandSuggestions(): boolean {
    const rawDraft = this.messageDraft;
    const trimmed = rawDraft.trim();
    if (!this.isSlashCommandCandidate(trimmed)) {
      return false;
    }
    if (rawDraft.indexOf(' ') >= 0) {
      return false;
    }
    if (this.isNoArgumentSlashCommand(trimmed.toLowerCase())) {
      return false;
    }
    return this.isSlashSuggestionCandidate('/ignore') ||
      this.isSlashSuggestionCandidate('/unignore') ||
      this.isSlashSuggestionCandidate('/plain') ||
      this.isSlashSuggestionCandidate('/me') ||
      this.isSlashSuggestionCandidate('/rainbow') ||
      this.isSlashSuggestionCandidate('/rainbowme') ||
      this.isSlashSuggestionCandidate('/spoiler') ||
      this.isSlashSuggestionCandidate('/nick') ||
      this.isSlashSuggestionCandidate('/myroomnick') ||
      this.isSlashSuggestionCandidate('/roomnick') ||
      this.isSlashSuggestionCandidate('/whois') ||
      this.isSlashSuggestionCandidate('/roomname') ||
      this.isSlashSuggestionCandidate('/topic') ||
      this.isSlashSuggestionCandidate('/invite') ||
      this.isSlashSuggestionCandidate('/remove') ||
      this.isSlashSuggestionCandidate('/ban') ||
      this.isSlashSuggestionCandidate('/unban') ||
      this.isSlashSuggestionCandidate('/shrug') ||
      this.isSlashSuggestionCandidate('/lenny') ||
      this.isSlashSuggestionCandidate('/tableflip') ||
      this.isSlashSuggestionCandidate('/unflip');
  }

  private isSlashSuggestionCandidate(command: string): boolean {
    const trimmed = this.messageDraft.trim().toLowerCase();
    if (trimmed === '/') {
      return true;
    }
    return command.startsWith(trimmed);
  }

  private selectSlashCommandSuggestion(command: string): void {
    this.messageDraft = `${command} `;
    this.sendStatus = '';
    this.sendError = '';
  }

  private slashCommandName(trimmed: string): string {
    const firstSpaceIndex = trimmed.indexOf(' ');
    if (firstSpaceIndex < 0) {
      return trimmed.toLowerCase();
    }
    return trimmed.substring(0, firstSpaceIndex).toLowerCase();
  }

  private slashCommandFirstArgument(trimmed: string): string {
    const firstSpaceIndex = trimmed.indexOf(' ');
    if (firstSpaceIndex < 0) {
      return '';
    }
    const rest = trimmed.substring(firstSpaceIndex + 1).trim();
    if (rest.length === 0) {
      return '';
    }
    const parts = rest.split(/\s+/);
    if (parts.length === 0) {
      return '';
    }
    return parts[0];
  }

  private slashCommandMessage(trimmed: string): string {
    const firstSpaceIndex = trimmed.indexOf(' ');
    if (firstSpaceIndex < 0) {
      return '';
    }
    return trimmed.substring(firstSpaceIndex + 1).trim();
  }

  private slashCommandMessageAfterFirstArgument(trimmed: string): string {
    const message = this.slashCommandMessage(trimmed);
    const firstSpaceIndex = message.indexOf(' ');
    if (firstSpaceIndex < 0) {
      return '';
    }
    return message.substring(firstSpaceIndex + 1).trim();
  }

  private slashCommandUsage(command: string): string {
    if (command === '/ignore') {
      return '/ignore <user-id> [reason]';
    }
    if (command === '/plain') {
      return '/plain <message>';
    }
    if (command === '/me') {
      return '/me <message>';
    }
    if (command === '/rainbow') {
      return '/rainbow <message>';
    }
    if (command === '/rainbowme') {
      return '/rainbowme <message>';
    }
    if (command === '/spoiler') {
      return '/spoiler <message>';
    }
    if (command === '/nick') {
      return '/nick <display-name>';
    }
    if (command === '/myroomnick' || command === '/roomnick') {
      return `${command} <display-name>`;
    }
    if (command === '/whois') {
      return '/whois <user-id>';
    }
    if (command === '/roomname') {
      return '/roomname <name>';
    }
    if (command === '/topic') {
      return '/topic <topic>';
    }
    if (command === '/join' || command === '/j' || command === '/goto') {
      return `${command} <room-address> [reason]`;
    }
    if (command === '/op') {
      return '/op <user-id> [<power-level>]';
    }
    if (command === '/deop') {
      return '/deop <user-id>';
    }
    if (command === '/roomavatar' || command === '/myavatar' || command === '/myroomavatar') {
      return `${command} <mxc_url>`;
    }
    if (command === '/devtools' || command === '/discardsession') {
      return command;
    }
    if (command === '/upgraderoom') {
      return '/upgraderoom newVersion';
    }
    if (command === '/invite') {
      return '/invite <user-id> [reason]';
    }
    if (command === '/remove' || command === '/kick') {
      return `${command} <user-id> [reason]`;
    }
    if (command === '/ban') {
      return '/ban <user-id> [reason]';
    }
    if (command === '/unban') {
      return '/unban <user-id> [reason]';
    }
    if (command === '/leave' || command === '/part') {
      return command;
    }
    return '/unignore <user-id>';
  }

  private isRoomMembershipSlashCommand(command: string): boolean {
    return command === '/invite' ||
      command === '/remove' ||
      command === '/kick' ||
      command === '/ban' ||
      command === '/unban';
  }

  private roomMembershipStatus(command: string, userId: string, completed: boolean): string {
    const name = this.displayNameFromUserId(userId);
    if (command === '/invite') {
      return completed ? `Invited ${name}` : `Inviting ${name}`;
    }
    if (command === '/ban') {
      return completed ? `Banned ${name}` : `Banning ${name}`;
    }
    if (command === '/unban') {
      return completed ? `Unbanned ${name}` : `Unbanning ${name}`;
    }
    return completed ? `Removed ${name}` : `Removing ${name}`;
  }

  private isPrefixSlashCommand(command: string): boolean {
    return command === '/shrug' ||
      command === '/lenny' ||
      command === '/tableflip' ||
      command === '/unflip';
  }

  private slashCommandPrefix(command: string): string {
    if (command === '/shrug') {
      return '¯\\\\_(ツ)\\_/¯';
    }
    if (command === '/lenny') {
      return '( ͡° ͜ʖ ͡°)';
    }
    if (command === '/tableflip') {
      return '(╯°□°）╯︵ ┻━┻';
    }
    return '┬──┬ ノ( ゜-゜ノ)';
  }

  private isRichMessageSlashCommand(command: string): boolean {
    return command === '/me' ||
      command === '/rainbow' ||
      command === '/rainbowme' ||
      command === '/spoiler';
  }

  private isNoArgumentSlashCommand(command: string): boolean {
    return command === '/leave' || command === '/part';
  }

  private isUnsupportedMxcSlashCommand(command: string): boolean {
    return command === '/roomavatar' ||
      command === '/myavatar' ||
      command === '/myroomavatar';
  }

  private slashCommandParts(trimmed: string): string[] {
    return trimmed.split(/\s+/).filter((part: string) => part.length > 0);
  }

  private isIntegerString(value: string): boolean {
    return /^-?[0-9]+$/.test(value);
  }

  private isMxcUrl(value: string): boolean {
    return /^mxc:\/\/[A-Za-z0-9.-]+(:[0-9]+)?\/[A-Za-z0-9._=\-/]+$/.test(value);
  }

  private createRainbowFormattedBody(message: string): string {
    const letters = this.splitEmojiAware(message);
    if (letters.length === 0) {
      return '';
    }
    const frequency = 2 * Math.PI / letters.length;
    let result = '';
    for (let index = 0; index < letters.length; index += 1) {
      const letter = letters[index];
      if (letter === ' ') {
        result = `${result}${letter}`;
      } else {
        const color = this.rainbowDashColor(index * frequency, 1);
        result = `${result}<font color="${color}">${this.escapeHtml(letter)}</font>`;
      }
    }
    return result;
  }

  private splitEmojiAware(value: string): string[] {
    const result: string[] = [];
    let index = 0;
    while (index < value.length) {
      const firstChar = value.substring(index, index + 1);
      const firstCode = value.charCodeAt(index);
      if (firstCode === 0x200e) {
        index += 1;
        continue;
      }
      if (firstCode >= 0xD800 && firstCode <= 0xDBFF && index + 1 < value.length) {
        const secondCode = value.charCodeAt(index + 1);
        if (secondCode >= 0xDC00 && secondCode <= 0xDFFF) {
          result.push(value.substring(index, index + 2));
          index += 2;
          continue;
        }
      }
      result.push(firstChar);
      index += 1;
    }
    return result;
  }

  private rainbowDashColor(hue: number, chroma: number): string {
    const a = chroma * 127 * Math.cos(hue);
    const b = chroma * 127 * Math.sin(hue);
    let y = (75 + 16) / 116.0;
    const x = this.adjustRainbowXyz(y + a / 500) * 0.9505;
    const z = this.adjustRainbowXyz(y - b / 200) * 1.0890;
    y = this.adjustRainbowXyz(y);
    const red = 3.24096994 * x - 1.53738318 * y - 0.49861076 * z;
    const green = -0.96924364 * x + 1.8759675 * y + 0.04155506 * z;
    const blue = 0.05563008 * x - 0.20397696 * y + 1.05697151 * z;
    return `#${this.toRainbowHex(this.adjustRainbowRgb(red))}${this.toRainbowHex(this.adjustRainbowRgb(green))}${this.toRainbowHex(this.adjustRainbowRgb(blue))}`;
  }

  private adjustRainbowXyz(value: number): number {
    if (value > 0.2069) {
      return Math.pow(value, 3);
    }
    return 0.1284 * value - 0.01771;
  }

  private adjustRainbowRgb(value: number): number {
    const corrected = value <= 0.0031308 ? 12.92 * value : 1.055 * Math.pow(value, 1 / 2.4) - 0.055;
    return Math.round(Math.min(Math.max(corrected, 0.0), 1.0) * 255);
  }

  private toRainbowHex(value: number): string {
    const hex = value.toString(16);
    return hex.length === 1 ? `0${hex}` : hex;
  }

  private escapeHtml(value: string): string {
    return value
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  private isMatrixUserId(value: string): boolean {
    if (value.length === 0) {
      return false;
    }
    return /^@[A-Za-z0-9._=\-/]+:[A-Za-z0-9.-]+(:[0-9]+)?$/.test(value);
  }

  private isMatrixRoomAddress(value: string): boolean {
    if (value.length === 0) {
      return false;
    }
    return /^[!#][A-Za-z0-9._=\-/]+:[A-Za-z0-9.-]+(:[0-9]+)?$/.test(value);
  }

  private handleMarkRoomRead(): void {
    if (this.isMarkingRead) {
      return;
    }
    this.isMarkingRead = true;
    this.readError = '';
    this.viewModel.markSelectedRoomAsRead(this.snapshot).then((result: MarkRoomReadResult) => {
      this.isMarkingRead = false;
      if (!result.ok) {
        this.readError = result.errorMessage;
        return;
      }
      this.snapshot = result.snapshot;
      this.clearJumpToUnread();
    }).catch((error: Error) => {
      this.isMarkingRead = false;
      this.readError = `${error}`;
    });
  }

  private handleMarkRoomUnread(): void {
    if (this.isMarkingUnread) {
      return;
    }
    this.isMarkingUnread = true;
    this.readError = '';
    this.viewModel.markSelectedRoomAsUnread(this.snapshot).then((result: MarkRoomReadResult) => {
      this.isMarkingUnread = false;
      if (!result.ok) {
        this.readError = result.errorMessage;
        return;
      }
      this.snapshot = result.snapshot;
    }).catch((error: Error) => {
      this.isMarkingUnread = false;
      this.readError = `${error}`;
    });
  }

  private handleRoomListContextMenuReadAction(): void {
    const room = this.roomListContextMenuRoom();
    if (room === null || this.isUpdatingRoomListContextMenu) {
      return;
    }
    this.isUpdatingRoomListContextMenu = true;
    this.roomListContextMenuError = '';
    const shouldClearJumpToUnread = this.roomHasNewContent(room);
    const task = shouldClearJumpToUnread
      ? this.viewModel.markRoomAsRead(this.snapshot, room.id)
      : this.viewModel.markRoomAsUnread(this.snapshot, room.id);
    task.then((result: MarkRoomReadResult) => {
      this.isUpdatingRoomListContextMenu = false;
      if (!result.ok) {
        this.roomListContextMenuError = result.errorMessage;
        return;
      }
      this.snapshot = result.snapshot;
      if (shouldClearJumpToUnread) {
        this.clearJumpToUnread();
      }
      this.closeRoomListContextMenu();
    }).catch((error: Error) => {
      this.isUpdatingRoomListContextMenu = false;
      this.roomListContextMenuError = `${error}`;
    });
  }

  private handleRoomListContextMenuFavoriteToggle(): void {
    const room = this.roomListContextMenuRoom();
    if (room === null || this.isUpdatingRoomListContextMenu) {
      return;
    }
    const nextFavorite = !room.isFavorite;
    this.isUpdatingRoomListContextMenu = true;
    this.roomListContextMenuError = '';
    this.viewModel.setRoomIsFavorite(this.snapshot, room.id, nextFavorite).then((result: UpdateRoomMetadataResult) => {
      this.isUpdatingRoomListContextMenu = false;
      if (!result.ok) {
        this.roomListContextMenuError = result.errorMessage;
        return;
      }
      this.snapshot = result.snapshot;
    }).catch((error: Error) => {
      this.isUpdatingRoomListContextMenu = false;
      this.roomListContextMenuError = `${error}`;
    });
  }

  private handleRoomDetailsReadAction(): void {
    const room = this.roomDetailsRoom();
    if (room === null || this.isUpdatingRoomDetails) {
      return;
    }
    this.isUpdatingRoomDetails = true;
    this.roomDetailsError = '';
    const shouldClearJumpToUnread = this.roomHasNewContent(room);
    const task = shouldClearJumpToUnread
      ? this.viewModel.markRoomAsRead(this.snapshot, room.id)
      : this.viewModel.markRoomAsUnread(this.snapshot, room.id);
    task.then((result: MarkRoomReadResult) => {
      this.isUpdatingRoomDetails = false;
      if (!result.ok) {
        this.roomDetailsError = result.errorMessage;
        return;
      }
      this.snapshot = result.snapshot;
      if (shouldClearJumpToUnread) {
        this.clearJumpToUnread();
      }
    }).catch((error: Error) => {
      this.isUpdatingRoomDetails = false;
      this.roomDetailsError = `${error}`;
    });
  }

  private handleRoomDetailsFavoriteToggle(): void {
    const room = this.roomDetailsRoom();
    if (room === null || this.isUpdatingRoomDetails) {
      return;
    }
    const nextFavorite = !room.isFavorite;
    this.isUpdatingRoomDetails = true;
    this.roomDetailsError = '';
    this.viewModel.setRoomIsFavorite(this.snapshot, room.id, nextFavorite).then((result: UpdateRoomMetadataResult) => {
      this.isUpdatingRoomDetails = false;
      if (!result.ok) {
        this.roomDetailsError = result.errorMessage;
        return;
      }
      this.snapshot = result.snapshot;
    }).catch((error: Error) => {
      this.isUpdatingRoomDetails = false;
      this.roomDetailsError = `${error}`;
    });
  }

  private confirmRoomDetailsLeave(): void {
    const room = this.roomDetailsRoom();
    if (room === null || this.isUpdatingRoomDetails) {
      return;
    }
    this.isUpdatingRoomDetails = true;
    this.roomDetailsError = '';
    this.viewModel.leaveRoom(this.snapshot, room.id).then((result: UpdateRoomMetadataResult) => {
      this.isUpdatingRoomDetails = false;
      if (!result.ok) {
        this.roomDetailsError = result.errorMessage;
        return;
      }
      this.snapshot = result.snapshot;
      this.refreshVisibleTimelineRoomTitle(this.snapshot.selectedRoomId);
      this.clearJumpToUnread();
      this.closeRoomDetails();
    }).catch((error: Error) => {
      this.isUpdatingRoomDetails = false;
      this.roomDetailsError = `${error}`;
    });
  }

  private confirmRoomListContextMenuLeave(): void {
    const room = this.roomListContextMenuRoom();
    if (room === null || this.isUpdatingRoomListContextMenu) {
      return;
    }
    this.isUpdatingRoomListContextMenu = true;
    this.roomListContextMenuError = '';
    this.viewModel.leaveRoom(this.snapshot, room.id).then((result: UpdateRoomMetadataResult) => {
      this.isUpdatingRoomListContextMenu = false;
      if (!result.ok) {
        this.roomListContextMenuError = result.errorMessage;
        return;
      }
      this.snapshot = result.snapshot;
      this.refreshVisibleTimelineRoomTitle(this.snapshot.selectedRoomId);
      this.clearJumpToUnread();
      this.closeRoomListContextMenu();
    }).catch((error: Error) => {
      this.isUpdatingRoomListContextMenu = false;
      this.roomListContextMenuError = `${error}`;
    });
  }

  private handleReportRoomSubmit(): void {
    const room = this.reportRoom();
    if (room === null || this.isReportingRoom) {
      return;
    }
    this.isReportingRoom = true;
    this.reportRoomError = '';
    const shouldReport = !this.reportRoomAlreadySubmitted;
    this.viewModel.reportRoom(this.snapshot, room.id, this.reportRoomReason, this.reportRoomLeaveRoom, shouldReport).then((result: UpdateRoomMetadataResult) => {
      this.isReportingRoom = false;
      if (!result.ok) {
        this.reportRoomError = result.errorMessage;
        if (result.errorMessage.indexOf('Leave room failed:') === 0) {
          this.reportRoomAlreadySubmitted = true;
        }
        return;
      }
      this.snapshot = result.snapshot;
      if (this.reportRoomLeaveRoom) {
        this.refreshVisibleTimelineRoomTitle(this.snapshot.selectedRoomId);
        this.clearJumpToUnread();
      }
      this.closeReportRoom();
    }).catch((error: Error) => {
      this.isReportingRoom = false;
      this.reportRoomError = `${error}`;
    });
  }

  private handleSelectRoom(roomId: string): void {
    this.snapshot = this.viewModel.selectRoom(this.snapshot, roomId);
    this.refreshVisibleTimelineRoomTitle(roomId);
    this.selectedTab = 1;
    this.handleTimelineVisibleForRead();
  }

  private handleTimelineVisibleForRead(): void {
    if (this.isAutoMarkingRead || this.snapshot.session === null || this.snapshot.selectedRoomId.length === 0) {
      return;
    }
    this.captureJumpToUnreadState();
    this.isAutoMarkingRead = true;
    this.viewModel.autoMarkSelectedRoomAsRead(this.snapshot).then((result: MarkRoomReadResult) => {
      this.isAutoMarkingRead = false;
      if (result.ok) {
        this.snapshot = result.snapshot;
      }
    }).catch(() => {
      this.isAutoMarkingRead = false;
    });
  }

  private handleMarkAllRoomsRead(): void {
    if (this.isMarkingAllRead) {
      return;
    }
    this.isMarkingAllRead = true;
    this.homeReadError = '';
    this.viewModel.markAllRoomsAsRead(this.snapshot).then((result: MarkRoomReadResult) => {
      this.isMarkingAllRead = false;
      if (!result.ok) {
        this.homeReadError = result.errorMessage;
        return;
      }
      this.snapshot = result.snapshot;
      this.clearJumpToUnread();
    }).catch((error: Error) => {
      this.isMarkingAllRead = false;
      this.homeReadError = `${error}`;
    });
  }

  private handleUpdateProfile(): void {
    if (this.isUpdatingProfile) {
      return;
    }
    this.isUpdatingProfile = true;
    this.profileError = '';
    const context = this.abilityContext();
    this.viewModel.updateOwnProfile(this.snapshot, this.displayNameDraft, this.userStatusDraft, context).then((result: UpdateProfileResult) => {
      this.isUpdatingProfile = false;
      if (!result.ok) {
        this.profileError = result.errorMessage;
        return;
      }
      this.snapshot = result.snapshot;
      this.syncProfileDrafts();
    }).catch((error: Error) => {
      this.isUpdatingProfile = false;
      this.profileError = `${error}`;
    });
  }

  private handleToggleReadReceiptPreference(): void {
    if (this.isUpdatingReadReceiptPreference || this.snapshot.session === null) {
      return;
    }
    this.isUpdatingReadReceiptPreference = true;
    this.privacyError = '';
    const context = this.abilityContext();
    const nextValue = !this.isPresenceSharingEnabled();
    this.viewModel.updateReadReceiptPreference(this.snapshot, nextValue, context).then((result: UpdateReadReceiptPreferenceResult) => {
      this.isUpdatingReadReceiptPreference = false;
      if (!result.ok) {
        this.privacyError = result.errorMessage;
        return;
      }
      this.snapshot = result.snapshot;
    }).catch((error: Error) => {
      this.isUpdatingReadReceiptPreference = false;
      this.privacyError = `${error}`;
    });
  }

  private handleSetTimelineMediaPreviewMode(mode: TimelineMediaPreviewMode): void {
    if (this.isUpdatingMediaPreviewPreference || this.snapshot.session === null) {
      return;
    }
    if (this.currentTimelineMediaPreviewMode() === mode) {
      return;
    }
    this.isUpdatingMediaPreviewPreference = true;
    this.mediaPreviewError = '';
    const context = this.abilityContext();
    this.viewModel.updateTimelineMediaPreviewMode(this.snapshot, mode, context).then((result: UpdateTimelineMediaPreviewModeResult) => {
      this.isUpdatingMediaPreviewPreference = false;
      if (!result.ok) {
        this.mediaPreviewError = result.errorMessage;
        return;
      }
      this.snapshot = result.snapshot;
    }).catch((error: Error) => {
      this.isUpdatingMediaPreviewPreference = false;
      this.mediaPreviewError = `${error}`;
    });
  }

  private handlePublishNotification(): void {
    if (this.isPublishingNotification) {
      return;
    }
    this.isPublishingNotification = true;
    this.notificationStatus = 'Publishing notification';
    this.notificationService.publishUnreadMessage(
      this.abilityContext(),
      'dm-bob',
      'Bob',
      'Bob',
      'Direct message timeline is separate from the room timeline.'
    ).then((result: PublishRoomNotificationResult) => {
      this.isPublishingNotification = false;
      this.notificationStatus = result.ok ? result.message : `Notification failed: ${result.message}`;
    }).catch((error: Error) => {
      this.isPublishingNotification = false;
      this.notificationStatus = `Notification failed: ${error}`;
    });
  }

  private syncProfileDrafts(): void {
    if (this.snapshot.session === null) {
      this.stopForegroundSyncLoop();
      this.displayNameDraft = '';
      this.userStatusDraft = '';
      return;
    }
    this.displayNameDraft = this.snapshot.session.account.displayName;
    this.userStatusDraft = this.snapshot.session.account.userStatus;
    this.startForegroundSyncLoop();
  }

  private startForegroundSyncLoop(): void {
    if (this.foregroundSyncTimerId >= 0 || this.snapshot.session === null) {
      return;
    }
    this.foregroundSyncStatus = 'Foreground sync: starting';
    this.runForegroundSyncTick();
    this.foregroundSyncTimerId = setInterval(() => {
      this.runForegroundSyncTick();
    }, 45000);
  }

  private stopForegroundSyncLoop(): void {
    if (this.foregroundSyncTimerId >= 0) {
      clearInterval(this.foregroundSyncTimerId);
      this.foregroundSyncTimerId = -1;
    }
    this.isForegroundSyncing = false;
    if (this.snapshot.session === null) {
      this.foregroundSyncStatus = '';
    }
  }

  private runForegroundSyncTick(): void {
    if (this.authState !== ClientAuthState.SignedIn || this.snapshot.session === null || this.isForegroundSyncing) {
      return;
    }
    this.isForegroundSyncing = true;
    const beforeBatch = this.snapshot.session.nextSyncBatch;
    this.foregroundSyncStatus = beforeBatch.length > 0 ? `Foreground sync: polling since ${this.compactUri(beforeBatch)}` : 'Foreground sync: initial poll';
    this.viewModel.runForegroundSyncOnce(this.snapshot, this.abilityContext()).then((result: ForegroundSyncResult) => {
      this.isForegroundSyncing = false;
      if (result.ok) {
        this.snapshot = result.snapshot;
        if (result.skipped) {
          this.foregroundSyncStatus = 'Foreground sync: fixture session idle';
        } else {
          const nextBatch = result.nextBatch.length > 0 ? this.compactUri(result.nextBatch) : 'none';
          this.foregroundSyncStatus = `Foreground sync: updated ${nextBatch}`;
        }
        return;
      }
      this.foregroundSyncStatus = `Foreground sync: error ${result.errorMessage}`;
    }).catch((error: Error) => {
      this.isForegroundSyncing = false;
      this.foregroundSyncStatus = `Foreground sync: error ${error}`;
    });
  }

  private abilityContext(): common.UIAbilityContext {
    return this.getUIContext().getHostContext() as common.UIAbilityContext;
  }

  private isPresenceSharingEnabled(): boolean {
    if (this.snapshot.session === null) {
      return false;
    }
    return this.snapshot.session.sendPublicReadReceipts && this.snapshot.session.renderReadReceipts;
  }
}
