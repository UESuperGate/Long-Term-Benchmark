import { DomainResult } from '../../core/DomainResult';
import {
  RoomManagementCommand,
  RoomManagementPayload,
  SearchPage,
  SearchRequest,
  SpacePage
} from './RoomManagementModels';

/** Native Matrix boundary. Implementations must report unsupported operations as failures. */
export interface RoomManagementDataSource {
  execute(command: RoomManagementCommand): Promise<DomainResult<RoomManagementPayload>>;
}

export interface SearchDataSource {
  search(request: SearchRequest): Promise<DomainResult<SearchPage>>;
}

export interface SpacesDataSource {
  loadSpaces(): Promise<DomainResult<SpacePage>>;
  switchSpace(spaceId: string | null): Promise<DomainResult<boolean>>;
}
