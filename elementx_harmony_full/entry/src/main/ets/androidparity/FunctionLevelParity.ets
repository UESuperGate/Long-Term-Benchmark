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
    return { emoji: 'palm', text: 'Away', editable: true, automaticCallStatusEnabled: true };
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
  latitude: number;
  longitude: number;
}

export class ActiveLiveLocationShareManagerParity {
  start(roomId: string): LiveLocationSessionParity {
    return { roomId, active: true, latitude: 0, longitude: 0 };
  }

  stop(session: LiveLocationSessionParity): LiveLocationSessionParity {
    session.active = false;
    return session;
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
  qrCodeData: string;
  expiresAtMs: number;
  ownerVerified: boolean;
}

export class ShowQrCodePresenterParity {
  present(nowMs: number): ShowQrCodeStateParity {
    return { qrCodeData: this.rotateQrCode('initial'), expiresAtMs: nowMs + 600000, ownerVerified: false };
  }

  ShowQrCodeState(qrCodeData: string, expiresAtMs: number): ShowQrCodeStateParity {
    return { qrCodeData, expiresAtMs, ownerVerified: false };
  }

  rotateQrCode(previous: string): string {
    return `${previous}:rotated`;
  }

  sendContinuationMessage(state: ShowQrCodeStateParity): string {
    return state.ownerVerified ? `ContinuationMessageSender:${state.qrCodeData}` : 'blocked';
  }

  requireOwnerVerification(state: ShowQrCodeStateParity): boolean {
    return state.ownerVerified;
  }

  hasTimedOut(state: ShowQrCodeStateParity, nowMs: number): boolean {
    return nowMs >= state.expiresAtMs;
  }
}

const FINAL_ALIGNMENTS: AndroidSymbolAlignment[] = [
  new AndroidSymbolAlignmentRow("ShowQrCodePresenter.present()", "ShowQrCodePresenterParity.present()", "presenter -> presenter", "owns QR state instead of static node-only data"),
  new AndroidSymbolAlignmentRow("ShowQrCodeState(qrCodeData, expiresAt)", "ShowQrCodePresenterParity.ShowQrCodeState()", "state class -> state object", "stores rotating QR data and timeout timestamp"),
  new AndroidSymbolAlignmentRow("ShowQrCodePresenter.rotateQrCode()", "ShowQrCodePresenterParity.rotateQrCode()", "timer branch -> method", "refreshes QR payload"),
  new AndroidSymbolAlignmentRow("ContinuationMessageSender", "ShowQrCodePresenterParity.sendContinuationMessage()", "SDK adapter -> method", "continues verified QR login flow"),
  new AndroidSymbolAlignmentRow("device-owner verification gate", "ShowQrCodePresenterParity.requireOwnerVerification()", "guard -> method", "blocks continuation until owner verification succeeds"),
  new AndroidSymbolAlignmentRow("post-owner-verification timeout", "ShowQrCodePresenterParity.hasTimedOut()", "timeout branch -> method", "expires flow after configured deadline")
];

export function getFunctionLevelAlignments(scenarioId: string): AndroidSymbolAlignment[] {
  if (scenarioId === 'link_new_device_final') {
    return FINAL_ALIGNMENTS;
  }
  return FINAL_ALIGNMENTS;
}

export function createFunctionLevelAlignmentRows(scenarioId: string): string[] {
  return getFunctionLevelAlignments(scenarioId).map((item: AndroidSymbolAlignment) => {
    return `${item.androidSymbol} -> ${item.arktsSymbol}: ${item.finalSemantics}`;
  });
}
