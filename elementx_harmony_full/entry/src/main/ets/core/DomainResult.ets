export enum DomainErrorCode {
  InvalidInput = 'invalid_input',
  AuthenticationRejected = 'authentication_rejected',
  InvalidToken = 'invalid_token',
  NetworkUnavailable = 'network_unavailable',
  ServiceUnavailable = 'service_unavailable',
  SessionMissing = 'session_missing',
  CredentialMissing = 'credential_missing',
  StorageReadFailed = 'storage_read_failed',
  StorageWriteFailed = 'storage_write_failed',
  StorageDeleteFailed = 'storage_delete_failed',
  NativeBridgeUnavailable = 'native_bridge_unavailable',
  Cancelled = 'cancelled',
  Unknown = 'unknown'
}

export interface DomainError {
  code: DomainErrorCode;
  message: string;
  retryable: boolean;
}

export class DomainFailure implements DomainError {
  readonly code: DomainErrorCode;
  readonly message: string;
  readonly retryable: boolean;

  constructor(code: DomainErrorCode, message: string, retryable: boolean) {
    this.code = code;
    this.message = message;
    this.retryable = retryable;
  }
}

/** A result whose failure path is always typed and user-presentable. */
export class DomainResult<T> {
  readonly success: boolean;
  readonly value: T | null;
  readonly error: DomainError | null;

  private constructor(success: boolean, value: T | null, error: DomainError | null) {
    this.success = success;
    this.value = value;
    this.error = error;
  }

  static succeed<T>(value: T): DomainResult<T> {
    return new DomainResult<T>(true, value, null);
  }

  static fail<T>(error: DomainError): DomainResult<T> {
    return new DomainResult<T>(false, null, error);
  }
}

export function unexpectedFailure(operation: string): DomainFailure {
  return new DomainFailure(
    DomainErrorCode.Unknown,
    `${operation} failed unexpectedly`,
    true
  );
}
