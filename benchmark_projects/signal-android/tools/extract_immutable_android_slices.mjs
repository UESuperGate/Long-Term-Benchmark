#!/usr/bin/env node

import { createHash } from 'node:crypto';
import { execFileSync } from 'node:child_process';
import { mkdirSync, writeFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const projectRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const repository = resolve(projectRoot, '..', '..', '_sources', 'signal-android');

const slices = [
  {
    taskId: '01_media_keyboard',
    role: 'base',
    ref: 'd0b314d2d7197c38737c6189d1f6c294e76e247e',
    paths: [
      'app/src/main/java/org/thoughtcrime/securesms/components/compose/mediakeyboard/MediaKeyboardController.kt',
      'app/src/main/java/org/thoughtcrime/securesms/components/compose/mediakeyboard/MediaKeyboardKey.kt'
    ]
  },
  {
    taskId: '01_media_keyboard',
    role: 'final',
    ref: 'd8d36376f480eb4669efe8bfee94b2c196a9f7bd',
    paths: [
      'app/src/main/java/org/thoughtcrime/securesms/conversation/v2/ChatStickerConfirmationController.kt',
      'core/ui/src/main/java/org/signal/core/ui/compose/EventDrivenViewModel.kt',
      'core/util/src/main/java/org/signal/core/util/Result.kt',
      'feature/media-keyboard/src/main/java/org/signal/mediakeyboard/MediaKeyboardAction.kt',
      'feature/media-keyboard/src/main/java/org/signal/mediakeyboard/MediaKeyboardScreenEvents.kt',
      'feature/media-keyboard/src/main/java/org/signal/mediakeyboard/MediaKeyboardState.kt',
      'feature/media-keyboard/src/main/java/org/signal/mediakeyboard/MediaKeyboardTab.kt',
      'feature/media-keyboard/src/main/java/org/signal/mediakeyboard/MediaKeyboardViewModel.kt',
      'feature/media-keyboard/src/main/java/org/signal/mediakeyboard/data/EmojiKeyboardRepository.kt',
      'feature/media-keyboard/src/main/java/org/signal/mediakeyboard/data/GifKeyboardRepository.kt',
      'feature/media-keyboard/src/main/java/org/signal/mediakeyboard/data/MediaKeyboardRepository.kt',
      'feature/media-keyboard/src/main/java/org/signal/mediakeyboard/data/StickerKeyboardRepository.kt',
      'feature/media-keyboard/src/main/java/org/signal/mediakeyboard/screens/MediaKeyboardPageViewModel.kt',
      'feature/media-keyboard/src/main/java/org/signal/mediakeyboard/screens/gif/GifPageScreenEvents.kt',
      'feature/media-keyboard/src/main/java/org/signal/mediakeyboard/screens/gif/GifPageState.kt',
      'feature/media-keyboard/src/main/java/org/signal/mediakeyboard/screens/gif/GifPageViewModel.kt',
      'feature/media-keyboard/src/main/java/org/signal/mediakeyboard/screens/gif/GifQuickSearchOption.kt',
      'feature/media-keyboard/src/main/java/org/signal/mediakeyboard/screens/sticker/StickerPageScreenEvents.kt',
      'feature/media-keyboard/src/main/java/org/signal/mediakeyboard/screens/sticker/StickerPageState.kt',
      'feature/media-keyboard/src/main/java/org/signal/mediakeyboard/screens/sticker/StickerPageViewModel.kt'
    ]
  },
  {
    taskId: '02_sticker_management',
    role: 'base',
    ref: '556bcda58ae65abbba75bf899a43666ba6d9d427',
    paths: [
      'app/src/main/java/org/thoughtcrime/securesms/database/model/StickerPackRecord.kt',
      'app/src/main/java/org/thoughtcrime/securesms/database/model/StickerRecord.kt',
      'app/src/main/java/org/thoughtcrime/securesms/stickers/BlessedPacks.java',
      'app/src/main/java/org/thoughtcrime/securesms/stickers/StickerManagementRepository.java',
      'app/src/main/java/org/thoughtcrime/securesms/stickers/StickerManagementViewModel.java'
    ]
  },
  {
    taskId: '02_sticker_management',
    role: 'final',
    ref: '23669c3c372284d42db486a218d9f29bef247abf',
    paths: [
      'app/src/main/java/org/thoughtcrime/securesms/database/model/StickerPackRecord.kt',
      'app/src/main/java/org/thoughtcrime/securesms/database/model/StickerRecord.kt',
      'app/src/main/java/org/thoughtcrime/securesms/stickers/BlessedPacks.java',
      'app/src/main/java/org/thoughtcrime/securesms/stickers/StickerManagementRepository.kt',
      'app/src/main/java/org/thoughtcrime/securesms/stickers/StickerManagementViewModel.kt',
      'core-util/src/main/java/org/signal/core/util/CollectionsExtensions.kt'
    ]
  }
];

for (const slice of slices) {
  const roleRoot = resolve(projectRoot, 'migrations', slice.taskId, 'android', slice.role);
  const records = [];

  for (const sourcePath of slice.paths) {
    let bytes;
    let transport = 'local-git-object';
    try {
      bytes = execFileSync('git', ['show', `${slice.ref}:${sourcePath}`], {
        cwd: repository,
        encoding: null,
        maxBuffer: 32 * 1024 * 1024,
        stdio: ['ignore', 'pipe', 'pipe']
      });
    } catch {
      transport = 'official-raw-commit-url';
      bytes = execFileSync('curl', [
        '-L', '--fail', '--retry', '3', '--connect-timeout', '10', '--max-time', '60', '-sS',
        `https://raw.githubusercontent.com/signalapp/Signal-Android/${slice.ref}/${sourcePath}`
      ], { encoding: null, maxBuffer: 32 * 1024 * 1024 });
    }

    const treeEntry = execFileSync('git', ['ls-tree', slice.ref, '--', sourcePath], {
      cwd: repository,
      encoding: 'utf8'
    }).trim();
    const expectedBlob = treeEntry.split(/\s+/)[2];
    const actualBlob = execFileSync('git', ['hash-object', '--stdin'], {
      cwd: repository,
      input: bytes,
      encoding: 'utf8'
    }).trim();
    if (!expectedBlob || actualBlob !== expectedBlob) {
      throw new Error(`Immutable blob mismatch for ${slice.ref}:${sourcePath}`);
    }
    const outputPath = resolve(roleRoot, 'immutable-src', sourcePath);
    mkdirSync(dirname(outputPath), { recursive: true });
    writeFileSync(outputPath, bytes);
    records.push({
      ref: slice.ref,
      path: sourcePath,
      gitBlob: expectedBlob,
      transport,
      bytes: bytes.byteLength,
      sha256: createHash('sha256').update(bytes).digest('hex')
    });
  }

  writeFileSync(resolve(roleRoot, 'IMMUTABLE_SOURCES.json'), `${JSON.stringify({
    schemaVersion: 1,
    taskId: slice.taskId,
    role: slice.role,
    sourceRepository: 'https://github.com/signalapp/Signal-Android.git',
    sourceCommit: slice.ref,
    extraction: 'git-show-exact-bytes',
    files: records
  }, null, 2)}\n`);
}

console.log(JSON.stringify({ extractedSlices: slices.length, sourceRepository: repository }));
