#!/usr/bin/env bash
set -euo pipefail
role="${1:?usage: build.sh <base|final>}"
root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
project="$root/$role"
[[ "$role" == base || "$role" == final ]] || { printf 'invalid role: %s\n' "$role" >&2; exit 64; }
available_kib="$(df -Pk "$project" | awk 'NR == 2 { print $4 }')"
(( available_kib >= 8388608 )) || { printf 'refusing ArkTS build below 8 GiB free\n' >&2; exit 75; }
export OHOS_BASE_SDK_HOME="${OHOS_BASE_SDK_HOME:-$HOME/Library/OpenHarmony/Sdk}"
export JAVA_HOME="${JAVA_HOME:-/Applications/DevEco-Studio.app/Contents/jbr/Contents/Home}"
export NODE_HOME="${NODE_HOME:-/Applications/DevEco-Studio.app/Contents/tools/node}"
export PATH="$NODE_HOME/bin:$JAVA_HOME/bin:$PATH"
hvigor="${HVIGORW:-/Applications/DevEco-Studio.app/Contents/tools/hvigor/bin/hvigorw}"
cd "$project"
"$hvigor" --mode module -p product=default -p module=entry@default assembleHap --no-daemon
