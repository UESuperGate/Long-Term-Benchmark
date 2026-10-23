#!/usr/bin/env bash
set -euo pipefail

project="${1:?usage: build_android_agent_visible.sh <agent-project>}"
project="$(cd "$project" && pwd)"
empty="$project/build/visible-empty-evaluator"
mkdir -p "$empty"
tools_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPILE_KOTLIN_SLICE="$tools_root/compile_kotlin_slice.sh" \
EVALUATOR_SRC="$empty" \
  bash "$project/tools/build.sh" "$project" "$project/build/visible"
