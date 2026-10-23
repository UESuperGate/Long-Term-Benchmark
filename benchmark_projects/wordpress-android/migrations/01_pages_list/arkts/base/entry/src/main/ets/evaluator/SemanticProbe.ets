import { LegacyPagesPageOwner, LegacyPagesPageRuntime } from '../pages/PagesPageOwner';

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

interface InvariantCheck { invariant: string; passed: boolean; evidence: string; }
interface LegacySnapshot { surface: string; rows: number[]; }
interface LegacyObserved { surface: string; availableActions: string[]; targetFeatureReached: boolean; }
interface RuntimeEvidence {
  pageOwnerId: string; controllerOwnerId: string; pageGeneration: number; storeSource: string;
  evaluatorStoreWrites: number; detachedControllers: number; leafCalls: string[];
}

export function prepareSemanticCase(_key: string): void { LegacyPagesPageRuntime.reset(); }

function invariantNames(key: string): string[] {
  if (key === 'open_published') return ['no posts request is dispatched', 'thumbnail resolution never removes the page row', 'the row opens through the existing editor bridge rather than a replacement editor'];
  if (key === 'refresh_retry') return ['loaded rows remain visible during the failed refresh', 'retry executes the application-owned refresh body', 'no obsolete collection writes after recovery'];
  if (key === 'short_search') return ['queries shorter than three characters never reach the service leaf', 'the selected tab is retained'];
  if (key === 'debounced_search') return ['the superseded hel request is not dispatched', 'search results are flat and independent of the selected tab hierarchy'];
  if (key === 'close_search') return ['closing search does not switch tabs', 'the obsolete search collection is closed before the tab reload'];
  if (key === 'author_filter') return ['the author identifier is derived from the signed-in account', 'unrelated preferences remain unchanged'];
  if (key === 'published_hierarchy') return ['every input page appears exactly once', 'missing-parent pages remain visible', 'indentation never exceeds three'];
  if (key === 'menu_eligibility') return ['destructive actions are not rendered for the homepage', 'action eligibility is derived from page and site state'];
  if (key === 'trash_success') return ['the service mutation is not called before confirmation', 'the application-owned mutation body is invoked exactly once'];
  if (key === 'trash_failure_retry') return ['failure does not optimistically remove the page', 'retry uses the same page identity', 'only the controlled external leaf supplies outcomes'];
  throw new Error(`unknown semantic case: ${key}`);
}

export async function runSemanticCase(key: string): Promise<SemanticPayload> {
  const owner: LegacyPagesPageOwner = await LegacyPagesPageRuntime.waitForOwner();
  const before: LegacySnapshot = { surface: owner.store().surface, rows: owner.store().rows.map(row => row.id) };
  owner.openPages();
  const after: LegacySnapshot = { surface: owner.store().surface, rows: owner.store().rows.map(row => row.id) };
  const observed: LegacyObserved = { surface: owner.store().surface, availableActions: ['open_pages'], targetFeatureReached: false };
  const checks: InvariantCheck[] = [];
  for (const name of invariantNames(key)) {
    const check: InvariantCheck = { invariant: name, passed: false,
      evidence: 'The mounted 26.8 page owner remains on the legacy Pages surface.' };
    checks.push(check);
  }
  const runtimeEvidence: RuntimeEvidence = {
    pageOwnerId: owner.ownerId,
    controllerOwnerId: owner.controllerId,
    pageGeneration: LegacyPagesPageRuntime.ownerGeneration(),
    storeSource: 'LegacyPagesPageOwner.controller.store',
    evaluatorStoreWrites: 0,
    detachedControllers: 0,
    leafCalls: []
  };
  return {
    key: key,
    beforeJson: JSON.stringify(before),
    afterJson: JSON.stringify(after),
    observedJson: JSON.stringify(observed),
    effectsJson: '[]',
    invariantChecksJson: JSON.stringify(checks),
    productionBodies: ['LegacyPagesPageOwner.aboutToAppear', 'LegacyPagesController.open'],
    runtimeEvidenceJson: JSON.stringify(runtimeEvidence)
  };
}
