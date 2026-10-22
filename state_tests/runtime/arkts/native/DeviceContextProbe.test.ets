import { describe, it, expect } from '@ohos/hypium';
import { abilityDelegatorRegistry } from '@kit.TestKit';
import common from '@ohos.app.ability.common';
import preferences from '@ohos.data.preferences';

interface ContextResult {
  origin: string;
  overload: string;
  available: boolean;
  observed?: string;
  error?: string;
}

async function probe(context: common.Context, origin: string, options: boolean): Promise<ContextResult> {
  const name = 'ltb_context_probe_' + Date.now() + '_' + origin;
  const result: ContextResult = { origin, overload: options ? 'options' : 'name', available: false };
  try {
    const store = options ? await preferences.getPreferences(context, { name }) :
      await preferences.getPreferences(context, name);
    await store.put('probe', name);
    await store.flush();
    await preferences.removePreferencesFromCache(context, name);
    const reopened = await preferences.getPreferences(context, { name });
    result.observed = String(await reopened.get('probe', 'missing'));
    result.available = result.observed === name;
  } catch (error) {
    result.error = String(error);
  } finally {
    try { await preferences.deletePreferences(context, name); } catch (_) {}
  }
  console.info('ARKTS_CONTEXT_PROBE ' + JSON.stringify(result));
  return result;
}

export default function contextProbe(): void {
  describe('DeviceContextProbe', () => {
    it('real_context_preferences_roundtrip', 0, async () => {
      const delegator = abilityDelegatorRegistry.getAbilityDelegator();
      const args = abilityDelegatorRegistry.getArguments();
      const base = delegator.getAppContext();
      const contexts: common.Context[] = [base, base.getApplicationContext(), base.createModuleContext('entry')];
      const origins: string[] = ['delegator', 'application', 'module'];
      let successes: number = 0;
      for (let index = 0; index < contexts.length; index++) {
        for (const options of [false, true]) {
          if ((await probe(contexts[index], origins[index], options)).available) successes++;
        }
      }
      try {
        const monitor: abilityDelegatorRegistry.AbilityMonitor = { abilityName: 'EntryAbility' };
        await delegator.addAbilityMonitor(monitor);
        await delegator.startAbility({ bundleName: args.bundleName, moduleName: 'entry', abilityName: 'EntryAbility' });
        const ability = await delegator.waitAbilityMonitor(monitor, 10000);
        for (const options of [false, true]) {
          if ((await probe(ability.context, 'ability', options)).available) successes++;
        }
        await delegator.removeAbilityMonitor(monitor);
      } catch (error) {
        console.info('ARKTS_CONTEXT_PROBE ' + JSON.stringify({ origin: 'ability', available: false, error: String(error) }));
      }
      expect(successes > 0).assertTrue();
    });
  });
}
