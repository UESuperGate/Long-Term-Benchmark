#!/usr/bin/env bash
set -euo pipefail
project="${1:?usage: build_android_agent_visible.sh <candidate>}"
gradle_bin="${GRADLE_BIN:-$HOME/.gradle/wrapper/dists/gradle-8.14.3-bin/cv11ve7ro1n3o1j4so8xd9n66/gradle-8.14.3/bin/gradle}"
"$gradle_bin" -p "$project" --no-daemon --offline :app:assembleDebug
