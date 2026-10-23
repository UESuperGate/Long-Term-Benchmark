#!/usr/bin/env bash
set -euo pipefail
project="$(cd "${1:?usage: build_arkts_api23.sh <agent-project>}" && pwd)"
export OHOS_BASE_SDK_HOME="${OHOS_BASE_SDK_HOME:-/Users/z1an/Library/OpenHarmony/Sdk}"
cd "$project"
exec /Applications/DevEco-Studio.app/Contents/tools/hvigor/bin/hvigorw --no-daemon --mode module -p module=entry@default assembleHap
