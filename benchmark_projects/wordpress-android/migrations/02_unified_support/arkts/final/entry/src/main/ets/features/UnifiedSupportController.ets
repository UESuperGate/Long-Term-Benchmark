export interface SupportMessage { id: number; author: string; text: string; }
export interface SupportConversation { id: number; title: string; status: string; canAcceptReply: boolean; messages: SupportMessage[]; }

export interface SupportServiceLeaf {
  loadConversations(): Promise<SupportConversation[]>;
  loadConversation(id: number): Promise<SupportConversation>;
  createBotConversation(botId: string, message: string): Promise<SupportConversation>;
  reply(id: number, message: string, attachments: string[], logIds: string[]): Promise<SupportConversation>;
}

export interface NetworkLeaf { online(): boolean; }
export interface AttachmentLeaf {
  uploadEncryptedLogs(): Promise<string[]>;
  createTempFiles(inputs: string[]): Promise<string[]>;
  removeTempFiles(paths: string[]): Promise<void>;
}

export class DemoSupportService implements SupportServiceLeaf {
  async loadConversations(): Promise<SupportConversation[]> {
    return [
      { id: 1, title: 'Publishing help', status: 'bot', canAcceptReply: true, messages: [] },
      { id: 2, title: 'Account ticket', status: 'open', canAcceptReply: true, messages: [] }
    ];
  }
  async loadConversation(id: number): Promise<SupportConversation> {
    return { id: id, title: id === 1 ? 'Publishing help' : 'Account ticket', status: id === 1 ? 'bot' : 'open', canAcceptReply: true, messages: [] };
  }
  async createBotConversation(_botId: string, message: string): Promise<SupportConversation> {
    return { id: 44, title: '', status: 'bot', canAcceptReply: true, messages: [{ id: 101, author: 'bot', text: `Reply to ${message}` }] };
  }
  async reply(id: number, message: string, _attachments: string[], _logIds: string[]): Promise<SupportConversation> {
    return { id: id, title: 'Updated conversation', status: 'open', canAcceptReply: true, messages: [{ id: 201, author: 'user', text: message }] };
  }
}

export class DemoNetworkLeaf implements NetworkLeaf { online(): boolean { return true; } }
export class DemoAttachmentLeaf implements AttachmentLeaf {
  async uploadEncryptedLogs(): Promise<string[]> { return []; }
  async createTempFiles(inputs: string[]): Promise<string[]> { return inputs.slice(); }
  async removeTempFiles(_paths: string[]): Promise<void> {}
}

export class ReplyFormState {
  message: string = '';
  attachments: string[] = [];
  includeAppLogs: boolean = false;
  sheetVisible: boolean = false;
  clear(): void { this.message = ''; this.attachments = []; this.includeAppLogs = false; this.sheetVisible = false; }
}

export class UnifiedSupportStore {
  surface: string = 'unified_support';
  entryLabel: string = 'get_help';
  conversations: SupportConversation[] = [];
  selected?: SupportConversation;
  replyForm: ReplyFormState = new ReplyFormState();
  loading: boolean = false;
  sending: boolean = false;
  error: string = '';
  requestCount: number = 0;
}

export class UnifiedSupportRepository {
  private service: SupportServiceLeaf;
  constructor(service: SupportServiceLeaf) { this.service = service; }
  loadConversations(): Promise<SupportConversation[]> { return this.service.loadConversations(); }
  loadConversation(id: number): Promise<SupportConversation> { return this.service.loadConversation(id); }
  createBot(message: string): Promise<SupportConversation> { return this.service.createBotConversation('jetpack-workflow-chat_mobile_support', message); }
  reply(id: number, message: string, attachments: string[], logIds: string[]): Promise<SupportConversation> {
    return this.service.reply(id, message, attachments, logIds);
  }
}

export interface DetailAffordance { composer: string; typingIndicatorSupported: boolean; closedBanner: boolean; }

export class UnifiedSupportController {
  readonly store: UnifiedSupportStore = new UnifiedSupportStore();
  private repository: UnifiedSupportRepository;
  private network: NetworkLeaf;
  private attachments: AttachmentLeaf;
  private optimisticId: number = -1;

  constructor(service: SupportServiceLeaf, network: NetworkLeaf = new DemoNetworkLeaf(), attachments: AttachmentLeaf = new DemoAttachmentLeaf()) {
    this.repository = new UnifiedSupportRepository(service);
    this.network = network;
    this.attachments = attachments;
  }

  async open(): Promise<boolean> {
    this.store.loading = true;
    this.store.requestCount += 1;
    try {
      this.store.conversations = await this.repository.loadConversations();
      this.store.error = '';
      return true;
    } catch (_error) {
      this.store.error = 'general';
      return false;
    } finally {
      this.store.loading = false;
    }
  }

  async retry(): Promise<boolean> { return this.open(); }

  async openConversation(id: number): Promise<boolean> {
    this.store.replyForm.clear();
    try {
      this.store.selected = await this.repository.loadConversation(id);
      this.store.error = '';
      return true;
    } catch (_error) {
      this.store.error = 'general';
      return false;
    }
  }

  createNewBotConversation(): void {
    this.store.replyForm.clear();
    this.store.selected = { id: 0, title: '', status: 'bot', canAcceptReply: true, messages: [] };
  }

  updateDraft(message: string): void { this.store.replyForm.message = message; }
  updateAttachments(values: string[]): void { this.store.replyForm.attachments = values.slice(); }
  setIncludeAppLogs(value: boolean): void { this.store.replyForm.includeAppLogs = value; }
  setReplySheetVisible(value: boolean): void { this.store.replyForm.sheetVisible = value; }

  detailState(conversation: SupportConversation): DetailAffordance {
    if (conversation.status.toLowerCase() === 'bot') return { composer: 'inline_chat', typingIndicatorSupported: true, closedBanner: false };
    if (conversation.canAcceptReply) return { composer: 'reply_sheet_button', typingIndicatorSupported: false, closedBanner: false };
    return { composer: 'none', typingIndicatorSupported: false, closedBanner: true };
  }

  detailAffordance(conversation: SupportConversation): string {
    const detail = this.detailState(conversation);
    return detail.closedBanner ? 'closed_banner' : detail.composer;
  }

  async sendReply(message: string): Promise<boolean> {
    const original = this.store.selected;
    if (original === undefined || !original.canAcceptReply || this.store.sending) return false;
    this.store.sending = true;
    if (!this.network.online()) {
      this.store.error = 'offline';
      this.store.sending = false;
      return false;
    }

    const attachmentInputs = this.store.replyForm.attachments.slice();
    const includeAppLogs = this.store.replyForm.includeAppLogs;
    const optimistic: SupportMessage = { id: this.optimisticId--, author: 'user', text: message };
    const optimisticMessages = original.messages.slice();
    optimisticMessages.push(optimistic);
    this.store.selected = {
      id: original.id, title: original.title, status: original.status,
      canAcceptReply: original.canAcceptReply, messages: optimisticMessages
    };
    this.store.replyForm.message = '';

    let temporaryPaths: string[] = [];
    try {
      if (original.id === 0) {
        const created = await this.repository.createBot(message);
        const combined = optimisticMessages.concat(created.messages);
        this.store.selected = {
          id: created.id, title: created.title, status: created.status,
          canAcceptReply: created.canAcceptReply, messages: combined
        };
        const summary: SupportConversation = {
          id: created.id, title: created.title, status: created.status,
          canAcceptReply: created.canAcceptReply, messages: []
        };
        this.store.conversations = [summary].concat(this.store.conversations);
      } else {
        const logIds = includeAppLogs ? await this.attachments.uploadEncryptedLogs() : [];
        temporaryPaths = await this.attachments.createTempFiles(attachmentInputs);
        const updated = await this.repository.reply(original.id, message, temporaryPaths, logIds);
        this.store.selected = updated;
        this.store.conversations = this.store.conversations.map((item: SupportConversation) => {
          if (item.id !== updated.id) return item;
          return { id: updated.id, title: updated.title, status: updated.status, canAcceptReply: updated.canAcceptReply, messages: [] };
        });
      }
      this.store.replyForm.clear();
      this.store.error = '';
      return true;
    } catch (_error) {
      const current = this.store.selected;
      if (current !== undefined && current.id === original.id) {
        const retained = current.messages.filter((item: SupportMessage) => item.id !== optimistic.id);
        this.store.selected = {
          id: current.id, title: current.title, status: current.status,
          canAcceptReply: current.canAcceptReply, messages: retained
        };
      }
      if (this.store.replyForm.message.length === 0) this.store.replyForm.message = message;
      this.store.error = 'general';
      return false;
    } finally {
      await this.attachments.removeTempFiles(temporaryPaths);
      this.store.sending = false;
    }
  }
}
