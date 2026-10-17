import common from '@ohos.app.ability.common';
import { OpenHarmonyStringPreferences, StringPreferences } from '../storage/StringPreferences';
import { PermissionHistory } from './RuntimePermissions';

interface PermissionHistoryRecord {
  permission: string;
  asked: boolean;
  permanentlyDenied: boolean;
}

interface PermissionHistoryEnvelope {
  schemaVersion: number;
  records: PermissionHistoryRecord[];
}

export class PreferencesPermissionHistory implements PermissionHistory {
  private static readonly STORE_NAME: string = 'elementx_permission_history_v1';
  private static readonly HISTORY_KEY: string = 'permission_history';
  private readonly preferences: StringPreferences;

  constructor(preferencesStore: StringPreferences) {
    this.preferences = preferencesStore;
  }

  static async create(context: common.Context): Promise<PreferencesPermissionHistory> {
    const store = await OpenHarmonyStringPreferences.create(
      context,
      PreferencesPermissionHistory.STORE_NAME
    );
    return new PreferencesPermissionHistory(store);
  }

  async wasAsked(permission: string): Promise<boolean> {
    const record = await this.find(permission);
    return record !== null && record.asked;
  }

  async wasDeniedPermanently(permission: string): Promise<boolean> {
    const record = await this.find(permission);
    return record !== null && record.permanentlyDenied;
  }

  async record(permission: string, asked: boolean, permanentlyDenied: boolean): Promise<void> {
    const records = await this.readAll();
    let replaced = false;
    for (let index = 0; index < records.length; index++) {
      if (records[index].permission === permission) {
        records[index] = {
          permission: permission,
          asked: asked,
          permanentlyDenied: permanentlyDenied
        };
        replaced = true;
        break;
      }
    }
    if (!replaced) {
      records.push({ permission: permission, asked: asked, permanentlyDenied: permanentlyDenied });
    }
    const envelope: PermissionHistoryEnvelope = { schemaVersion: 1, records: records };
    await this.preferences.put(PreferencesPermissionHistory.HISTORY_KEY, JSON.stringify(envelope));
  }

  private async find(permission: string): Promise<PermissionHistoryRecord | null> {
    const records = await this.readAll();
    for (let index = 0; index < records.length; index++) {
      if (records[index].permission === permission) {
        return records[index];
      }
    }
    return null;
  }

  private async readAll(): Promise<PermissionHistoryRecord[]> {
    const raw = await this.preferences.get(PreferencesPermissionHistory.HISTORY_KEY, '');
    if (raw.length === 0) {
      return [];
    }
    const envelope = JSON.parse(raw) as PermissionHistoryEnvelope;
    if (envelope.schemaVersion !== 1 || !Array.isArray(envelope.records)) {
      throw new Error('Unsupported permission history schema');
    }
    return envelope.records;
  }
}
