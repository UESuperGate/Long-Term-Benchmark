#!/usr/bin/env bash
set -euo pipefail

project="${1:?usage: build_arkts_api23.sh <project-root>}"
project="$(cd "$project" && pwd)"
tools_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
role="$(basename "$project")"
migration="$(cd "$project/../.." 2>/dev/null && pwd || true)"

hvigorw="${HVIGORW:-/Applications/DevEco-Studio.app/Contents/tools/hvigor/bin/hvigorw}"
sdk_home="${OHOS_BASE_SDK_HOME:-$HOME/Library/OpenHarmony/Sdk}"

if [[ ! -x "$hvigorw" ]]; then
  printf 'hvigor wrapper unavailable: %s\n' "$hvigorw" >&2
  exit 69
fi
if [[ ! -d "$sdk_home/23" ]]; then
  printf 'OpenHarmony API 23 SDK unavailable: %s/23\n' "$sdk_home" >&2
  exit 69
fi

tool_home="${ARKTS_TOOL_HOME:-$tools_root/.arkts-tool-home}"
legacy_home="$tools_root/../01_media_keyboard/arkts/base/.build-home"
if [[ ! -d "$tool_home" && -d "$legacy_home" ]]; then
  tool_home="$legacy_home"
fi
mkdir -p "$tool_home"

index="$project/entry/src/main/ets/pages/Index.ets"
hidden="$project/entry/src/main/ets/.benchmark-evaluator"
backup=""
if [[ ! -f "$project/.benchmark-evaluator/PREPARED" ]]; then
  observer="$migration/arkts/evaluator/$role/RuntimeObserver.ets"
  test -f "$observer" || { printf 'calibration observer unavailable: %s\n' "$observer" >&2; exit 65; }
  backup="$(mktemp "${TMPDIR:-/tmp}/signal-arkts-index.XXXXXX")"
  cp "$index" "$backup"
  cleanup_injection() {
    cp "$backup" "$index"
    rm -f "$backup"
    rm -rf "$hidden"
  }
  trap cleanup_injection EXIT
  node "$tools_root/inject_arkts_observer.mjs" "$project" "$observer"
fi

cd "$project"
HOME="$tool_home" \
OHOS_BASE_SDK_HOME="$sdk_home" \
  "$hvigorw" --mode module -p product=default -p module=entry@default assembleHap --no-daemon
