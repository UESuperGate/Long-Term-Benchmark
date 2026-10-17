import { AccountProfile, BaseFeatureFlags, RoomSummary, TimelineEvent } from './ElementModels';
import { LoggedInRuntimeState, RootNavState, TimelineMediaPreviewMode } from './ClientRuntimeModels';

export enum ClientAuthState {
  SignedOut = 'signed_out',
  ManualLogin = 'manual_login',
  QrLogin = 'qr_login',
  CreateAccount = 'create_account',
  SignedIn = 'signed_in'
}

export interface ClientSession {
  sessionId: string;
  homeserver: string;
  deviceId: string;
  accessToken: string;
  nextSyncBatch: string;
  ignoredUsers: string[];
  sendPublicReadReceipts: boolean;
  renderReadReceipts: boolean;
  timelineMediaPreviewMode: TimelineMediaPreviewMode;
  account: AccountProfile;
}

export interface ClientSnapshot {
  appName: string;
  versionName: string;
  session: ClientSession | null;
  rootNavState: RootNavState;
  loggedInState: LoggedInRuntimeState | null;
  rooms: RoomSummary[];
  selectedRoomId: string;
  timeline: TimelineEvent[];
  featureFlags: BaseFeatureFlags;
  runtimeRows: string[];
  intentRows: string[];
  featureStatusRows: string[];
  deviceRows: string[];
  securityRows: string[];
}
