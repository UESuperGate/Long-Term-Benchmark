# Task14 Independent Clock Fixture

Parent-approved host scheduler follow-on, 2026-10-19. This supplements the earlier
read-only `native/Task14DebounceClock.audit.md`; it does not claim native timing
or original-page UI evidence. Device files remain frozen. No device operation,
production change, canonical change, shared adapter edit, or primary promotion.

## Execution Boundary

`Task14Clock.cjs` binds original candidate `.ets` exports through the existing
TypeScript production loader. It injects a standalone `@sinonjs/fake-timers`
10.3.0 clock into that VM only. Process-global timers are unchanged. The only
generic loader extension is optional fourth argument `timerEnvironment`, limited
to set/clearTimeout, set/clearInterval and Date. Default three-argument calls and
the native generator's extracted `evaluateCase` remain unchanged.

The resolver is a controlled external gateway with pending real Promises.
All presenter state changes execute the candidate's original methods; no
presenter fields, methods, or domain algorithm are replaced.

1. Construct the original presenter and read empty address/internal Unknown.
   Verify every canonical given before dispatching the canonical whitespace edit.
2. Advance the isolated scheduler 299 ms. Read actual internal state and require
   zero resolver calls. Visible Unknown alone is not used as internal Unknown.
3. Advance one more millisecond. Require exactly one actual request for the
   trimmed alias. `resolveAfterMs` is recorded inside the gateway invocation as
   current virtual time minus event-start virtual time. It is not a timeout
   argument, expected value, or rounded wall-clock duration.
4. Only after canonical observations, edit another alias and settle the old
   pending response. Verify no old result/state/navigation is applied. Finish
   using original dismiss, release external responses, and discard this clock.

The 299+1 protocol matches the existing Android
`state_tests/runtime/android/14_join_room_by_address/JoinAddressTest.kt:80`
virtual TestScope boundary. This is `host_transpiled_production`, not ArkVM,
native UI, physical time, network behavior, or device scheduling proof.

## Negative Controls

`Task14Clock.mutations.cjs` generates disposable source copies of the original
feature with five precisely recorded mutations: wrong100, wrong600,
two300serial, stateResolvingearly, staleresponse. It retains original/mutant
hashes and exact substitutions, checks the original stays unchanged, and removes
temporary sources. Wrong/serial delays use actual request times (100/600/600);
late diagnostic advancement never overwrites the retained t=300 boundary.
Early Resolving fails the t=299 observation. Stale response fails the invariant
even when all canonical expected fields still match.

Tests also execute the archived agent patch reconstructed into a disposable
feature-only project. The same API-capability binding observes its real early
Resolving failure. Base's missing presenter is NS, not an inferred semantic
failure. Role metadata never drives evaluation.

## Reproduce And Review

```sh
node --test state_tests/runtime/arkts/Task14Clock.test.cjs
node state_tests/runtime/arkts/Task14Clock.cjs --source final_dev_nodes/14_join_room_by_address_final_25_03_0 --role final --output experiment_results/runtime_transition_20261019/task14-clock-review/arkts_14_final_clock.json
node state_tests/runtime/arkts/Task14Clock.mutations.cjs --output experiment_results/runtime_transition_20261019/task14-clock-review/mutations.json
```

`LTB_FAKE_TIMERS` may select another locally installed package; the report binds
the actual entry/package hashes and version. Missing scheduler/API/givens remain
unscored. `LTB_TYPESCRIPT` retains the existing loader override.

The independent report preserves all nine canonical IDs/digests. Only002 is
executed: final has 1 pass, 0 fail, 8 explicitly unexecuted NS rows. These other
rows are not changes to primary scores. The real device entry/DM failure remains
untouched. Parent review is required before selecting any supplementary row.
Reports retain source/call/checkpoint evidence, fixture/loader/contract hashes,
full canonical comparison and every case002 invariant; no native build claimed.
