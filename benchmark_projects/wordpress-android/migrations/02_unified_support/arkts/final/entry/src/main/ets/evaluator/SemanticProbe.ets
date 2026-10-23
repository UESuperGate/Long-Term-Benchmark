import {
  AttachmentLeaf,
  NetworkLeaf,
  SupportConversation,
  SupportMessage,
  SupportServiceLeaf
} from '../features/UnifiedSupportController';
import {
  RenderedAffordance,
  UnifiedSupportPageOwner,
  UnifiedSupportPageRuntime
} from '../pages/UnifiedSupportPageOwner';

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
interface LeafCall { name: string; detail: string; }
interface CreateCall { botId: string; message: string; }
interface ReplyCall { id: number; message: string; attachments: string[]; logIds: string[]; }
interface RuntimeEvidence {
  pageOwnerId: string;
  controllerOwnerId: string;
  pageGeneration: number;
  storeSource: string;
  evaluatorStoreWrites: number;
  detachedControllers: number;
  leafCalls: LeafCall[];
  previousPageOwnerId?: string;
  previousControllerOwnerId?: string;
  pageRecreated: boolean;
}
interface NamedEffect { name: string; }
interface AttachmentEffect { name: string; inputs: string[]; }
interface CreateEffect { name: string; botId: string; message: string; }
interface ReplyEffect { name: string; conversationId: number; message?: string; }
interface CreateDetail { botId: string; message: string; }
interface ReplyDetail { id: number; message: string; attachments: string[]; logIds: string[]; }
interface SurfaceSnapshot { surface: string; }
interface RowsSnapshot { rows: number[]; }
interface ListRow { id: number; presentation: string; status?: string; }
interface ListObserved {
  surface: string; entryLabel: string; loading: boolean; error: null; rows: ListRow[]; serviceEffect: NamedEffect;
}
interface ListFailureObserved { surface: string; loading: boolean; error: string; emptyState: boolean; rows: number[]; }
interface ListRetryObserved { surface: string; error: null; rows: ListRow[]; requestCount: number; }
interface MessageObserved { author: string; text: string; }
interface SelectedBot { id: number; type: string; messages: MessageObserved[]; }
interface NewBotObserved {
  surface: string; selectedConversation: SelectedBot; listFirstId: number; draft: string; sending: boolean;
  serviceEffect: CreateEffect;
}
interface ReplyObserved {
  surface: string; selectedMessages: number[]; listConversationId: number; draft: string; attachments: string[];
  includeAppLogs: boolean; sending: boolean; effects: Object[];
}
interface OfflineObserved {
  surface: string; selectedMessages: number[]; draft: string; error: string; sending: boolean; repositoryCallCount: number;
}
interface PendingFrame { draft: string; messageIds: (number | string)[]; }
interface SettledFrame { draft: string; messageIds: number[]; error: string; sending: boolean; }
interface ReplyFailureObserved { surface: string; pending: PendingFrame; settled: SettledFrame; effects: Object[]; }
interface ConcurrentObserved { surface: string; sendingWhileHeld: boolean; repositoryCallCountWhileHeld: number; sentMessages: string[]; }
interface DraftFrame {
  selectedConversationId: number; message: string; attachments: string[]; includeAppLogs: boolean; sheetVisible: boolean;
}
interface DraftObserved { surface: string; afterRecreate: DraftFrame; afterSwitch: DraftFrame; }
interface AffordanceObserved { id: number; composer: string; typingIndicatorSupported?: boolean; closedBanner?: boolean; }
interface DetailObserved { surface: string; affordances: AffordanceObserved[]; }

class ControlledNetwork implements NetworkLeaf {
  isOnline: boolean = true;
  calls: LeafCall[];
  constructor(calls: LeafCall[]) { this.calls = calls; }
  online(): boolean {
    this.calls.push({ name: 'networkOnline', detail: `${this.isOnline}` });
    return this.isOnline;
  }
}

class ControlledAttachments implements AttachmentLeaf {
  calls: LeafCall[];
  effects: Object[];
  reportCreateEffect: boolean = true;
  removed: string[] = [];

  constructor(calls: LeafCall[], effects: Object[]) { this.calls = calls; this.effects = effects; }

  async uploadEncryptedLogs(): Promise<string[]> {
    this.calls.push({ name: 'uploadEncryptedLogs', detail: 'log-1' });
    const effect: NamedEffect = { name: 'uploadEncryptedLogs' };
    this.effects.push(effect);
    return ['log-1'];
  }

  async createTempFiles(inputs: string[]): Promise<string[]> {
    this.calls.push({ name: 'createTempAttachments', detail: JSON.stringify(inputs) });
    if (this.reportCreateEffect) {
      const effect: AttachmentEffect = { name: 'createTempAttachments', inputs: inputs.slice() };
      this.effects.push(effect);
    }
    return inputs.map(value => `/tmp/${value}`);
  }

  async removeTempFiles(paths: string[]): Promise<void> {
    this.removed = paths.slice();
    this.calls.push({ name: 'removeTempAttachments', detail: JSON.stringify(paths) });
    const effect: NamedEffect = { name: 'removeTempAttachments' };
    this.effects.push(effect);
  }
}

class ControlledSupportService implements SupportServiceLeaf {
  calls: LeafCall[];
  effects: Object[];
  listResults: SupportConversation[][] = [];
  listFailures: boolean[] = [];
  conversationResults: SupportConversation[] = [];
  createResult: SupportConversation = conversation(44, 'bot', true, []);
  replyResult: SupportConversation = conversation(1, 'open', true, []);
  createCalls: CreateCall[] = [];
  replyCalls: ReplyCall[] = [];
  holdReply: boolean = false;
  failHeldReply: boolean = false;
  replyEffectIncludesMessage: boolean = true;
  private replyResolve?: (value: SupportConversation) => void;
  private replyReject?: (reason: Error) => void;

  constructor(calls: LeafCall[], effects: Object[]) { this.calls = calls; this.effects = effects; }

  async loadConversations(): Promise<SupportConversation[]> {
    this.calls.push({ name: 'loadUnifiedConversations', detail: '' });
    const effect: NamedEffect = { name: 'loadUnifiedConversations' };
    this.effects.push(effect);
    const failed = this.listFailures.length > 0 ? this.listFailures.shift() : false;
    if (failed) throw new Error('controlled_list_failure');
    const result = this.listResults.length > 0 ? this.listResults.shift() : [];
    return result === undefined ? [] : result;
  }

  async loadConversation(id: number): Promise<SupportConversation> {
    this.calls.push({ name: 'loadUnifiedConversation', detail: `${id}` });
    const result = this.conversationResults.length > 0 ? this.conversationResults.shift() : undefined;
    if (result === undefined) throw new Error('missing controlled conversation');
    return result;
  }

  async createBotConversation(botId: string, message: string): Promise<SupportConversation> {
    this.createCalls.push({ botId: botId, message: message });
    const detail: CreateDetail = { botId: botId, message: message };
    this.calls.push({ name: 'createBotConversation', detail: JSON.stringify(detail) });
    const effect: CreateEffect = { name: 'createBotConversation', botId: botId, message: message };
    this.effects.push(effect);
    return this.createResult;
  }

  reply(id: number, message: string, attachments: string[], logIds: string[]): Promise<SupportConversation> {
    this.replyCalls.push({ id: id, message: message, attachments: attachments.slice(), logIds: logIds.slice() });
    const detail: ReplyDetail = { id: id, message: message, attachments: attachments, logIds: logIds };
    this.calls.push({ name: 'replyToUnifiedConversation', detail: JSON.stringify(detail) });
    if (this.replyEffectIncludesMessage) {
      const effect: ReplyEffect = { name: 'replyToUnifiedConversation', conversationId: id, message: message };
      this.effects.push(effect);
    } else {
      const effect: ReplyEffect = { name: 'replyToUnifiedConversation', conversationId: id };
      this.effects.push(effect);
    }
    if (!this.holdReply) return Promise.resolve(this.replyResult);
    return new Promise<SupportConversation>((resolve, reject) => {
      this.replyResolve = resolve;
      this.replyReject = reject;
    });
  }

  releaseReply(): void {
    if (this.failHeldReply) {
      if (this.replyReject !== undefined) this.replyReject(new Error('controlled_reply_failure'));
    } else if (this.replyResolve !== undefined) {
      this.replyResolve(this.replyResult);
    }
  }
}

let leafCalls: LeafCall[] = [];
let effectLog: Object[] = [];
let activeService: ControlledSupportService = new ControlledSupportService(leafCalls, effectLog);
let activeNetwork: ControlledNetwork = new ControlledNetwork(leafCalls);
let activeAttachments: ControlledAttachments = new ControlledAttachments(leafCalls, effectLog);

function conversation(id: number, status: string, canAcceptReply: boolean, messageIds: number[]): SupportConversation {
  return {
    id: id,
    title: `Conversation ${id}`,
    status: status,
    canAcceptReply: canAcceptReply,
    messages: messageIds.map(messageId => {
      const message: SupportMessage = { id: messageId, author: 'bot', text: `message-${messageId}` };
      return message;
    })
  };
}

function emptyConversation(): SupportConversation {
  return { id: 0, title: '', status: '', canAcceptReply: false, messages: [] };
}

function emptyAffordance(): RenderedAffordance {
  return { id: 0, composer: '', typingIndicatorSupported: false, closedBanner: false };
}

export function prepareSemanticCase(key: string): void {
  leafCalls = [];
  effectLog = [];
  const service = new ControlledSupportService(leafCalls, effectLog);
  const network = new ControlledNetwork(leafCalls);
  const attachments = new ControlledAttachments(leafCalls, effectLog);
  if (key === 'list_success') {
    service.listResults.push([conversation(1, 'bot', true, []), conversation(2, 'open', true, [])]);
  } else if (key === 'list_failure') {
    service.listFailures.push(true);
  } else if (key === 'list_retry') {
    service.listFailures.push(true, false);
    service.listResults.push([conversation(3, 'bot', true, [])]);
  } else if (key === 'new_bot_success') {
    service.listResults.push([]);
    service.createResult = { id: 44, title: '', status: 'bot', canAcceptReply: true,
      messages: [{ id: 101, author: 'bot', text: 'Here is how.' }] };
  } else if (key === 'reply_success') {
    service.listResults.push([conversation(5, 'open', true, [])]);
    service.conversationResults.push(conversation(5, 'open', true, [10]));
    service.replyResult = conversation(5, 'open', true, [10, 11, 12]);
    service.holdReply = true;
  } else if (key === 'offline_reply') {
    service.listResults.push([conversation(6, 'open', true, [])]);
    service.conversationResults.push(conversation(6, 'open', true, [20]));
    network.isOnline = false;
  } else if (key === 'reply_failure') {
    service.listResults.push([conversation(7, 'open', true, [])]);
    service.conversationResults.push(conversation(7, 'open', true, [30]));
    service.holdReply = true;
    service.failHeldReply = true;
    service.replyEffectIncludesMessage = false;
    attachments.reportCreateEffect = false;
  } else if (key === 'concurrent_guard') {
    service.listResults.push([conversation(8, 'open', true, [])]);
    service.conversationResults.push(conversation(8, 'open', true, []));
    service.holdReply = true;
    service.replyResult = conversation(8, 'open', true, [1]);
  } else if (key === 'draft_lifecycle') {
    service.listResults.push([conversation(9, 'open', true, []), conversation(10, 'open', true, [])]);
    service.listResults.push([conversation(9, 'open', true, []), conversation(10, 'open', true, [])]);
    service.conversationResults.push(conversation(9, 'open', true, []), conversation(10, 'open', true, []));
  } else if (key === 'detail_affordances') {
    service.listResults.push([conversation(11, 'bot', true, []), conversation(12, 'open', true, []),
      conversation(13, 'closed', false, [])]);
  } else {
    throw new Error(`unknown semantic case: ${key}`);
  }
  activeService = service;
  activeNetwork = network;
  activeAttachments = attachments;
  UnifiedSupportPageRuntime.configure(service, network, attachments);
}

function runtimeEvidence(owner: UnifiedSupportPageOwner, previous?: UnifiedSupportPageOwner): RuntimeEvidence {
  const value: RuntimeEvidence = {
    pageOwnerId: owner.ownerId,
    controllerOwnerId: owner.controllerId,
    pageGeneration: UnifiedSupportPageRuntime.ownerGeneration(),
    storeSource: 'UnifiedSupportPageOwner.controller.store',
    evaluatorStoreWrites: 0,
    detachedControllers: 0,
    leafCalls: leafCalls.slice(),
    pageRecreated: previous !== undefined
  };
  if (previous !== undefined) {
    value.previousPageOwnerId = previous.ownerId;
    value.previousControllerOwnerId = previous.controllerId;
  }
  return value;
}

function payload(key: string, owner: UnifiedSupportPageOwner, before: Object, after: Object, observed: Object,
  effects: Object[], checks: InvariantCheck[], bodies: string[], previous?: UnifiedSupportPageOwner): SemanticPayload {
  return {
    key: key,
    beforeJson: JSON.stringify(before),
    afterJson: JSON.stringify(after),
    observedJson: JSON.stringify(observed),
    effectsJson: JSON.stringify(effects),
    invariantChecksJson: JSON.stringify(checks),
    productionBodies: bodies,
    runtimeEvidenceJson: JSON.stringify(runtimeEvidence(owner, previous))
  };
}

function eventEffects(start: number): Object[] { return effectLog.slice(start); }
function messageIds(owner: UnifiedSupportPageOwner): number[] {
  const selected = owner.store().selected;
  return selected === undefined ? [] : selected.messages.map(message => message.id);
}

async function allowAsyncProgress(): Promise<void> {
  await Promise.resolve(0);
  await Promise.resolve(0);
  await Promise.resolve(0);
}

export async function runSemanticCase(key: string, recreator?: PageRecreator): Promise<SemanticPayload> {
  const owner = await UnifiedSupportPageRuntime.waitForOwner();
  await owner.waitUntilReady();
  if (key === 'list_success') return listSuccess(key, owner);
  if (key === 'list_failure') return listFailure(key, owner);
  if (key === 'list_retry') return listRetry(key, owner);
  if (key === 'new_bot_success') return newBotSuccess(key, owner);
  if (key === 'reply_success') return replySuccess(key, owner);
  if (key === 'offline_reply') return offlineReply(key, owner);
  if (key === 'reply_failure') return replyFailure(key, owner);
  if (key === 'concurrent_guard') return concurrentGuard(key, owner);
  if (key === 'draft_lifecycle') {
    if (recreator === undefined) throw new Error('page recreator is required');
    return draftLifecycle(key, owner, recreator);
  }
  if (key === 'detail_affordances') return detailAffordances(key, owner);
  throw new Error(`unknown semantic case: ${key}`);
}

async function listSuccess(key: string, owner: UnifiedSupportPageOwner): Promise<SemanticPayload> {
  const rows: ListRow[] = owner.store().conversations.map(conversation => {
    const row: ListRow = conversation.status === 'bot' ?
      { id: conversation.id, presentation: 'bot' } :
      { id: conversation.id, presentation: 'ticket', status: conversation.status };
    return row;
  });
  const serviceEffect: NamedEffect = effectLog.length > 0 ? effectLog[0] as NamedEffect : { name: 'none' };
  const observed: ListObserved = { surface: owner.store().surface, entryLabel: owner.store().entryLabel, loading: owner.store().loading,
    error: null, rows: rows, serviceEffect: serviceEffect };
  const before: RowsSnapshot = { rows: [] };
  return payload(key, owner, before, observed, observed, effectLog.slice(), [
    { invariant: 'bot and Happiness Engineer conversations share one ordered list', passed: rows.length === 2 && rows[0].id === 1 && rows[1].id === 2, evidence: JSON.stringify(rows) },
    { invariant: 'the retired separate entries are not rendered', passed: owner.store().surface === 'unified_support', evidence: owner.store().surface }
  ], ['UnifiedSupportPageOwner.aboutToAppear', 'UnifiedSupportController.open', 'UnifiedSupportRepository.loadConversations']);
}

async function listFailure(key: string, owner: UnifiedSupportPageOwner): Promise<SemanticPayload> {
  const observed: ListFailureObserved = { surface: owner.store().surface, loading: owner.store().loading, error: owner.store().error,
    emptyState: false, rows: [] };
  const before: RowsSnapshot = { rows: [] };
  return payload(key, owner, before, observed, observed, effectLog.slice(), [
    { invariant: 'a failed request is not represented as an empty successful list', passed: owner.store().error === 'general', evidence: owner.store().error },
    { invariant: 'the repository body reaches the controlled service leaf', passed: owner.store().requestCount === 1, evidence: `${owner.store().requestCount} request` }
  ], ['UnifiedSupportPageOwner.aboutToAppear', 'UnifiedSupportController.open', 'UnifiedSupportRepository.loadConversations']);
}

async function listRetry(key: string, owner: UnifiedSupportPageOwner): Promise<SemanticPayload> {
  const before: SurfaceSnapshot = { surface: owner.store().surface };
  await owner.retryConversations();
  const rows: ListRow[] = owner.store().conversations.map(conversation => {
    const row: ListRow = { id: conversation.id, presentation: 'bot' };
    return row;
  });
  const observed: ListRetryObserved = { surface: owner.store().surface, error: null, rows: rows, requestCount: owner.store().requestCount };
  return payload(key, owner, before, observed, observed, effectLog.slice(), [
    { invariant: 'retry uses the same unified repository path', passed: owner.store().requestCount === 2, evidence: `${owner.store().requestCount} requests` },
    { invariant: 'recovery replaces the error state without recreating separate support flows', passed: owner.store().error === '' && owner.store().surface === 'unified_support', evidence: owner.store().surface }
  ], ['UnifiedSupportPageOwner.retryConversations', 'UnifiedSupportController.retry', 'UnifiedSupportController.open', 'UnifiedSupportRepository.loadConversations']);
}

async function newBotSuccess(key: string, owner: UnifiedSupportPageOwner): Promise<SemanticPayload> {
  const before: SurfaceSnapshot = { surface: owner.store().surface };
  owner.createBotConversation();
  owner.updateDraft('How do I publish?');
  const effectStart = effectLog.length;
  await owner.sendReply('How do I publish?');
  const selected = owner.store().selected === undefined ? emptyConversation() : owner.store().selected as SupportConversation;
  const messages: MessageObserved[] = selected.messages.map(message => {
    const item: MessageObserved = { author: message.author, text: message.text };
    return item;
  });
  const effects = eventEffects(effectStart);
  const selectedObserved: SelectedBot = { id: selected.id, type: selected.status, messages: messages };
  const serviceEffect: CreateEffect = effects.length > 0 ? effects[0] as CreateEffect :
    { name: 'none', botId: '', message: '' };
  const observed: NewBotObserved = { surface: owner.store().surface,
    selectedConversation: selectedObserved,
    listFirstId: owner.store().conversations.length > 0 ? owner.store().conversations[0].id : 0,
    draft: owner.store().replyForm.message,
    sending: owner.store().sending, serviceEffect: serviceEffect };
  return payload(key, owner, before, observed, observed, effects, [
    { invariant: 'the local user question remains exactly once', passed: messages.filter(message => message.author === 'user').length === 1, evidence: JSON.stringify(messages) },
    { invariant: 'the application-owned create mapping executes before the service leaf response is consumed',
      passed: activeService.createCalls.length > 0 && activeService.createCalls[0].botId === 'jetpack-workflow-chat_mobile_support',
      evidence: activeService.createCalls.length > 0 ? activeService.createCalls[0].botId : 'no create call' }
  ], ['UnifiedSupportPageOwner.createBotConversation', 'UnifiedSupportPageOwner.sendReply', 'UnifiedSupportController.createNewBotConversation', 'UnifiedSupportController.sendReply', 'UnifiedSupportRepository.createBot']);
}

async function replySuccess(key: string, owner: UnifiedSupportPageOwner): Promise<SemanticPayload> {
  await owner.openConversation(5);
  owner.updateDraft('Please help');
  owner.updateAttachments(['image-a']);
  owner.setIncludeAppLogs(true);
  const before: RowsSnapshot = { rows: messageIds(owner) };
  const effectStart = effectLog.length;
  const send = owner.sendReply('Please help');
  await allowAsyncProgress();
  const draftClearedWhilePending = owner.store().sending && owner.store().replyForm.message === '';
  activeService.releaseReply();
  await send;
  const effects = eventEffects(effectStart);
  const observed: ReplyObserved = { surface: owner.store().surface, selectedMessages: messageIds(owner),
    listConversationId: owner.store().conversations.length > 0 ? owner.store().conversations[0].id : 0,
    draft: owner.store().replyForm.message,
    attachments: owner.store().replyForm.attachments.slice(), includeAppLogs: owner.store().replyForm.includeAppLogs,
    sending: owner.store().sending, effects: effects };
  return payload(key, owner, before, observed, observed, effects, [
    { invariant: 'the input is cleared while the request is pending', passed: draftClearedWhilePending, evidence: `pending=${draftClearedWhilePending}` },
    { invariant: 'temporary files are removed after completion', passed: activeAttachments.removed.length === 1, evidence: JSON.stringify(activeAttachments.removed) },
    { invariant: 'the list and selected detail refer to the same conversation identity',
      passed: owner.store().selected !== undefined && owner.store().conversations.length > 0 &&
        owner.store().selected?.id === owner.store().conversations[0].id,
      evidence: `${owner.store().selected?.id}` }
  ], ['UnifiedSupportPageOwner.openConversation', 'UnifiedSupportPageOwner.sendReply', 'UnifiedSupportController.sendReply', 'UnifiedSupportRepository.reply']);
}

async function offlineReply(key: string, owner: UnifiedSupportPageOwner): Promise<SemanticPayload> {
  await owner.openConversation(6);
  owner.updateDraft('Still there?');
  const before: RowsSnapshot = { rows: messageIds(owner) };
  await owner.sendReply('Still there?');
  const observed: OfflineObserved = { surface: owner.store().surface, selectedMessages: messageIds(owner), draft: owner.store().replyForm.message,
    error: owner.store().error, sending: owner.store().sending, repositoryCallCount: activeService.replyCalls.length };
  return payload(key, owner, before, observed, observed, [], [
    { invariant: 'offline detection occurs before optimistic insertion', passed: messageIds(owner).length === 1, evidence: JSON.stringify(messageIds(owner)) },
    { invariant: "the user's draft remains retryable", passed: owner.store().replyForm.message === 'Still there?', evidence: owner.store().replyForm.message }
  ], ['UnifiedSupportPageOwner.openConversation', 'UnifiedSupportPageOwner.sendReply', 'UnifiedSupportController.sendReply']);
}

async function replyFailure(key: string, owner: UnifiedSupportPageOwner): Promise<SemanticPayload> {
  await owner.openConversation(7);
  owner.updateDraft('Retry me');
  owner.updateAttachments(['image-b']);
  const before: RowsSnapshot = { rows: messageIds(owner) };
  const effectStart = effectLog.length;
  const send = owner.sendReply('Retry me');
  await allowAsyncProgress();
  const pendingSelected = owner.store().selected === undefined ? emptyConversation() :
    owner.store().selected as SupportConversation;
  const pending: PendingFrame = { draft: owner.store().replyForm.message,
    messageIds: pendingSelected.messages.map(message => message.id < 0 ? 'optimistic' : message.id) };
  activeService.releaseReply();
  await send;
  const settled: SettledFrame = { draft: owner.store().replyForm.message, messageIds: messageIds(owner), error: owner.store().error,
    sending: owner.store().sending };
  const effects = eventEffects(effectStart);
  const observed: ReplyFailureObserved = { surface: owner.store().surface, pending: pending, settled: settled, effects: effects };
  return payload(key, owner, before, observed, observed, effects, [
    { invariant: 'only the optimistic message is rolled back', passed: settled.messageIds.length === 1 && settled.messageIds[0] === 30, evidence: JSON.stringify(settled.messageIds) },
    { invariant: 'pre-existing messages remain unchanged', passed: settled.messageIds[0] === 30, evidence: JSON.stringify(settled.messageIds) },
    { invariant: 'temporary files are removed on failure', passed: activeAttachments.removed.length === 1, evidence: JSON.stringify(activeAttachments.removed) }
  ], ['UnifiedSupportPageOwner.openConversation', 'UnifiedSupportPageOwner.sendReply', 'UnifiedSupportController.sendReply', 'UnifiedSupportRepository.reply']);
}

async function concurrentGuard(key: string, owner: UnifiedSupportPageOwner): Promise<SemanticPayload> {
  await owner.openConversation(8);
  const before: SurfaceSnapshot = { surface: owner.store().surface };
  const first = owner.sendReply('first');
  await allowAsyncProgress();
  await owner.sendReply('second');
  const sent = activeService.replyCalls.map(call => call.message);
  const observed: ConcurrentObserved = { surface: owner.store().surface, sendingWhileHeld: owner.store().sending,
    repositoryCallCountWhileHeld: activeService.replyCalls.length, sentMessages: sent };
  activeService.releaseReply();
  await first;
  return payload(key, owner, before, observed, observed, [], [
    { invariant: 'the sending guard is set before asynchronous work begins', passed: observed.sendingWhileHeld, evidence: `${observed.sendingWhileHeld}` },
    { invariant: 'the second event cannot reach the repository or external leaf', passed: activeService.replyCalls.length === 1 && sent[0] === 'first', evidence: JSON.stringify(sent) }
  ], ['UnifiedSupportPageOwner.openConversation', 'UnifiedSupportPageOwner.sendReply', 'UnifiedSupportController.sendReply']);
}

function draftFrame(owner: UnifiedSupportPageOwner): DraftFrame {
  const selected = owner.store().selected === undefined ? emptyConversation() :
    owner.store().selected as SupportConversation;
  const frame: DraftFrame = { selectedConversationId: selected.id, message: owner.store().replyForm.message,
    attachments: owner.store().replyForm.attachments.slice(), includeAppLogs: owner.store().replyForm.includeAppLogs,
    sheetVisible: owner.store().replyForm.sheetVisible };
  return frame;
}

async function draftLifecycle(key: string, owner: UnifiedSupportPageOwner, recreator: PageRecreator): Promise<SemanticPayload> {
  await owner.openConversation(9);
  owner.updateDraft('draft-a');
  owner.updateAttachments(['a']);
  owner.setIncludeAppLogs(true);
  owner.setReplySheetVisible(true);
  const before: SurfaceSnapshot = { surface: owner.store().surface };
  await recreator.recreate();
  const recreatedOwner = await UnifiedSupportPageRuntime.waitForOwnerAfter(owner.ownerId);
  await recreatedOwner.waitUntilReady();
  const afterRecreate = draftFrame(recreatedOwner);
  await recreatedOwner.openConversation(10);
  const afterSwitch = draftFrame(recreatedOwner);
  const observed: DraftObserved = { surface: recreatedOwner.store().surface, afterRecreate: afterRecreate, afterSwitch: afterSwitch };
  return payload(key, recreatedOwner, before, observed, observed, [], [
    { invariant: 'page recreation reuses the production view model', passed: owner.ownerId !== recreatedOwner.ownerId && owner.controllerId === recreatedOwner.controllerId &&
      JSON.stringify(afterRecreate).indexOf('draft-a') >= 0, evidence: `${owner.ownerId}->${recreatedOwner.ownerId},${owner.controllerId}` },
    { invariant: 'draft state from conversation 9 never appears in conversation 10', passed: JSON.stringify(afterSwitch).indexOf('draft-a') < 0 &&
      recreatedOwner.store().selected !== undefined && (recreatedOwner.store().selected as SupportConversation).id === 10,
      evidence: JSON.stringify(afterSwitch) }
  ], ['EntryAbility.recreatePage', 'UnifiedSupportPageRuntime.createOwner', 'UnifiedSupportPageOwner.openConversation',
    'UnifiedSupportController.openConversation', 'ReplyFormState.clear'], owner);
}

async function detailAffordances(key: string, owner: UnifiedSupportPageOwner): Promise<SemanticPayload> {
  const before: SurfaceSnapshot = { surface: owner.store().surface };
  const rendered: RenderedAffordance[] = owner.renderedAffordances();
  const botSource = rendered.length > 0 ? rendered[0] : emptyAffordance();
  const openSource = rendered.length > 1 ? rendered[1] : emptyAffordance();
  const closedSource = rendered.length > 2 ? rendered[2] : emptyAffordance();
  const bot: AffordanceObserved = { id: botSource.id, composer: botSource.composer,
    typingIndicatorSupported: botSource.typingIndicatorSupported };
  const open: AffordanceObserved = { id: openSource.id, composer: openSource.composer,
    closedBanner: openSource.closedBanner };
  const closed: AffordanceObserved = { id: closedSource.id, composer: closedSource.composer,
    closedBanner: closedSource.closedBanner };
  const observed: DetailObserved = { surface: owner.store().surface, affordances: [bot, open, closed] };
  return payload(key, owner, before, observed, observed, [], [
    { invariant: 'affordances derive from status and reply capability',
      passed: rendered.length > 1 && rendered[0].composer === 'inline_chat' && rendered[1].composer === 'reply_sheet_button',
      evidence: JSON.stringify(rendered) },
    { invariant: 'closed tickets cannot dispatch replies',
      passed: rendered.length > 2 && rendered[2].composer === 'none' && rendered[2].closedBanner,
      evidence: rendered.length > 2 ? JSON.stringify(rendered[2]) : 'no closed-ticket affordance' }
  ], ['UnifiedSupportPageOwner.renderedAffordances', 'UnifiedSupportController.detailState']);
}
