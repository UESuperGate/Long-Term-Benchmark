import { common } from '@kit.AbilityKit';
import { preferences } from '@kit.ArkData';

export type JsonMap = Record<string, Object>;
function clone(value: JsonMap): JsonMap { return JSON.parse(JSON.stringify(value)) as JsonMap; }
export function jsonMap(keys: string[] = [], values: Object[] = []): JsonMap {
  const value = JSON.parse('{}') as JsonMap;
  for (let index = 0; index < keys.length; index++) value[keys[index]] = values[index];
  return value;
}

/** Production-compatible model of the v8.28.4 local-only waveform behavior. */
export class WaveformPageOwner {
  private input: JsonMap;
  private state: JsonMap = jsonMap();
  private effects: JsonMap[] = [];
  private calls: string[] = [];
  private record?: JsonMap;
  private store: preferences.Preferences;

  private constructor(store: preferences.Preferences, input: JsonMap) { this.store = store; this.input = clone(input); }

  static async create(context: common.UIAbilityContext, input: JsonMap): Promise<WaveformPageOwner> {
    const store = await preferences.getPreferences(context, 'voice_waveform');
    const owner = new WaveformPageOwner(store, input);
    await owner.mount(input);
    return owner;
  }

  async mount(input: JsonMap): Promise<void> {
    this.input = clone(input); this.state = jsonMap(); this.effects = []; this.calls = ['WaveformPageOwner.mount']; this.record = undefined;
    await this.store.clear();
    const attachment = this.map(input['attachment']);
    if (Object.keys(attachment).length > 0) {
      this.state['attachmentId'] = this.text(attachment, 'id');
      const stored = this.map(attachment['storedWaveform']);
      if (Object.keys(stored).length > 0) await this.persistRecord(this.recordFromStored(stored));
    }
    await this.store.flush();
  }

  async generateWaveform(samples: number[], durationUs: number): Promise<void> {
    this.call('WaveformPageOwner.generateWaveform');
    this.effect('persistGenerationPlaceholder', this.attachmentId());
    await this.persistRecord(this.emptyRecord());
    this.effect('decodeAudio', this.attachmentId());
    const record = this.generatedRecord(samples, durationUs);
    await this.persistRecord(record);
    this.effect('persistGeneratedWaveform', this.attachmentId());
    this.state['result'] = 'success'; this.state['storedWaveform'] = clone(record);
  }

  async startUploadGraph(): Promise<void> {
    this.call('WaveformPageOwner.startUploadGraph');
    const id = this.text(this.map(this.input['attachment']), 'id');
    this.effect('compressAttachment', id); this.effect('uploadAttachment', id);
    this.state['upload'] = jsonMap(['compression', 'waveformGeneration', 'upload'], ['complete', 'not_scheduled', 'complete']);
  }
  async releaseHeldWaveform(samples: number[], durationUs: number): Promise<void> { this.call('WaveformPageOwner.releaseHeldWaveform'); }

  async startMixedUploadGraph(): Promise<void> {
    this.call('WaveformPageOwner.startMixedUploadGraph');
    const uploads: JsonMap = jsonMap();
    this.maps(this.input['attachments']).forEach((attachment: JsonMap): void => {
      const id = this.text(attachment, 'id');
      this.effect('compressAttachment', id); this.effect('uploadAttachment', id);
      uploads[id] = jsonMap(['compression', 'waveformGeneration', 'upload'], ['complete', 'not_scheduled', 'complete']);
    });
    this.state['uploads'] = uploads;
  }
  async releaseMixedAudio(samples: number[], durationUs: number): Promise<void> { this.call('WaveformPageOwner.releaseMixedAudio'); }

  async serializeOutgoingPointer(): Promise<void> {
    this.call('WaveformPageOwner.serializeOutgoingPointer');
    const attachment = this.map(this.input['attachment']);
    this.state['pointer'] = jsonMap(['contentType', 'cdnKey', 'encryptionDigest'],
      [this.text(attachment, 'contentType'), this.text(attachment, 'cdnKey'), this.text(attachment, 'encryptionDigest')]);
    this.effect('buildAttachmentPointer', this.text(attachment, 'id'));
  }

  async validateIncomingEnvelope(): Promise<void> {
    this.call('WaveformPageOwner.validateIncomingEnvelope');
    this.state['validation'] = jsonMap(['accepted', 'reason'], [true, '']);
  }

  async importIncomingAttachment(): Promise<void> {
    this.call('WaveformPageOwner.importIncomingAttachment');
    const pointer = this.map(this.input['incomingAttachmentPointer']);
    this.state['persistedAttachment'] = jsonMap(['contentType'], [this.text(pointer, 'contentType')]);
    this.state['reloadedAttachment'] = jsonMap();
    this.effect('persistAttachment', this.text(pointer, 'cdnKey'));
  }

  async requestRenderableWaveform(samples: number[], durationUs: number): Promise<void> {
    this.call('WaveformPageOwner.requestRenderableWaveform');
    const attachment = this.map(this.input['attachment']);
    if (this.text(attachment, 'localMedia') !== 'readable') { this.state['result'] = 'error'; return; }
    if (this.record === undefined || this.num(this.record, 'barCount') === 0) {
      this.effect('generateWaveform', this.text(attachment, 'id'));
      const replacement = this.generatedRecord(samples, durationUs);
      await this.persistRecord(replacement);
      this.effect('persistGeneratedWaveform', this.text(attachment, 'id'));
      this.state['persistedReplacement'] = clone(replacement);
    }
    if (this.record === undefined) { this.state['result'] = 'error'; return; }
    this.state['result'] = 'success';
    this.state['renderWaveform'] = this.numbers(this.record['bytes']).map((value: number): number => value / 255);
    this.state['durationSeconds'] = this.num(this.record, 'durationSeconds');
  }

  async backupRestoreAndRender(): Promise<void> {
    this.call('WaveformPageOwner.backupRestoreAndRender');
    const attachment = this.map(this.input['attachment']);
    this.state['exportedFilePointer'] = jsonMap(['contentType'], [this.text(attachment, 'contentType')]);
    await this.store.clear(); this.record = undefined;
    this.state['restoredAttachment'] = jsonMap();
    this.state['renderAfterRestore'] = jsonMap(['result'], ['error']);
    this.effect('exportAttachment', this.text(attachment, 'id'));
    this.effect('restoreAttachment', this.text(attachment, 'id'));
  }

  currentState(): JsonMap { return clone(this.state); }
  currentEffects(): JsonMap[] { return JSON.parse(JSON.stringify(this.effects)) as JsonMap[]; }
  currentPersistence(): JsonMap { return this.record === undefined ? jsonMap() : jsonMap(['waveform'], [clone(this.record)]); }
  productionTrace(): string[] { return [...this.calls]; }
  async reopenedPersistence(): Promise<JsonMap> {
    const raw = await this.store.get('waveform', '');
    return typeof raw === 'string' && raw.length > 0 ? jsonMap(['waveform'], [JSON.parse(raw) as JsonMap]) : jsonMap();
  }

  private generatedRecord(samples: number[], durationUs: number): JsonMap {
    const peaks: number[] = []; let global = 0;
    for (let bar = 0; bar < 46; bar++) {
      const start = Math.floor(bar * samples.length / 46);
      const end = Math.min(samples.length, Math.max(start + 1, Math.floor((bar + 1) * samples.length / 46)));
      let sum = 0; for (let index = start; index < end; index++) sum += Math.abs(samples[index]);
      const peak = end > start ? sum / (end - start) : 0; peaks.push(peak); global = Math.max(global, peak);
    }
    const bars = peaks.map((peak: number): number => global === 0 ? 0 : Math.round(255 * peak / global));
    return jsonMap(['bytes', 'barCount', 'durationUs', 'durationSeconds'],
      [bars, bars.length, durationUs, durationUs / 1000000]);
  }

  private recordFromStored(stored: JsonMap): JsonMap {
    const bytes = this.waveformBytes(stored);
    const seconds = stored['durationSeconds'] !== undefined ? this.num(stored, 'durationSeconds') : this.num(stored, 'durationUs') / 1000000;
    return jsonMap(['bytes', 'barCount', 'durationSeconds', 'durationUs'],
      [bytes, bytes.length, seconds, Math.round(seconds * 1000000)]);
  }
  private waveformBytes(source: JsonMap): number[] {
    if (Array.isArray(source['bytes'])) return this.numbers(source['bytes']);
    const result: number[] = []; const segments = this.maps(source['segments']);
    segments.forEach((segment: JsonMap): void => { for (let index = 0; index < this.num(segment, 'count'); index++) result.push(this.num(segment, 'value')); });
    if (segments.length === 0) for (let index = 0; index < this.num(source, 'barCount'); index++) result.push(this.num(source, 'fill'));
    return result;
  }
  private emptyRecord(): JsonMap { return jsonMap(['bytes', 'barCount', 'durationUs', 'durationSeconds'], [[], 0, 0, 0]); }
  private async persistRecord(record: JsonMap): Promise<void> { this.record = clone(record); await this.store.put('waveform', JSON.stringify(this.record)); await this.store.flush(); }
  private map(value: Object | undefined): JsonMap { return value !== undefined && value !== null && !Array.isArray(value) ? value as JsonMap : jsonMap(); }
  private maps(value: Object | undefined): JsonMap[] { return Array.isArray(value) ? (value as Object[]).map((item: Object): JsonMap => this.map(item)) : []; }
  private numbers(value: Object | undefined): number[] { return Array.isArray(value) ? (value as Object[]).map((item: Object): number => Number(item)) : []; }
  private text(value: JsonMap, key: string): string { const item = value[key]; return typeof item === 'string' ? item : ''; }
  private num(value: JsonMap, key: string): number { const item = value[key]; return typeof item === 'number' ? item : 0; }
  private attachmentId(): string { return this.text(this.map(this.input['attachment']), 'id'); }
  private call(name: string): void { this.calls.push(name); }
  private effect(name: string, attachmentId: string): void { this.effects.push(jsonMap(['name', 'attachmentId'], [name, attachmentId])); }
}
