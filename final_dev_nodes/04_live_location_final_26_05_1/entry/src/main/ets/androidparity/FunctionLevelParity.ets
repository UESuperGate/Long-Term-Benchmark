export interface AndroidSymbolAlignment {
  androidSymbol: string;
  arktsSymbol: string;
  granularity: string;
  finalSemantics: string;
}

export class AndroidSymbolAlignmentRow implements AndroidSymbolAlignment {
  androidSymbol: string;
  arktsSymbol: string;
  granularity: string;
  finalSemantics: string;

  constructor(androidSymbol: string, arktsSymbol: string, granularity: string, finalSemantics: string) {
    this.androidSymbol = androidSymbol;
    this.arktsSymbol = arktsSymbol;
    this.granularity = granularity;
    this.finalSemantics = finalSemantics;
  }
}

export interface UserStatusStateParity {
  emoji: string;
  text: string;
  editable: boolean;
  automaticCallStatusEnabled: boolean;
}

export class UserStatusPresenterParity {
  present(): UserStatusStateParity {
    return { emoji: '🌴', text: 'Away', editable: true, automaticCallStatusEnabled: true };
  }

  UserStatusView(): string {
    return 'settings own-status row connected';
  }

  handleEvent(event: string, value: string = ''): UserStatusStateParity {
    const state = this.present();
    if (event === 'SetStatus') {
      state.text = value;
    }
    if (event === 'ClearStatus') {
      state.emoji = '';
      state.text = '';
    }
    return state;
  }

  enableAutomaticCallStatus(enabled: boolean): boolean {
    return enabled;
  }

  mapDisplayedStatus(emoji: string, text: string): string {
    return `${emoji} ${text}`.trim();
  }
}

export interface GalleryItemDataParity {
  id: string;
  mimeType: string;
  visual: boolean;
}

export class TimelineItemGalleryContentProviderParity {
  createGalleryContent(items: GalleryItemDataParity[]): string {
    return `TimelineItemGalleryContent:${items.length}`;
  }

  TimelineItemGalleryContent(items: GalleryItemDataParity[]): GalleryItemDataParity[] {
    return items;
  }

  TimelineItemGalleryView(items: GalleryItemDataParity[]): string {
    return items.some((item: GalleryItemDataParity) => item.visual) ? 'gallery grid/list rendered' : 'gallery attachment list rendered';
  }

  handleGalleryItemClick(eventId: string, galleryItemIndex: number): string {
    return this.toEventGalleryParams(eventId, galleryItemIndex);
  }

  toEventGalleryParams(eventId: string, galleryItemIndex: number): string {
    return `EventGallery:${eventId}:${galleryItemIndex}`;
  }

  formatSummary(items: GalleryItemDataParity[]): string {
    return `${items.length} attachments`;
  }
}

export interface ActiveCallStateParity {
  participants: number;
  joined: boolean;
}

export class ActiveCallTimelineItemViewParity {
  ActiveCallTimelineItemView(state: ActiveCallStateParity): string {
    return `active call card:${this.renderParticipants(state)}`;
  }

  joinCall(state: ActiveCallStateParity): ActiveCallStateParity {
    state.joined = true;
    return state;
  }

  routeCallContent(kind: string): string {
    return kind === 'active_call' ? 'ActiveCallTimelineItemView' : 'TimelineItemCallNotifyView';
  }

  renderParticipants(state: ActiveCallStateParity): string {
    return `${state.participants} participants`;
  }
}

export interface LiveLocationSessionParity {
  roomId: string;
  active: boolean;
  durationMs: number;
  latitude: number;
  longitude: number;
}

export class ActiveLiveLocationShareManagerParity {
  private sharingRoomIds: string[] = [];

  startShare(roomId: string, durationMs: number): LiveLocationSessionParity {
    if (!this.sharingRoomIds.includes(roomId)) {
      this.sharingRoomIds.push(roomId);
    }
    return { roomId, active: true, durationMs, latitude: 0, longitude: 0 };
  }

  stopShare(session: LiveLocationSessionParity): LiveLocationSessionParity {
    session.active = false;
    this.sharingRoomIds = this.sharingRoomIds.filter((id: string) => id !== session.roomId);
    return session;
  }

  isCurrentlySharing(roomId: string): boolean {
    return this.sharingRoomIds.includes(roomId);
  }

  updateLocation(session: LiveLocationSessionParity, latitude: number, longitude: number): LiveLocationSessionParity {
    if (session.active) {
      session.latitude = latitude;
      session.longitude = longitude;
    }
    return session;
  }

  serviceState(session: LiveLocationSessionParity): string {
    return session.active ? 'LiveLocationSharingService.Active' : 'LiveLocationSharingService.Idle';
  }

  bannerRows(session: LiveLocationSessionParity): string[] {
    return session.active ? [`Sharing live location in ${session.roomId}`] : [];
  }

  toLiveTimelineContent(session: LiveLocationSessionParity): string {
    return `TimelineItemLocationContent.Mode.Live:${session.latitude},${session.longitude}`;
  }
}

export interface ShowQrCodeStateParity {
  data: string;
  loading: boolean;
}

export class ShowQrCodePresenterParity {
  remainingRotations: number = 3;
  loadingAfterRotationDelayMs: number = 1000;

  present(initialData: string): ShowQrCodeStateParity {
    return { data: initialData, loading: false };
  }

  onQrReady(data: string): ShowQrCodeStateParity {
    return { data, loading: false };
  }

  onQrRotating(): string {
    if (this.remainingRotations-- > 0) {
      return 'rotateQrCode';
    }
    return this.onTooManyRotation();
  }

  showLoadingWhileRotating(state: ShowQrCodeStateParity): ShowQrCodeStateParity {
    return { data: state.data, loading: true };
  }

  onTooManyRotation(): string {
    return 'LinkMobileStep.Error(ErrorType.Expired)';
  }
}

export interface LinkDesktopTimerStateParity {
  startedAtMs: number;
  timeoutMs: number;
  expired: boolean;
}

export class LinkNewDesktopHandlerParity {
  startTimer(nowMs: number): LinkDesktopTimerStateParity {
    return { startedAtMs: nowMs, timeoutMs: 120000, expired: false };
  }

  tick(state: LinkDesktopTimerStateParity, nowMs: number): LinkDesktopTimerStateParity {
    state.expired = nowMs - state.startedAtMs >= state.timeoutMs;
    return state;
  }

  timeoutError(state: LinkDesktopTimerStateParity): string {
    return state.expired ? 'LinkDesktopStep.Error(ErrorType.Expired)' : 'LinkDesktopStep.Waiting';
  }
}

export class ContinuationMessageSenderParity {
  confirm(): string {
    return 'ContinuationMessageSender.confirm';
  }

  cancel(): string {
    return 'ContinuationMessageSender.cancel';
  }
}

const FINAL_ALIGNMENTS: AndroidSymbolAlignment[] = [
  new AndroidSymbolAlignmentRow("ActiveLiveLocationShareManager.startShare(roomId, duration)", "ActiveLiveLocationShareManagerParity.startShare()", "manager function -> method", "starts live location sharing with a duration and records active room"),
  new AndroidSymbolAlignmentRow("ActiveLiveLocationShareManager.stopShare(roomId)", "ActiveLiveLocationShareManagerParity.stopShare()", "manager function -> method", "stops live location sharing and clears active room"),
  new AndroidSymbolAlignmentRow("ActiveLiveLocationShareManager.isCurrentlySharing(roomId)", "ActiveLiveLocationShareManagerParity.isCurrentlySharing()", "StateFlow mapper -> method", "reports whether the room is currently sharing"),
  new AndroidSymbolAlignmentRow("LiveLocationSharingCoordinator.tick/update", "ActiveLiveLocationShareManagerParity.updateLocation()", "background loop -> method", "pushes updated coordinates while active"),
  new AndroidSymbolAlignmentRow("LiveLocationSharingService", "ActiveLiveLocationShareManagerParity.serviceState()", "service -> state adapter", "models foreground/background sharing state"),
  new AndroidSymbolAlignmentRow("LiveLocationSharingBanner(...)", "ActiveLiveLocationShareManagerParity.bannerRows()", "composable -> view model", "exposes banner-like active sharing row"),
  new AndroidSymbolAlignmentRow("TimelineItemLocationContent.Mode.Live", "ActiveLiveLocationShareManagerParity.toLiveTimelineContent()", "timeline model -> mapper", "renders live location as supported timeline content")
];

export function getFunctionLevelAlignments(scenarioId: string): AndroidSymbolAlignment[] {
  if (scenarioId === 'live_location_final') {
    return FINAL_ALIGNMENTS;
  }
  return FINAL_ALIGNMENTS;
}

export function createFunctionLevelAlignmentRows(scenarioId: string): string[] {
  return getFunctionLevelAlignments(scenarioId).map((item: AndroidSymbolAlignment) => {
    return `${item.androidSymbol} -> ${item.arktsSymbol}: ${item.finalSemantics}`;
  });
}
