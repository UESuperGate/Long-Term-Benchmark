export interface SearchHttpLeaf {
  prefix(query: string, language: string): Promise<string[]>;
  fullText(query: string, language: string): Promise<string[]>;
  semantic(query: string, language: string): Promise<string[]>;
}

export interface FeedbackPayload {
  elementId: string;
  query: string;
  position: number;
  title: string;
}

export interface FeedbackLeaf {
  submit(payload: FeedbackPayload): Promise<void>;
}

export interface StandardSearchLeaf {
  request(query: string): void;
}

export interface HybridSearchState {
  phase: string;
  lexicalTitles: string[];
  semanticTitles: string[];
  notice?: string;
  retryAvailable: boolean;
}

export interface HybridSearchSettings {
  language: string;
  experimentGroup: string;
  remoteEnabled: boolean;
  hybridEnabled: boolean;
  query: string;
}
