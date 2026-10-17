import { DomainError, DomainErrorCode } from '../../core/DomainResult';
import {
  SpacePage,
  SpaceSummary,
  SpacesPhase,
  SpacesSnapshot
} from '../../matrix/api/RoomManagementModels';

export class SpacesReducer {
  private snapshot: SpacesSnapshot = {
    phase: SpacesPhase.Loading,
    spaces: [],
    activeSpaceId: null,
    pendingSpaceId: null,
    error: null,
    retryable: false
  };

  getSnapshot(): SpacesSnapshot {
    return {
      phase: this.snapshot.phase,
      spaces: this.snapshot.spaces.slice(),
      activeSpaceId: this.snapshot.activeSpaceId,
      pendingSpaceId: this.snapshot.pendingSpaceId,
      error: this.snapshot.error,
      retryable: this.snapshot.retryable
    };
  }

  beginLoad(): SpacesSnapshot {
    this.snapshot.phase = SpacesPhase.Loading;
    this.snapshot.error = null;
    this.snapshot.retryable = false;
    return this.getSnapshot();
  }

  replace(page: SpacePage): SpacesSnapshot {
    this.snapshot.spaces = this.uniqueSorted(page.spaces);
    this.snapshot.activeSpaceId = page.activeSpaceId;
    this.snapshot.pendingSpaceId = null;
    this.snapshot.error = null;
    this.snapshot.retryable = false;
    this.snapshot.phase = this.snapshot.spaces.length === 0 ? SpacesPhase.Empty : SpacesPhase.Ready;
    return this.getSnapshot();
  }

  beginSwitch(spaceId: string | null): SpacesSnapshot {
    this.snapshot.phase = SpacesPhase.Switching;
    this.snapshot.pendingSpaceId = spaceId;
    this.snapshot.error = null;
    return this.getSnapshot();
  }

  finishSwitch(spaceId: string | null): SpacesSnapshot {
    this.snapshot.activeSpaceId = spaceId;
    this.snapshot.pendingSpaceId = null;
    this.snapshot.error = null;
    this.snapshot.retryable = false;
    this.snapshot.phase = this.snapshot.spaces.length === 0 ? SpacesPhase.Empty : SpacesPhase.Ready;
    return this.getSnapshot();
  }

  fail(error: DomainError): SpacesSnapshot {
    this.snapshot.pendingSpaceId = null;
    this.snapshot.error = error;
    this.snapshot.retryable = error.retryable;
    this.snapshot.phase = error.code === DomainErrorCode.NetworkUnavailable ?
      SpacesPhase.Offline : SpacesPhase.Error;
    return this.getSnapshot();
  }

  private uniqueSorted(spaces: SpaceSummary[]): SpaceSummary[] {
    const result: SpaceSummary[] = [];
    spaces.forEach((space: SpaceSummary) => {
      const index = result.findIndex((candidate: SpaceSummary) => candidate.roomId === space.roomId);
      if (index >= 0) {
        result[index] = space;
      } else {
        result.push(space);
      }
    });
    result.sort((left: SpaceSummary, right: SpaceSummary) => left.name.localeCompare(right.name));
    return result;
  }
}
