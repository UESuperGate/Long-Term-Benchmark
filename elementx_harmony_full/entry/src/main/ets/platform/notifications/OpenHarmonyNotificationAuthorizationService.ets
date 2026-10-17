import notificationManager from '@ohos.notificationManager';
import common from '@ohos.app.ability.common';
import { DomainErrorCode, DomainResult } from '../../core/DomainResult';
import { PlatformFailure, PlatformFailureKind, platformCodeOf } from '../errors/PlatformFailure';
import {
  NotificationAuthorizationService,
  NotificationAuthorizationState
} from './NotificationPushContracts';

export class OpenHarmonyNotificationAuthorizationService implements NotificationAuthorizationService {
  private readonly context: common.UIAbilityContext;

  constructor(context: common.UIAbilityContext) {
    this.context = context;
  }

  async state(): Promise<DomainResult<NotificationAuthorizationState>> {
    try {
      const enabled = await notificationManager.isNotificationEnabled();
      return DomainResult.succeed<NotificationAuthorizationState>(
        enabled ? NotificationAuthorizationState.Enabled : NotificationAuthorizationState.Disabled
      );
    } catch (error) {
      return this.failure('notification.state', error as Error);
    }
  }

  async request(): Promise<DomainResult<NotificationAuthorizationState>> {
    try {
      if (!(await notificationManager.isNotificationEnabled())) {
        await notificationManager.requestEnableNotification(this.context);
      }
      const enabled = await notificationManager.isNotificationEnabled();
      return DomainResult.succeed<NotificationAuthorizationState>(
        enabled ? NotificationAuthorizationState.Enabled : NotificationAuthorizationState.Disabled
      );
    } catch (error) {
      return this.failure('notification.request', error as Error);
    }
  }

  private failure(operation: string, error: Error): DomainResult<NotificationAuthorizationState> {
    return DomainResult.fail<NotificationAuthorizationState>(new PlatformFailure(
      DomainErrorCode.ServiceUnavailable,
      PlatformFailureKind.PermissionDenied,
      operation,
      'Notification authorization is unavailable or denied',
      false,
      platformCodeOf(error)
    ));
  }
}
