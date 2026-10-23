#!/usr/bin/env bash
set -euo pipefail

project="${1:?usage: build_android_agent_harness.sh <agent-project>}"
project="$(cd "$project" && pwd)"
prepared="$project/.benchmark-evaluator/PREPARED"
test -f "$prepared" || { printf 'hidden agent harness not prepared\n' >&2; exit 65; }
tools_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
attempts="$project/.benchmark-evaluator/binding-attempts.tsv"
node - "$prepared" > "$attempts" <<'NODE'
const fs = require('fs');
const prepared = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
for (const candidate of prepared.bindingContract?.candidates ?? []) {
  process.stdout.write(`${candidate.id}\t${candidate.sourceDirectory}\t${candidate.probeMainClass}\n`);
}
NODE
test -s "$attempts" || { printf 'prepared Android binding candidates are missing\n' >&2; exit 65; }

selected_id=""
selected_probe=""
while IFS=$'\t' read -r binding_id source_directory probe_main_class; do
  source="$project/.benchmark-evaluator/$source_directory"
  test -d "$source" || { printf 'binding source missing: %s\n' "$source" >&2; exit 65; }
  attempt_log="$project/.benchmark-evaluator/binding-attempt.log"
  if COMPILE_KOTLIN_SLICE="$tools_root/compile_kotlin_slice.sh" \
     EVALUATOR_SRC="$source" \
     bash "$tools_root/build_android_harness.sh" "$project" >"$attempt_log" 2>&1; then
    selected_id="$binding_id"
    selected_probe="$probe_main_class"
    cat "$attempt_log"
    find "$attempt_log" -type f -delete
    break
  fi
  printf 'Android action bridge %s is not compile-compatible with this candidate; trying the next public ABI.\n' "$binding_id"
  find "$project/build" -depth -delete 2>/dev/null || true
  find "$attempt_log" -type f -delete
done < "$attempts"
find "$attempts" -type f -delete

if [[ -z "$selected_id" || -z "$selected_probe" ]]; then
  printf 'no Android production action bridge compiled against the candidate\n' >&2
  exit 65
fi

node - "$prepared" "$selected_id" "$selected_probe" <<'NODE'
const fs = require('fs');
const [preparedPath, selectedBinding, probeMainClass] = process.argv.slice(2);
const prepared = JSON.parse(fs.readFileSync(preparedPath, 'utf8'));
prepared.probeMainClass = probeMainClass;
prepared.selectedBinding = selectedBinding;
prepared.bindingSelection = 'first_compile_compatible_public_action_bridge';
fs.writeFileSync(preparedPath, `${JSON.stringify(prepared, null, 2)}\n`);
NODE
printf 'Selected Android production action bridge: %s (%s)\n' "$selected_id" "$selected_probe"
