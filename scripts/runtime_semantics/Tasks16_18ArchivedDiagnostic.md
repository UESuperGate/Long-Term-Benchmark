# Task18 Archived Context Diagnostic

This is an evaluator-only reconstruction and packaging tool for the **existing**
task18 archived ArkTS agent. It does not run an agent, execute a device, calibrate
base/final, update a contract, modify candidate source, or merge a report.

Canonical OS channel recreation evidence is under independent audit. A ledger
write or production-class invocation does not establish an OS effect. Any later
device result is only the current adapter's diagnostic outcome until the actual
effect boundary is verified. Nothing here makes an outcome promotable.

## Commands

Run from the repository root. Every output directory must be new.

```sh
node scripts/runtime_semantics/Tasks16_18ArchivedDiagnostic.cjs \
  --audit-only \
  --output-dir experiment_results/runtime_transition_20261019/device-calibration/task18-archived-audit-NEW

node scripts/runtime_semantics/Tasks16_18ArchivedDiagnostic.cjs \
  --prepare-only --case ns_state_004_message_custom_copy \
  --output-dir experiment_results/runtime_transition_20261019/device-calibration/task18-archived-prepare-NEW

node scripts/runtime_semantics/Tasks16_18ArchivedDiagnostic.cjs \
  --build --case ns_state_004_message_custom_copy \
  --output-dir experiment_results/runtime_transition_20261019/device-calibration/task18-archived-copy-NEW
```

`--build` is an explicit packaging operation, not device execution. Existing
packager signing arguments `--signing-config FILE --signing-name NAME` are
forwarded when requested. For the picker UI diagnostic, select
`ns_state_003_message_picker_launch --native-ui`. An unavailable original agent
UI binding must remain NS; do not relabel or substitute the final page.

One case is packaged per invocation; there is no all-case device loop. The parent
may serially execute a built `package/device-build-report.json` using its existing
authorized device workflow. This tool has no serial, execute, merge, source
override, role override, or skip-calibration option. Temporary candidate and
packager workspaces are removed even on a failed reconstruction or package step.

## Provenance

The fixed inputs are the task18 base path from `task.json` and the original
`provenance/patches/arkts_18_custom_notification_sounds.patch` from
`new_tasks_opencode_minimax_m3_20261015_semantic_repair`.

1. Check patch bytes/SHA-256 against the published archive index and prior agent
   native report. Check canonical case IDs/digests without changing assertions.
2. Reject local base changes. Snapshot every base file, mode, length and SHA-256;
   confirm the copied base's Git tree equals the recorded repository commit's
   base tree. Ignored extra files and symlinks cannot silently enter the candidate.
3. Apply the original binary-safe patch exactly once in an isolated temporary
   repository, using `git apply --check --index --binary` followed by actual apply
   and a reverse check. No three-way merge, patch rewrite, or source repair.
4. Check all changed paths against the archived generated-file inventory. Match
   every retained task18 agent feature hash against its prior native manifest.
5. Record a complete reconstructed source manifest and Git tree, the original
   patch copy/hash, canonical hashes, archive references, command output, and
   current evaluator/bridge/packager hashes.
6. Packaging calls the existing `arkts_native_device.cjs` with `--role agent` and
   the reconstructed candidate as `--source`. Its call to `generate` supplies
   `sourceOverride`, so the generator preserves agent identity and does **not**
   apply the patch again. Verify the resulting role, sourceOverride, exact main
   source inventory, bundled feature hashes and original UI page hash if enabled.

The archived evaluation did not publish a full historical base manifest. The
new full-source snapshot is a current reconstruction audit, not a retroactive
claim of such a historical artifact. The prior native feature manifest provides
the independently retained code-hash comparison boundary.

Local verification found 19 base files, 35 reconstructed files (85,148 bytes),
20 changed paths, and all 11 prior native feature hashes matching. `prepare-only`
confirmed agent/sourceOverride identity without compilation or device execution.

## No Promotion

`run_arkts_device_matrix.cjs` still rejects agent execution. The existing strict
`apply_arkts_device_evidence.py` still accepts only calibrated-source base/final
evidence. Neither file is modified. This tool's report has
`reportMergeAllowed:false`, `freshAgent:false`, `calibrationPassed:false`,
`nativeRuntimeExecuted:false`, and `benchmarkSemanticMetric:null`.

Merging any later archived-agent device evidence requires a separately reviewed
strict reconstruction validator binding that execution/build to the immutable
base/patch/full-source evidence, all existing device nonce/transport checks, and
the independently audited business-effect boundary. Do not feed these artifacts
to an altered apply script that merely permits the string `agent`.

## Tests

```sh
node --test scripts/runtime_semantics/Tasks16_18ArchivedDiagnostic.test.cjs
```

Tests cover archive hash mismatch, dirty/ignored-extra base files, changed-path
and prior feature mismatches, protected output aliases, symlinks, cleanup, role
and sourceOverride identity, double-application claims, full-main/page hash drift,
and refusal of execution/promotion/bypass CLI options. They never use a device.
