import { describe, it, expect } from '@ohos/hypium';
import { ReportRoomGateway, ReportRoomService, ReportRoomPresenter, ReportActionState } from '../main/ets/features/ReportRoomFeature';

export default function nativeReportRoomTests(): void {
  describe('ReportRoomNative', () => {
    it('rr_state_007_report_failure_stops_leave', 0, () => {
      const gateway = new ReportRoomGateway();
      gateway.reportShouldFail = true;
      const presenter = new ReportRoomPresenter(new ReportRoomService(gateway));
      presenter.updateReason('Spam');
      presenter.toggleLeaveRoom();
      console.info('ARKTS_NATIVE_BEFORE ' + JSON.stringify({
        reportAction: presenter.reportAction, reason: presenter.reason,
        leaveRoom: presenter.leaveRoom, reportCalls: gateway.reportCalls,
        leaveCalls: gateway.leaveCalls
      }));
      presenter.submit();
      console.info('ARKTS_NATIVE_AFTER ' + JSON.stringify({
        reportAction: presenter.reportAction, reason: presenter.reason,
        leaveRoom: presenter.leaveRoom, reportCalls: gateway.reportCalls,
        leaveCalls: gateway.leaveCalls, effects: gateway.effects
      }));
      expect(presenter.reportAction).assertEqual(ReportActionState.ReportFailed);
      expect(presenter.reason).assertEqual('Spam');
      expect(presenter.leaveRoom).assertTrue();
      expect(gateway.reportCalls).assertEqual(1);
      expect(gateway.leaveCalls).assertEqual(0);
      expect(gateway.effects.join(',')).assertEqual('report_room');
      console.info('ARKTS_NATIVE_SMOKE_PASS rr_state_007_report_failure_stops_leave');
    });
  });
}
