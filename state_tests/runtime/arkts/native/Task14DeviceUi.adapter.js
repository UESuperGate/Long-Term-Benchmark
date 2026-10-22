import { startTask14Page } from './Task14DeviceUi.core';
import { runTask14Transition, TASK14_CASES } from './Task14DeviceUi.suite';

// Standalone hook: no dependency on any shared adapter factory or domain object.
export async function evaluateTask14UI(args, config, ports, record) {
  const { taskId, caseSpec, load, trace = () => {} } = args;
  const unsupported = reason => ({ observed: {}, evidence: [], invariantChecks: [], unsupported: reason,
    unsupportedInvariants: (caseSpec.invariants || []).map(description => ({ description, reason })) });
  if (taskId !== '14_join_room_by_address' || TASK14_CASES[caseSpec.caseId] !== caseSpec.key)
    return unsupported('Independent Task14 device suite supports only cases001/003/007');
  trace('before:binding', { taskId, caseId: caseSpec.caseId, mode: config.mode });
  let session;
  try {
    if (config.mode !== 'after-page-ready') throw new Error('Task14 original-app import disabled; explicit after-page-ready opt-in required');
    // Register source provenance only. Never construct/call these bundled
    // exports or combine their state with native UI. Actual observation binds
    // the original /entry/ class after the real page is positively observed.
    if (config.presenterSourcePath) load(config.presenterSourcePath);
    session = await startTask14Page(ports, config, record);
    return await runTask14Transition(caseSpec, config, session, ports.importModule, record, trace);
  } catch (error) {
    const reason = String(error.message || error);
    trace('before:event', { executed: false, reason });
    trace('after:event', { executed: false, reason });
    return unsupported(reason);
  } finally { if (session) await session.release(); }
}
