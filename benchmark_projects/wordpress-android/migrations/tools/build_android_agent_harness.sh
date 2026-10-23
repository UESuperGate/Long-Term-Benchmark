#!/usr/bin/env bash
set -euo pipefail
project="$(cd "${1:?usage: build_android_agent_harness.sh <agent-project>}" && pwd)"
test -f "$project/.benchmark-evaluator/PREPARED" || { printf 'hidden agent harness not prepared\n' >&2; exit 65; }
python3 "$(cd "$(dirname "$0")" && pwd)/audit_hidden_android_harness.py" --project "$project"
gradle="${GRADLE_BIN:-$HOME/.gradle/wrapper/dists/gradle-8.14.3-bin/cv11ve7ro1n3o1j4so8xd9n66/gradle-8.14.3/bin/gradle}"
export JAVA_HOME="${JAVA_HOME:-/Applications/DevEco-Studio.app/Contents/jbr/Contents/Home}"
export GRADLE_USER_HOME="$HOME/.gradle"
export ANDROID_HOME="${ANDROID_HOME:-$HOME/Library/Android/sdk}"
export ANDROID_SDK_ROOT="${ANDROID_SDK_ROOT:-$ANDROID_HOME}"
exec "$gradle" --no-daemon --project-dir "$project" assembleDebug assembleDebugAndroidTest
