import {
  AttachmentLeaf,
  LegacySupportController,
  LegacySupportStore,
  NetworkLeaf,
  SupportServiceLeaf,
  UnifiedSupportStore
} from '../features/UnifiedSupportController';

export interface RenderedAffordance {
  id: number;
  composer: string;
  typingIndicatorSupported: boolean;
  closedBanner: boolean;
}

export class LegacySupportPageOwner {
  readonly ownerId: string;
  readonly controllerId: string;
  readonly controller: LegacySupportController = new LegacySupportController();

  constructor(ownerId: string, controllerId: string) {
    this.ownerId = ownerId;
    this.controllerId = controllerId;
  }

  aboutToAppear(): void { this.controller.open(); }
  store(): LegacySupportStore { return this.controller.store; }
  openSupport(): void { this.controller.open(); }
}

export class LegacySupportPageRuntime {
  private static current?: LegacySupportPageOwner;
  private static generation: number = 0;

  static reset(): void {
    LegacySupportPageRuntime.current = undefined;
    LegacySupportPageRuntime.generation = 0;
  }

  static createOwner(): LegacySupportPageOwner {
    LegacySupportPageRuntime.generation += 1;
    const suffix = LegacySupportPageRuntime.generation.toString();
    const owner = new LegacySupportPageOwner(`legacy-support-owner-${suffix}`, `legacy-support-controller-${suffix}`);
    LegacySupportPageRuntime.current = owner;
    UnifiedSupportPageRuntime.attachLegacy(owner);
    return owner;
  }

  static currentOwner(): LegacySupportPageOwner {
    const owner = LegacySupportPageRuntime.current;
    if (owner === undefined) throw new Error('Legacy support page owner is not mounted');
    return owner;
  }

  static async waitForOwner(attempt: number = 0): Promise<LegacySupportPageOwner> {
    const owner = LegacySupportPageRuntime.current;
    if (owner !== undefined) return owner;
    if (attempt >= 80) throw new Error('Legacy support page owner mount timed out');
    await new Promise<void>((resolve) => { setTimeout(() => resolve(), 25); });
    return LegacySupportPageRuntime.waitForOwner(attempt + 1);
  }

  static async waitForOwnerAfter(previousOwnerId: string, attempt: number = 0): Promise<LegacySupportPageOwner> {
    const owner = LegacySupportPageRuntime.current;
    if (owner !== undefined && owner.ownerId !== previousOwnerId) return owner;
    if (attempt >= 80) throw new Error('Legacy support replacement page owner mount timed out');
    await new Promise<void>((resolve) => { setTimeout(() => resolve(), 25); });
    return LegacySupportPageRuntime.waitForOwnerAfter(previousOwnerId, attempt + 1);
  }

  static ownerGeneration(): number { return LegacySupportPageRuntime.generation; }
}

export class UnifiedSupportPageOwner {
  readonly ownerId: string;
  readonly controllerId: string;
  private legacy: LegacySupportPageOwner;

  constructor(legacy: LegacySupportPageOwner) {
    this.legacy = legacy;
    this.ownerId = legacy.ownerId;
    this.controllerId = legacy.controllerId;
  }

  waitUntilReady(): Promise<void> { return Promise.resolve(); }
  store(): UnifiedSupportStore { return this.legacy.store(); }
  retryConversations(): Promise<boolean> { return Promise.resolve(false); }
  openConversation(_id: number): Promise<boolean> { return Promise.resolve(false); }
  createBotConversation(): void {}
  updateDraft(_message: string): void {}
  updateAttachments(_values: string[]): void {}
  setIncludeAppLogs(_value: boolean): void {}
  setReplySheetVisible(_value: boolean): void {}
  sendReply(_message: string): Promise<boolean> { return Promise.resolve(false); }
  renderedAffordances(): RenderedAffordance[] { return []; }
}

export class UnifiedSupportPageRuntime {
  private static current?: UnifiedSupportPageOwner;
  private static generation: number = 0;

  static configure(_service: SupportServiceLeaf, _network: NetworkLeaf, _attachments: AttachmentLeaf): void {
    UnifiedSupportPageRuntime.current = undefined;
    UnifiedSupportPageRuntime.generation = 0;
  }

  static attachLegacy(owner: LegacySupportPageOwner): void {
    UnifiedSupportPageRuntime.current = new UnifiedSupportPageOwner(owner);
    UnifiedSupportPageRuntime.generation = LegacySupportPageRuntime.ownerGeneration();
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
