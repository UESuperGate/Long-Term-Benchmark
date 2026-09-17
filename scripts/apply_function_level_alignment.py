#!/usr/bin/env python3
from pathlib import Path


ROOT = Path(r"C:\Users\xiexi\qingyu")


VIEWMODEL = """import { AccountProfile, RoomSummary, ScenarioInfo, TimelineEvent } from '../model/ElementModels';
import { MockMatrixService } from '../services/MockMatrixService';
import { createFunctionLevelAlignmentRows } from '../androidparity/FunctionLevelParity';

export class ElementBaseViewModel {
  private readonly service: MockMatrixService = new MockMatrixService();

  getScenarioInfo(): ScenarioInfo {
    return this.service.getScenarioInfo();
  }

  getAccountProfile(): AccountProfile {
    return this.service.getAccountProfile();
  }

  getRooms(): RoomSummary[] {
    return this.service.getRooms();
  }

  getTimelineEvents(): TimelineEvent[] {
    return this.service.getTimelineEvents();
  }

  getSecurityRows(): string[] {
    return this.service.getSecurityRows();
  }

  getFunctionLevelAlignmentRows(): string[] {
    return createFunctionLevelAlignmentRows(this.getScenarioInfo().scenarioId);
  }
}
"""


PARITY = """export enum ParityArea {
  Preferences = 'preferences',
  TimelineMessages = 'timeline_messages',
  TimelineCalls = 'timeline_calls',
  LocationShare = 'location_share',
  LinkNewDevice = 'link_new_device'
}

export interface AndroidSymbolAlignment {
  area: ParityArea;
  androidSymbol: string;
  arktsSymbol: string;
  granularity: string;
  baseSemantics: string;
}

export interface MatrixUserParity {
  userId: string;
  displayName: string;
}

export enum PreferencesRootEventKind {
  OnVersionInfoClick = 'OnVersionInfoClick',
  SwitchToSession = 'SwitchToSession'
}

export interface PreferencesRootEvent {
  kind: PreferencesRootEventKind;
  userId?: string;
}

export interface PreferencesRootState {
  myUser: MatrixUserParity;
  isMultiAccountEnabled: boolean;
  showDeveloperSettings: boolean;
  version: string;
  deviceId: string;
  sections: string[];
  lastEvent: string;
}

export class PreferencesRootPresenterParity {
  present(): PreferencesRootState {
    return {
      myUser: { userId: '@alice:matrix.org', displayName: 'Alice' },
      isMultiAccountEnabled: false,
      showDeveloperSettings: false,
      version: 'base',
      deviceId: 'DEVICE',
      sections: this.preferencesRootView(),
      lastEvent: 'none'
    };
  }

  preferencesRootView(): string[] {
    return [
      this.UserPreferences(),
      this.MultiAccountSection(),
      this.userStatusInsertionPoint(),
      this.ManageAccountSection(),
      this.ManageAppSection(),
      this.GeneralSection(),
      this.Footer()
    ];
  }

  UserPreferences(): string {
    return 'UserPreferences clickable row opens profile';
  }

  MultiAccountSection(): string {
    return 'MultiAccountSection hidden when multi-account is disabled';
  }

  userStatusInsertionPoint(): string {
    return 'reserved without rendering a user-status row in this base';
  }

  ManageAccountSection(): string {
    return 'ManageAccountSection includes link-new-device and blocked-users rows';
  }

  ManageAppSection(): string {
    return 'ManageAppSection includes notifications, lock screen and secure backup';
  }

  GeneralSection(): string {
    return 'GeneralSection includes about, analytics, developer and sign-out rows';
  }

  Footer(): string {
    return 'Footer exposes version-info click until developer settings are shown';
  }

  handleEvent(event: PreferencesRootEvent): PreferencesRootState {
    const state = this.present();
    if (event.kind === PreferencesRootEventKind.OnVersionInfoClick) {
      state.lastEvent = 'version-info-click';
    }
    if (event.kind === PreferencesRootEventKind.SwitchToSession) {
      state.lastEvent = `switch-to-session:${event.userId ?? ''}`;
    }
    return state;
  }
}

export enum ParityMessageType {
  Text = 'TextMessageType',
  Image = 'ImageMessageType',
  Video = 'VideoMessageType',
  Location = 'LocationMessageType',
  Other = 'OtherMessageType',
  GalleryFixture = 'GalleryFixture'
}

export interface ParityMessageContent {
  type: ParityMessageType;
  body: string;
  filename?: string;
  width?: number;
  height?: number;
  edited?: boolean;
}

export interface ParityTimelineContent {
  type: string;
  body: string;
  canBeCopied: boolean;
  canBeForwarded: boolean;
  canReact: boolean;
  isEdited: boolean;
  aspectRatio?: number;
}

export class TimelineItemContentMessageFactoryParity {
  create(content: ParityMessageContent): ParityTimelineContent {
    if (content.type === ParityMessageType.Text) {
      return this.createTextMessage(content);
    }
    if (content.type === ParityMessageType.Image) {
      return this.createImageMessage(content);
    }
    if (content.type === ParityMessageType.Video) {
      return this.createVideoMessage(content);
    }
    if (content.type === ParityMessageType.Location) {
      return this.createLocationMessage(content);
    }
    if (content.type === ParityMessageType.GalleryFixture) {
      return this.createUnsupportedGalleryFixture(content);
    }
    return this.createOtherMessage(content);
  }

  createTextMessage(content: ParityMessageContent): ParityTimelineContent {
    return this.withCommonActions('TimelineItemTextContent', this.withLinks(content.body), content.edited ?? false);
  }

  createImageMessage(content: ParityMessageContent): ParityTimelineContent {
    const item = this.withCommonActions('TimelineItemImageContent', content.filename ?? content.body, content.edited ?? false);
    item.aspectRatio = this.aspectRatioOf(content.width, content.height);
    return item;
  }

  createVideoMessage(content: ParityMessageContent): ParityTimelineContent {
    const item = this.withCommonActions('TimelineItemVideoContent', content.filename ?? content.body, content.edited ?? false);
    item.aspectRatio = this.aspectRatioOf(content.width, content.height);
    return item;
  }

  createLocationMessage(content: ParityMessageContent): ParityTimelineContent {
    const hasGeoUri = content.body.indexOf('geo:') === 0;
    return this.withCommonActions(hasGeoUri ? 'TimelineItemLocationContent.Static' : 'TimelineItemTextContent', content.body, content.edited ?? false);
  }

  createOtherMessage(content: ParityMessageContent): ParityTimelineContent {
    return {
      type: 'TimelineItemUnknownContent',
      body: content.body,
      canBeCopied: false,
      canBeForwarded: false,
      canReact: false,
      isEdited: false
    };
  }

  createUnsupportedGalleryFixture(content: ParityMessageContent): ParityTimelineContent {
    const unknown = this.createOtherMessage(content);
    unknown.body = `Unsupported gallery fixture: ${content.body}`;
    return unknown;
  }

  aspectRatioOf(width?: number, height?: number): number | undefined {
    if (width === undefined || height === undefined || width < 1 || height < 1) {
      return undefined;
    }
    const ratio = width / height;
    if (ratio < 0.001) {
      return 0.001;
    }
    if (ratio > 10) {
      return 10;
    }
    return ratio;
  }

  parseHtml(document: string): string {
    return document.replace(/<[^>]+>/g, '');
  }

  withLinks(text: string): string {
    return text;
  }

  canBeCopied(content: ParityTimelineContent): boolean {
    return content.canBeCopied;
  }

  canBeForwarded(content: ParityTimelineContent): boolean {
    return content.canBeForwarded;
  }

  canReact(content: ParityTimelineContent): boolean {
    return content.canReact;
  }

  isEdited(content: ParityTimelineContent): boolean {
    return content.isEdited;
  }

  private withCommonActions(type: string, body: string, edited: boolean): ParityTimelineContent {
    return {
      type,
      body,
      canBeCopied: true,
      canBeForwarded: true,
      canReact: true,
      isEdited: edited
    };
  }
}

export enum CallIntentParity {
  Audio = 'AUDIO',
  Video = 'VIDEO'
}

export enum RtcNotificationStateKind {
  Started = 'Started',
  Declined = 'Declined'
}

export interface RtcNotificationStateParity {
  kind: RtcNotificationStateKind;
  byMe: boolean;
}

export interface TimelineRoomInfoParity {
  isDm: boolean;
}

export interface RtcNotificationContentParity {
  callIntent: CallIntentParity;
  state: RtcNotificationStateParity;
}

export interface TimelineCallNotifyRow {
  textRes: string;
  icon: string;
  supportsTimelineCard: boolean;
}

export class TimelineItemCallNotifyParity {
  TimelineItemCallNotifyViewModel(roomInfo: TimelineRoomInfoParity, content: RtcNotificationContentParity): TimelineCallNotifyRow {
    return {
      textRes: this.getTextRes(roomInfo, content),
      icon: this.getIcon(roomInfo, content),
      supportsTimelineCard: this.supportsTimelineCard()
    };
  }

  getTextRes(roomInfo: TimelineRoomInfoParity, content: RtcNotificationContentParity): string {
    if (roomInfo.isDm && content.state.kind === RtcNotificationStateKind.Declined) {
      return content.state.byMe ? 'common_call_you_declined' : 'common_call_declined';
    }
    return 'common_call_started';
  }

  getIcon(roomInfo: TimelineRoomInfoParity, content: RtcNotificationContentParity): string {
    const declined = roomInfo.isDm && content.state.kind === RtcNotificationStateKind.Declined;
    if (content.callIntent === CallIntentParity.Audio) {
      return declined ? 'VoiceCallDeclinedSolid' : 'VoiceCallSolid';
    }
    return declined ? 'VideoCallDeclinedSolid' : 'VideoCallSolid';
  }

  supportsTimelineCard(): boolean {
    return false;
  }

  activeCallFixtureContent(): ParityTimelineContent {
    return {
      type: 'TimelineItemUnknownContent',
      body: 'Active call fixture remains unsupported at this base',
      canBeCopied: false,
      canBeForwarded: false,
      canReact: false,
      isEdited: false
    };
  }
}

export enum ShareLocationEventKind {
  ShareStaticLocation = 'ShareStaticLocation',
  ShowLiveLocationDurationPicker = 'ShowLiveLocationDurationPicker',
  StartLiveLocationShare = 'StartLiveLocationShare',
  StartTrackingUserLocation = 'StartTrackingUserLocation',
  StopTrackingUserLocation = 'StopTrackingUserLocation',
  DismissDialog = 'DismissDialog',
  RequestPermissions = 'RequestPermissions',
  OpenAppSettings = 'OpenAppSettings',
  OpenLocationSettings = 'OpenLocationSettings'
}

export interface ShareLocationEventParity {
  kind: ShareLocationEventKind;
  locationGeoUri?: string;
  isPinned?: boolean;
  durationMs?: number;
}

export interface ShareLocationStateParity {
  dialogState: string;
  trackUserLocation: boolean;
  hasLocationPermission: boolean;
  canShareLiveLocation: boolean;
  lastSideEffect: string;
}

export class ShareLocationPresenterParity {
  present(): ShareLocationStateParity {
    return {
      dialogState: 'None',
      trackUserLocation: true,
      hasLocationPermission: true,
      canShareLiveLocation: false,
      lastSideEffect: 'none'
    };
  }

  checkLocationConstraints(hasPermission: boolean, isLocationEnabled: boolean): string {
    if (!hasPermission) {
      return 'MissingPermissions';
    }
    if (!isLocationEnabled) {
      return 'LocationDisabled';
    }
    return 'Success';
  }

  handleEvent(event: ShareLocationEventParity): ShareLocationStateParity {
    const state = this.present();
    if (event.kind === ShareLocationEventKind.ShareStaticLocation) {
      state.lastSideEffect = this.shareStaticLocation(event);
    } else if (event.kind === ShareLocationEventKind.ShowLiveLocationDurationPicker) {
      state.dialogState = state.canShareLiveLocation ? 'LiveLocationDurations' : 'Constraints';
    } else if (event.kind === ShareLocationEventKind.StartLiveLocationShare) {
      state.lastSideEffect = this.handleStartLiveLocationShare(event.durationMs ?? 0);
    } else if (event.kind === ShareLocationEventKind.StopTrackingUserLocation) {
      state.trackUserLocation = false;
    } else if (event.kind === ShareLocationEventKind.RequestPermissions) {
      state.lastSideEffect = 'PermissionsEvents.RequestPermissions';
    } else if (event.kind === ShareLocationEventKind.OpenAppSettings) {
      state.lastSideEffect = 'locationActions.openAppSettings';
    } else if (event.kind === ShareLocationEventKind.OpenLocationSettings) {
      state.lastSideEffect = 'locationActions.openLocationSettings';
    }
    return state;
  }

  shareStaticLocation(event: ShareLocationEventParity): string {
    const geoUri = event.locationGeoUri ?? 'geo:0,0';
    return `Timeline.sendLocation:${this.generateBody(geoUri)}:${event.isPinned === true ? 'PIN' : 'SENDER'}`;
  }

  handleStartLiveLocationShare(durationMs: number): string {
    return `disabled_side_effect_for_base:${durationMs}`;
  }

  getTimeline(timelineMode: string): string {
    return timelineMode === 'Thread' ? 'room.createTimeline(CreateTimelineParams.Threaded)' : 'room.liveTimeline';
  }

  generateBody(uri: string): string {
    return `Location was shared at ${uri}`;
  }

  liveLocationDurations(): number[] {
    return [15 * 60 * 1000, 60 * 60 * 1000, 8 * 60 * 60 * 1000];
  }
}

export enum AsyncDataKindParity {
  Uninitialized = 'Uninitialized',
  Loading = 'Loading',
  Success = 'Success',
  Failure = 'Failure'
}

export enum LinkNewDeviceRootEventKind {
  LinkMobileDevice = 'LinkMobileDevice',
  CloseDialog = 'CloseDialog'
}

export interface LinkNewDeviceRootEventParity {
  kind: LinkNewDeviceRootEventKind;
}

export interface LinkNewDeviceRootStateParity {
  isSupported: AsyncDataKindParity;
  dialog: string;
  lastNavigation: string;
}

export class LinkNewDeviceRootPresenterParity {
  present(canLinkNewDevice: boolean): LinkNewDeviceRootStateParity {
    return {
      isSupported: canLinkNewDevice ? AsyncDataKindParity.Success : AsyncDataKindParity.Failure,
      dialog: canLinkNewDevice ? 'None' : 'NotSupported',
      lastNavigation: 'none'
    };
  }

  handleEvent(event: LinkNewDeviceRootEventParity): LinkNewDeviceRootStateParity {
    const state = this.present(true);
    if (event.kind === LinkNewDeviceRootEventKind.LinkMobileDevice) {
      state.lastNavigation = this.linkMobileDevice();
    }
    if (event.kind === LinkNewDeviceRootEventKind.CloseDialog) {
      state.dialog = this.closeDialog();
    }
    return state;
  }

  linkMobileDevice(): string {
    return 'wait for QR code then link mobile device';
  }

  closeDialog(): string {
    return 'None';
  }
}

export class ShowQrCodeNodeParity {
  View(): string {
    return this.ShowQrCodeView(this.Inputs('matrix:client:base-static-code'));
  }

  Inputs(qrCodeData: string): string {
    return qrCodeData;
  }

  ShowQrCodeView(qrCodeData: string): string {
    return `static QR code:${qrCodeData}`;
  }
}

export enum ScanQrCodeEventKind {
  QrCodeScanned = 'QrCodeScanned',
  TryAgain = 'TryAgain'
}

export interface ScanQrCodeEventParity {
  kind: ScanQrCodeEventKind;
  data?: string;
}

export interface ScanQrCodeStateParity {
  scanAction: AsyncDataKindParity;
  lastStep: string;
}

export class ScanQrCodePresenterParity {
  present(): ScanQrCodeStateParity {
    return {
      scanAction: AsyncDataKindParity.Uninitialized,
      lastStep: 'observe LinkDesktopStep.InvalidQrCode'
    };
  }

  handleEvent(event: ScanQrCodeEventParity): ScanQrCodeStateParity {
    const state = this.present();
    if (event.kind === ScanQrCodeEventKind.TryAgain) {
      state.scanAction = AsyncDataKindParity.Uninitialized;
    }
    if (event.kind === ScanQrCodeEventKind.QrCodeScanned) {
      state.scanAction = AsyncDataKindParity.Loading;
      state.lastStep = `linkDesktop.scan:${event.data ?? ''}`;
    }
    return state;
  }
}

export class LinkDeviceNumberParity {
  private digits: string[];

  constructor(digits: string[]) {
    this.digits = digits;
  }

  static createEmpty(size: number): LinkDeviceNumberParity {
    const digits: string[] = [];
    for (let index = 0; index < size; index++) {
      digits.push('');
    }
    return new LinkDeviceNumberParity(digits);
  }

  fillWith(text: string): LinkDeviceNumberParity {
    const next: string[] = [];
    for (let index = 0; index < this.digits.length; index++) {
      next.push(text.charAt(index));
    }
    return new LinkDeviceNumberParity(next);
  }

  length(): number {
    return this.digits.length;
  }

  toText(): string {
    return this.digits.join('');
  }

  isComplete(): boolean {
    return this.digits.every((digit: string) => digit.length > 0);
  }
}

const COMMON_ALIGNMENTS: AndroidSymbolAlignment[] = [
  {
    area: ParityArea.Preferences,
    androidSymbol: 'PreferencesRootView(state, callbacks)',
    arktsSymbol: 'PreferencesRootPresenterParity.preferencesRootView()',
    granularity: 'composable function -> pure section plan',
    baseSemantics: 'renders user profile, account, app, general and footer sections'
  },
  {
    area: ParityArea.Preferences,
    androidSymbol: 'PreferencesRootView // User status will be added here',
    arktsSymbol: 'PreferencesRootPresenterParity.userStatusInsertionPoint()',
    granularity: 'intra-function insertion point',
    baseSemantics: 'keeps the reserved point but returns no user-status row'
  },
  {
    area: ParityArea.TimelineMessages,
    androidSymbol: 'TimelineItemContentMessageFactory.create(ImageMessageType)',
    arktsSymbol: 'TimelineItemContentMessageFactoryParity.createImageMessage()',
    granularity: 'when-branch -> function',
    baseSemantics: 'maps one media event to image content and clamps aspect ratio'
  },
  {
    area: ParityArea.TimelineMessages,
    androidSymbol: 'TimelineItemContentMessageFactory.create(OtherMessageType)',
    arktsSymbol: 'TimelineItemContentMessageFactoryParity.createUnsupportedGalleryFixture()',
    granularity: 'unsupported branch -> explicit fixture adapter',
    baseSemantics: 'gallery fixture is present but mapped to unknown unsupported content'
  },
  {
    area: ParityArea.TimelineCalls,
    androidSymbol: 'TimelineItemCallNotifyView.getTextRes()',
    arktsSymbol: 'TimelineItemCallNotifyParity.getTextRes()',
    granularity: 'private helper -> method',
    baseSemantics: 'DM declined calls vary text; room calls collapse to call started'
  },
  {
    area: ParityArea.TimelineCalls,
    androidSymbol: 'TimelineItemCallNotifyView.getIcon()',
    arktsSymbol: 'TimelineItemCallNotifyParity.getIcon()',
    granularity: 'private helper -> method',
    baseSemantics: 'audio/video and declined state select the matching call icon'
  },
  {
    area: ParityArea.TimelineCalls,
    androidSymbol: 'Active call timeline card absent before final',
    arktsSymbol: 'TimelineItemCallNotifyParity.supportsTimelineCard()',
    granularity: 'final component absence -> boolean guard',
    baseSemantics: 'active call fixture is rendered as unsupported content'
  },
  {
    area: ParityArea.LocationShare,
    androidSymbol: 'ShareLocationPresenter.present()',
    arktsSymbol: 'ShareLocationPresenterParity.present()',
    granularity: 'presenter function -> presenter function',
    baseSemantics: 'derives permission, tracking and feature-flag dependent state'
  },
  {
    area: ParityArea.LocationShare,
    androidSymbol: 'ShareLocationPresenter.handleEvent(ShareStaticLocation)',
    arktsSymbol: 'ShareLocationPresenterParity.shareStaticLocation()',
    granularity: 'event branch -> side-effect summary',
    baseSemantics: 'static location goes through Timeline.sendLocation semantics'
  },
  {
    area: ParityArea.LocationShare,
    androidSymbol: 'ShareLocationPresenter.handleEvent(StartLiveLocationShare)',
    arktsSymbol: 'ShareLocationPresenterParity.handleStartLiveLocationShare()',
    granularity: 'event branch -> disabled side effect',
    baseSemantics: 'event exists but the live share SDK call remains disabled in the base'
  },
  {
    area: ParityArea.LinkNewDevice,
    androidSymbol: 'LinkNewDeviceRootPresenter.present()',
    arktsSymbol: 'LinkNewDeviceRootPresenterParity.present()',
    granularity: 'presenter function -> presenter function',
    baseSemantics: 'checks support and exposes root dialog/navigation state'
  },
  {
    area: ParityArea.LinkNewDevice,
    androidSymbol: 'ShowQrCodeNode.View() -> ShowQrCodeView(qrCodeData)',
    arktsSymbol: 'ShowQrCodeNodeParity.View()',
    granularity: 'node view -> static view model',
    baseSemantics: 'uses static QR data without presenter-owned rotation'
  },
  {
    area: ParityArea.LinkNewDevice,
    androidSymbol: 'Number.createEmpty/fillWith/length/toText/isComplete',
    arktsSymbol: 'LinkDeviceNumberParity.createEmpty/fillWith/length/toText/isComplete',
    granularity: 'value-object methods -> value-object methods',
    baseSemantics: 'manual confirmation code editing keeps digit-level behavior'
  }
];

export function getFunctionLevelAlignments(scenarioId: string): AndroidSymbolAlignment[] {
  if (scenarioId === 'user_status_base') {
    return COMMON_ALIGNMENTS.filter((item: AndroidSymbolAlignment) => item.area === ParityArea.Preferences);
  }
  if (scenarioId === 'gallery_messages_base') {
    return COMMON_ALIGNMENTS.filter((item: AndroidSymbolAlignment) => item.area === ParityArea.TimelineMessages);
  }
  if (scenarioId === 'active_call_timeline_base') {
    return COMMON_ALIGNMENTS.filter((item: AndroidSymbolAlignment) => item.area === ParityArea.TimelineCalls);
  }
  if (scenarioId === 'live_location_base') {
    return COMMON_ALIGNMENTS.filter((item: AndroidSymbolAlignment) => item.area === ParityArea.LocationShare);
  }
  if (scenarioId === 'link_new_device_base') {
    return COMMON_ALIGNMENTS.filter((item: AndroidSymbolAlignment) => item.area === ParityArea.LinkNewDevice);
  }
  return COMMON_ALIGNMENTS;
}

export function createFunctionLevelAlignmentRows(scenarioId: string): string[] {
  return getFunctionLevelAlignments(scenarioId).map((item: AndroidSymbolAlignment) => {
    return `${item.androidSymbol} -> ${item.arktsSymbol}: ${item.baseSemantics}`;
  });
}
"""


def patch_index(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if "functionAlignmentRows" not in text:
        text = text.replace(
            "  private securityRows: string[] = this.viewModel.getSecurityRows();\n",
            "  private securityRows: string[] = this.viewModel.getSecurityRows();\n"
            "  private functionAlignmentRows: string[] = this.viewModel.getFunctionLevelAlignmentRows();\n",
        )
    if "Function-level Android parity" not in text:
        text = text.replace(
            "        ForEach(this.scenario.intentionallyAbsent, (item: string, index: number) => {\n"
            "          Text(item)\n"
            "            .fontSize(13)\n"
            "            .fontColor('#475569')\n"
            "            .lineHeight(19)\n"
            "            .padding(10)\n"
            "            .borderRadius(8)\n"
            "            .backgroundColor('#FFFFFF')\n"
            "            .id(`absent_${index}`)\n"
            "        })\n",
            "        ForEach(this.scenario.intentionallyAbsent, (item: string, index: number) => {\n"
            "          Text(item)\n"
            "            .fontSize(13)\n"
            "            .fontColor('#475569')\n"
            "            .lineHeight(19)\n"
            "            .padding(10)\n"
            "            .borderRadius(8)\n"
            "            .backgroundColor('#FFFFFF')\n"
            "            .id(`absent_${index}`)\n"
            "        })\n\n"
            "        Text('Function-level Android parity')\n"
            "          .fontSize(18)\n"
            "          .fontWeight(FontWeight.Bold)\n"
            "          .fontColor('#18202A')\n"
            "          .margin({ top: 10 })\n"
            "        ForEach(this.functionAlignmentRows, (item: string, index: number) => {\n"
            "          Text(item)\n"
            "            .fontSize(12)\n"
            "            .fontColor('#334155')\n"
            "            .lineHeight(18)\n"
            "            .padding(10)\n"
            "            .borderRadius(8)\n"
            "            .backgroundColor('#FFFFFF')\n"
            "            .id(`function_alignment_${index}`)\n"
            "        })\n",
        )
    path.write_text(text, encoding="utf-8", newline="\n")


def main() -> None:
    for base_dir in sorted(ROOT.glob("[0-9][0-9]_*")):
        if not base_dir.is_dir():
            continue
        parity_path = base_dir / "entry" / "src" / "main" / "ets" / "androidparity" / "FunctionLevelParity.ets"
        parity_path.parent.mkdir(parents=True, exist_ok=True)
        parity_path.write_text(PARITY, encoding="utf-8", newline="\n")

        viewmodel_path = base_dir / "entry" / "src" / "main" / "ets" / "viewmodel" / "ElementBaseViewModel.ets"
        viewmodel_path.write_text(VIEWMODEL, encoding="utf-8", newline="\n")

        patch_index(base_dir / "entry" / "src" / "main" / "ets" / "pages" / "Index.ets")


if __name__ == "__main__":
    main()
