import { DomainError } from '../core/DomainResult';
import { ObservableState, StateObserver } from '../core/ObservableState';
import { MatrixSessionHandle } from '../matrix/api/MatrixAuthentication';
import { SessionMetadata } from '../session/SessionModels';
import {
  AuthenticationSource,
  RootNavigationPhase,
  RootNavigationState
} from './RootNavigationState';

/** Deterministic root navigation reducer. Stale async completions are ignored. */
export class RootNavigationStateMachine {
  private readonly state: ObservableState<RootNavigationState>;
  private nextAttemptId: number = 1;

  constructor(initialState: RootNavigationState = RootNavigationState.signedOut()) {
    this.state = new ObservableState<RootNavigationState>(initialState);
  }

  getState(): RootNavigationState {
    return this.state.getValue();
  }

  subscribe(observer: StateObserver<RootNavigationState>): number {
    return this.state.subscribe(observer);
  }

  unsubscribe(observerId: number): void {
    this.state.unsubscribe(observerId);
  }

  beginAuthentication(source: AuthenticationSource): number {
    const attemptId = this.nextAttemptId;
    this.nextAttemptId += 1;
    this.state.setValue(new RootNavigationState(
      RootNavigationPhase.Authenticating,
      source,
      attemptId,
      null,
      null,
      '',
      null
    ));
    return attemptId;
  }

  completeAuthentication(
    attemptId: number,
    metadata: SessionMetadata,
    handle: MatrixSessionHandle
  ): boolean {
    if (!this.isActiveAttempt(attemptId) || metadata.sessionId !== handle.sessionId) {
      return false;
    }
    this.state.setValue(new RootNavigationState(
      RootNavigationPhase.LoggedIn,
      null,
      attemptId,
      metadata,
      handle,
      '',
      null
    ));
    return true;
  }

  failAuthentication(attemptId: number, error: DomainError): boolean {
    if (!this.isActiveAttempt(attemptId)) {
      return false;
    }
    this.state.setValue(new RootNavigationState(
      RootNavigationPhase.Error,
      null,
      attemptId,
      null,
      null,
      '',
      error
    ));
    return true;
  }

  finishSignedOut(attemptId: number, sessionId: string = ''): boolean {
    if (!this.isActiveAttempt(attemptId)) {
      return false;
    }
    this.state.setValue(RootNavigationState.signedOut(sessionId));
    return true;
  }

  resetToSignedOut(sessionId: string = ''): void {
    this.state.setValue(RootNavigationState.signedOut(sessionId));
  }

  private isActiveAttempt(attemptId: number): boolean {
    const current = this.state.getValue();
    return current.phase === RootNavigationPhase.Authenticating && current.attemptId === attemptId;
  }
}
