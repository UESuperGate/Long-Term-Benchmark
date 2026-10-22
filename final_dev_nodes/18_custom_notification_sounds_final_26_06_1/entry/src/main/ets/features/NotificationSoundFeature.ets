import common from '@ohos.app.ability.common';
import preferences from '@ohos.data.preferences';
import fs from '@ohos.file.fs';
import media from '@ohos.multimedia.media';

export enum SoundSlot {
  Message = 'message',
  Call = 'call'
}

export enum NotificationSoundKind {
  SystemDefault = 'system_default',
  ElementDefault = 'element_default',
  ElementFade = 'element_fade',
  Silent = 'silent',
  Custom = 'custom'
}

export class NotificationSoundSelection {
  kind: NotificationSoundKind;
  uri: string;
  displayName: string;

  constructor(kind: NotificationSoundKind, uri: string = '', displayName: string = '') {
    this.kind = kind;
    this.uri = uri;
    this.displayName = displayName;
  }

  static preset(kind: NotificationSoundKind): NotificationSoundSelection {
    return new NotificationSoundSelection(kind, '', NotificationSoundSelection.labelFor(kind));
  }

  static custom(uri: string, displayName: string): NotificationSoundSelection {
    return new NotificationSoundSelection(NotificationSoundKind.Custom, uri, displayName);
  }

  static labelFor(kind: NotificationSoundKind): string {
    if (kind === NotificationSoundKind.ElementDefault) {
      return 'Element default';
    }
    if (kind === NotificationSoundKind.ElementFade) {
      return 'Element fade';
    }
    if (kind === NotificationSoundKind.Silent) {
      return 'Silent';
    }
    if (kind === NotificationSoundKind.Custom) {
      return 'Custom sound';
    }
    return 'System default';
  }

  copy(): NotificationSoundSelection {
    return new NotificationSoundSelection(this.kind, this.uri, this.displayName);
  }
}

export class NotificationSoundSnapshot {
  messageSound: NotificationSoundSelection;
  callRingtone: NotificationSoundSelection;
  messageChannelVersion: number;
  callChannelVersion: number;

  constructor(
    messageSound: NotificationSoundSelection = NotificationSoundSelection.preset(NotificationSoundKind.SystemDefault),
    callRingtone: NotificationSoundSelection = NotificationSoundSelection.preset(NotificationSoundKind.SystemDefault),
    messageChannelVersion: number = 0,
    callChannelVersion: number = 0
  ) {
    this.messageSound = messageSound;
    this.callRingtone = callRingtone;
    this.messageChannelVersion = messageChannelVersion;
    this.callChannelVersion = callChannelVersion;
  }

  copy(): NotificationSoundSnapshot {
    return new NotificationSoundSnapshot(
      this.messageSound.copy(),
      this.callRingtone.copy(),
      this.messageChannelVersion,
      this.callChannelVersion
    );
  }
}

export class NotificationSoundStore {
  private static readonly STORE_NAME: string = 'element_x_notification_sounds';

  async load(context: common.Context): Promise<NotificationSoundSnapshot> {
    const store = await preferences.getPreferences(context, NotificationSoundStore.STORE_NAME);
    const message = await this.readSelection(store, SoundSlot.Message);
    const call = await this.readSelection(store, SoundSlot.Call);
    const messageVersion = await store.get('message_channel_version', 0);
    const callVersion = await store.get('call_channel_version', 0);
    return new NotificationSoundSnapshot(
      message,
      call,
      typeof messageVersion === 'number' ? messageVersion : 0,
      typeof callVersion === 'number' ? callVersion : 0
    );
  }

  async save(context: common.Context, snapshot: NotificationSoundSnapshot): Promise<void> {
    const store = await preferences.getPreferences(context, NotificationSoundStore.STORE_NAME);
    await this.writeSelection(store, SoundSlot.Message, snapshot.messageSound);
    await this.writeSelection(store, SoundSlot.Call, snapshot.callRingtone);
    await store.put('message_channel_version', snapshot.messageChannelVersion);
    await store.put('call_channel_version', snapshot.callChannelVersion);
    await store.flush();
  }

  private async readSelection(store: preferences.Preferences, slot: SoundSlot): Promise<NotificationSoundSelection> {
    const kindValue = await store.get(`${slot}_kind`, NotificationSoundKind.SystemDefault);
    const uriValue = await store.get(`${slot}_uri`, '');
    const nameValue = await store.get(`${slot}_display_name`, '');
    const kind = typeof kindValue === 'string' ? kindValue as NotificationSoundKind : NotificationSoundKind.SystemDefault;
    const uri = typeof uriValue === 'string' ? uriValue : '';
    const displayName = typeof nameValue === 'string' && nameValue.length > 0
      ? nameValue
      : NotificationSoundSelection.labelFor(kind);
    return new NotificationSoundSelection(kind, uri, displayName);
  }

  private async writeSelection(
    store: preferences.Preferences,
    slot: SoundSlot,
    selection: NotificationSoundSelection
  ): Promise<void> {
    await store.put(`${slot}_kind`, selection.kind);
    await store.put(`${slot}_uri`, selection.uri);
    await store.put(`${slot}_display_name`, selection.displayName);
  }
}

export class SoundCopyResult {
  succeeded: boolean;
  appOwnedUri: string;
  displayName: string;
  errorMessage: string;

  constructor(succeeded: boolean, appOwnedUri: string, displayName: string, errorMessage: string) {
    this.succeeded = succeeded;
    this.appOwnedUri = appOwnedUri;
    this.displayName = displayName;
    this.errorMessage = errorMessage;
  }
}

export class NotificationSoundCopier {
  async copyToAppFiles(context: common.Context, sourceUri: string, slot: SoundSlot): Promise<SoundCopyResult> {
    if (!this.isSupportedSource(sourceUri)) {
      return new SoundCopyResult(false, '', '', 'The selected audio source cannot be opened');
    }
    const displayName = await this.resolveDisplayName(sourceUri);
    const targetPath = `${context.filesDir}/notification_sound_${slot}.audio`;
    try {
      // Picker URIs can be opened, but copyFile accepts only paths or descriptors.
      const source = await fs.open(sourceUri, fs.OpenMode.READ_ONLY);
      try {
        await fs.copyFile(source.fd, targetPath);
      } finally {
        await fs.close(source);
      }
      return new SoundCopyResult(true, `file://${targetPath}`, displayName, '');
    } catch (error) {
      return new SoundCopyResult(false, '', '', `${error}`);
    }
  }

  deleteStoredSoundFor(context: common.Context, slot: SoundSlot): void {
    const targetPath = `${context.filesDir}/notification_sound_${slot}.audio`;
    try {
      fs.unlinkSync(targetPath);
    } catch (error) {
    }
  }

  sanitizeDisplayName(value: string): string {
    let sanitized = '';
    for (let index = 0; index < value.length && sanitized.length < 256; index += 1) {
      const code = value.charCodeAt(index);
      if (code > 31 && code !== 127) {
        sanitized += value.charAt(index);
      }
    }
    sanitized = sanitized.trim();
    return sanitized.length > 0 ? sanitized : 'Custom sound';
  }

  private async resolveDisplayName(sourceUri: string): Promise<string> {
    const fallback = this.sanitizeDisplayName(this.fileNameFromUri(sourceUri));
    let source: fs.File | undefined = undefined;
    let extractor: media.AVMetadataExtractor | undefined = undefined;
    try {
      source = await fs.open(sourceUri, fs.OpenMode.READ_ONLY);
      const stat = await fs.stat(source.fd);
      extractor = await media.createAVMetadataExtractor();
      extractor.fdSrc = { fd: source.fd, offset: 0, length: stat.size };
      const metadata = await extractor.fetchMetadata();
      if (metadata.title !== undefined && metadata.title.trim().length > 0) {
        return this.sanitizeDisplayName(metadata.title);
      }
    } catch (error) {
      // Optional metadata must not prevent an otherwise supported file copy.
    } finally {
      if (extractor !== undefined) {
        try {
          await extractor.release();
        } catch (error) {
        }
      }
      if (source !== undefined) {
        try {
          await fs.close(source);
        } catch (error) {
        }
      }
    }
    return fallback;
  }

  private isSupportedSource(sourceUri: string): boolean {
    return sourceUri.startsWith('file://') || sourceUri.startsWith('content://') ||
      sourceUri.startsWith('datashare://') || sourceUri.startsWith('/');
  }

  private fileNameFromUri(uri: string): string {
    const stableUri = uri.split('#')[0].split('?')[0];
    const slash = stableUri.lastIndexOf('/');
    const encoded = slash >= 0 ? stableUri.substring(slash + 1) : stableUri;
    try {
      return decodeURIComponent(encoded);
    } catch (error) {
      return encoded;
    }
  }
}

export class NotificationChannelGateway {
  private static readonly STORE_NAME: string = 'element_x_notification_channels';
  lastRecreatedSlot: SoundSlot | null = null;
  lastRecreatedVersion: number = 0;
  failNextRecreation: boolean = false;

  async recreateChannel(
    context: common.Context,
    slot: SoundSlot,
    selection: NotificationSoundSelection,
    version: number
  ): Promise<void> {
    if (this.failNextRecreation) {
      this.failNextRecreation = false;
      throw new Error('Notification channel update failed');
    }
    const store = await preferences.getPreferences(context, NotificationChannelGateway.STORE_NAME);
    await store.put(`${slot}_active_channel_id`, `${slot}_notifications_v${version}`);
    await store.put(`${slot}_effective_sound_kind`, selection.kind);
    await store.put(`${slot}_effective_sound_uri`, selection.uri);
    await store.flush();
    this.lastRecreatedSlot = slot;
    this.lastRecreatedVersion = version;
  }
}

export class NotificationSettingsPresenter {
  readonly store: NotificationSoundStore;
  readonly copier: NotificationSoundCopier;
  readonly channelGateway: NotificationChannelGateway;
  snapshot: NotificationSoundSnapshot = new NotificationSoundSnapshot();
  showMessageSoundDialog: boolean = false;
  showCallRingtoneDialog: boolean = false;
  pendingMessageSoundPickerLaunch: number = 0;
  pendingCallRingtonePickerLaunch: number = 0;
  messageCopyError: string = '';
  callCopyError: string = '';
  private messageQueue: Promise<void> = Promise.resolve();
  private callQueue: Promise<void> = Promise.resolve();

  constructor(store: NotificationSoundStore, copier: NotificationSoundCopier, channelGateway: NotificationChannelGateway) {
    this.store = store;
    this.copier = copier;
    this.channelGateway = channelGateway;
  }

  async load(context: common.Context): Promise<void> {
    const loaded = await this.store.load(context);
    // Preserve the legacy bundled message tone, as Android channel bootstrap does.
    // A versioned SystemDefault is an explicit choice and must not be migrated.
    if (loaded.messageChannelVersion === 0 &&
      loaded.messageSound.kind === NotificationSoundKind.SystemDefault) {
      const migrated = loaded.copy();
      migrated.messageSound = NotificationSoundSelection.preset(NotificationSoundKind.ElementDefault);
      migrated.messageChannelVersion = 1;
      await this.store.save(context, migrated);
      this.snapshot = migrated;
    } else {
      this.snapshot = loaded;
    }
  }

  showDialog(slot: SoundSlot): void {
    if (slot === SoundSlot.Message) {
      this.showMessageSoundDialog = true;
    } else {
      this.showCallRingtoneDialog = true;
    }
  }

  dismissDialog(slot: SoundSlot): void {
    if (slot === SoundSlot.Message) {
      this.showMessageSoundDialog = false;
    } else {
      this.showCallRingtoneDialog = false;
    }
  }

  launchSystemPicker(slot: SoundSlot): void {
    this.dismissDialog(slot);
    if (slot === SoundSlot.Message) {
      this.pendingMessageSoundPickerLaunch += 1;
    } else {
      this.pendingCallRingtonePickerLaunch += 1;
    }
  }

  selectPreset(context: common.Context, slot: SoundSlot, kind: NotificationSoundKind): Promise<boolean> {
    this.dismissDialog(slot);
    return this.setSound(context, slot, NotificationSoundSelection.preset(kind));
  }

  setCustomSound(context: common.Context, slot: SoundSlot, sourceUri: string): Promise<boolean> {
    return this.setSound(context, slot, NotificationSoundSelection.custom(sourceUri, ''));
  }

  setSound(context: common.Context, slot: SoundSlot, requested: NotificationSoundSelection): Promise<boolean> {
    if (slot === SoundSlot.Message) {
      const operation = this.messageQueue.then(() => this.applySound(context, slot, requested));
      this.messageQueue = operation.then((): void => {}, (): void => {});
      return operation;
    }
    const operation = this.callQueue.then(() => this.applySound(context, slot, requested));
    this.callQueue = operation.then((): void => {}, (): void => {});
    return operation;
  }

  dismissCopyError(slot: SoundSlot): void {
    if (slot === SoundSlot.Message) {
      this.messageCopyError = '';
    } else {
      this.callCopyError = '';
    }
  }

  async migrateLegacyCallRingtone(
    context: common.Context,
    legacySelection: NotificationSoundSelection
  ): Promise<boolean> {
    if (this.snapshot.callChannelVersion !== 0 ||
      this.snapshot.callRingtone.kind !== NotificationSoundKind.SystemDefault) {
      return false;
    }
    const migrated = this.snapshot.copy();
    migrated.callRingtone = legacySelection.copy();
    migrated.callChannelVersion = 1;
    await this.store.save(context, migrated);
    await this.channelGateway.recreateChannel(context, SoundSlot.Call, migrated.callRingtone, 1);
    this.snapshot = migrated;
    return true;
  }

  private async applySound(
    context: common.Context,
    slot: SoundSlot,
    requested: NotificationSoundSelection
  ): Promise<boolean> {
    const previous = this.snapshot.copy();
    const current = slot === SoundSlot.Message ? previous.messageSound : previous.callRingtone;
    if (requested.kind !== NotificationSoundKind.Custom && current.kind === requested.kind) {
      return true;
    }
    let effective = requested.copy();
    if (requested.kind === NotificationSoundKind.Custom) {
      const copyResult = await this.copier.copyToAppFiles(context, requested.uri, slot);
      if (!copyResult.succeeded) {
        this.setCopyError(slot, copyResult.errorMessage);
        return false;
      }
      effective = NotificationSoundSelection.custom(copyResult.appOwnedUri, copyResult.displayName);
    } else {
      this.copier.deleteStoredSoundFor(context, slot);
    }

    const updated = previous.copy();
    const nextVersion = slot === SoundSlot.Message
      ? previous.messageChannelVersion + 1
      : previous.callChannelVersion + 1;
    if (slot === SoundSlot.Message) {
      updated.messageSound = effective;
      updated.messageChannelVersion = nextVersion;
    } else {
      updated.callRingtone = effective;
      updated.callChannelVersion = nextVersion;
    }

    try {
      await this.store.save(context, updated);
      await this.channelGateway.recreateChannel(context, slot, effective, nextVersion);
      this.snapshot = updated;
      this.setCopyError(slot, '');
      return true;
    } catch (error) {
      await this.store.save(context, previous);
      this.snapshot = previous;
      this.setCopyError(slot, `${error}`);
      return false;
    }
  }

  private setCopyError(slot: SoundSlot, message: string): void {
    if (slot === SoundSlot.Message) {
      this.messageCopyError = message;
    } else {
      this.callCopyError = message;
    }
  }
}
