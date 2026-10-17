import domainHarnessTest from './DomainHarness.test';
import productionSliceTest from './ProductionSlice.test';
import platformFoundationTest from './PlatformFoundation.test';
import productionAuthenticationTest from './ProductionAuthentication.test';
import appShellHarnessTest from './AppShellHarness.test';
import productionRoomTransportTest from './ProductionRoomTransport.test';
import productionTimelineTransportTest from './ProductionTimelineTransport.test';

export default function testsuite(): void {
  domainHarnessTest();
  productionSliceTest();
  platformFoundationTest();
  productionAuthenticationTest();
  appShellHarnessTest();
  productionRoomTransportTest();
  productionTimelineTransportTest();
}
