import { DomainErrorCode, DomainResult } from '../../core/DomainResult';
import { PlatformFailure, PlatformFailureKind } from '../errors/PlatformFailure';

export enum RuntimePermissionState {
  Granted = 'granted',
  NotRequested = 'not_requested',
  DeniedCanAskAgain = 'denied_can_ask_again',
  DeniedPermanently = 'denied_permanently'
}

export interface PermissionRequestDecision {
  granted: boolean;
  dialogShown: boolean;
  requestAllowed: boolean;
}

export interface RuntimePermissionBackend {
  isGranted(permission: string): Promise<boolean>;
  request(permission: string): Promise<PermissionRequestDecision>;
}

export interface PermissionHistory {
  wasAsked(permission: string): Promise<boolean>;
  wasDeniedPermanently(permission: string): Promise<boolean>;
  record(permission: string, asked: boolean, permanentlyDenied: boolean): Promise<void>;
}

export class RuntimePermissionController {
  private readonly backend: RuntimePermissionBackend;
  private readonly history: PermissionHistory;

  constructor(backend: RuntimePermissionBackend, history: PermissionHistory) {
    this.backend = backend;
    this.history = history;
  }

  async state(permission: string): Promise<DomainResult<RuntimePermissionState>> {
    if (permission.length === 0) {
      return this.invalid<RuntimePermissionState>('Permission name is empty');
    }
    try {
      if (await this.backend.isGranted(permission)) {
        return DomainResult.succeed<RuntimePermissionState>(RuntimePermissionState.Granted);
      }
      if (!(await this.history.wasAsked(permission))) {
        return DomainResult.succeed<RuntimePermissionState>(RuntimePermissionState.NotRequested);
      }
      return DomainResult.succeed<RuntimePermissionState>(
        await this.history.wasDeniedPermanently(permission) ?
          RuntimePermissionState.DeniedPermanently : RuntimePermissionState.DeniedCanAskAgain
      );
    } catch (error) {
      return this.failure<RuntimePermissionState>('permission.state', 'Unable to read permission state');
    }
  }

  async request(permission: string): Promise<DomainResult<RuntimePermissionState>> {
    if (permission.length === 0) {
      return this.invalid<RuntimePermissionState>('Permission name is empty');
    }
    try {
      const decision = await this.backend.request(permission);
      const permanentlyDenied = !decision.granted && (!decision.requestAllowed || !decision.dialogShown);
      await this.history.record(permission, true, permanentlyDenied);
      if (decision.granted) {
        return DomainResult.succeed<RuntimePermissionState>(RuntimePermissionState.Granted);
      }
      return DomainResult.succeed<RuntimePermissionState>(
        permanentlyDenied ? RuntimePermissionState.DeniedPermanently : RuntimePermissionState.DeniedCanAskAgain
      );
    } catch (error) {
      return this.failure<RuntimePermissionState>('permission.request', 'Unable to request runtime permission');
    }
  }

  private invalid<T>(message: string): DomainResult<T> {
    return DomainResult.fail<T>(new PlatformFailure(
      DomainErrorCode.InvalidInput,
      PlatformFailureKind.InvalidData,
      'permission.validate',
      message,
      false
    ));
  }

  private failure<T>(operation: string, message: string): DomainResult<T> {
    return DomainResult.fail<T>(new PlatformFailure(
      DomainErrorCode.ServiceUnavailable,
      PlatformFailureKind.PermissionDenied,
      operation,
      message,
      true
    ));
  }
}
