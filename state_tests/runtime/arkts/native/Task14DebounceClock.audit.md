# Task14 Debounce Clock Audit

Read-only investigation, 2026-10-19. Only this independent note was added.
Existing Task14 device suite/installer/observer/tests remain frozen for parent
copy/build. No production, canonical, shared adapter, timer hook or device action.

## Conclusion

The existing evidence supports a **logical 300 ms debounce boundary**, not an
exact physical elapsed-time guarantee. Observing the original timer argument
and actual callback/request order is a useful native diagnostic, but is **not
yet an approved replacement** for `resolveAfterMs: 300`. Preserve case002 NS
until the parent approves a cross-platform observation interpretation or binds
an equivalent controllable scheduler. Never round, clamp or replace measured
wall time with 300, and never copy the expected value into observed.

A second, independent setup defect exists: the current shared ArkTS branch
starts its canonical update from `#old:example.org` / internal `resolving`, not
the canonical empty-address / `unknown` given. Adding timing evidence alone
must not turn that existing run into a scored case.

## Exact Contract

`benchmark_tasks/14_join_room_by_address/transitions.json:33`:

```json
{
  "caseId": "jr_state_002_update_trims_and_debounces",
  "given": { "address": "", "addressState": "unknown" },
  "event": { "name": "update_address", "value": "  #team:example.org  " },
  "expected": {
    "address": "#team:example.org",
    "addressStateBefore300ms": "unknown",
    "resolveAfterMs": 300
  },
  "invariants": ["each address change invalidates the previous resolution"]
}
```

Trace digest: `59cd4003c86f35637c4c99e7a655e5a3d670cb5754be4d104a4fc8a036f11d17`.
The JSON does not define whether `resolveAfterMs` means requested timer delay,
virtual scheduler time, or physical elapsed time. Therefore an adapter cannot
silently choose a weaker meaning. The production and original executable test
provide stronger evidence for the intended boundary than the field name alone.

## Immutable Production And Existing Proof

Android `v25.03.0^{commit}`:
`18b9593c147141974c542b6c06a33e770f01886a`, read with `git show` in
`_sources/element-x-android`.

`features/createroom/impl/src/main/kotlin/io/element/android/features/createroom/impl/joinbyaddress/JoinRoomByAddressPresenter.kt`,
`RoomAddressStateEffect`: reset internal state to Unknown, execute `delay(300)`,
then validate and call the resolver. `LaunchedEffect(fullAddress)` cancels the
previous address job. Kotlin's documented delay is a minimum wait, not exact
wall-clock execution; scheduling depends on the dispatcher.
[Official delay API](https://kotlinlang.org/api/kotlinx.coroutines/kotlinx-coroutines-core/kotlinx.coroutines/delay.html).

`state_tests/runtime/android/14_join_room_by_address/JoinAddressTest.kt:80`:
starts from empty/Unknown, sends the canonical edit, advances virtual time 299,
asserts zero requests and internal Unknown, advances 1, asserts exactly the
target alias request, and records `testScheduler.currentTime` as resolveAfterMs.
Only afterward it edits to another address and completes the stale request for
the invariant. `state_tests/runtime/android/common/Harness.kt:34-54` uses a
TestScope scheduler, `advanceTimeBy` and `runCurrent`; no rendered device elapsed
time is measured. The standalone alternative uses the same 299+1 boundary.
The official scheduler API identifies currentTime as virtual milliseconds.
[Official TestCoroutineScheduler API](https://kotlinlang.org/api/kotlinx.coroutines/kotlinx-coroutines-test/kotlinx.coroutines.test/-test-coroutine-scheduler/).
These documentation pages currently describe 1.11.0; the retained runtime
dependency report uses 1.10.2. The local executed harness is the decisive proof
of the clock actually used here, not an assumption about the newer dependency.

ArkTS final `entry/src/main/ets/features/JoinRoomByAddressFeature.ets`:
`updateAddress` lines82-99 trims, resets state and increments updateToken, then
awaits module-local `delay(ADDRESS_DEBOUNCE_MS)`. `delay` lines26-29 invokes the
runtime `setTimeout(resolve, milliseconds)`. After it returns, token checks
reject stale work and the original resolver boundary is reached. The resolver
timeout separately schedules 10000; DemoRoomAliasResolver separately waits120.
Original `entry/src/main/ets/pages/Index.ets:47-50` ALSO schedules a 300 ms UI
refresh outside the presenter call. Thus finding any 300 ms timer is inadequate.

Local SDK23 `ets/api/@internal/full/global.d.ts:629-647` documents setTimeout:
the argument is the requested delay, actual delay may be longer, and the API
returns a timer ID. `clearTimeout` lines689-699 cancels the timer in its owning
thread. These declarations do not guarantee that replacing a test-module
global intercepts the original app's timer binding, nor expose an advanceable
native test scheduler.

## Current Runtime Gap

Read snapshot of
`experiment_results/runtime_transition_20261019/reports/arkts_14_join_room_by_address_final.json`:

- Runtime is native Previewer ArkVM execution of transpiled production.
- case002 status is `not_scored`; exact resolveAfterMs is missing.
- `debounce_wall_clock.elapsedMs` is 302, with two resolver requests.
- `before_event.state` has address `#old:example.org`, addressState `resolving`,
  visibleAddressState `unknown`, resolveCalls1. Canonical given is not met.
- Its invariant records stale completion retaining the new address/Unknown;
  useful evidence, but not permission to substitute a different canonical given.

`state_tests/runtime/arkts/tasks12_15.cjs:542-562` produces that sequence: seed
old pending work, call c.before, then the canonical edit, then wall-clock probe.
`scripts/runtime_semantics/arkts_runtime.cjs:31` currently supplies Node's real
timers/Date to the production VM. No Task14 controllable-clock binding appears
in this checked-in call path. A host controllable clock reported elsewhere can
be reused only once its actual binding is identified; it does not establish a
clock for the original native app module. No claim is made that such a host
facility is absent from another workspace or pending parent work.

## What A Native Timer Probe Could Prove

An opt-in future probe could establish all of the following without replacing
business logic, if native interception is actually supported:

1. Cold original page, post-load original-module import, one real page receiver,
   canonical empty/Unknown given. Use the real input event and preserve its raw
   whitespace argument and resulting trimmed production address.
2. Observe the timer created synchronously INSIDE that original updateAddress
   call. Record actual receiver/edit identity, raw delay argument, returned timer
   ID and original callback. Separately classify the page's refresh timer and
   resolver timeout; do not select a timer by `delay === expected`.
3. Forward to the ORIGINAL setTimeout unchanged, wrap only the callback for
   ordered checkpoints, preserving callback receiver/arguments/return/throw and
   the original timer ID/clearTimeout relationship. Never fire manually, skip,
   delay, suppress or reschedule callbacks. Do not replace Date.now.
4. Record no resolver request at update return and immediately before the
   matching original callback; record callback execution and the actual
   resolver request for this edit afterward. Account for the Promise continuation
   between timer callback and resolver call. Actual callback order alone does
   not identify causality if concurrent unrelated work is present.
5. Observe internal state, not just visibleAddressState: the final visible
   projection stays Unknown even AFTER resolution begins unless Continue was
   requested. A UI Unknown label alone cannot prove pre-deadline internal state.
6. After the canonical measurement, perform a separate real edit and complete
   the older external request. Check same receiver, new address, non-stale result
   and no navigation. Resetting a presenter or pre-seeding old state before the
   canonical edit is not a valid replacement.

Record separate facts such as `requestedDelayMs`, `timerId`, callback/request
sequence, receiver/edit IDs, internal state and `measuredElapsedMs` with the
identified clock source. These are observations, not new contract fields to
silently map to resolveAfterMs. Global wrapping must be tested against the
original app realm; missing interception is NS. A wrapper in the test ABC or
the host-transpiled duplicate does not suffice. Restore descriptors in finally,
one cold process per case, and audit evaluator hashes.

## Insufficient Evidence And Counterexamples

- A wrong 100 ms debounce can fire at302 under load; elapsed302 or rounding it
  to300 would conceal the defect.
- The UI refresh timer can request300 while the actual resolver starts early.
- A cancelled or unrelated timer can request300 without any resolution.
- Two serial 300 ms timers request300 each but resolve only after600 logically.
- Sampling Unknown immediately after edit does not prove Unknown at299. Sampling
  just before a delayed callback is a boundary observation, not a physical299
  measurement. Neither alone proves the entire pre-deadline interval.
- The archived agent schedules300 but changes internal/visible state to
  Resolving immediately on a syntactically valid edit. Its patch's
  `updateAddress` and `scheduleResolve` illustrate why delay evidence must not
  overwrite an independently observed `addressStateBefore300ms` mismatch.

## Parent Decision Required

Preferred unchanged-contract path: equivalent deterministic scheduler evidence,
with t=299 no request/Unknown and t=300 actual request, plus stale-result
invariant. If only host-transpiled execution can provide it, label that scope
honestly; do not merge it as original-page native UI/timing proof without policy
approval. A native fake clock would be a separate scheduler fixture requiring
explicit approval and validation; it is not the passive probe described above.

Alternative for parent approval: document `resolveAfterMs` as the logical
debounce scheduling delay, and specify whether causal native schedule/dispatch
evidence is accepted as equivalent to Android's virtual299/300 test. This is an
observation-policy decision even if numeric expected values and case IDs stay
unchanged. It needs common cross-platform acceptance criteria and mutation
tests (early request, wrong delay, extra delay, wrong timer, stale response,
pre-deadline Resolving). Until approved and executed, emit diagnostic facts and
retain NS; no unilateral contract or comparator change is recommended here.

## Read Snapshot Digests

```text
benchmark_tasks/14_join_room_by_address/transitions.json
b333aa4d8a67464e05f24c50cd17a3a5ddf88f82d0560e5ea04af905b23610e1
state_tests/runtime/android/14_join_room_by_address/JoinAddressTest.kt
aa1012f72e17fec1feebf42136132055e7a83834684b4699f779faeda84376d2
final_dev_nodes/14_join_room_by_address_final_25_03_0/entry/src/main/ets/features/JoinRoomByAddressFeature.ets
8eea07d1993230e0d78ca08327fa43cacc04d57b4ffe53f4e146d79b88d26160
experiment_results/runtime_transition_20261019/reports/arkts_14_join_room_by_address_final.json
a6cf2e8e44d61282fe50c3312ad8cf1a4101444ae71957ff24976befe9a2d891
```

Reports may subsequently be replaced by parent merges. These hashes identify
the exact files read for this audit, not a lock on parent-owned report updates.
