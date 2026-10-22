import { startTask11Page } from './Task11Session';
import { runTask11Case, TASK11_CASES } from './Task11Suite';

export async function evaluateTask11Strict(args, config, ports, record) {
  const { caseSpec, taskId, trace = () => {} } = args;
  let session;
  try {
    if (taskId !== '11_room_upgrade_navigation' || !TASK11_CASES.includes(caseSpec.caseId))
      throw new Error('Task11 strict runtime suite requires one of the six canonical cases');
    if (!['base', 'final', 'agent'].includes(config.role) || !['base', 'final', 'auto'].includes(config.apiVariant) ||
        config.mode !== 'after-page-ready-prefix')
      throw new Error('Task11 strict runtime role/mode is not bound');
    for (const source of config.productionSources) {
      if (config.productionModuleUrl.endsWith(source.path.replace('entry/src/main/', '').replace(/\.ets$/, '')))
        args.load(source.path);
    }
    session = await startTask11Page(ports, config, record);
    const namespace = await ports.importModule(config.productionModuleUrl);
    const fullEntry = typeof namespace.RoomUpgradePresenter?.prototype?.observeTimelineRoomInfo === 'function';
    const commonEntry = typeof namespace.RoomPresenter?.prototype?.observeRoomInfo === 'function';
    if (fullEntry === commonEntry) throw new Error('Production runtime entry capability missing or ambiguous');
    const resolved = { ...config, apiVariant: fullEntry ? 'final' : 'base' };
    record({ method: 'Task11.runtimeEntryCapability', role: config.role,
      source: config.productionModuleUrl, commonEntry, fullEntry, resolvedApi: resolved.apiVariant });
    return await runTask11Case(caseSpec, resolved, session, ports.importModule, record, trace);
  } catch (error) {
    const reason = String(error.message || error);
    trace('before:event', { executed: false, reason });
    trace('after:event', { executed: false, reason });
    return { observed: {}, evidence: [], invariantChecks: [], unsupported: reason,
      unsupportedInvariants: (caseSpec.invariants || []).map(description => ({ description, reason })) };
  } finally {
    if (session) await session.release();
  }
}
