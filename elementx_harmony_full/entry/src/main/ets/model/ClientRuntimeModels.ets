export enum AsyncDataStatus {
  Uninitialized = 'uninitialized',
  Loading = 'loading',
  Success = 'success',
  Failure = 'failure'
}

export enum RootNavTargetKind {
  SplashScreen = 'splash_screen',
  AccountSelect = 'account_select',
  NotLoggedInFlow = 'not_logged_in_flow',
  LoggedInFlow = 'logged_in_flow',
  SignedOutFlow = 'signed_out_flow',
  BugReport = 'bug_report'
}

export enum SyncServiceState {
  Idle = 'idle',
  Running = 'running',
  Offline = 'offline',
  Error = 'error'
}

export enum SyncIndicatorState {
  Hidden = 'hidden',
  Syncing = 'syncing',
  ServerUnreachable = 'server_unreachable'
}

export enum NetworkStatus {
  Connected = 'connected',
  Disconnected = 'disconnected'
}

export enum SessionVerificationStatus {
  Unknown = 'unknown',
  NotVerified = 'not_verified',
  Verified = 'verified',
  IncomingRequest = 'incoming_request'
}

export enum RecoveryState {
  Unknown = 'unknown',
  Enabled = 'enabled',
  Disabled = 'disabled',
  Incomplete = 'incomplete'
}

export enum LocalNetworkPermissionDialog {
  Hidden = 'hidden',
  ShowRationale = 'show_rationale',
  ShowSystemDialog = 'show_system_dialog'
}

export enum TimelineMediaPreviewMode {
  AlwaysShow = 'always_show',
  PrivateRooms = 'private_rooms',
  AlwaysHide = 'always_hide'
}

export enum ResolvedIntentKind {
  None = 'none',
  Navigation = 'navigation',
  OAuth = 'oauth',
  Permalink = 'permalink',
  Login = 'login',
  IncomingShare = 'incoming_share'
}

export interface AsyncDataState {
  status: AsyncDataStatus;
  message: string;
}

export interface RootNavTarget {
  kind: RootNavTargetKind;
  sessionId: string;
  navId: number;
  pendingLoginProvider: string;
}

export interface RootNavState {
  cacheIndex: number;
  isLoggedIn: boolean;
  isTokenValid: boolean;
  currentTarget: RootNavTarget;
  pendingIntent: ResolvedIntentKind;
}

export interface SyncRuntimeState {
  serviceState: SyncServiceState;
  indicatorState: SyncIndicatorState;
  appForeground: boolean;
  inCall: boolean;
  sharingLiveLocation: boolean;
  firstSyncState: SyncServiceState;
}

export interface LoggedInRuntimeState {
  sync: SyncRuntimeState;
  pusherRegistrationState: AsyncDataState;
  ignoreRegistrationError: boolean;
  forceNativeSlidingSyncMigration: boolean;
  appName: string;
  localNetworkPermissionDialog: LocalNetworkPermissionDialog;
  verificationStatus: SessionVerificationStatus;
  recoveryState: RecoveryState;
  networkStatus: NetworkStatus;
  automaticCallStatusEnabled: boolean;
}

export interface HomeserverCapabilitiesState {
  canChangeDisplayName: boolean;
  canChangeAvatarUrl: boolean;
  canDeactivateAccount: boolean;
  canReportRoom: boolean;
  canLinkNewDevice: boolean;
  maxFileUploadSizeBytes: number;
  livekitRtcSupported: boolean;
}

export interface SessionStoreRecord {
  userId: string;
  deviceId: string;
  homeserver: string;
  accessToken: string;
  nextSyncBatch: string;
  ignoredUsers: string[];
  displayName: string;
  avatarUrl: string;
  userStatus: string;
  sendPublicReadReceipts: boolean;
  renderReadReceipts: boolean;
  timelineMediaPreviewMode: TimelineMediaPreviewMode;
  lastUsageIndex: number;
  isTokenValid: boolean;
}

export interface MatrixClientRuntime {
  sessionId: string;
  userId: string;
  deviceId: string;
  homeserver: string;
  accessToken: string;
  nextSyncBatch: string;
  ignoredUsers: string[];
  displayName: string;
  avatarUrl: string;
  userStatus: string;
  sendPublicReadReceipts: boolean;
  renderReadReceipts: boolean;
  timelineMediaPreviewMode: TimelineMediaPreviewMode;
  isShuttingDown: boolean;
  syncService: SyncRuntimeState;
  homeserverCapabilities: HomeserverCapabilitiesState;
}
