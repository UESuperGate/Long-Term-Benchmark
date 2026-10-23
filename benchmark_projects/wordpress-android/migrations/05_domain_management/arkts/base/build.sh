#!/usr/bin/env bash
set -euo pipefail
project_dir="$(cd "$(dirname "$0")" && pwd)"
cd "$project_dir"
export OHOS_BASE_SDK_HOME="${OHOS_BASE_SDK_HOME:-/Users/z1an/Library/OpenHarmony/Sdk}"
exec /Applications/DevEco-Studio.app/Contents/tools/hvigor/bin/hvigorw --no-daemon --mode module -p module=entry@default assembleHap
