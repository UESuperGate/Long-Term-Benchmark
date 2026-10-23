#!/usr/bin/env bash
set -euo pipefail
project="${1:?usage: build_android_agent_harness.sh <candidate>}"
test -f "$project/.benchmark-evaluator/PREPARED" || { printf 'hidden harness not prepared\n' >&2; exit 65; }
bash "$project/.benchmark-evaluator/android-harness/build.sh"
