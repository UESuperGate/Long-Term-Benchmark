#!/usr/bin/env bash
set -euo pipefail

project="${1:?usage: build_arkts_focused_candidate.sh <candidate-project> <migration-root> [source-manifest]}"
migration="${2:?usage: build_arkts_focused_candidate.sh <candidate-project> <migration-root> [source-manifest]}"
source_manifest="${3:-$project/SOURCE_MANIFEST.json}"
project="$(cd "$project" && pwd)"
migration="$(cd "$migration" && pwd)"
tools_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
hvigorw="${HVIGORW:-/Applications/DevEco-Studio.app/Contents/tools/hvigor/bin/hvigorw}"
sdk_home="${OHOS_BASE_SDK_HOME:-$HOME/Library/OpenHarmony/Sdk}"
tool_home="${ARKTS_TOOL_HOME:-/tmp/ltb-signal-arkts-tool-home}"

available_kib="$(df -Pk "$project" | awk 'NR == 2 { print $4 }')"
(( available_kib >= 8388608 )) || { printf 'refusing ArkTS build below 8 GiB free\n' >&2; exit 75; }
test -x "$hvigorw" || { printf 'hvigor unavailable: %s\n' "$hvigorw" >&2; exit 69; }
test -d "$sdk_home/23" || { printf 'OpenHarmony API 23 SDK unavailable\n' >&2; exit 69; }
node "$tools_root/verify_arkts_candidate.mjs" "$project" "$source_manifest"

index="$project/entry/src/main/ets/pages/Index.ets"
hidden="$project/entry/src/main/ets/.benchmark-evaluator"
observer="$migration/arkts/evaluator/RuntimeObserver.ets"
backup="$(mktemp "${TMPDIR:-/tmp}/signal-focused-index.XXXXXX")"
cp "$index" "$backup"
cleanup_injection() {
  cp "$backup" "$index"
  rm -f "$backup"
  rm -rf "$hidden"
}
trap cleanup_injection EXIT
node "$tools_root/inject_arkts_focused_observer.mjs" "$project" "$observer"
mkdir -p "$tool_home"
cd "$project"
HOME="$tool_home" OHOS_BASE_SDK_HOME="$sdk_home" \
  "$hvigorw" --mode module -p product=default -p module=entry@default assembleHap --no-daemon
