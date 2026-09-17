import notificationManager from '@ohos.notificationManager';
import wantAgent from '@ohos.app.ability.wantAgent';
import type { WantAgent } from '@ohos.app.ability.wantAgent';
import common from '@ohos.app.ability.common';

export interface PublishRoomNotificationResult {
  ok: boolean;
  message: string;
}

export class ElementNotificationService {
  async publishUnreadMessage(
    context: common.UIAbilityContext,
    roomId: string,
    roomName: string,
    sender: string,
    body: string
  ): Promise<PublishRoomNotificationResult> {
    try {
      await this.ensureNotificationsEnabled(context);
      await notificationManager.addSlot(notificationManager.SlotType.SOCIAL_COMMUNICATION);

      const notificationId = this.nextNotificationId();
      const messageKey = roomId + '-' + notificationId.toString();
      const openAgent = await this.createStartAbilityAgent(messageKey + '-open', 'elementx://room/open?roomId=' + encodeURIComponent(roomId));
      const markReadAgent = await this.createStartAbilityAgent(
        messageKey + '-read',
        'elementx://notification/markRead?roomId=' + encodeURIComponent(roomId),
        'com.qingyu.elementx.NOTIFICATION_MARK_ROOM_READ'
      );
      const content: notificationManager.NotificationContent = {
        notificationContentType: notificationManager.ContentType.NOTIFICATION_CONTENT_BASIC_TEXT,
        normal: {
          title: roomName,
          text: sender + ': ' + body,
          additionalText: 'Element X'
        }
      };
      const request: notificationManager.NotificationRequest = {
        id: notificationId,
        appMessageId: 'elementx-' + messageKey,
        notificationSlotType: notificationManager.SlotType.SOCIAL_COMMUNICATION,
        content: content,
        wantAgent: openAgent,
        actionButtons: [
          {
            title: 'Mark read',
            wantAgent: markReadAgent,
            extras: {
              roomId: roomId
            }
          }
        ],
        tapDismissed: true,
        showDeliveryTime: true,
        badgeNumber: 1
      };
      await notificationManager.publish(request);
      return {
        ok: true,
        message: 'Notification published'
      };
    } catch (error) {
      return {
        ok: false,
        message: `${error}`
      };
    }
  }

  private async ensureNotificationsEnabled(context: common.UIAbilityContext): Promise<void> {
    try {
      const enabled = await notificationManager.isNotificationEnabled();
      if (!enabled) {
        await notificationManager.requestEnableNotification(context);
      }
    } catch (error) {
      throw new Error(`Notification permission unavailable: ${error}`);
    }
  }

  private async createStartAbilityAgent(requestKey: string, uri: string, action: string = 'ohos.want.action.viewData'): Promise<WantAgent> {
    try {
      return await wantAgent.getWantAgent({
        wants: [
          {
            bundleName: 'com.qingyu.elementx.client',
            abilityName: 'EntryAbility',
            action: action,
            uri: uri
          }
        ],
        operationType: wantAgent.OperationType.START_ABILITY,
        requestCode: this.requestCode(requestKey),
        wantAgentFlags: [wantAgent.WantAgentFlags.UPDATE_PRESENT_FLAG]
      });
    } catch (error) {
      throw new Error(`Notification action unavailable: ${error}`);
    }
  }

  private requestCode(value: string): number {
    let code = 0;
    for (let i = 0; i < value.length; i++) {
      code = (code + value.charCodeAt(i) * (i + 1)) % 100000;
    }
    return code;
  }

  private nextNotificationId(): number {
    return new Date().getTime() % 2147483647;
  }
}
