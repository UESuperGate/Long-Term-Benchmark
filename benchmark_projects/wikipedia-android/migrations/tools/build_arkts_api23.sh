#!/usr/bin/env bash
set -euo pipefail
project="${1:?usage: build_arkts_api23.sh <project>}"
hvigorw="${HVIGORW:-/Applications/DevEco-Studio.app/Contents/tools/hvigor/bin/hvigorw}"
test -x "$hvigorw" || { printf 'hvigor unavailable: %s\n' "$hvigorw" >&2; exit 69; }
cd "$project"
"$hvigorw" --mode module -p product=default -p module=entry@default assembleHap --no-daemon
