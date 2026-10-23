#!/usr/bin/env sh
set -eu
project_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
gradle_bin=${GRADLE_BIN:-$HOME/.gradle/wrapper/dists/gradle-8.14.3-bin/cv11ve7ro1n3o1j4so8xd9n66/gradle-8.14.3/bin/gradle}
"$gradle_bin" -p "$project_dir" --no-daemon --offline :app:assembleDebug :app:assembleDebugAndroidTest
