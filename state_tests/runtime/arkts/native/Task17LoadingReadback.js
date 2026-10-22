const storeName = 'element_x_pinned_messages', key = 'room_design_pinned_events';
const missing = '__task17_read_only_missing__';
// Only reads and SDK cache eviction after original operations have completed.
// No preference put/delete/clear/flush or production method invocation.
export function createTask17LoadingReadback(preferences, abilityContext) {
  let prepared = false, finished = false;
  const operations = [];
  const context = () => ({ bundleName: abilityContext?.abilityInfo?.bundleName,
    moduleName: abilityContext?.abilityInfo?.moduleName || abilityContext?.currentHapModuleInfo?.name,
    preferencesDir: abilityContext?.preferencesDir, area: abilityContext?.area });
  const check = actual => {
    if (!actual || actual !== abilityContext) throw new Error('Readback requires the identical original AbilityContext');
  };
  async function call(phase, method, fn) {
    const receipt = { sequence: operations.length + 1, phase, method, completed: false };
    operations.push(receipt);
    try { const value = await fn(); receipt.completed = true; return value; }
    catch (error) { receipt.error = String(error); throw error; }
  }
  async function read(phase, actual) {
    check(actual);
    const store = await call(phase, 'getPreferences', () => preferences.getPreferences(actual, storeName));
    const present = await call(phase, 'has', () => store.has(key));
    const rawValue = await call(phase, 'get', () => store.get(key, missing));
    return { phase, sameAbilityContext: true, context: context(), storeName, key, present, rawValue };
  }
  return {
    async before(actual) {
      if (prepared || finished) throw new Error('Readback fixture is single-use');
      const result = await read('before_open', actual);
      prepared = true;
      return result;
    },
    async after(actual) {
      check(actual);
      if (!prepared || finished) throw new Error('Readback completion requires one prepared context');
      finished = true;
      await call('after_original_completion', 'removePreferencesFromCache', () => preferences.removePreferencesFromCache(actual, storeName));
      const result = await read('after_cache_reopen', actual);
      result.cacheEvicted = true;
      if (result.present && typeof result.rawValue === 'string') {
        try { result.rows = JSON.parse(result.rawValue); }
        catch (error) { result.parseError = String(error); }
      }
      return result;
    },
    snapshot() { return JSON.parse(JSON.stringify({ context: context(), storeName, key, operations, prepared, finished,
      mechanism: 'native_preferences_absent_before_then_cache_eviction_and_reopen_after_original_completion', evaluatorDataWrites: [] })); }
  };
}
