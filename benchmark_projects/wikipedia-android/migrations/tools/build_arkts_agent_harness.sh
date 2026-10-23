#!/usr/bin/env bash
set -euo pipefail
project="${1:?usage: build_arkts_agent_harness.sh <candidate>}"
test -f "$project/.benchmark-evaluator/PREPARED" || { printf 'hidden harness not prepared\n' >&2; exit 65; }
bash "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/build_arkts_api23.sh" "$project"
