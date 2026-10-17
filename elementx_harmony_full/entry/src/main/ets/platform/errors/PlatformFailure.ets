import { DomainErrorCode, DomainFailure } from '../../core/DomainResult';

export enum PlatformFailureKind {
  InvalidData = 'invalid_data',
  CapabilityUnavailable = 'capability_unavailable',
  PermissionDenied = 'permission_denied',
  ReadFailed = 'read_failed',
  WriteFailed = 'write_failed',
  DeleteFailed = 'delete_failed',
  SubscriptionFailed = 'subscription_failed',
  ResourceClosed = 'resource_closed',
  SchedulingFailed = 'scheduling_failed'
}

/** Keeps platform-specific diagnostics typed without changing the shared domain contract. */
export class PlatformFailure extends DomainFailure {
  readonly kind: PlatformFailureKind;
  readonly operation: string;
  readonly platformCode: number | null;

  constructor(
    code: DomainErrorCode,
    kind: PlatformFailureKind,
    operation: string,
    message: string,
    retryable: boolean,
    platformCode: number | null = null
  ) {
    super(code, message, retryable);
    this.kind = kind;
    this.operation = operation;
    this.platformCode = platformCode;
  }
}

interface PlatformCodeCarrier {
  code?: number;
}

/** Normalizes SDK rejection values to a throwable Error while retaining numeric diagnostics. */
export class PlatformSdkError extends Error {
  readonly code: number | undefined;

  constructor(operation: string, platformCode: number | null) {
    super(`Platform operation failed: ${operation}`);
    this.code = platformCode === null ? undefined : platformCode;
  }
}

export function platformCodeOf(error: Error): number | null {
  const candidate = error as PlatformCodeCarrier;
  return typeof candidate.code === 'number' ? candidate.code : null;
}

export function platformSdkError(operation: string, error: Error): PlatformSdkError {
  return new PlatformSdkError(operation, platformCodeOf(error));
}
