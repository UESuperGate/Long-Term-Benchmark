import { HybridSearchState, SearchHttpLeaf } from './HybridSearchModels';

interface SettledSearch {
  ok: boolean;
  values: string[];
}

export class HybridSearchViewModel {
  state: HybridSearchState = {
    phase: 'idle',
    lexicalTitles: [],
    semanticTitles: [],
    retryAvailable: false
  };
  private query: string = '';
  private language: string = '';
  private http: SearchHttpLeaf;

  constructor(http: SearchHttpLeaf) {
    this.http = http;
  }

  async search(query: string, language: string): Promise<HybridSearchState> {
    this.query = query;
    this.language = language;
    this.state = {
      phase: 'loading',
      lexicalTitles: [],
      semanticTitles: [],
      retryAvailable: false
    };
    if (query.length === 0 || language.length === 0) {
      this.state.phase = 'success';
      return this.state;
    }

    const lexicalPromise = this.lexicalBody(query, language)
      .then((values: string[]) => ({ ok: true, values: values } as SettledSearch))
      .catch(() => ({ ok: false, values: [] } as SettledSearch));
    const semanticPromise = this.http.semantic(query, language)
      .then((values: string[]) => ({ ok: true, values: values } as SettledSearch))
      .catch(() => ({ ok: false, values: [] } as SettledSearch));
    const outcomes = await Promise.all([lexicalPromise, semanticPromise]);
    if (!outcomes[0].ok && !outcomes[1].ok) {
      this.state = {
        phase: 'error',
        lexicalTitles: [],
        semanticTitles: [],
        retryAvailable: true
      };
      return this.state;
    }
    this.state = {
      phase: 'success',
      lexicalTitles: outcomes[0].values,
      semanticTitles: outcomes[1].values,
      notice: outcomes[0].values.length === 0 ? 'lexical_empty' :
        outcomes[1].values.length === 0 ? 'semantic_empty' : undefined,
      retryAvailable: false
    };
    return this.state;
  }

  retry(): Promise<HybridSearchState> {
    return this.search(this.query, this.language);
  }

  private async lexicalBody(query: string, language: string): Promise<string[]> {
    const values = await this.http.prefix(query, language);
    if (values.length < 3) {
      values.push(...await this.http.fullText(query, language));
    }
    return Array.from(new Set(values));
  }
}
