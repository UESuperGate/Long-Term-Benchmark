import preferences from '@ohos.data.preferences';
import common from '@ohos.app.ability.common';
import { platformSdkError } from '../errors/PlatformFailure';

/** Minimal injectable surface used by non-secret platform stores. */
export interface StringPreferences {
  get(key: string, defaultValue: string): Promise<string>;
  put(key: string, value: string): Promise<void>;
  remove(key: string): Promise<void>;
}

export class OpenHarmonyStringPreferences implements StringPreferences {
  private readonly store: preferences.Preferences;

  private constructor(store: preferences.Preferences) {
    this.store = store;
  }

  static async create(context: common.Context, name: string): Promise<OpenHarmonyStringPreferences> {
    try {
      const store = await preferences.getPreferences(context, name);
      return new OpenHarmonyStringPreferences(store);
    } catch (error) {
      throw platformSdkError('preferences.create', error as Error);
    }
  }

  async get(key: string, defaultValue: string): Promise<string> {
    try {
      const value = await this.store.get(key, defaultValue);
      if (typeof value !== 'string') {
        throw new Error(`Preference ${key} is not a string`);
      }
      return value;
    } catch (error) {
      throw platformSdkError('preferences.get', error as Error);
    }
  }

  async put(key: string, value: string): Promise<void> {
    try {
      await this.store.put(key, value);
      await this.store.flush();
    } catch (error) {
      throw platformSdkError('preferences.put', error as Error);
    }
  }

  async remove(key: string): Promise<void> {
    try {
      await this.store.delete(key);
      await this.store.flush();
    } catch (error) {
      throw platformSdkError('preferences.remove', error as Error);
    }
  }
}
