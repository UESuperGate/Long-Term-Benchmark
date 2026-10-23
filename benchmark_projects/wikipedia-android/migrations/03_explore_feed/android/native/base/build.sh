#!/usr/bin/env sh
set -eu
project_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
gradle_bin=${GRADLE_BIN:-$HOME/.gradle/wrapper/dists/gradle-8.14.3-bin/cv11ve7ro1n3o1j4so8xd9n66/gradle-8.14.3/bin/gradle}
python3 - "$gradle_bin" "$project_dir" <<'PY'
import fcntl, shutil, subprocess, sys
gradle, project = sys.argv[1:]
if shutil.disk_usage(project).free < 8 * 1024 ** 3:
    raise SystemExit("refusing disk-heavy Android build below 8 GiB free")
with open("/tmp/long-term-benchmark-android-full-build.lock", "a+") as lock:
    fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
    raise SystemExit(subprocess.run([gradle, "-p", project, "--no-daemon", "--offline", ":app:assembleDebug", ":app:assembleDebugAndroidTest"]).returncode)
PY
