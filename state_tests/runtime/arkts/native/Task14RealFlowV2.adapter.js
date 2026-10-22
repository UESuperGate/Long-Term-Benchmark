import { runTask14RealFlowV2 } from './Task14RealFlowV2.suite';
import { startTask14Page } from './Task14DeviceUi.core';

export async function evaluateTask14RealFlowV2(args, config, ports, record) {
  const { taskId, caseSpec, load, trace = () => {} } = args;
  const unsupported = reason => ({ observed: {}, evidence: [], invariantChecks: [],
    unsupported: reason, unsupportedInvariants: (caseSpec.invariants || []).map(description => ({ description, reason })) });
  if (taskId !== '14_join_room_by_address' || caseSpec.caseId !== 'jr_state_001_entry_opens_address_flow')
    return unsupported('Task14 real_flow_v2 executes only canonical case001');
  let session;
  try {
    if (config.mode !== 'after-page-ready' || config.realFlowV2 !== true)
      throw new Error('Task14 real_flow_v2 source/import mode is not explicitly bound');
    const bound = new Set([
      'entry/src/main/ets/features/JoinRoomByAddressFeature.ets',
      'entry/src/main/ets/features/JoinRoomRuntime.ets',
      'entry/src/main/ets/features/ChatFeature.ets',
      'entry/src/main/ets/features/ChatRoutes.ets',
      'entry/src/main/ets/features/ChatRuntime.ets'
    ]);
    for (const source of config.productionSources || []) if (bound.has(source.path)) load(source.path);
    session = await startTask14Page(ports, config, record);
    return await runTask14RealFlowV2(caseSpec, config, session, ports.importModule, record, trace);
  } catch (error) {
    const reason = String(error?.message || error);
    trace('before:event', { executed: false, reason });
    trace('after:event', { executed: false, reason });
    return unsupported(reason);
  } finally { if (session) await session.release(); }
}
