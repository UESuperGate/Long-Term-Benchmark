import { hilog } from '@kit.PerformanceAnalysisKit';
import {
  StickerManagementEnvironment,
  StickerManagementPageOwner,
  StickerManagementState,
  StickerPack,
  StickerRuntimeEffect
} from '../feature/StickerManagementStore';

interface PromptState {
  numItemsToDelete: number;
}

interface ObservedState {
  installedPackIds: string[];
  availableOfficialIds: string[];
  availableOtherIds: string[];
  availablePackIds: string[];
  selectedPackIds: string[];
  multiSelectEnabled: boolean;
  prompt: PromptState | null;
  confirmation: Object | null;
  downloadStatus: string | null;
}

interface AvailablePackEvidence {
  id: string;
  key: string;
  title: string;
}

interface DownloadStatusesEvidence {
  p1: string | null;
}

interface StickerGivenEvidence {
  installedPackIds?: string[];
  availablePackIds?: string[];
  selectedPackIds?: string[];
  multiSelectEnabled?: boolean;
  prompt?: PromptState | null;
  availablePack?: AvailablePackEvidence;
  linkedDevices?: boolean;
  downloadStatuses?: DownloadStatusesEvidence;
  repositoryInstalledIds?: string[];
}

interface StickerObservationRecord {
  caseId: string;
  productionEntrypoint: string;
  ownerAction: string;
  ownerId: string;
  entryLifecycle: string;
  given: StickerGivenEvidence;
  before: ObservedState;
  after: ObservedState;
  effects: StickerRuntimeEffect[];
  orderedStates: string[];
  orderedTimeline: string[];
  persistenceReopened: boolean;
  availability: string;
}

let observerRan: boolean = false;

function pack(id: string, installed: boolean, order: number = 0, title: string = id): StickerPack {
  return { id, key: id === 'p1' ? 'k1' : `key-${id}`, title, installed, official: false, order };
}

function observed(owner: StickerManagementPageOwner, statusId: string = ''): ObservedState {
  const state: StickerManagementState = owner.state();
  return {
    installedPackIds: state.installedPackIds,
    availableOfficialIds: state.availableOfficialIds,
    availableOtherIds: state.availableOtherIds,
    availablePackIds: [...state.availableOfficialIds, ...state.availableOtherIds],
    selectedPackIds: state.selectedPackIds,
    multiSelectEnabled: state.multiSelectEnabled,
    prompt: state.prompt === null ? null : { numItemsToDelete: state.prompt },
    confirmation: state.confirmation,
    downloadStatus: statusId.length === 0 ? null : owner.downloadStatus(statusId)
  };
}

function stateTimeline(timeline: string[]): string[] {
  return timeline.filter((item: string) => item.startsWith('state:')).map((item: string) => item.slice(6));
}

function emit(
  owner: StickerManagementPageOwner,
  leaf: StickerManagementEnvironment,
  caseId: string,
  ownerAction: string,
  given: StickerGivenEvidence,
  before: ObservedState,
  after: ObservedState,
  effects: StickerRuntimeEffect[],
  persistenceReopened: boolean = false
): void {
  const timeline: string[] = leaf.orderedTimeline();
  const record: StickerObservationRecord = {
    caseId,
    productionEntrypoint: `Index.owner.${ownerAction}`,
    ownerAction,
    ownerId: owner.ownerId,
    entryLifecycle: 'Index.aboutToAppear',
    given,
    before,
    after,
    effects,
    orderedStates: stateTimeline(timeline),
    orderedTimeline: timeline,
    persistenceReopened,
    availability: 'executed_arkvm_entryability_arkui_page_owner'
  };
  hilog.info(0x0B02, 'BenchmarkObserver', 'BENCHMARK_CASE:%{public}s', JSON.stringify(record));
}

function prepare(
  owner: StickerManagementPageOwner,
  leaf: StickerManagementEnvironment,
  records: StickerPack[],
  linkedDevices: boolean = false
): void {
  leaf.replacePacks(records);
  leaf.configureLinkedDevices(linkedDevices);
  owner.reopen();
  leaf.resetEffects();
}

export function runStickerSemanticObserver(owner: StickerManagementPageOwner): void {
  if (observerRan) return;
  observerRan = true;
  const leaf: StickerManagementEnvironment = owner.externalLeaf();
  let before: ObservedState;
  let cursor: number;

  prepare(owner, leaf, [pack('a', true, 0), pack('b', true, 1)]);
  owner.toggleSelection('a');
  leaf.resetEffects();
  before = observed(owner);
  cursor = leaf.effectCursor();
  owner.setMultiSelectEnabled(false);
  emit(owner, leaf, 'sm_state_001_exit_multiselect', 'setMultiSelectEnabled', {
    installedPackIds: before.installedPackIds,
    selectedPackIds: before.selectedPackIds,
    multiSelectEnabled: before.multiSelectEnabled
  }, before, observed(owner), leaf.effectsAfter(cursor));

  const p1: StickerPack = pack('p1', false, 0, 'One');
  prepare(owner, leaf, [p1]);
  before = observed(owner, 'p1');
  cursor = leaf.effectCursor();
  owner.installPack('p1');
  emit(owner, leaf, 'sm_state_002_install_lifecycle', 'installPack', {
    availablePack: { id: p1.id, key: p1.key, title: p1.title },
    linkedDevices: leaf.hasLinkedDevices()
  }, before, observed(owner, 'p1'), leaf.effectsAfter(cursor));

  prepare(owner, leaf, [p1]);
  owner.installPack('p1');
  leaf.resetEffects();
  before = observed(owner, 'p1');
  cursor = leaf.effectCursor();
  owner.installationLingerElapsed('p1');
  emit(owner, leaf, 'sm_state_003_install_status_settles', 'installationLingerElapsed', {
    availablePackIds: before.availablePackIds,
    downloadStatuses: { p1: before.downloadStatus },
    repositoryInstalledIds: leaf.repositoryInstalledIds()
  }, before, observed(owner, 'p1'), leaf.effectsAfter(cursor));

  prepare(owner, leaf, [pack('a', true, 0), pack('b', true, 1), pack('c', true, 2)]);
  before = observed(owner);
  cursor = leaf.effectCursor();
  owner.movePack(0, 2);
  emit(owner, leaf, 'sm_state_004_drag_reorder', 'movePack', {
    installedPackIds: before.installedPackIds
  }, before, observed(owner), leaf.effectsAfter(cursor));

  prepare(owner, leaf, [pack('a', true, 0), pack('b', true, 1), pack('c', true, 2)]);
  before = observed(owner);
  cursor = leaf.effectCursor();
  owner.completeDrag(0, 2);
  const persistEffects: StickerRuntimeEffect[] = leaf.effectsAfter(cursor);
  owner.reopen();
  emit(owner, leaf, 'sm_state_005_drop_persists_order', 'completeDrag+reopen', {
    installedPackIds: before.installedPackIds
  }, before, observed(owner), persistEffects, true);

  prepare(owner, leaf, [pack('a', true, 0), pack('b', true, 1)]);
  before = observed(owner);
  cursor = leaf.effectCursor();
  owner.toggleSelection('a');
  emit(owner, leaf, 'sm_state_006_select_enters_multiselect', 'toggleSelection', {
    installedPackIds: before.installedPackIds,
    selectedPackIds: before.selectedPackIds,
    multiSelectEnabled: before.multiSelectEnabled
  }, before, observed(owner), leaf.effectsAfter(cursor));

  prepare(owner, leaf, [pack('a', true, 0), pack('b', true, 1), pack('c', true, 2)]);
  owner.toggleSelection('a');
  leaf.resetEffects();
  before = observed(owner);
  cursor = leaf.effectCursor();
  owner.toggleSelectAll();
  emit(owner, leaf, 'sm_state_007_select_all_toggle', 'toggleSelectAll', {
    installedPackIds: before.installedPackIds,
    selectedPackIds: before.selectedPackIds,
    multiSelectEnabled: before.multiSelectEnabled
  }, before, observed(owner), leaf.effectsAfter(cursor));

  prepare(owner, leaf, [pack('a', true, 0), pack('b', true, 1), pack('c', true, 2)]);
  owner.toggleSelection('a');
  owner.toggleSelection('c');
  leaf.resetEffects();
  before = observed(owner);
  cursor = leaf.effectCursor();
  owner.requestUninstall(['a', 'c']);
  emit(owner, leaf, 'sm_state_008_request_multi_delete', 'requestUninstall', {
    installedPackIds: before.installedPackIds,
    selectedPackIds: before.selectedPackIds,
    multiSelectEnabled: before.multiSelectEnabled
  }, before, observed(owner), leaf.effectsAfter(cursor));

  prepare(owner, leaf, [pack('a', true, 0), pack('b', true, 1), pack('c', true, 2)]);
  owner.toggleSelection('a');
  owner.toggleSelection('c');
  owner.requestUninstall(['a', 'c']);
  leaf.resetEffects();
  before = observed(owner);
  cursor = leaf.effectCursor();
  owner.cancelUninstall();
  emit(owner, leaf, 'sm_state_009_cancel_multi_delete', 'cancelUninstall', {
    installedPackIds: before.installedPackIds,
    selectedPackIds: before.selectedPackIds,
    prompt: before.prompt
  }, before, observed(owner), leaf.effectsAfter(cursor));

  prepare(owner, leaf, [pack('a', true, 0), pack('b', true, 1), pack('c', true, 2)], true);
  owner.toggleSelection('a');
  owner.toggleSelection('c');
  owner.requestUninstall(['a', 'c']);
  leaf.resetEffects();
  before = observed(owner);
  cursor = leaf.effectCursor();
  owner.confirmUninstall();
  emit(owner, leaf, 'sm_state_010_confirm_multi_delete', 'confirmUninstall', {
    installedPackIds: before.installedPackIds,
    selectedPackIds: before.selectedPackIds,
    prompt: before.prompt,
    linkedDevices: leaf.hasLinkedDevices()
  }, before, observed(owner), leaf.effectsAfter(cursor));

  hilog.info(0x0B02, 'BenchmarkObserver', 'BENCHMARK_COMPLETE:02_sticker_management');
}

