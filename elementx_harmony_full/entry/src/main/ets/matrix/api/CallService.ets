import { DomainResult } from '../../core/DomainResult';
import { RoomCallInput } from './CallModels';

export interface RoomCallDataSource {
  load(roomId: string): Promise<DomainResult<RoomCallInput>>;
  join(roomId: string, callId: string): Promise<DomainResult<boolean>>;
  decline(roomId: string, callId: string): Promise<DomainResult<boolean>>;
}
