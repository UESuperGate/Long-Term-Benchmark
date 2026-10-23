#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
tools="$root/../tools"
hdc="${HDC:-$HOME/Library/OpenHarmony/Sdk/23/toolchains/hdc}"
target="${HDC_TARGET:-$($hdc list targets | sed -n '1p')}"
test -n "$target" || { printf 'no API23 ArkVM target\n' >&2; exit 69; }
device_hash="$(printf '%s' "$target" | shasum -a 256 | awk '{print substr($1,1,16)}')"
device_lock="/tmp/ltb-arkts-device-$device_hash"
build_lock="/tmp/long-term-benchmark-full-build.lock"
available_kib="$(df -Pk "$root" | awk 'NR == 2 { print $4 }')"
(( available_kib >= 8388608 )) || { printf 'refusing calibration below 8 GiB free\n' >&2; exit 75; }
mkdir -p "$root/provenance/build-logs" "$root/results"
python3 /Users/z1an/.codex/skills/migration-skill/scripts/validate_transition_parity.py \
  --android "$root/canonical/transitions.json" --arkts "$root/arkts/transitions.json" \
  --output "$root/provenance/arkts-transition-parity.json"
for role in base final; do
  node "$tools/verify_arkts_candidate.mjs" "$root/arkts/$role"
  python3 "$tools/with_device_lock.py" --lock "$build_lock" -- \
    bash "$tools/build_arkts_focused_candidate.sh" "$root/arkts/$role" "$root" \
    >"$root/provenance/build-logs/arkts-$role.log" 2>&1
  HDC_TARGET="$target" python3 "$tools/with_device_lock.py" --lock "$device_lock" -- \
    node "$tools/run_arkts_focused_candidate.mjs" --project "$root/arkts/$role" --migration "$root" \
      --role "$role" --output "$root/results/arkts-$role.json"
done
node "$tools/run_arkts_focused_controls.mjs" --migration "$root" --target "$target"
node "$tools/finalize_arkts_focused_calibration.mjs" "$root"
find "$root/arkts/base" "$root/arkts/final" -type d \( -name build -o -name .hvigor -o -name oh_modules \) -depth -exec rm -rf {} + 2>/dev/null || true
