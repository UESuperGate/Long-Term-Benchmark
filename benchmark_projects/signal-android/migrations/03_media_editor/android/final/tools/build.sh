#!/usr/bin/env bash
set -euo pipefail
project="${1:-$(cd "$(dirname "$0")/.." && pwd)}"
output="${2:-$project/build}"
compiler="${COMPILE_KOTLIN_SLICE:-$(cd "$project/../../../tools" && pwd)/compile_kotlin_slice.sh}"
bash "$compiler" "$project" "$output" "2.2.20"
