import type { Driver, On } from '@ohos.UiTest';
import type common from '@ohos.app.ability.common';

export interface Task15NativeE2EConfig {
  enabled: boolean;
  nonce: string;
  homeserver: string;
  caSha256: string;
}

export function task15NativeE2EConfig(parameters: Record<string, string>): Task15NativeE2EConfig | undefined;
export function createTask15NativeE2E(config: Task15NativeE2EConfig, context: common.Context,
  resourceContext: common.Context, driver: Driver, selectors: On, platform: Object): Object;
