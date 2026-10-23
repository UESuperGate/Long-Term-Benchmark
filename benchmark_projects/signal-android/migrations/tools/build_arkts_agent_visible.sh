#!/usr/bin/env bash
set -euo pipefail

project="${1:?usage: build_arkts_agent_visible.sh <project-root>}"
project="$(cd "$project" && pwd)"
tools_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
hvigorw="${HVIGORW:-/Applications/DevEco-Studio.app/Contents/tools/hvigor/bin/hvigorw}"
sdk_home="${OHOS_BASE_SDK_HOME:-$HOME/Library/OpenHarmony/Sdk}"

test -x "$hvigorw" || { printf 'hvigor wrapper unavailable: %s\n' "$hvigorw" >&2; exit 69; }
test -d "$sdk_home/23" || { printf 'OpenHarmony API 23 SDK unavailable: %s/23\n' "$sdk_home" >&2; exit 69; }

tool_home="${ARKTS_TOOL_HOME:-$tools_root/.arkts-tool-home}"
legacy_home="$tools_root/../01_media_keyboard/arkts/base/.build-home"
if [[ ! -d "$tool_home" && -d "$legacy_home" ]]; then
  tool_home="$legacy_home"
fi
mkdir -p "$tool_home"

cd "$project"
HOME="$tool_home" OHOS_BASE_SDK_HOME="$sdk_home" \
  "$hvigorw" --mode module -p product=default -p module=entry@default assembleHap --no-daemon
