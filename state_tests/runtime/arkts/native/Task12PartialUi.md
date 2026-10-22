# Task12 Native Partial Failure

Scope: `rr_state_008_leave_failure_is_partial` only. All files use the
independent `Task12Partial*` prefix. Existing task12 blank-case fixtures,
production, contracts, shared adapters, packager and executor are unchanged.

## Parent Integration

In the shared device packager's existing task12 native-UI branch, select this
installer **only** when `caseId === 'rr_state_008_leave_failure_is_partial'`:

```javascript
require('./state_tests/runtime/arkts/native/Task12PartialUi.install.cjs').install(work);
```

Retain the returned manifest in `nativeUIObserver`. For all other task12 cases,
keep the existing installer selection. Do not apply both installers to one
generated bundle. The standalone CLI is:

```sh
node state_tests/runtime/arkts/native/Task12PartialUi.install.cjs WORK
```

This validates generated lifecycle anchors, copies nine evaluator modules,
generates a dependency-free ES adapter module, and changes only generated
suite/bundle dispatch. Existing `evaluateCase`, source recorder, canonical row
file transport and evidence merger remain in use. No external CJS require is
introduced into the adapter factory. The native bridge API is
`bridge.runTask12PartialUI(caseSpec)`; standalone adapter exports `runCase(args)`.

Parent owns all device access. Parent packaged and executed the slice on the
device; the worker audited the retained evidence without operating the device.
Shared result merging remains parent-owned.

## Given And Boundary

Canonical inputs are unchanged: reason `Spam`, leave=true, report success and
leave failure. The real page starts with its own original presenter, service
and gateway. UI setup selects leave before input and enters the reason with
the actual TextInput. Basic IME onboarding is a parent environment prerequisite;
the probe does not accept keyboard permissions or privacy dialogs. Optional
real OS `hideTextInput()` housekeeping records its receipt/error and never
substitutes for native control observations.

After the original page is ready, a standard-JS explicit app-module import
binds `@bundle:<candidate>/entry/ets/features/ReportRoomFeature`. No relative
production import, second presenter construction or test-copy fallback is used.
Original methods are wrapped pass-through for observation only; return values,
Promise identities, receiver/arguments and throws are preserved.

The sole fixture write is to **existing own boolean result fields on that
original page's ReportRoomGateway**: `reportShouldFail=false`,
`leaveShouldFail=true`. These declared production outcome controls select the
canonical external result scenario. Nothing replaces `ReportRoomGateway`,
`ReportRoomService.execute`, `ReportRoomPresenter.submit/retry`, counters,
effects or page state. Those actual production methods execute and their
returns/effect records are retained. No real Matrix server/network request is
claimed: the migrated production gateway itself is in-memory. Missing writable
own outcome fields or missing source bindings stay NS, not synthetic failures.

The fixture refuses to reset counters, erase effects, or assign presenter
state. Before report it requires fresh zero counters/effects and original
uninitialized state, exact UI/receiver reason/leave, and established outcome
flags. It then clicks the real enabled report button once.

## Partial State And Retry

`after_report_before_retry_scroll` preserves the first post-report state.
When necessary a real Scroll `scrollSearch` reveals the actual retry control.
`after_event` is the canonical partial-failure checkpoint. Its original
reportAction/reportCalls/leaveCalls and real native retry enabled property
provide **all four expected fields**. No retry-success state replaces them.

To check `the successful report is remembered`, only the original gateway's
leave result flag is changed to success (report remains success). Business
state/counters/effects must remain unchanged during this boundary setup.
Then the real enabled `retry_leave_room` button is clicked. The invariant
requires unchanged report count, one further leave, original service
`shouldReport=false`, original gateway leave success, and actual success state.
This is a physical UI retry, never a direct retained presenter call.

The page remains subject to actual lifecycle/main-window guards before every
UI query: original create/foreground/top ability, Stage main-window identity,
native focused bundle/geometry and matching UIContext host. Current router
state must resolve to the original `pages/Index` route. Before/after/retry
checkpoints must share window ID, route, session, presenter, service and gateway
identities. Navigation away or a new receiver prevents replay through the old
object. Page actions only occur through scoped native controls.

Unknown route binding, lost foreground, missing/disabled retry, missing
original class, duplicate module receivers, or incomplete outcome evidence
remain NS with stage/error and partial frames. A disabled or absent retry does
not trigger direct method injection. Such cases cannot currently complete the
retry-based invariant, even if some expected fields already mismatch; any
early-failure policy change requires parent review, not this adapter.

## Verification And Limits

```sh
node --test state_tests/runtime/arkts/native/Task12PartialUi.test.cjs
```

Nine host scaffold regressions execute unchanged original feature code with
fake OS/UI transport; they are not native semantic results:

- Complete original production report/failure/physical retry, all expectations
  and invariant through the unchanged shared evaluator.
- Mutated retry that duplicates the original report operation produces FAIL.
- Navigation away prevents reuse of a retained presenter and remains NS.
- Missing/disabled retry or duplicate original-module class remains NS.
- Actual scroll transport must reveal an offscreen retry.
- Result fixtures change flags only; original gateway/service methods run.
- Provenance, page lifetime, receiver and physical retry evidence are mandatory.
- Installer retains production hashes, shared row transport and isolated scope.
- Other task12 cases are not intercepted.

## Device Evidence: task12-partial-real-retry

Parent's retained row is
`experiment_results/runtime_transition_20261019/device-calibration/task12-partial-real-retry/native-result.json`.
It reports PASS for `rr_state_008_leave_failure_is_partial`, canonical digest
`dee8902983851e344647af5dd57104c803a2a0b360e12bc23132b309bf88f01f`.
Replaying that raw observation through the unchanged independent adapter
reproduced all four expected fields and the invariant, with no unsupported
binding. This replay validates evidence interpretation, not another device run.

- `before_event` (sequence 7): actual reason `Spam`, leave selected,
  uninitialized action, zero report/leave calls, and real enabled submit.
- `after_event` (sequence 10): `leave_failed`, report calls 1, leave calls 1,
  real visible and enabled Retry. These are the canonical expected observations.
- `retry_boundary_recovered` (sequence 12): only the original leave-result
  flag changed; business state, counters and effects remained unchanged.
- `after_invariant_retry` (sequence 14): physical Retry reached the original
  service with `shouldReport=false`, state became success, report calls stayed
  1 and leave calls became 2. The only added gateway call was successful leave.

All canonical/retry checkpoints retain original window ID 115, route
`pages/Index`, presenter/service/gateway identity 1, focused candidate window,
matching Ability UIContext and postload original entry-module binding. Actual
input and toggle callbacks reached that receiver. No navigation away, second
presenter or direct injected submit/retry was used. The original page's inline
success state is observed; no additional navigation behavior is claimed.

The row is 256585 bytes with SHA-256
`76a2e759ca1f4a9f0c937dbb27d64a98824be7d333205d210b7dcd4d093803d2`,
matching `device-execution.json` and its process marker, execution nonce
`065022eb10d1f40af2df0c2124f5370e`. Transport records production unchanged.
Recorded production hashes are:

- `ReportRoomFeature.ets`:
  `9873db2a0739aed6dc61834d68e882cb09d0914a46d34557a33836bbe21909cc`.
- `pages/Index.ets`:
  `afc255061ee502421786983e618b8bfd37c05f17c44b28b9cac8991cadd3663a`.

This is a real device UI transition through the unchanged migrated production
presenter, service and in-memory gateway. Existing gateway outcome booleans
configure failure/recovery; **no Matrix network, server response or durable
persistence is tested**. This device replay required no scroll, so offscreen
retry/Scroll behavior remains host-transport coverage only. Other device or
candidate failures still retain NS diagnostics rather than relaxed assertions.

Parent repeated the same HAP with an independent fresh install in
`experiment_results/runtime_transition_20261019/device-calibration/task12-partial-real-retry-repeat/`.
The second raw row again has exactly `leave_failed`, report calls 1, leave
calls 1, enabled Retry, and the same successful-report-remembered invariant.
Its 241153 bytes have SHA-256
`f9da49e531cce104529510f2779ebfc6498cfe4becf8aa585d2b65d955fb8648`,
matching transport and nonce `c31cc6132fb697bbf233ed17bae76c00`.
Both transport records attest candidate absent before install and production
unchanged. Parent reports the independently retained strict validation again
at 10 pass / 0 fail / 0 NS for task12 final; the repeat does not overwrite the
primary report or count as a second canonical case. The worker's audit confirms
the two raw rows agree within the original in-memory gateway boundary above.
