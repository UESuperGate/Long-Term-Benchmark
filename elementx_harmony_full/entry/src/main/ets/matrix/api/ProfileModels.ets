import { DomainError } from '../../core/DomainResult';

export const PROFILE_CONTRACT_VERSION: string = '1';

export interface UserStatus {
  emoji: string;
  text: string;
}

export enum DisplayedStatusKind {
  None = 'none',
  UserSet = 'user_set',
  InCall = 'in_call'
}

export interface DisplayedStatus {
  kind: DisplayedStatusKind;
  status: UserStatus | null;
  callJoinedAtSeconds: number | null;
}

export interface UserProfile {
  userId: string;
  displayName: string | null;
  avatarUrl: string | null;
  rawStatus: UserStatus | null;
  displayedStatus: DisplayedStatus;
}

export enum UserStatusPickerState {
  Hidden = 'hidden',
  ShowingPicker = 'showing_picker',
  CustomInput = 'custom_input'
}

export enum ProfilePhase {
  Loading = 'loading',
  Ready = 'ready',
  Saving = 'saving',
  Offline = 'offline',
  Error = 'error'
}

export enum ProfileMutationKind {
  None = 'none',
  EditProfile = 'edit_profile',
  SetStatus = 'set_status',
  ClearStatus = 'clear_status'
}

export interface UserStatusPresentation {
  visible: boolean;
  kind: DisplayedStatusKind;
  emoji: string | null;
  text: string | null;
  callJoinedAtSeconds: number | null;
}

export interface ProfileSnapshot {
  phase: ProfilePhase;
  profile: UserProfile | null;
  picker: UserStatusPickerState;
  customEmoji: string;
  customText: string;
  pendingMutation: ProfileMutationKind;
  timelinePresentation: UserStatusPresentation;
  activeCallPresentation: UserStatusPresentation;
  error: DomainError | null;
}
