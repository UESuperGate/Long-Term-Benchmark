#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
workspace="$(cd "$root/../../../.." && pwd)"
tools="$root/../tools"

available_kib="$(df -Pk "$root" | awk 'NR == 2 { print $4 }')"
if (( available_kib < 8388608 )); then
  printf 'refusing calibration with less than 8 GiB free\n' >&2
  exit 75
fi

bash "$root/materialize.sh"
for role in base final; do
  project="$root/android/$role"
  node "$tools/verify_immutable_sources.mjs" --project "$project" --repository "$workspace/_sources/signal-android"
  python3 "$tools/with_device_lock.py" --lock /tmp/long-term-benchmark-android-full-build.lock -- \
    bash "$tools/build_android_focused_candidate.sh" "$project" "$root"
  python3 "$tools/with_device_lock.py" --lock /tmp/long-term-benchmark-android-device.lock -- \
    node "$tools/run_android_focused_candidate.mjs" --project "$project" --migration "$root" \
      --role "$role" --output "$root/results/android-$role.json"
done

find "$root/android/base/build" "$root/android/final/build" -depth -delete 2>/dev/null || true
find "$root" -type f -name 'build.compile.log' -delete
find "$root" -type d \( -name .gradle -o -name .cache \) -depth -delete 2>/dev/null || true
