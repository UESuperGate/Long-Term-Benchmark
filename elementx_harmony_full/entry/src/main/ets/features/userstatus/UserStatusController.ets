import {
  DomainError,
  DomainErrorCode,
  DomainFailure,
  DomainResult,
  unexpectedFailure
} from '../../core/DomainResult';
import {
  DisplayedStatus,
  DisplayedStatusKind,
  ProfileMutationKind,
  ProfilePhase,
  ProfileSnapshot,
  UserProfile,
  UserStatus,
  UserStatusPickerState,
  UserStatusPresentation
} from '../../matrix/api/ProfileModels';
import { ProfileEdit, UserProfileDataSource } from '../../matrix/api/ProfileService';

function noStatus(): DisplayedStatus {
  return {
    kind: DisplayedStatusKind.None,
    status: null,
    callJoinedAtSeconds: null
  };
}

function userSetStatus(status: UserStatus): DisplayedStatus {
  return {
    kind: DisplayedStatusKind.UserSet,
    status: status,
    callJoinedAtSeconds: null
  };
}

function inCallStatus(joinedAtSeconds: number): DisplayedStatus {
  return {
    kind: DisplayedStatusKind.InCall,
    status: null,
    callJoinedAtSeconds: joinedAtSeconds
  };
}

function presentation(status: DisplayedStatus): UserStatusPresentation {
  if (status.kind === DisplayedStatusKind.UserSet && status.status !== null) {
    return {
      visible: true,
      kind: status.kind,
      emoji: status.status.emoji,
      text: status.status.text,
      callJoinedAtSeconds: null
    };
  }
  if (status.kind === DisplayedStatusKind.InCall) {
    return {
      visible: true,
      kind: status.kind,
      emoji: null,
      text: null,
      callJoinedAtSeconds: status.callJoinedAtSeconds
    };
  }
  return {
    visible: false,
    kind: DisplayedStatusKind.None,
    emoji: null,
    text: null,
    callJoinedAtSeconds: null
  };
}

export class UserStatusController {
  private readonly source: UserProfileDataSource;
  private retryEdit: ProfileEdit | null = null;
  private retryStatus: UserStatus | null = null;
  private mutationGeneration: number = 0;
  private snapshot: ProfileSnapshot = {
    phase: ProfilePhase.Loading,
    profile: null,
    picker: UserStatusPickerState.Hidden,
    customEmoji: '',
    customText: '',
    pendingMutation: ProfileMutationKind.None,
    timelinePresentation: presentation(noStatus()),
    activeCallPresentation: presentation(noStatus()),
    error: null
  };

  constructor(source: UserProfileDataSource) {
    this.source = source;
  }

  getSnapshot(): ProfileSnapshot {
    return {
      phase: this.snapshot.phase,
      profile: this.snapshot.profile,
      picker: this.snapshot.picker,
      customEmoji: this.snapshot.customEmoji,
      customText: this.snapshot.customText,
      pendingMutation: this.snapshot.pendingMutation,
      timelinePresentation: this.snapshot.timelinePresentation,
      activeCallPresentation: this.snapshot.activeCallPresentation,
      error: this.snapshot.error
    };
  }

  async start(): Promise<DomainResult<ProfileSnapshot>> {
    this.snapshot.phase = ProfilePhase.Loading;
    this.snapshot.error = null;
    const result = await this.source.loadProfile();
    if (!result.success || result.value === null) {
      return this.failLoad(result.error);
    }
    this.applyProfile(result.value);
    this.clearRetry();
    return DomainResult.succeed<ProfileSnapshot>(this.getSnapshot());
  }

  openPicker(): ProfileSnapshot {
    this.snapshot.picker = UserStatusPickerState.ShowingPicker;
    return this.getSnapshot();
  }

  dismissPicker(): ProfileSnapshot {
    this.snapshot.picker = UserStatusPickerState.Hidden;
    return this.getSnapshot();
  }

  openCustomInput(): ProfileSnapshot {
    const raw = this.snapshot.profile === null ? null : this.snapshot.profile.rawStatus;
    this.snapshot.customEmoji = raw === null ? '😀' : raw.emoji;
    this.snapshot.customText = raw === null ? '' : raw.text;
    this.snapshot.picker = UserStatusPickerState.CustomInput;
    return this.getSnapshot();
  }

  updateCustom(emoji: string, text: string): DomainResult<ProfileSnapshot> {
    if (this.snapshot.picker !== UserStatusPickerState.CustomInput || emoji.length === 0) {
      return DomainResult.fail<ProfileSnapshot>(new DomainFailure(
        DomainErrorCode.InvalidInput,
        'Custom status editor is not ready',
        true
      ));
    }
    this.snapshot.customEmoji = emoji;
    this.snapshot.customText = text;
    return DomainResult.succeed<ProfileSnapshot>(this.getSnapshot());
  }

  async editProfile(edit: ProfileEdit): Promise<DomainResult<ProfileSnapshot>> {
    if (this.snapshot.profile === null ||
      (edit.displayName === null && edit.avatarSourceHandle === null && !edit.removeAvatar)) {
      return DomainResult.fail<ProfileSnapshot>(new DomainFailure(
        DomainErrorCode.InvalidInput,
        'Profile edit is empty or profile is unavailable',
        true
      ));
    }
    this.retryEdit = edit;
    this.retryStatus = null;
    return this.runEdit(edit);
  }

  async setStatus(status: UserStatus): Promise<DomainResult<ProfileSnapshot>> {
    if (this.snapshot.profile === null || status.emoji.length === 0 || status.text.length === 0) {
      return DomainResult.fail<ProfileSnapshot>(new DomainFailure(
        DomainErrorCode.InvalidInput,
        'Status emoji and text are required',
        true
      ));
    }
    this.retryStatus = status;
    this.retryEdit = null;
    return this.runSetStatus(status);
  }

  async clearStatus(): Promise<DomainResult<ProfileSnapshot>> {
    if (this.snapshot.profile === null) {
      return DomainResult.fail<ProfileSnapshot>(new DomainFailure(
        DomainErrorCode.InvalidInput,
        'Profile is unavailable',
        true
      ));
    }
    this.retryStatus = null;
    this.retryEdit = null;
    return this.runClearStatus();
  }

  async retryLastMutation(): Promise<DomainResult<ProfileSnapshot>> {
    if (this.snapshot.pendingMutation === ProfileMutationKind.EditProfile && this.retryEdit !== null) {
      return this.runEdit(this.retryEdit);
    }
    if (this.snapshot.pendingMutation === ProfileMutationKind.SetStatus && this.retryStatus !== null) {
      return this.runSetStatus(this.retryStatus);
    }
    if (this.snapshot.pendingMutation === ProfileMutationKind.ClearStatus) {
      return this.runClearStatus();
    }
    return DomainResult.fail<ProfileSnapshot>(new DomainFailure(
      DomainErrorCode.InvalidInput,
      'No failed profile mutation is available to retry',
      true
    ));
  }

  receiveRemoteProfile(profile: UserProfile): DomainResult<ProfileSnapshot> {
    if (this.snapshot.profile !== null && this.snapshot.profile.userId !== profile.userId) {
      return DomainResult.fail<ProfileSnapshot>(new DomainFailure(
        DomainErrorCode.InvalidInput,
        'Profile update belongs to another user',
        false
      ));
    }
    this.applyProfile(profile);
    return DomainResult.succeed<ProfileSnapshot>(this.getSnapshot());
  }

  receiveActiveCall(isInCall: boolean, joinedAtSeconds: number | null): DomainResult<ProfileSnapshot> {
    if (this.snapshot.profile === null || (isInCall && joinedAtSeconds === null)) {
      return DomainResult.fail<ProfileSnapshot>(new DomainFailure(
        DomainErrorCode.InvalidInput,
        'Active call status is incomplete',
        false
      ));
    }
    const profile = this.snapshot.profile;
    profile.displayedStatus = isInCall ? inCallStatus(joinedAtSeconds!) :
      profile.rawStatus === null ? noStatus() : userSetStatus(profile.rawStatus);
    this.updatePresentations(profile.displayedStatus);
    return DomainResult.succeed<ProfileSnapshot>(this.getSnapshot());
  }

  private async runEdit(edit: ProfileEdit): Promise<DomainResult<ProfileSnapshot>> {
    const generation = this.beginMutation(ProfileMutationKind.EditProfile);
    const result = await this.source.editProfile(edit);
    return this.completeMutation(result, 'profile edit', generation);
  }

  private async runSetStatus(status: UserStatus): Promise<DomainResult<ProfileSnapshot>> {
    const generation = this.beginMutation(ProfileMutationKind.SetStatus);
    this.snapshot.picker = UserStatusPickerState.Hidden;
    const result = await this.source.setUserStatus(status);
    return this.completeMutation(result, 'set user status', generation);
  }

  private async runClearStatus(): Promise<DomainResult<ProfileSnapshot>> {
    const generation = this.beginMutation(ProfileMutationKind.ClearStatus);
    this.snapshot.picker = UserStatusPickerState.Hidden;
    const result = await this.source.clearUserStatus();
    return this.completeMutation(result, 'clear user status', generation);
  }

  private beginMutation(kind: ProfileMutationKind): number {
    this.mutationGeneration++;
    this.snapshot.phase = ProfilePhase.Saving;
    this.snapshot.pendingMutation = kind;
    this.snapshot.error = null;
    return this.mutationGeneration;
  }

  private completeMutation(
    result: DomainResult<UserProfile>,
    operation: string,
    generation: number
  ): DomainResult<ProfileSnapshot> {
    if (generation !== this.mutationGeneration) {
      return DomainResult.fail<ProfileSnapshot>(new DomainFailure(
        DomainErrorCode.Cancelled,
        'Stale profile mutation result was ignored',
        false
      ));
    }
    if (!result.success || result.value === null) {
      const failure: DomainError = result.error === null ? unexpectedFailure(operation) : result.error;
      this.snapshot.phase = failure.code === DomainErrorCode.NetworkUnavailable ?
        ProfilePhase.Offline : ProfilePhase.Error;
      this.snapshot.error = failure;
      return DomainResult.fail<ProfileSnapshot>(failure);
    }
    this.applyProfile(result.value);
    this.clearRetry();
    return DomainResult.succeed<ProfileSnapshot>(this.getSnapshot());
  }

  private applyProfile(profile: UserProfile): void {
    this.snapshot.profile = profile;
    this.snapshot.phase = ProfilePhase.Ready;
    this.snapshot.pendingMutation = ProfileMutationKind.None;
    this.snapshot.error = null;
    this.updatePresentations(profile.displayedStatus);
  }

  private updatePresentations(status: DisplayedStatus): void {
    this.snapshot.timelinePresentation = presentation(status);
    this.snapshot.activeCallPresentation = presentation(status);
  }

  private clearRetry(): void {
    this.retryEdit = null;
    this.retryStatus = null;
  }

  private failLoad(error: DomainError | null): DomainResult<ProfileSnapshot> {
    const failure = error === null ? unexpectedFailure('profile load') : error;
    this.snapshot.phase = failure.code === DomainErrorCode.NetworkUnavailable ?
      ProfilePhase.Offline : ProfilePhase.Error;
    this.snapshot.error = failure;
    return DomainResult.fail<ProfileSnapshot>(failure);
  }
}
