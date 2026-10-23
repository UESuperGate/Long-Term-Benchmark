import { http } from '@kit.NetworkKit';
import { SearchHttpLeaf } from './HybridSearchModels';

export interface SearchJsonTransport {
  getJson(url: string): Promise<Record<string, Object>>;
}

class NetworkSearchJsonTransport implements SearchJsonTransport {
  async getJson(url: string): Promise<Record<string, Object>> {
    const client = http.createHttp();
    try {
      const response = await client.request(url, {
        method: http.RequestMethod.GET,
        expectDataType: http.HttpDataType.STRING
      });
      if (response.responseCode < 200 || response.responseCode >= 300) {
        throw new Error('HTTP ' + response.responseCode);
      }
      return JSON.parse(String(response.result)) as Record<string, Object>;
    } finally {
      client.destroy();
    }
  }
}

export class HttpSearchLeaf implements SearchHttpLeaf {
  private transport: SearchJsonTransport;

  constructor(transport: SearchJsonTransport = new NetworkSearchJsonTransport()) {
    this.transport = transport;
  }

  async prefix(query: string, language: string): Promise<string[]> {
    return this.mediaWiki(query, language, 'prefix');
  }

  async fullText(query: string, language: string): Promise<string[]> {
    return this.mediaWiki(query, language, 'text');
  }

  async semantic(query: string, language: string): Promise<string[]> {
    const url = 'https://semantic-search.wmcloud.org/api/search?query=' +
      encodeURIComponent(query) + '&k=3&table=' + encodeURIComponent(language + 'wiki_sections') +
      '&include_text=true';
    const body = await this.transport.getJson(url);
    const values = body['semantic_search_results'] as Array<Record<string, Object>>;
    return (values ?? []).map((item: Record<string, Object>) => {
      const title = String(item['page_title'] ?? '');
      const section = String(item['section_header'] ?? '');
      return section.length > 0 ? title + '#' + section.replaceAll(' ', '_') : title;
    });
  }

  private async mediaWiki(query: string, language: string, mode: string): Promise<string[]> {
    const url = 'https://' + language + '.wikipedia.org/w/api.php?action=query&format=json' +
      '&generator=search&gsrnamespace=0&gsrlimit=3&gsrwhat=' + mode +
      '&gsrsearch=' + encodeURIComponent(query);
    const body = await this.transport.getJson(url);
    const queryBody = body['query'] as Record<string, Object>;
    if (!queryBody) {
      return [];
    }
    const pages = queryBody['pages'] as Record<string, Record<string, Object>>;
    return Object.values(pages)
      .sort((left: Record<string, Object>, right: Record<string, Object>) =>
        Number(left['index'] ?? 0) - Number(right['index'] ?? 0))
      .map((page: Record<string, Object>) => String(page['title'] ?? '').replaceAll(' ', '_'));
  }

}
