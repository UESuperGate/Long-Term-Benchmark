import { Driver, ON } from '@ohos.UiTest';
import preferences from '@ohos.data.preferences';
import common from '@ohos.app.ability.common';
import { createTask17LoadingLaunch } from './Task17LoadingLaunchNative';
import { runPagePortsUi } from './Tasks16_17PagePortsUi';

class NativePreferencesPort {
  getPreferences(context: common.Context, name: string): Promise<preferences.Preferences> {
    return preferences.getPreferences(context, name);
  }
}

export async function runPagePortsProbe(caseJson: string, bundle: string): Promise<string> {
  return runPagePortsUi(caseJson, bundle, Driver.create(), ON, createTask17LoadingLaunch(bundle), new NativePreferencesPort());
}
