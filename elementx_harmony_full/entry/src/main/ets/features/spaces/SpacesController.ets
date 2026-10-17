import {
  DomainErrorCode,
  DomainFailure,
  DomainResult,
  unexpectedFailure
} from '../../core/DomainResult';
import { ObservableState } from '../../core/ObservableState';
import { SpaceSummary, SpacesSnapshot } from '../../matrix/api/RoomManagementModels';
import { SpacesDataSource } from '../../matrix/api/RoomManagementServices';
import { SpacesReducer } from './SpacesReducer';

enum SpacesRetryKind {
  None = 'none',
  Load = 'load',
  Switch = 'switch'
}

export class SpacesController {
  readonly state: ObservableState<SpacesSnapshot>;
  private readonly source: SpacesDataSource;
  private readonly reducer: SpacesReducer = new SpacesReducer();
  private generation: number = 0;
  private switching: boolean = false;
  private retryKind: SpacesRetryKind = SpacesRetryKind.None;
  private retrySpaceId: string | null = null;

  constructor(source: SpacesDataSource) {
    this.source = source;
    this.state = new ObservableState<SpacesSnapshot>(this.reducer.getSnapshot());
  }

  getSnapshot(): SpacesSnapshot {
    return this.reducer.getSnapshot();
  }

  async load(): Promise<DomainResult<SpacesSnapshot>> {
    const generation = ++this.generation;
    this.publish(this.reducer.beginLoad());
    const result = await this.source.loadSpaces();
    if (generation !== this.generation) {
      return DomainResult.fail<SpacesSnapshot>(new DomainFailure(
        DomainErrorCode.Cancelled,
        'Space list load was superseded by a newer request',
        true
      ));
    }
    if (!result.success || result.value === null) {
      const error = result.error === null ? unexpectedFailure('load spaces') : result.error;
      this.retryKind = SpacesRetryKind.Load;
      this.publish(this.reducer.fail(error));
      return DomainResult.fail<SpacesSnapshot>(error);
    }
    this.retryKind = SpacesRetryKind.None;
    const snapshot = this.reducer.replace(result.value);
    this.publish(snapshot);
    return DomainResult.succeed<SpacesSnapshot>(snapshot);
  }

  async switchSpace(spaceId: string | null): Promise<DomainResult<SpacesSnapshot>> {
    if (this.switching) {
      return DomainResult.fail<SpacesSnapshot>(new DomainFailure(
        DomainErrorCode.ServiceUnavailable,
        'A space switch is already in progress',
        true
      ));
    }
    if (spaceId !== null && !this.getSnapshot().spaces.some(
      (space: SpaceSummary) => space.roomId === spaceId
    )) {
      return DomainResult.fail<SpacesSnapshot>(new DomainFailure(
        DomainErrorCode.InvalidInput,
        `Unknown space ${spaceId}`,
        false
      ));
    }
    const generation = ++this.generation;
    this.switching = true;
    this.publish(this.reducer.beginSwitch(spaceId));
    const result = await this.source.switchSpace(spaceId);
    this.switching = false;
    if (generation !== this.generation) {
      return DomainResult.fail<SpacesSnapshot>(new DomainFailure(
        DomainErrorCode.Cancelled,
        'Space switch was superseded by a newer request',
        true
      ));
    }
    if (!result.success || result.value !== true) {
      const error = result.error === null ? unexpectedFailure('switch space') : result.error;
      this.retryKind = SpacesRetryKind.Switch;
      this.retrySpaceId = spaceId;
      this.publish(this.reducer.fail(error));
      return DomainResult.fail<SpacesSnapshot>(error);
    }
    this.retryKind = SpacesRetryKind.None;
    this.retrySpaceId = null;
    const snapshot = this.reducer.finishSwitch(spaceId);
    this.publish(snapshot);
    return DomainResult.succeed<SpacesSnapshot>(snapshot);
  }

  retry(): Promise<DomainResult<SpacesSnapshot>> {
    if (this.retryKind === SpacesRetryKind.Load) {
      return this.load();
    }
    if (this.retryKind === SpacesRetryKind.Switch) {
      return this.switchSpace(this.retrySpaceId);
    }
    return Promise.resolve(DomainResult.fail<SpacesSnapshot>(new DomainFailure(
      DomainErrorCode.InvalidInput,
      'There is no failed space operation to retry',
      false
    )));
  }

  private publish(snapshot: SpacesSnapshot): void {
    this.state.setValue(snapshot);
  }
}
