import { LegacySupportPageOwner, LegacySupportPageRuntime } from '../pages/UnifiedSupportPageOwner';

export interface SemanticPayload {
  key: string;
  beforeJson: string;
  afterJson: string;
  observedJson: string;
  effectsJson: string;
  invariantChecksJson: string;
  productionBodies: string[];
  runtimeEvidenceJson: string;
}

export interface PageRecreator { recreate(): Promise<void>; }

interface InvariantCheck { invariant: string; passed: boolean; evidence: string; }
interface LegacySnapshot { surface: string; entries: string[]; }
interface LegacyObserved { surface: string; availableActions: string[]; targetFeatureReached: boolean; }
interface RuntimeEvidence {
  pageOwnerId: string; controllerOwnerId: string; pageGeneration: number; storeSource: string;
  evaluatorStoreWrites: number; detachedControllers: number; leafCalls: string[]; pageRecreated: boolean;
  previousPageOwnerId?: string; previousControllerOwnerId?: string;
}

export function prepareSemanticCase(_key: string): void { LegacySupportPageRuntime.reset(); }

function invariantNames(key: string): string[] {
  if (key === 'list_success') return ['bot and Happiness Engineer conversations share one ordered list', 'the retired separate entries are not rendered'];
  if (key === 'list_failure') return ['a failed request is not represented as an empty successful list', 'the repository body reaches the controlled service leaf'];
  if (key === 'list_retry') return ['retry uses the same unified repository path', 'recovery replaces the error state without recreating separate support flows'];
  if (key === 'new_bot_success') return ['the local user question remains exactly once', 'the application-owned create mapping executes before the service leaf response is consumed'];
  if (key === 'reply_success') return ['the input is cleared while the request is pending', 'temporary files are removed after completion', 'the list and selected detail refer to the same conversation identity'];
  if (key === 'offline_reply') return ['offline detection occurs before optimistic insertion', "the user's draft remains retryable"];
  if (key === 'reply_failure') return ['only the optimistic message is rolled back', 'pre-existing messages remain unchanged', 'temporary files are removed on failure'];
  if (key === 'concurrent_guard') return ['the sending guard is set before asynchronous work begins', 'the second event cannot reach the repository or external leaf'];
  if (key === 'draft_lifecycle') return ['page recreation reuses the production view model', 'draft state from conversation 9 never appears in conversation 10'];
  if (key === 'detail_affordances') return ['affordances derive from status and reply capability', 'closed tickets cannot dispatch replies'];
  throw new Error(`unknown semantic case: ${key}`);
}

export async function runSemanticCase(key: string, recreator?: PageRecreator): Promise<SemanticPayload> {
  const owner: LegacySupportPageOwner = await LegacySupportPageRuntime.waitForOwner();
  const before: LegacySnapshot = { surface: owner.store().surface, entries: owner.store().entries.slice() };
  let observedOwner: LegacySupportPageOwner = owner;
  if (key === 'draft_lifecycle') {
    if (recreator === undefined) throw new Error('page recreator is required');
    await recreator.recreate();
    observedOwner = await LegacySupportPageRuntime.waitForOwnerAfter(owner.ownerId);
  }
  observedOwner.openSupport();
  const after: LegacySnapshot = { surface: observedOwner.store().surface, entries: observedOwner.store().entries.slice() };
  const observed: LegacyObserved = { surface: observedOwner.store().surface,
    availableActions: observedOwner.store().entries.slice(), targetFeatureReached: false };
  const checks: InvariantCheck[] = [];
  for (const name of invariantNames(key)) {
    const check: InvariantCheck = { invariant: name, passed: false,
      evidence: 'The mounted 26.8 page owner still renders separate support entries.' };
    checks.push(check);
  }
  const runtimeEvidence: RuntimeEvidence = {
    pageOwnerId: observedOwner.ownerId,
    controllerOwnerId: observedOwner.controllerId,
    pageGeneration: LegacySupportPageRuntime.ownerGeneration(),
    storeSource: 'LegacySupportPageOwner.controller.store',
    evaluatorStoreWrites: 0,
    detachedControllers: 0,
    leafCalls: [],
    pageRecreated: key === 'draft_lifecycle'
  };
  if (key === 'draft_lifecycle') {
    runtimeEvidence.previousPageOwnerId = owner.ownerId;
    runtimeEvidence.previousControllerOwnerId = owner.controllerId;
  }
  return {
    key: key,
    beforeJson: JSON.stringify(before),
    afterJson: JSON.stringify(after),
    observedJson: JSON.stringify(observed),
    effectsJson: '[]',
    invariantChecksJson: JSON.stringify(checks),
    productionBodies: key === 'draft_lifecycle' ?
      ['EntryAbility.recreatePage', 'LegacySupportPageRuntime.createOwner', 'LegacySupportController.open'] :
      ['LegacySupportPageOwner.aboutToAppear', 'LegacySupportController.open'],
    runtimeEvidenceJson: JSON.stringify(runtimeEvidence)
  };
}
