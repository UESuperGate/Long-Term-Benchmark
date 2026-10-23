import { hilog } from '@kit.PerformanceAnalysisKit';
import {
  GifPageResult,
  GifState,
  KeyboardSticker,
  MediaKeyboardEnvironment,
  MediaKeyboardPageOwner,
  MediaKeyboardState,
  MediaRuntimeEffect
} from '../feature/MediaKeyboardStore';

interface ConfirmationState {
  confirmation: KeyboardSticker | null;
}

interface GifRepositoryInput {
  result: string;
  gifIds?: string[];
  hasMore?: boolean;
}

interface MediaGivenEvidence {
  repositoryTabs?: string[];
  initialTab?: string | null;
  offeredTabs?: string[];
  preferredTab?: string;
  restrictedTo?: string[] | null;
  availableTabs?: string[];
  selectedTab?: string;
  searchActive?: boolean;
  searchQuery?: string;
  gifs?: string[];
  loadFailed?: boolean;
  hasMore?: boolean;
  repositoryFirstPage?: GifRepositoryInput;
  repositoryNextPage?: GifRepositoryInput;
  sticker?: KeyboardSticker;
  confirmation?: KeyboardSticker | null;
}

interface MediaObservationRecord {
  caseId: string;
  productionEntrypoint: string;
  ownerAction: string;
  ownerId: string;
  entryLifecycle: string;
  given: MediaGivenEvidence;
  before: Object;
  after: Object;
  effects: MediaRuntimeEffect[];
  availability: string;
}

let observerRan: boolean = false;

function emit(
  owner: MediaKeyboardPageOwner,
  caseId: string,
  ownerAction: string,
  given: MediaGivenEvidence,
  before: Object,
  after: Object,
  effects: MediaRuntimeEffect[]
): void {
  const record: MediaObservationRecord = {
    caseId,
    productionEntrypoint: `Index.owner.${ownerAction}`,
    ownerAction,
    ownerId: owner.ownerId,
    entryLifecycle: 'Index.aboutToAppear',
    given,
    before,
    after,
    effects,
    availability: 'executed_arkvm_entryability_arkui_page_owner'
  };
  hilog.info(0x0B01, 'BenchmarkObserver', 'BENCHMARK_CASE:%{public}s', JSON.stringify(record));
}

function confirmationState(owner: MediaKeyboardPageOwner): ConfirmationState {
  return { confirmation: owner.confirmation() };
}

function gifInput(page: GifPageResult): GifRepositoryInput {
  if (page.failed) return { result: 'network_failure' };
  return { result: 'success', gifIds: [...page.ids], hasMore: page.hasMore };
}

export function runMediaSemanticObserver(owner: MediaKeyboardPageOwner): void {
  if (observerRan) return;
  observerRan = true;
  const leaf: MediaKeyboardEnvironment = owner.externalLeaf();
  const sticker: KeyboardSticker = { packId: 'pack-1', packKey: 'key-1', stickerId: 7 };

  leaf.configureTabs(['GIF', 'EMOJI', 'STICKER']);
  leaf.resetEffects();
  owner.reopen();
  let beforeKeyboard: MediaKeyboardState = owner.keyboardState();
  let cursor: number = leaf.effectCursor();
  owner.initializeKeyboard();
  emit(owner, 'mk_state_001_initialize_tabs', 'initializeKeyboard', {
    repositoryTabs: leaf.configuredTabs(),
    initialTab: beforeKeyboard.initialized ? beforeKeyboard.selectedTab : null
  }, beforeKeyboard, owner.keyboardState(), leaf.effectsAfter(cursor));

  leaf.configureTabs(['EMOJI', 'STICKER', 'GIF']);
  owner.reopen();
  owner.initializeKeyboard();
  owner.selectTab('GIF');
  leaf.resetEffects();
  beforeKeyboard = owner.keyboardState();
  cursor = leaf.effectCursor();
  owner.restrictTabs(['EMOJI']);
  emit(owner, 'mk_state_002_restrict_fallback', 'restrictTabs', {
    offeredTabs: beforeKeyboard.offeredTabs,
    preferredTab: beforeKeyboard.preferredTab,
    restrictedTo: beforeKeyboard.restrictedTo
  }, beforeKeyboard, owner.keyboardState(), leaf.effectsAfter(cursor));

  owner.reopen();
  owner.initializeKeyboard();
  owner.selectTab('GIF');
  owner.restrictTabs(['EMOJI']);
  leaf.resetEffects();
  beforeKeyboard = owner.keyboardState();
  cursor = leaf.effectCursor();
  owner.restrictTabs(null);
  emit(owner, 'mk_state_003_lift_restriction', 'restrictTabs', {
    offeredTabs: beforeKeyboard.offeredTabs,
    preferredTab: beforeKeyboard.preferredTab,
    restrictedTo: beforeKeyboard.restrictedTo
  }, beforeKeyboard, owner.keyboardState(), leaf.effectsAfter(cursor));

  owner.reopen();
  owner.initializeKeyboard();
  owner.setSearch(true, 'cats');
  leaf.resetEffects();
  beforeKeyboard = owner.keyboardState();
  cursor = leaf.effectCursor();
  owner.selectTab('GIF');
  emit(owner, 'mk_state_004_tab_clears_query', 'selectTab', {
    availableTabs: beforeKeyboard.availableTabs,
    selectedTab: beforeKeyboard.selectedTab,
    searchActive: beforeKeyboard.searchActive,
    searchQuery: beforeKeyboard.searchQuery
  }, beforeKeyboard, owner.keyboardState(), leaf.effectsAfter(cursor));

  owner.reopen();
  leaf.configureGifPage(0, { failed: true, ids: [], hasMore: false });
  leaf.resetEffects();
  let beforeGif: GifState = owner.gifState();
  cursor = leaf.effectCursor();
  owner.loadFirstGifPage();
  emit(owner, 'mk_state_005_gif_initial_failure', 'loadFirstGifPage', {
    gifs: beforeGif.gifs,
    hasMore: beforeGif.hasMore,
    repositoryFirstPage: gifInput(leaf.configuredGifPage(0))
  }, beforeGif, owner.gifState(), leaf.effectsAfter(cursor));

  owner.reopen();
  leaf.configureGifPage(0, { failed: true, ids: [], hasMore: false });
  owner.loadFirstGifPage();
  leaf.configureGifPage(0, { failed: false, ids: ['g1', 'g2'], hasMore: true });
  leaf.resetEffects();
  beforeGif = owner.gifState();
  cursor = leaf.effectCursor();
  owner.retryGifLoad();
  emit(owner, 'mk_state_006_gif_retry_recovery', 'retryGifLoad', {
    gifs: beforeGif.gifs,
    loadFailed: beforeGif.loadFailed,
    hasMore: beforeGif.hasMore,
    repositoryFirstPage: gifInput(leaf.configuredGifPage(0))
  }, beforeGif, owner.gifState(), leaf.effectsAfter(cursor));

  owner.reopen();
  leaf.configureGifPage(0, { failed: false, ids: ['g1', 'g2'], hasMore: true });
  owner.loadFirstGifPage();
  leaf.configureGifPage(2, { failed: false, ids: ['g3'], hasMore: false });
  leaf.resetEffects();
  beforeGif = owner.gifState();
  cursor = leaf.effectCursor();
  owner.loadMoreGifs();
  emit(owner, 'mk_state_007_gif_pagination', 'loadMoreGifs', {
    gifs: beforeGif.gifs,
    hasMore: beforeGif.hasMore,
    loadFailed: beforeGif.loadFailed,
    repositoryNextPage: gifInput(leaf.configuredGifPage(2))
  }, beforeGif, owner.gifState(), leaf.effectsAfter(cursor));

  owner.reopen();
  leaf.resetEffects();
  let beforeConfirmation: ConfirmationState = confirmationState(owner);
  cursor = leaf.effectCursor();
  owner.tapSticker(sticker);
  emit(owner, 'mk_state_008_sticker_tap_defers_send', 'tapSticker', {
    sticker,
    confirmation: beforeConfirmation.confirmation
  }, beforeConfirmation, confirmationState(owner), leaf.effectsAfter(cursor));

  owner.reopen();
  owner.tapSticker(sticker);
  leaf.resetEffects();
  beforeConfirmation = confirmationState(owner);
  cursor = leaf.effectCursor();
  owner.cancelStickerConfirmation();
  emit(owner, 'mk_state_009_confirmation_cancel', 'cancelStickerConfirmation', {
    confirmation: beforeConfirmation.confirmation
  }, beforeConfirmation, confirmationState(owner), leaf.effectsAfter(cursor));

  owner.reopen();
  owner.tapSticker(sticker);
  leaf.resetEffects();
  beforeConfirmation = confirmationState(owner);
  cursor = leaf.effectCursor();
  owner.confirmStickerSend();
  emit(owner, 'mk_state_010_confirmation_send_once', 'confirmStickerSend', {
    confirmation: beforeConfirmation.confirmation
  }, beforeConfirmation, confirmationState(owner), leaf.effectsAfter(cursor));

  hilog.info(0x0B01, 'BenchmarkObserver', 'BENCHMARK_COMPLETE:01_media_keyboard');
}

