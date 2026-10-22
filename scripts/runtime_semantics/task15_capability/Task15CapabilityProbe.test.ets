import { describe, it, expect } from '@ohos/hypium';
import abilityDelegatorRegistry from '@ohos.app.ability.abilityDelegatorRegistry';
import { Driver, ON } from '@ohos.UiTest';
import fs from '@ohos.file.fs';
import { runCapabilityProbe } from './Task15CapabilityProbe';

class NativeResultFilesystem {
  writeText(path: string, content: string): void {
    const file = fs.openSync(path, fs.OpenMode.CREATE | fs.OpenMode.WRITE_ONLY | fs.OpenMode.TRUNC);
    try {
      fs.writeSync(file.fd, content);
    } finally {
      fs.closeSync(file);
    }
  }
}

export default function capabilityTests(): void {
  describe('Task15OriginalUnsupportedCapability', () => {
    it('restores_authenticated_unsupported_session_on_original_page', 0, async () => {
      const args = abilityDelegatorRegistry.getArguments();
      const entryId = args.parameters['-s task15EntryId'] || args.parameters['task15EntryId'] || 'deactivate_account_entry';
      const result: string = await runCapabilityProbe(abilityDelegatorRegistry.getArguments().bundleName,
        abilityDelegatorRegistry.getAbilityDelegator(), Driver.create(), ON, new NativeResultFilesystem(),
        entryId);
      console.info('TASK15_CAPABILITY_RESULT ' + result);
      expect(result.length > 0).assertTrue();
    });
  });
}
