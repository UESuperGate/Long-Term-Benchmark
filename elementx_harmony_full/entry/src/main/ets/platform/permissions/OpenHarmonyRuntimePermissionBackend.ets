import abilityAccessCtrl from '@ohos.abilityAccessCtrl';
import type { Permissions } from '@ohos.abilityAccessCtrl';
import common from '@ohos.app.ability.common';
import { PermissionRequestDecision, RuntimePermissionBackend } from './RuntimePermissions';
import { platformSdkError } from '../errors/PlatformFailure';

export class OpenHarmonyRuntimePermissionBackend implements RuntimePermissionBackend {
  private readonly context: common.UIAbilityContext;
  private readonly accessTokenId: number;
  private readonly manager: abilityAccessCtrl.AtManager;

  constructor(context: common.UIAbilityContext, accessTokenId: number) {
    this.context = context;
    this.accessTokenId = accessTokenId;
    this.manager = abilityAccessCtrl.createAtManager();
  }

  async isGranted(permission: string): Promise<boolean> {
    try {
      const status = await this.manager.checkAccessToken(this.accessTokenId, permission as Permissions);
      return status === abilityAccessCtrl.GrantStatus.PERMISSION_GRANTED;
    } catch (error) {
      throw platformSdkError('permission.check', error as Error);
    }
  }

  async request(permission: string): Promise<PermissionRequestDecision> {
    try {
      const result = await this.manager.requestPermissionsFromUser(
        this.context,
        [permission as Permissions]
      );
      const granted = result.authResults.length > 0 &&
        result.authResults[0] === abilityAccessCtrl.GrantStatus.PERMISSION_GRANTED;
      const dialogShown = result.dialogShownResults === undefined ||
        result.dialogShownResults.length === 0 ? true : result.dialogShownResults[0];
      const requestAllowed = result.errorReasons === undefined || result.errorReasons.length === 0 ||
        result.errorReasons[0] === 0;
      return {
        granted: granted,
        dialogShown: dialogShown,
        requestAllowed: requestAllowed
      };
    } catch (error) {
      throw platformSdkError('permission.request', error as Error);
    }
  }
}
