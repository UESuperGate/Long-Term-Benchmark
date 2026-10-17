import { describe, expect, it } from '@ohos/hypium';
import { runMediaFeatureDomainTests } from './MediaFeatureDomain.test';
import { runRoomManagementDomainTests } from './RoomManagementDomain.test';
import { runRoomTimelineDomainTests } from './RoomTimelineDomain.test';
import { runSecurityDomainTests } from './SecurityDomain.test';

export default function domainHarnessTest(): void {
  describe('domainHarness', () => {
    it('runs room-list and timeline transitions', 0, async () => {
      const passed = await runRoomTimelineDomainTests();
      expect(passed.length).assertEqual(7);
    });

    it('runs room-management, search and space transitions', 0, async () => {
      const passed = await runRoomManagementDomainTests();
      expect(passed.length).assertEqual(6);
    });

    it('runs security and device-link transitions', 0, async () => {
      const passed = await runSecurityDomainTests();
      expect(passed.length).assertEqual(10);
    });

    it('runs media, location, call and profile transitions', 0, async () => {
      const passed = await runMediaFeatureDomainTests();
      expect(passed.length).assertEqual(6);
    });
  });
}
