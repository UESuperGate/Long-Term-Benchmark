import { RoomClient, RoomInfo, requireRoomId } from './RoomClient';

export enum LeaveAction {
  Uninitialized = 'uninitialized',
  Confirming = 'confirming',
  Loading = 'loading',
  Success = 'success',
  Failure = 'failure'
}

export class RoomDetailsPresenter {
  readonly roomId: string;
  readonly client: RoomClient;
  room: RoomInfo | undefined = undefined;
  loading: boolean = false;
  errorMessage: string = '';
  leaveAction: LeaveAction = LeaveAction.Uninitialized;

  constructor(roomId: string, client: RoomClient) {
    requireRoomId(roomId);
    this.roomId = roomId;
    this.client = client;
  }

  async load(): Promise<void> {
    if (this.loading) return;
    this.loading = true;
    this.errorMessage = '';
    try {
      const room = await this.client.getRoom(this.roomId);
      if (!room || room.roomId !== this.roomId) throw new Error('Room unavailable');
      this.room = room;
    } catch (error) {
      this.room = undefined;
      this.errorMessage = 'Unable to load this room.';
    } finally {
      this.loading = false;
    }
  }

  requestLeave(): void {
    if (this.room && this.leaveAction !== LeaveAction.Loading && this.leaveAction !== LeaveAction.Success) {
      this.leaveAction = LeaveAction.Confirming;
    }
  }

  cancelLeave(): void {
    if (this.leaveAction === LeaveAction.Confirming || this.leaveAction === LeaveAction.Failure) {
      this.leaveAction = LeaveAction.Uninitialized;
    }
  }

  async confirmLeave(): Promise<void> {
    if (this.leaveAction !== LeaveAction.Confirming && this.leaveAction !== LeaveAction.Failure) return;
    this.leaveAction = LeaveAction.Loading;
    try {
      await this.client.leaveRoom(this.roomId);
      this.leaveAction = LeaveAction.Success;
    } catch (error) {
      this.leaveAction = LeaveAction.Failure;
    }
  }
}
