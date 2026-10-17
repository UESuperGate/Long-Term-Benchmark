import { describe, expect, it } from '@ohos/hypium';
import { runAppShellCoordinatorTests } from './AppShellCoordinator.test';

export default function appShellHarnessTest(): void {
  describe('appShellHarness', () => {
    it('runs app-shell state transitions', 0, async () => {
      const passed = await runAppShellCoordinatorTests();
      expect(passed.length).assertEqual(5);
    });
  });
}
