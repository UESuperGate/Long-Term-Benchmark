import { describe, it, expect } from '@ohos/hypium';
import { abilityDelegatorRegistry } from '@kit.TestKit';
import { probeTasks16To18CopyTransport } from './Tasks16_18CopyTransport.test';

export default function copyProbe(): void {
  describe('DeviceCopyTransport', () => {
    it('records_real_sdk_path_uri_fd_outcomes', 0, async () => {
      const context = abilityDelegatorRegistry.getAbilityDelegator().getAppContext().getApplicationContext();
      const result = await probeTasks16To18CopyTransport(context);
      expect(result.attempts.length).assertEqual(3);
      expect(result.cleanupErrors.length).assertEqual(0);
    });
  });
}
