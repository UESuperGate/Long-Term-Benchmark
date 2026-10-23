import { common } from '@kit.AbilityKit';
import { preferences } from '@kit.ArkData';

export type JsonMap = Record<string, Object>;

function clone(value: JsonMap): JsonMap {
  return JSON.parse(JSON.stringify(value)) as JsonMap;
}

export function jsonMap(keys: string[] = [], values: Object[] = []): JsonMap {
  const value = JSON.parse('{}') as JsonMap;
  for (let index = 0; index < keys.length; index++) value[keys[index]] = values[index];
  return value;
}

export class WaveformPageOwner {
  private input: JsonMap;
  private state: JsonMap = jsonMap();
  private effects: JsonMap[] = [];
  private calls: string[] = [];
  private record?: JsonMap;
  private heldAudioId: string = '';
  private store: preferences.Preferences;

  private constructor(store: preferences.Preferences, input: JsonMap) {
    this.store = store;
    this.input = clone(input);
  }

  static async create(context: common.UIAbilityContext, input: JsonMap): Promise<WaveformPageOwner> {
    const store = await preferences.getPreferences(context, 'voice_waveform');
    const owner = new WaveformPageOwner(store, input);
    await owner.mount(input);
    return owner;
  }

  async mount(input: JsonMap): Promise<void> {
    this.input = clone(input);
    this.state = jsonMap();
    this.effects = [];
    this.calls = ['WaveformPageOwner.mount'];
    this.record = undefined;
    this.heldAudioId = '';
    await this.store.clear();
    const attachment = this.map(input['attachment']);
    if (Object.keys(attachment).length > 0) {
      this.state['attachmentId'] = this.text(attachment, 'id');
      const stored = this.map(attachment['storedWaveform']);
      if (Object.keys(stored).length > 0) {
        await this.persistRecord(this.recordFromStored(stored, stored['senderProvided'] === true));
      }
    }
    await this.store.flush();
  }

  async generateWaveform(samples: number[], durationUs: number): Promise<void> {
    this.call('WaveformPageOwner.generateWaveform');
    this.effect('persistGenerationPlaceholder', this.attachmentId());
    await this.persistRecord(this.emptyRecord(false));
    this.effect('decodeAudio', this.attachmentId());
    const record = this.generatedRecord(samples, durationUs);
    await this.persistRecord(record);
    this.effect('persistGeneratedWaveform', this.attachmentId());
    this.state['result'] = 'success';
    this.state['storedWaveform'] = clone(record);
  }

  async startUploadGraph(): Promise<void> {
    this.call('WaveformPageOwner.startUploadGraph');
    const attachment = this.map(this.input['attachment']);
    const id = this.text(attachment, 'id');
    this.effect('compressAttachment', id);
    const upload: JsonMap = jsonMap(['compression'], ['complete']);
    if (this.isAudio(this.text(attachment, 'contentType'))) {
      this.heldAudioId = id;
      upload['waveformGeneration'] = 'running';
      upload['upload'] = 'not_started';
      this.effect('generateWaveform', id);
    } else {
      upload['waveformGeneration'] = 'not_scheduled';
      upload['upload'] = 'complete';
      this.effect('uploadAttachment', id);
    }
    this.state['upload'] = upload;
  }

  async releaseHeldWaveform(samples: number[], durationUs: number): Promise<void> {
    this.call('WaveformPageOwner.releaseHeldWaveform');
    if (this.heldAudioId.length === 0) return;
    await this.persistRecord(this.generatedRecord(samples, durationUs));
    this.effect('uploadAttachment', this.heldAudioId);
    const upload = this.map(this.state['upload']);
    upload['waveformGeneration'] = 'complete';
    upload['upload'] = 'complete';
    this.heldAudioId = '';
  }

  async startMixedUploadGraph(): Promise<void> {
    this.call('WaveformPageOwner.startMixedUploadGraph');
    const uploads: JsonMap = jsonMap();
    const attachments = this.maps(this.input['attachments']);
    attachments.forEach((attachment: JsonMap): void => {
      const id = this.text(attachment, 'id');
      this.effect('compressAttachment', id);
      const item: JsonMap = jsonMap(['compression'], ['complete']);
      if (this.isAudio(this.text(attachment, 'contentType'))) {
        this.heldAudioId = id;
        item['waveformGeneration'] = 'running';
        item['upload'] = 'not_started';
        this.effect('generateWaveform', id);
      } else {
        item['waveformGeneration'] = 'not_scheduled';
        item['upload'] = 'complete';
        this.effect('uploadAttachment', id);
      }
      uploads[id] = item;
    });
    this.state['uploads'] = uploads;
  }

  async releaseMixedAudio(samples: number[], durationUs: number): Promise<void> {
    this.call('WaveformPageOwner.releaseMixedAudio');
    if (this.heldAudioId.length === 0) return;
    await this.persistRecord(this.generatedRecord(samples, durationUs));
    this.effect('uploadAttachment', this.heldAudioId);
    const uploads = this.map(this.state['uploads']);
    const item = this.map(uploads[this.heldAudioId]);
    item['waveformGeneration'] = 'complete';
    item['upload'] = 'complete';
    this.heldAudioId = '';
  }

  async serializeOutgoingPointer(): Promise<void> {
    this.call('WaveformPageOwner.serializeOutgoingPointer');
    const attachment = this.map(this.input['attachment']);
    const pointer: JsonMap = jsonMap(['contentType', 'cdnKey', 'encryptionDigest'],
      [this.text(attachment, 'contentType'), this.text(attachment, 'cdnKey'),
        this.text(attachment, 'encryptionDigest')]);
    if (this.record !== undefined) {
      pointer['audioWaveform'] = this.numbers(this.record['bytes']);
      const duration = this.num(this.record, 'durationSeconds');
      if (duration > 0) pointer['audioDurationSeconds'] = duration;
    }
    this.effect('buildAttachmentPointer', this.text(attachment, 'id'));
    this.state['pointer'] = pointer;
  }

  async validateIncomingEnvelope(): Promise<void> {
    this.call('WaveformPageOwner.validateIncomingEnvelope');
    const envelope = this.map(this.input['incomingEnvelope']);
    const pointer = this.map(envelope['attachmentPointer']);
    const accepted = this.waveformBytes(pointer['audioWaveform']).length <= 100;
    this.state['validation'] = jsonMap(['accepted', 'reason'], [accepted, accepted ? '' : 'oversized_audio_waveform']);
  }

  async importIncomingAttachment(): Promise<void> {
    this.call('WaveformPageOwner.importIncomingAttachment');
    const pointer = this.map(this.input['incomingAttachmentPointer']);
    const bytes = this.waveformBytes(pointer['audioWaveform']);
    const duration = this.num(pointer, 'audioDurationSeconds');
    const record: JsonMap = jsonMap(['bytes', 'barCount', 'durationSeconds', 'durationUs', 'senderProvided'],
      [bytes, bytes.length, duration, Math.round(duration * 1000000), true]);
    await this.persistRecord(record);
    this.state['persistedAttachment'] = jsonMap(['contentType', 'waveform'],
      [this.text(pointer, 'contentType'), clone(record)]);
    this.state['reloadedAttachment'] = jsonMap(['waveform'], [clone(record)]);
    this.effect('persistAttachment', this.text(pointer, 'cdnKey'));
  }

  async requestRenderableWaveform(samples: number[], durationUs: number): Promise<void> {
    this.call('WaveformPageOwner.requestRenderableWaveform');
    const attachment = this.map(this.input['attachment']);
    const localReadable = this.text(attachment, 'localMedia') === 'readable';
    if (this.record === undefined && !localReadable) {
      this.state['result'] = 'error';
      return;
    }
    const senderProvided = this.record !== undefined && this.record['senderProvided'] === true;
    const count = this.record === undefined ? 0 : this.num(this.record, 'barCount');
    if (!senderProvided && count !== 100) {
      this.effect('generateWaveform', this.text(attachment, 'id'));
      const replacement = this.generatedRecord(samples, durationUs);
      await this.persistRecord(replacement);
      this.effect('persistGeneratedWaveform', this.text(attachment, 'id'));
      this.state['persistedReplacement'] = clone(replacement);
    }
    if (this.record === undefined || this.numbers(this.record['bytes']).length === 0) {
      this.state['result'] = 'error';
      return;
    }
    this.state['result'] = 'success';
    this.state['renderWaveform'] = this.render(this.numbers(this.record['bytes']));
    this.state['durationSeconds'] = this.num(this.record, 'durationSeconds');
  }

  async backupRestoreAndRender(): Promise<void> {
    this.call('WaveformPageOwner.backupRestoreAndRender');
    const attachment = this.map(this.input['attachment']);
    const pointer: JsonMap = jsonMap(['contentType'], [this.text(attachment, 'contentType')]);
    if (this.record !== undefined) {
      pointer['audioWaveform'] = this.numbers(this.record['bytes']);
      pointer['audioDurationSeconds'] = this.num(this.record, 'durationSeconds');
    }
    this.state['exportedFilePointer'] = clone(pointer);
    await this.store.clear();
    const bytes = this.waveformBytes(pointer['audioWaveform']);
    const duration = this.num(pointer, 'audioDurationSeconds');
    const restored: JsonMap = jsonMap(['bytes', 'barCount', 'durationSeconds', 'durationUs', 'senderProvided'],
      [bytes, bytes.length, duration, Math.round(duration * 1000000), true]);
    await this.persistRecord(restored);
    this.state['restoredAttachment'] = jsonMap(['waveform'], [clone(restored)]);
    this.state['renderAfterRestore'] = jsonMap(['result', 'bars'], ['success', this.render(bytes)]);
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
    const bars: number[] = [];
    for (let bar = 0; bar < 100; bar++) {
      const start = Math.floor(bar * samples.length / 100);
      const end = Math.min(samples.length, Math.max(start + 1, Math.floor((bar + 1) * samples.length / 100)));
      let sum = 0;
      for (let index = start; index < end; index++) sum += samples[index] * samples[index];
      const rms = end > start ? Math.sqrt(sum / (end - start)) / 32767 : 0;
      const db = rms <= 0 ? -60 : 20 * Math.log10(rms);
      const normalized = Math.max(0, db + 60) / 60;
      bars.push(Math.round(Math.min(1, normalized) * 255));
    }
    return jsonMap(['bytes', 'barCount', 'durationUs', 'durationSeconds', 'senderProvided'],
      [bars, bars.length, durationUs, durationUs / 1000000, false]);
  }

  private render(source: number[]): number[] {
    const output: number[] = [];
    for (let bar = 0; bar < 46; bar++) {
      const start = Math.floor(bar * source.length / 46);
      const end = Math.min(source.length, Math.max(start + 1, Math.floor((bar + 1) * source.length / 46)));
      let sum = 0;
      for (let index = start; index < end; index++) sum += source[index];
      output.push(sum / (end - start) / 255);
    }
    return output;
  }

  private recordFromStored(stored: JsonMap, senderProvided: boolean): JsonMap {
    const bytes = this.waveformBytes(stored);
    const seconds = stored['durationSeconds'] !== undefined ? this.num(stored, 'durationSeconds') : this.num(stored, 'durationUs') / 1000000;
    return jsonMap(['bytes', 'barCount', 'durationSeconds', 'durationUs', 'senderProvided'],
      [bytes, bytes.length, seconds, Math.round(seconds * 1000000), senderProvided]);
  }

  private waveformBytes(value: Object | undefined): number[] {
    if (Array.isArray(value)) return (value as Object[]).map((item: Object): number => Number(item));
    const source = this.map(value);
    if (Array.isArray(source['bytes'])) return this.numbers(source['bytes']);
    const result: number[] = [];
    const segments = this.maps(source['segments']);
    segments.forEach((segment: JsonMap): void => {
      for (let index = 0; index < this.num(segment, 'count'); index++) result.push(this.num(segment, 'value'));
    });
    if (segments.length === 0) {
      for (let index = 0; index < this.num(source, 'barCount'); index++) result.push(this.num(source, 'fill'));
    }
    return result;
  }

  private emptyRecord(senderProvided: boolean): JsonMap {
    return jsonMap(['bytes', 'barCount', 'durationUs', 'durationSeconds', 'senderProvided'],
      [[], 0, 0, 0, senderProvided]);
  }

  private async persistRecord(record: JsonMap): Promise<void> {
    this.record = clone(record);
    await this.store.put('waveform', JSON.stringify(this.record));
    await this.store.flush();
  }

  private map(value: Object | undefined): JsonMap {
    return value !== undefined && value !== null && !Array.isArray(value) ? value as JsonMap : jsonMap();
  }
  private maps(value: Object | undefined): JsonMap[] {
    return Array.isArray(value) ? (value as Object[]).map((item: Object): JsonMap => this.map(item)) : [];
  }
  private numbers(value: Object | undefined): number[] {
    return Array.isArray(value) ? (value as Object[]).map((item: Object): number => Number(item)) : [];
  }
  private text(value: JsonMap, key: string, fallback: string = ''): string {
    const item = value[key];
    return typeof item === 'string' ? item : fallback;
  }
  private num(value: JsonMap, key: string): number {
    const item = value[key];
    return typeof item === 'number' ? item : 0;
  }
  private attachmentId(): string { return this.text(this.map(this.input['attachment']), 'id'); }
  private isAudio(contentType: string): boolean { return contentType.startsWith('audio/'); }
  private call(name: string): void { this.calls.push(name); }
  private effect(name: string, attachmentId: string): void { this.effects.push(jsonMap(['name', 'attachmentId'], [name, attachmentId])); }
}
