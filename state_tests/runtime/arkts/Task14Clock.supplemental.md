# Task14 Strict Single-Case Supplement

Approved scope: promote only original `not_scored`
`jr_state_002_update_trims_and_debounces` using the reviewed host-clock fixture.
This narrowly supports complete passing clock evidence on manifest-bound
base/final source locations; archived-agent packaging is not accepted here.
Other cases, including the real entry/DM invariant FAIL, are copied unchanged.

`Task14Clock.supplemental.cjs` independently verifies:

- All nine canonical IDs, order, trace digests, counts, exact comparisons and
  complete invariants. The full live contract hash must match the supplement
  and the primary native bundle's contract record, including givens/events.
- Matching task, role and canonical source location; original bundle candidate
  identity and hashes for every production module, matched to the incoming row.
- Exact reviewed fixture/loader paths and live hashes; configured clock entry,
  package hash and version. Report-supplied module paths are never imported.
- Real empty/unknown before-event state and raw canonical edit; zero requests
  at virtual299; the actual resolver timestamp and alias at virtual300; derived
  observations, ordered checkpoints, matching evidence and boundary records.
- A second actual production edit after canonical measurement, completion of
  the old response, unchanged unknown state, no stale room/navigation, and all
  invariant observations, not just success flags.
- A fresh isolated host production replay must exactly match the submitted row.
  This also rejects internally consistent fabricated calls or checkpoints.
- Original NS status and no prior clock promotion; no native/compile claims;
  no attempts to promote another case or overwrite an existing output file.

The output retains primary native evidence and compile/runtimeCompile metadata
without adding compile credit. Overall runtime is explicitly mixed per-case.
The promoted row is `host_transpiled_production`, never ArkVM/native UI. An audit
records both input artifact hashes, manifest/contract/source-bound provenance,
the validator hash, replay digest, original NS row, and hashes/statuses of all
eight untouched rows. Input artifacts are rehashed before writing. Output uses
exclusive creation and cannot overwrite primary, supplement, or earlier output.

```sh
node --test state_tests/runtime/arkts/Task14Clock.supplemental.test.cjs
node state_tests/runtime/arkts/Task14Clock.supplemental.cjs --primary experiment_results/runtime_transition_20261019/context-repair/prior-reports/arkts_14_final_before_clock_supplement.json --supplemental experiment_results/runtime_transition_20261019/task14-clock-review/arkts_14_final_clock.json --output experiment_results/runtime_transition_20261019/task14-clock-review/arkts_14_final_clock_revalidated.json
```

Tests always use the retained pre-supplement archive above and disposable JSON
mutations. They do not read the mutable primary or require an environment
override, so adopting the validated output cannot invalidate their fixture.
An already-promoted input is still deliberately rejected by the merger. The
example output must not already exist; use a fresh filename for another replay.

## Actual Mixed Scope

The parent's `task14-clock-review/arkts_14_final_clock_parent_validated.json`
binds its primary-input audit to the preserved archive, not the mutable reports
path. Its 8 pass / 1 fail / 0 unscored result combines these distinct scopes:

| Cases | Actual execution and observation scope | Result |
| --- | --- | --- |
| 001 | Original candidate device UI plus production state | FAIL: existing DM action invariant |
| 003, 007 | Original candidate device UI plus production state | PASS |
| 004, 005, 006, 008, 009 | Retained native Previewer ArkVM execution, production-domain observations | PASS |
| 002 | Host-transpiled original production with isolated virtual scheduler | PASS |

The report runtime is `mixed_per_case_native_and_host_transpiled_production`.
This is not nine device-UI tests or nine ArkVM tests. Case002 proves the virtual
299/300 boundary and stale-response handling, not physical/native timing or UI.
The five domain-observation rows do not acquire device-UI coverage through this
merge. Entry's real FAIL remains unchanged; 8/9 is not all-final-pass.

Existing `compile.passed: null` (candidate application not compiled by that
primary runner) and `runtimeCompile.passed: true` (generated JS bundle/Hypium
wrapper) remain exactly as recorded. Per-case device build evidence is retained
in its own rows. The host supplement earns no application/native compile credit.

No production, canonical, shared adapter, public matrix, primary report, device
fixture or device execution is changed by this merger. Parent adoption remains
a separate operation; producing this validated output does not copy it into the
primary location.
