#!/usr/bin/env sh
set -eu
project_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
gradle_bin=${GRADLE_BIN:-$HOME/.gradle/wrapper/dists/gradle-8.14-bin/38aieal9i53h9rfe7vjup95b9/gradle-8.14/bin/gradle}
"$gradle_bin" -p "$project_dir" --no-daemon classes writeRuntimeClasspath
