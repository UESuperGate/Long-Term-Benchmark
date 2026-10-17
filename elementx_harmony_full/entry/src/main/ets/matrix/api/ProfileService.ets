import { DomainResult } from '../../core/DomainResult';
import { UserProfile, UserStatus } from './ProfileModels';

export interface ProfileEdit {
  displayName: string | null;
  avatarSourceHandle: string | null;
  removeAvatar: boolean;
}

export interface UserProfileDataSource {
  loadProfile(): Promise<DomainResult<UserProfile>>;
  editProfile(edit: ProfileEdit): Promise<DomainResult<UserProfile>>;
  setUserStatus(status: UserStatus): Promise<DomainResult<UserProfile>>;
  clearUserStatus(): Promise<DomainResult<UserProfile>>;
}
