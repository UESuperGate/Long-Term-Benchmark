import {
  AttachmentLeaf,
  DemoAttachmentLeaf,
  DemoNetworkLeaf,
  DemoSupportService,
  DetailAffordance,
  NetworkLeaf,
  SupportConversation,
  SupportServiceLeaf,
  UnifiedSupportController,
  UnifiedSupportStore
} from '../features/UnifiedSupportController';

export interface RenderedAffordance {
  id: number;
  composer: string;
  typingIndicatorSupported: boolean;
  closedBanner: boolean;
}

export class UnifiedSupportPageOwner {
  readonly ownerId: string;
  readonly controllerId: string;
  readonly controller: UnifiedSupportController;
  private lifecycle: Promise<boolean> = Promise.resolve(true);

  constructor(ownerId: string, controllerId: string, controller: UnifiedSupportController) {
    this.ownerId = ownerId;
    this.controllerId = controllerId;
    this.controller = controller;
  }

  aboutToAppear(): void { this.lifecycle = this.controller.open(); }
  async waitUntilReady(): Promise<void> { await this.lifecycle; }
  store(): UnifiedSupportStore { return this.controller.store; }
  retryConversations(): Promise<boolean> { return this.controller.retry(); }
  openConversation(id: number): Promise<boolean> { return this.controller.openConversation(id); }
  createBotConversation(): void { this.controller.createNewBotConversation(); }
  updateDraft(message: string): void { this.controller.updateDraft(message); }
  updateAttachments(values: string[]): void { this.controller.updateAttachments(values); }
  setIncludeAppLogs(value: boolean): void { this.controller.setIncludeAppLogs(value); }
  setReplySheetVisible(value: boolean): void { this.controller.setReplySheetVisible(value); }
  sendReply(message: string): Promise<boolean> { return this.controller.sendReply(message); }

  renderedAffordances(): RenderedAffordance[] {
    return this.controller.store.conversations.map((conversation: SupportConversation) => {
      const state: DetailAffordance = this.controller.detailState(conversation);
      const rendered: RenderedAffordance = {
        id: conversation.id,
        composer: state.composer,
        typingIndicatorSupported: state.typingIndicatorSupported,
        closedBanner: state.closedBanner
      };
      return rendered;
    });
  }
}

export class UnifiedSupportPageRuntime {
  private static service: SupportServiceLeaf = new DemoSupportService();
  private static network: NetworkLeaf = new DemoNetworkLeaf();
  private static attachments: AttachmentLeaf = new DemoAttachmentLeaf();
  private static retainedController?: UnifiedSupportController;
  private static retainedControllerId: string = 'support-controller-1';
  private static current?: UnifiedSupportPageOwner;
  private static generation: number = 0;

  static configure(service: SupportServiceLeaf, network: NetworkLeaf, attachments: AttachmentLeaf): void {
    UnifiedSupportPageRuntime.service = service;
    UnifiedSupportPageRuntime.network = network;
    UnifiedSupportPageRuntime.attachments = attachments;
    UnifiedSupportPageRuntime.retainedController = undefined;
    UnifiedSupportPageRuntime.current = undefined;
    UnifiedSupportPageRuntime.generation = 0;
    UnifiedSupportPageRuntime.retainedControllerId = 'support-controller-1';
  }

  static createOwner(): UnifiedSupportPageOwner {
    if (UnifiedSupportPageRuntime.retainedController === undefined) {
      UnifiedSupportPageRuntime.retainedController = new UnifiedSupportController(UnifiedSupportPageRuntime.service,
        UnifiedSupportPageRuntime.network, UnifiedSupportPageRuntime.attachments);
    }
    UnifiedSupportPageRuntime.generation += 1;
    const owner = new UnifiedSupportPageOwner(`support-owner-${UnifiedSupportPageRuntime.generation}`,
      UnifiedSupportPageRuntime.retainedControllerId, UnifiedSupportPageRuntime.retainedController);
    UnifiedSupportPageRuntime.current = owner;
    return owner;
  }

  static currentOwner(): UnifiedSupportPageOwner {
    const owner = UnifiedSupportPageRuntime.current;
    if (owner === undefined) throw new Error('Unified Support page owner is not mounted');
    return owner;
  }

  static async waitForOwner(attempt: number = 0): Promise<UnifiedSupportPageOwner> {
    const owner = UnifiedSupportPageRuntime.current;
    if (owner !== undefined) return owner;
    if (attempt >= 80) throw new Error('Unified Support page owner mount timed out');
    await new Promise<void>((resolve) => { setTimeout(() => resolve(), 25); });
    return UnifiedSupportPageRuntime.waitForOwner(attempt + 1);
  }

  static async waitForOwnerAfter(previousOwnerId: string, attempt: number = 0): Promise<UnifiedSupportPageOwner> {
    const owner = UnifiedSupportPageRuntime.current;
    if (owner !== undefined && owner.ownerId !== previousOwnerId) return owner;
    if (attempt >= 80) throw new Error('Unified Support replacement page owner mount timed out');
    await new Promise<void>((resolve) => { setTimeout(() => resolve(), 25); });
    return UnifiedSupportPageRuntime.waitForOwnerAfter(previousOwnerId, attempt + 1);
  }

  static ownerGeneration(): number { return UnifiedSupportPageRuntime.generation; }
}
