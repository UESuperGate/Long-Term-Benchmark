// Device ohosTest only. Never include these imports in the Previewer bundle.
import abilityDelegatorRegistry from '@ohos.app.ability.abilityDelegatorRegistry';
import fileUri from '@ohos.file.fileuri';
import media from '@ohos.multimedia.media';
import notification from '@ohos.notification';
import { createNativeContext as createPlatformContext } from './native-platform';

export async function createNativeContext(caseId, _hostSandboxRoot, candidateRoute) {
  // Delegator exposes a base Context wrapper; Preferences requires its native application context.
  const context = abilityDelegatorRegistry.getAbilityDelegator().getAppContext().getApplicationContext();
  const bridge = await createPlatformContext(caseId, '', candidateRoute, context);
  bridge.capabilities.context.origin = 'device AbilityDelegator.getAppContext().getApplicationContext()';
  // AbilityDelegator retains the aa option prefix; Hypium strips it separately.
  const executionNonce = abilityDelegatorRegistry.getArguments().parameters['-s ltbExecutionNonce'];
  if (executionNonce !== undefined && !/^[a-f0-9]{32}$/.test(executionNonce)) throw new Error('Invalid device execution nonce');
  bridge.capabilities.execution = { nonce: executionNonce || null, origin: 'AbilityDelegator test arguments' };
  bridge.modules['@ohos.file.fileuri'] = { default: fileUri };
  bridge.modules['@ohos.multimedia.media'] = { default: media };
  bridge.modules['@ohos.notification'] = { default: notification };
  bridge.audioSources = {};
  bridge.persistRow = async function(json) {
    const name = 'ltb-native-result_' + Date.now() + '.json';
    const filePath = context.cacheDir + '/' + name;
    const file = await bridge.fs.open(filePath, bridge.fs.OpenMode.CREATE | bridge.fs.OpenMode.WRITE_ONLY | bridge.fs.OpenMode.TRUNC);
    try { await bridge.fs.write(file.fd, json); }
    finally { await bridge.fs.close(file); }
    const stat = await bridge.fs.stat(filePath);
    return { name, bytes: stat.size, characters: json.length, executionNonce: executionNonce || null };
  };
  bridge.capabilities.runtime = { backend: 'device_ohosTest',
    serviceSupport: 'Unverified until actual per-case calls and effects are recorded' };
  return bridge;
}
