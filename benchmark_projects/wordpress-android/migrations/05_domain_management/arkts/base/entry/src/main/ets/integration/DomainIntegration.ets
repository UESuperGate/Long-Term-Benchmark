import { common } from '@kit.AbilityKit';

export interface DomainEffect {
  name: string;
  count?: number;
  query?: string;
  dispatchAtMs?: number;
  normalizedQuery?: string;
  mode?: string;
  domain?: string;
  productId?: number;
  supportsPrivacy?: boolean;
  url?: string;
}
export interface DomainBackend {
  fetchAllDomains(): Promise<Record<string, Object>>;
  searchForDomains(query: string): Promise<string[]>;
  createCart(mode: string, domain: string): Promise<Record<string, Object>>;
}
export interface DomainLeaf { emit(effect: DomainEffect): Promise<void>; }
export interface DomainInput { backend: DomainBackend; leaf: DomainLeaf; }
export interface DomainPageOwner {
  mount(context: common.UIAbilityContext, input: DomainInput, initialize: boolean): Promise<void>;
  invoke(name: string, event: Record<string, Object>): Promise<void>;
  currentState(): Record<string, Object>;
  ownerId(): string;
  controllerId(): string;
  storeSource(): string;
  featureAvailable(): boolean;
}
