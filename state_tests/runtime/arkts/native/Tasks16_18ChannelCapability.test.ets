import { describe, it, expect } from '@ohos/hypium';
import { abilityDelegatorRegistry } from '@kit.TestKit';
import notificationManager from '@ohos.notificationManager';
import reminderAgentManager from '@ohos.reminderAgentManager';
import fs from '@ohos.file.fs';
import { BusinessError } from '@ohos.base';

interface CapabilityCall {
  api: string;
  inputJson: string;
  startedAtMs: number;
  finishedAtMs?: number;
  resultJson?: string;
  error?: string;
  errorCode?: number;
}

interface CapabilityReport {
  schemaVersion: number;
  taskId: string;
  observationLevel: string;
  canonicalPromotionAllowed: boolean;
  nonce: string;
  bundleName: string;
  startedAtMs: number;
  finishedAtMs?: number;
  cacheDir: string;
  calls: CapabilityCall[];
  unsupported: string[];
  cleanupErrors: string[];
  finished: boolean;
}

// This fixture calls SDKs, not a candidate gateway. Even a successful publish
// and matching request readback do not prove effective audio or canonical parity.
export default function channelCapabilityProbe(): void {
  describe('Tasks16_18ChannelCapability', () => {
    it('records_public_SDK_slot_and_notification_boundaries', 0, async () => {
      const args = abilityDelegatorRegistry.getArguments();
      const nonce = args.parameters['-s ltbExecutionNonce'];
      if (typeof nonce !== 'string' || !/^[a-f0-9]{32}$/.test(nonce)) {
        throw new Error('A fresh 32-hex ltbExecutionNonce is required');
      }
      const context = abilityDelegatorRegistry.getAbilityDelegator().getAppContext().getApplicationContext();
      const report: CapabilityReport = {
        schemaVersion: 1, taskId: '18_custom_notification_sounds',
        observationLevel: 'native_sdk_capability_diagnostic_only', canonicalPromotionAllowed: false,
        nonce, bundleName: args.bundleName, cacheDir: context.cacheDir,
        startedAtMs: Date.now(), calls: [], unsupported: [], cleanupErrors: [], finished: false
      };
      const output = context.cacheDir + '/Tasks16_18ChannelCapability-' + nonce + '.json';
      const persist = (): void => {
        const text = JSON.stringify(report);
        const file = fs.openSync(output, fs.OpenMode.CREATE | fs.OpenMode.WRITE_ONLY | fs.OpenMode.TRUNC);
        try { fs.writeSync(file.fd, text); } finally { fs.closeSync(file); }
        console.info('TASK18_CAPABILITY_CHECKPOINT ' + nonce + ' ' + report.calls.length);
      };
      let timedOut = false;
      const call = async (api: string, inputJson: string, operation: () => Promise<string>): Promise<string | undefined> => {
        if (timedOut || Date.now() - report.startedAtMs > 35000) throw new Error('Capability probe budget exhausted');
        const entry: CapabilityCall = { api, inputJson, startedAtMs: Date.now() };
        report.calls.push(entry);
        persist();
        let timer: number = 0;
        try {
          const deadline = new Promise<string>((_resolve, reject) => {
            timer = setTimeout(() => { timedOut = true; reject(new Error('SDK call exceeded 4000ms; no further writes')); }, 4000);
          });
          const value = await Promise.race([operation(), deadline]);
          entry.resultJson = value;
          return value;
        } catch (error) {
          entry.error = String(error);
          entry.errorCode = (error as BusinessError).code;
          return undefined;
        } finally {
          clearTimeout(timer);
          entry.finishedAtMs = Date.now();
          persist();
        }
      };
      const type = notificationManager.SlotType.SOCIAL_COMMUNICATION;
      const otherType = notificationManager.SlotType.SERVICE_INFORMATION;
      const ownedSlots: notificationManager.SlotType[] = [];
      const ownedRequests: notificationManager.NotificationRequest[] = [];
      try {
        const original = await call('notificationManager.getSlots', 'null', async () => JSON.stringify(await notificationManager.getSlots()));
        if (original === undefined) throw new Error('Cannot establish fresh slot state');
        const existing: notificationManager.NotificationSlot[] = JSON.parse(original) as notificationManager.NotificationSlot[];
        if (existing.length !== 0) throw new Error('Fresh diagnostic app required; existing slots are never modified');
        for (const slot of [type, otherType]) {
          ownedSlots.push(slot);
          await call('notificationManager.addSlot', JSON.stringify(slot), async () => { await notificationManager.addSlot(slot); return 'null'; });
          await call('notificationManager.getSlot', JSON.stringify(slot), async () => JSON.stringify(await notificationManager.getSlot(slot)));
        }
        const proposed: notificationManager.NotificationSlot = { notificationType: type, sound: 'Tasks16_18Capability.wav' };
        await call('reminderAgentManager.addNotificationSlot', JSON.stringify(proposed), async () => {
          await reminderAgentManager.addNotificationSlot(proposed); return 'null';
        });
        await call('notificationManager.getSlot', JSON.stringify(type), async () => JSON.stringify(await notificationManager.getSlot(type)));
        await call('notificationManager.getSlot', JSON.stringify(otherType), async () => JSON.stringify(await notificationManager.getSlot(otherType)));
        const enabled = await call('notificationManager.isNotificationEnabled', 'null', async () => JSON.stringify(await notificationManager.isNotificationEnabled()));
        if (enabled !== 'true') {
          report.unsupported.push('Notification permission not enabled: no automatic grant, policy mutation or publish claim.');
        } else {
          for (let index = 0; index < 3; index++) {
            const request: notificationManager.NotificationRequest = {
              id: 180020 + index, label: 'Tasks16_18-' + nonce,
              notificationSlotType: type,
              content: { notificationContentType: notificationManager.ContentType.NOTIFICATION_CONTENT_BASIC_TEXT,
                normal: { title: 'Task18 capability diagnostic', text: nonce + ' sample ' + index } },
              autoDeletedTime: Date.now() + 30000
            };
            if (index === 1) request.sound = 'Tasks16_18Capability.wav';
            // SDK23 notification/notificationFlags.d.ts TYPE_CLOSE = 2 is not
            // re-exported on notificationManager; retain the declaration hash.
            if (index === 2) request.notificationFlags = { soundEnabled: 2 };
            ownedRequests.push(request);
            await call('notificationManager.publish', JSON.stringify(request), async () => { await notificationManager.publish(request); return 'null'; });
            await call('notificationManager.getActiveNotifications', JSON.stringify({ id: request.id, label: request.label }), async () => {
              const active = await notificationManager.getActiveNotifications();
              return JSON.stringify(active.filter(item => item.id === request.id && item.label === request.label));
            });
            await call('notificationManager.getSlot', JSON.stringify(type), async () => JSON.stringify(await notificationManager.getSlot(type)));
          }
        }
        report.unsupported.push('SDK23 documents rawfile request sounds only; no supported user-picked sandbox sound or mutable per-slot sound binding established.');
        report.unsupported.push('Request readback is not an effective ringtone resolver, production consumer, or audible playback proof.');
      } catch (error) {
        report.unsupported.push(String(error));
      } finally {
        if (timedOut) {
          report.cleanupErrors.push('SDK operation still unresolved; parent must uninstall this owned fresh app. No overlapping cleanup calls.');
        } else {
          try {
            for (const request of ownedRequests) {
            const result = await call('notificationManager.cancel', JSON.stringify({ id: request.id, label: request.label }), async () => {
              await notificationManager.cancel(request.id as number, request.label); return 'null';
            });
            if (result === undefined) report.cleanupErrors.push('Cancel failed for own request ' + request.id);
            }
            for (const slot of ownedSlots) {
            const result = await call('notificationManager.removeSlot', JSON.stringify(slot), async () => { await notificationManager.removeSlot(slot); return 'null'; });
            if (result === undefined) report.cleanupErrors.push('Remove failed for own slot ' + slot);
            }
          } catch (error) { report.cleanupErrors.push(String(error)); }
        }
        report.finishedAtMs = Date.now();
        report.finished = !timedOut;
        persist();
        console.info('TASK18_CAPABILITY_FILE ' + nonce + ' ' + output);
      }
      expect(report.canonicalPromotionAllowed).assertFalse();
    });
  });
}
