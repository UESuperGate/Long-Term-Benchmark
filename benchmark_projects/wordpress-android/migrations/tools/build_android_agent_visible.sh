#!/usr/bin/env bash
set -euo pipefail
project="$(cd "${1:?usage: build_android_agent_visible.sh <agent-project>}" && pwd)"
task_id="${2:-}"
if [[ -z "$task_id" ]]; then
  if [[ -f "$project/_benchmark_inputs/requirement.md" ]] && grep -qi "unified support" "$project/_benchmark_inputs/requirement.md"; then
    task_id="02_unified_support"
  else
    task_id="01_pages_list"
  fi
fi
gradle="${GRADLE_BIN:-$HOME/.gradle/wrapper/dists/gradle-8.14.3-bin/cv11ve7ro1n3o1j4so8xd9n66/gradle-8.14.3/bin/gradle}"
export JAVA_HOME="${JAVA_HOME:-/Applications/DevEco-Studio.app/Contents/jbr/Contents/Home}"
export GRADLE_USER_HOME="$HOME/.gradle"
export ANDROID_HOME="${ANDROID_HOME:-$HOME/Library/Android/sdk}"
export ANDROID_SDK_ROOT="${ANDROID_SDK_ROOT:-$ANDROID_HOME}"
tools_dir="$(cd "$(dirname "$0")" && pwd)"
python3 "$tools_dir/prepare_visible_scaffold.py" \
  --task-id "$task_id" \
  --project "$project" \
  --migration "$tools_dir/../$task_id"
"$gradle" --no-daemon --project-dir "$project" assembleDebug
python3 "$tools_dir/record_visible_android_abi.py" \
  --task-id "$task_id" \
  --project "$project" \
  --output "$project/.benchmark-scaffold/visible-abi.json"
