#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(cd "$root/../../../.." && pwd)/_sources/signal-android"

sources=(
  core/models/src/main/java/org/signal/core/models/media/Media.kt
  core/models/src/main/java/org/signal/core/models/media/TransformProperties.kt
  core/ui/src/main/java/org/signal/core/ui/compose/EventDrivenViewModel.kt
  feature/media-send/src/main/java/org/signal/mediasend/EditorState.kt
  feature/media-send/src/main/java/org/signal/mediasend/MediaSendFlowEvent.kt
  feature/media-send/src/main/java/org/signal/mediasend/MediaSendFlowState.kt
  feature/media-send/src/main/java/org/signal/mediasend/MediaSendFlowViewModel.kt
  feature/media-send/src/main/java/org/signal/mediasend/screens/edit/MediaEditScreenEvents.kt
  feature/media-send/src/main/java/org/signal/mediasend/screens/edit/MediaEditState.kt
  feature/media-send/src/main/java/org/signal/mediasend/screens/edit/MediaEditViewModel.kt
  feature/media-send/src/main/java/org/signal/mediasend/screens/edit/video/VideoTrimData.kt
  app/src/main/java/org/thoughtcrime/securesms/mediasend/MediaTransform.java
  app/src/main/java/org/thoughtcrime/securesms/mediasend/VideoTrimTransform.kt
  lib/video/src/main/java/org/thoughtcrime/securesms/video/StreamingTranscoder.java
)

tests=(
  feature/media-send/src/test/java/org/signal/mediasend/screens/edit/MediaEditStateTest.kt
  feature/media-send/src/test/java/org/signal/mediasend/screens/edit/MediaEditViewModelTest.kt
  feature/media-send/src/test/java/org/signal/mediasend/screens/edit/MediaEditorToolbarSharedButtonsTest.kt
  core/models/src/test/java/org/signal/core/models/media/TransformPropertiesTest.kt
  app/src/test/java/org/thoughtcrime/securesms/database/AttachmentDatabaseTransformPropertiesTest.java
  demo/video/src/androidTest/java/org/thoughtcrime/video/app/transcode/VideoTranscodeInstrumentationTest.kt
)

production_paths=(
  feature/media-send/src/main/java/org/signal/mediasend/MediaSendFlowState.kt
  feature/media-send/src/main/java/org/signal/mediasend/MediaSendFlowViewModel.kt
  feature/media-send/src/main/java/org/signal/mediasend/MediaSendRepository.kt
  feature/media-send/src/main/java/org/signal/mediasend/screens/edit/MediaEditState.kt
  feature/media-send/src/main/java/org/signal/mediasend/screens/edit/MediaEditViewModel.kt
  feature/media-send/src/main/java/org/signal/mediasend/screens/edit/MediaEditScreen.kt
  feature/media-send/src/main/java/org/signal/mediasend/screens/edit/MediaEditorToolbar.kt
  feature/media-send/src/main/java/org/signal/mediasend/screens/edit/video/VideoTrimData.kt
  core/models/src/main/java/org/signal/core/models/media/TransformProperties.kt
  app/src/main/java/org/thoughtcrime/securesms/mediasend/VideoTrimTransform.kt
  lib/video/src/main/java/org/thoughtcrime/securesms/video/StreamingTranscoder.java
)

materialize() {
  local name="$1" ref="$2" project
  project="$root/android/$name"
  rm -rf "$project/immutable-src"
  mkdir -p "$project/immutable-src"
  : > "$project/.inventory.tsv"
  for source in "${sources[@]}"; do
    if [[ "$name" == base && "$source" == "feature/media-send/src/main/java/org/signal/mediasend/MediaSendFlowViewModel.kt" ]]; then
      continue
    fi
    if git -C "$repo" cat-file -e "$ref:$source" 2>/dev/null; then
      mkdir -p "$project/immutable-src/$(dirname "$source")"
      git -C "$repo" cat-file blob "$ref:$source" > "$project/immutable-src/$source"
      printf '%s\t%s\t%s\t%s\n' "$source" "$(git -C "$repo" rev-parse "$ref:$source")" "$(wc -c < "$project/immutable-src/$source" | tr -d ' ')" "$(shasum -a 256 "$project/immutable-src/$source" | awk '{print $1}')" >> "$project/.inventory.tsv"
    fi
  done
  : > "$project/.tests.tsv"
  for source in "${tests[@]}"; do
    if git -C "$repo" cat-file -e "$ref:$source" 2>/dev/null; then
      printf '%s\t%s\t%s\t%s\n' "$source" "$(git -C "$repo" rev-parse "$ref:$source")" "$(git -C "$repo" cat-file -s "$ref:$source")" "$(git -C "$repo" cat-file blob "$ref:$source" | shasum -a 256 | awk '{print $1}')" >> "$project/.tests.tsv"
    fi
  done
  : > "$project/.production.tsv"
  for source in "${production_paths[@]}"; do
    if git -C "$repo" cat-file -e "$ref:$source" 2>/dev/null; then
      printf '%s\tpresent\t%s\t%s\t%s\n' "$source" "$(git -C "$repo" rev-parse "$ref:$source")" "$(git -C "$repo" cat-file -s "$ref:$source")" "$(git -C "$repo" cat-file blob "$ref:$source" | shasum -a 256 | awk '{print $1}')" >> "$project/.production.tsv"
    else
      printf '%s\tabsent\t\t0\t\n' "$source" >> "$project/.production.tsv"
    fi
  done
  python3 - "$project" "$ref" <<'PY'
import json, pathlib, sys
project, ref = pathlib.Path(sys.argv[1]), sys.argv[2]
def rows(name):
    values=[]
    for line in (project/name).read_text().splitlines():
        path, blob, size, sha = line.split('\t')
        values.append({'path': path, 'gitBlob': blob, 'bytes': int(size), 'sha256': sha})
    return values
(project/'IMMUTABLE_SOURCES.json').write_text(json.dumps({'schemaVersion':2,'sourceCommit':ref,'classification':'official_immutable_production_bytes','files':rows('.inventory.tsv')},indent=2)+'\n')
(project/'VERIFIED_TEST_PATHS.json').write_text(json.dumps({'schemaVersion':1,'sourceCommit':ref,'classification':'official_test_evidence_not_packaged','files':rows('.tests.tsv')},indent=2)+'\n')
production=[]
for line in (project/'.production.tsv').read_text().splitlines():
    path, status, blob, size, sha = line.split('\t')
    production.append({'path': path, 'status': status, 'gitBlob': blob or None, 'bytes': int(size), 'sha256': sha or None})
(project/'VERIFIED_PRODUCTION_PATHS.json').write_text(json.dumps({'schemaVersion':1,'sourceCommit':ref,'classification':'official_task_production_path_evidence','files':production},indent=2)+'\n')
(project/'.inventory.tsv').unlink()
(project/'.tests.tsv').unlink()
(project/'.production.tsv').unlink()
PY
}

materialize base e3a7a9c8764bf5961bbbb54f5d72d1056dd3974e
materialize final 64fa9f50a38fecb088135fd0200c331fe0686bd3
