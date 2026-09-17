import Want from '@ohos.app.ability.Want';

export interface LaunchIntentPayload {
  action: string;
  uri: string;
  command: string;
  roomId: string;
  shareText: string;
  shareUris: string[];
  shareMimeTypes: string[];
}

interface SerializedLaunchIntentPayload {
  action: string;
  uri: string;
  command: string;
  roomId: string;
  shareText: string;
  shareUris: string[];
  shareMimeTypes: string[];
}

export class LaunchIntentStore {
  static readonly KEY: string = 'elementx_launch_intent_payload';

  static capture(want: Want): void {
    const action = want.action ?? '';
    const uri = want.uri ?? '';
    const queryShareText = LaunchIntentStore.queryValue(uri, 'text');
    const parameterShareText = LaunchIntentStore.parameterString(want, [
      'text',
      'ohos.extra.TEXT',
      'android.intent.extra.TEXT'
    ]);
    const payload: SerializedLaunchIntentPayload = {
      action: action,
      uri: uri,
      command: LaunchIntentStore.commandFrom(action, uri),
      roomId: LaunchIntentStore.queryValue(uri, 'roomId'),
      shareText: queryShareText.length > 0 ? queryShareText : parameterShareText,
      shareUris: LaunchIntentStore.uniqueNonEmpty([
        ...LaunchIntentStore.directShareUri(action, uri),
        ...LaunchIntentStore.queryValues(uri, 'uri'),
        ...LaunchIntentStore.queryValues(uri, 'uris'),
        ...LaunchIntentStore.parameterStrings(want, [
          'uri',
          'uris',
          'ability.params.stream',
          'ohos.extra.STREAM',
          'android.intent.extra.STREAM'
        ]),
        ...LaunchIntentStore.fdStrings(want)
      ]),
      shareMimeTypes: LaunchIntentStore.uniqueNonEmpty([
        ...LaunchIntentStore.queryValues(uri, 'mimeType'),
        ...LaunchIntentStore.queryValues(uri, 'mime'),
        ...LaunchIntentStore.parameterStrings(want, [
          'mimeType',
          'mime',
          'type'
        ]),
        ...(want.type === undefined ? [] : [want.type])
      ])
    };
    LaunchIntentStore.writePayload(JSON.stringify(payload));
  }

  static consume(): LaunchIntentPayload {
    const raw = AppStorage.get<string>(LaunchIntentStore.KEY) ?? '';
    LaunchIntentStore.writePayload('');
    if (raw.length === 0) {
      return LaunchIntentStore.emptyPayload();
    }
    try {
      const parsed = JSON.parse(raw) as SerializedLaunchIntentPayload;
      return {
        action: parsed.action ?? '',
        uri: parsed.uri ?? '',
        command: parsed.command ?? '',
        roomId: parsed.roomId ?? '',
        shareText: parsed.shareText ?? '',
        shareUris: parsed.shareUris ?? [],
        shareMimeTypes: parsed.shareMimeTypes ?? []
      };
    } catch (error) {
      return LaunchIntentStore.emptyPayload();
    }
  }

  private static commandFrom(action: string, uri: string): string {
    if (action.indexOf('MARK_ROOM_READ') >= 0 || uri.indexOf('/markRead') >= 0) {
      return 'mark_room_read';
    }
    if (uri.indexOf('/room/open') >= 0 || uri.indexOf('roomId=') >= 0) {
      return 'open_room';
    }
    if (uri.indexOf('oauth') >= 0 || uri.indexOf('loginToken') >= 0 || uri.indexOf('io.element.android') >= 0) {
      return 'oauth';
    }
    if (uri.indexOf('mobile.element.io') >= 0) {
      return 'login_link';
    }
    if (uri.indexOf('matrix.to') >= 0 || uri.indexOf('element.io') >= 0) {
      return 'permalink';
    }
    if (action.indexOf('SEND') >= 0 || action.indexOf('sendData') >= 0 || action.indexOf('sendMultipleData') >= 0 || uri.indexOf('/share') >= 0) {
      return 'incoming_share';
    }
    return '';
  }

  private static queryValue(uri: string, key: string): string {
    const values = LaunchIntentStore.queryValues(uri, key);
    if (values.length === 0) {
      return '';
    }
    return values[0];
  }

  private static queryValues(uri: string, key: string): string[] {
    const prefix = `${key}=`;
    const queryIndex = uri.indexOf('?');
    if (queryIndex < 0) {
      return [];
    }
    const values: string[] = [];
    const query = uri.substring(queryIndex + 1);
    const parts = query.split('&');
    for (let index = 0; index < parts.length; index += 1) {
      const part = parts[index];
      if (part.startsWith(prefix)) {
        values.push(decodeURIComponent(part.substring(prefix.length).replace(/\+/g, '%20')));
      }
    }
    return values;
  }

  private static parameterString(want: Want, keys: string[]): string {
    const values = LaunchIntentStore.parameterStrings(want, keys);
    if (values.length === 0) {
      return '';
    }
    return values[0];
  }

  private static directShareUri(action: string, uri: string): string[] {
    if (uri.length === 0) {
      return [];
    }
    if (action.indexOf('SEND') < 0 && action.indexOf('sendData') < 0 && action.indexOf('sendMultipleData') < 0) {
      return [];
    }
    if (uri.indexOf('elementx://') === 0 || uri.indexOf('matrix.to') >= 0 || uri.indexOf('mobile.element.io') >= 0 || uri.indexOf('app.element.io') >= 0) {
      return [];
    }
    return [uri];
  }

  private static parameterStrings(want: Want, keys: string[]): string[] {
    const parameters = want.parameters;
    if (parameters === undefined) {
      return [];
    }
    const values: string[] = [];
    for (let keyIndex = 0; keyIndex < keys.length; keyIndex += 1) {
      const raw = parameters[keys[keyIndex]];
      if (raw === undefined || raw === null) {
        continue;
      }
      values.push(...LaunchIntentStore.objectStrings(raw));
    }
    return LaunchIntentStore.uniqueNonEmpty(values);
  }

  private static fdStrings(want: Want): string[] {
    const fds = want.fds;
    if (fds === undefined) {
      return [];
    }
    const values: string[] = [];
    const keys = Object.keys(fds);
    for (let index = 0; index < keys.length; index += 1) {
      const key = keys[index];
      const fd = fds[key];
      if (fd === undefined || fd < 0) {
        continue;
      }
      values.push(`fd://${encodeURIComponent(key)}?fd=${fd}`);
    }
    return values;
  }

  private static objectStrings(value: Object): string[] {
    if (Array.isArray(value)) {
      const array = value as Object[];
      const values: string[] = [];
      for (let index = 0; index < array.length; index += 1) {
        values.push(...LaunchIntentStore.objectStrings(array[index]));
      }
      return values;
    }
    const raw = String(value);
    if (raw.indexOf('|') >= 0) {
      return raw.split('|');
    }
    if (raw.indexOf(',') >= 0 && raw.indexOf('://') < 0) {
      return raw.split(',');
    }
    return [raw];
  }

  private static uniqueNonEmpty(values: string[]): string[] {
    const result: string[] = [];
    for (let index = 0; index < values.length; index += 1) {
      const value = values[index].trim();
      if (value.length === 0 || result.indexOf(value) >= 0) {
        continue;
      }
      result.push(value);
    }
    return result;
  }

  private static writePayload(value: string): void {
    if (!AppStorage.set<string>(LaunchIntentStore.KEY, value)) {
      AppStorage.setOrCreate<string>(LaunchIntentStore.KEY, value);
    }
  }

  private static emptyPayload(): LaunchIntentPayload {
    return {
      action: '',
      uri: '',
      command: '',
      roomId: '',
      shareText: '',
      shareUris: [],
      shareMimeTypes: []
    };
  }
}
