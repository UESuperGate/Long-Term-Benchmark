import { describe, it, expect } from '@ohos/hypium';
import { probeNativePlatform } from './native-platform';
import { sandboxRoot, entryRequestJson } from './native-platform-config';

export default function nativePlatformTests(): void {
  describe('NativePlatformProbe', () => {
    it('native_platform_capabilities', 0, async () => {
      const result: string = await probeNativePlatform(sandboxRoot, entryRequestJson);
      expect(result).assertEqual('executed');
    });
  });
}
