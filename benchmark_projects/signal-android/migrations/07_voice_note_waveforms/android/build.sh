#!/usr/bin/env bash
set -euo pipefail
role="${1:?usage: build.sh <base|final>}"
root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
project="$root/$role"
[[ "$role" == base || "$role" == final ]] || { printf 'invalid role: %s\n' "$role" >&2; exit 64; }
gradle="${GRADLE_BIN:-$HOME/.gradle/wrapper/dists/gradle-8.14.3-bin/cv11ve7ro1n3o1j4so8xd9n66/gradle-8.14.3/bin/gradle}"
export ANDROID_HOME="${ANDROID_HOME:-$HOME/Library/Android/sdk}"
export ANDROID_SDK_ROOT="${ANDROID_SDK_ROOT:-$ANDROID_HOME}"
export JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home"
export PATH="$JAVA_HOME/bin:$PATH"
[[ -x "$JAVA_HOME/bin/java" && -x "$JAVA_HOME/bin/jlink" ]] || {
    printf 'Android Studio JBR is incomplete: %s\n' "$JAVA_HOME" >&2
    exit 69
}
gradle_runtime_jdk="${GRADLE_RUNTIME_JDK:-/opt/homebrew/Cellar/openjdk@17/17.0.18/libexec/openjdk.jdk/Contents/Home}"
[[ -x "$gradle_runtime_jdk/bin/java" && -x "$gradle_runtime_jdk/bin/jlink" ]] || {
    printf 'Gradle 8 compatibility JDK is incomplete: %s\n' "$gradle_runtime_jdk" >&2
    exit 69
}
available_kib="$(df -Pk "$project" | awk 'NR == 2 { print $4 }')"
(( available_kib >= 8388608 )) || { printf 'refusing Android build below 8 GiB free\n' >&2; exit 75; }
python3 - "$gradle" "$project" "$gradle_runtime_jdk" <<'PY'
import fcntl, subprocess, sys
gradle, project, runtime_jdk = sys.argv[1:]
with open('/tmp/long-term-benchmark-android-full-build.lock', 'a+') as lock:
    fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
    command = [gradle, f'-Dorg.gradle.java.home={runtime_jdk}', '-p', project, '--no-daemon', '--offline',
               ':app:assembleDebug', ':app:assembleDebugAndroidTest']
    raise SystemExit(subprocess.run(command).returncode)
PY
