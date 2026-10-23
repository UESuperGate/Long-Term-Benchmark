export interface SupportMessage { id: number; author: string; text: string; }
export interface SupportConversation {
  id: number; title: string; status: string; canAcceptReply: boolean; messages: SupportMessage[];
}
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

export class ReplyFormState {
  message: string = '';
  attachments: string[] = [];
  includeAppLogs: boolean = false;
  sheetVisible: boolean = false;
}

export class UnifiedSupportStore {
  surface: string = 'separate_support_entries';
  entryLabel: string = '';
  conversations: SupportConversation[] = [];
  selected?: SupportConversation;
  replyForm: ReplyFormState = new ReplyFormState();
  loading: boolean = false;
  sending: boolean = false;
  error: string = '';
  requestCount: number = 0;
}

export class LegacySupportStore extends UnifiedSupportStore {
  entries: string[] = ['Ask the Bots', 'Ask the Happiness Engineers'];
}

export class LegacySupportController {
  readonly store: LegacySupportStore = new LegacySupportStore();
  open(): void { this.store.surface = 'separate_support_entries'; }
}
