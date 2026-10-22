import { startTask11Page } from './Task11Session';
import { runTask09Case, TASK09_CASES } from './Task09Suite';
import { prepareTask09Repository } from './Task09Repository';

export async function evaluateTask09Strict(args, config, ports, record) {
  const { caseSpec, taskId, trace = () => {} } = args;
  let session, repositoryObserver;
  try {
    if (taskId !== '09_spaces_lifecycle' || !TASK09_CASES.includes(caseSpec.caseId))
      throw new Error('Task09 strict runtime suite requires one of the nine canonical cases');
    if (!['base', 'final', 'agent'].includes(config.role) || config.mode !== 'after-page-ready-prefix')
      throw new Error('Task09 strict runtime role/mode is not bound');
    // Native repository modules already execute via ArkVM import(). Loading a
    // second host-transpiled copy here both changes receivers and loses imports.
    if (config.productionVariant !== 'repository') args.load(config.productionSourcePath);
    session = await startTask11Page(ports, config, record);
    session.checked = async selector => {
      const frame = await session.observe('Task09.checkboxAnchor', { target: [selector] });
      if (!frame.controls.target.present || !frame.controls.target.visible)
        throw new Error('Task09 native checkbox unavailable');
      const driver = ports.createDriver();
      let found = await driver.findComponents(ports.selector(selector, config.bundleName));
      if (found == null) {
        const inventory = await driver.findComponents(ports.selector({}, config.bundleName));
        if (!Array.isArray(inventory) || !inventory.length)
          throw new Error('Task09 native checkbox inventory unavailable');
        found = [];
        for (const component of inventory) if (await component.getId() === selector.id) found.push(component);
      }
      if (!Array.isArray(found) || found.length !== 1 || !await found[0].isCheckable())
        throw new Error('Task09 native checkbox state unavailable');
      return await found[0].isChecked();
    };
    if (config.productionVariant === 'repository') {
      repositoryObserver = await prepareTask09Repository(caseSpec, config, ports.importModule, record);
      await session.reloadOriginalPage();
    }
    return await runTask09Case(caseSpec, config, session, ports.importModule, record, trace, repositoryObserver);
  } catch (error) {
    const reason = String(error.message || error);
    trace('before:event', { executed: false, reason });
    trace('after:event', { executed: false, reason });
    return { observed: {}, evidence: [], invariantChecks: [], unsupported: reason,
      unsupportedInvariants: (caseSpec.invariants || []).map(description => ({ description, reason })) };
  } finally {
    if (repositoryObserver) repositoryObserver.dispose();
    if (session) await session.release();
  }
}
