# Task15 First Submit

Scored UI scope: `ad_state_005_first_submit_confirms` / `first_submit_confirms`.
The evaluator also captures case001 settings entry and case006 confirmation
as partial diagnostics only. Neither diagnostic can promote its case to PASS.
Evaluator installation changes no production, canonical, shared adapter,
packager or executor. The separately authorized production repair and actual
device outcomes are recorded in
`experiment_results/runtime_transition_20261020/task15_repair/v2/README.md`.

## Parent Wiring

After the device bundle packager has generated `entry/src/test/native-bundle.js`
and `NativeBundle.test.ets`, call:

```javascript
const { install } = require('./state_tests/runtime/arkts/native/Task15NativeUi.install.cjs');
const task15UiManifest = install(work);
```

Or run `node state_tests/runtime/arkts/native/Task15NativeUi.install.cjs WORK`.
Retain the returned fixture hashes/binding/production hashes in build provenance.
Run this instead of other native-UI installers for this case. The installer
validates exact generated lifecycle anchors before writing. It edits generated
test files only and verifies all production files stayed byte-identical.

The installer copies nine evaluator modules and generates
`Task15NativeUiAdapter.js` from dependency-free `Task15NativeUi.adapter.cjs`.
Generated `native-bundle.js` imports its `runTask15Case`; there is **no external
CJS require** and no new `adapterFactories` registration requirement. Only the
selected case is dispatched to this adapter. Other cases retain the existing
adapter. Existing `evaluateCase`, source recorder, checkpoints, `persistRow`,
fresh-device row transport and evidence merger are unchanged.

The native bridge method is `bridge.runTask15UI(caseSpec) -> raw UI result`.
The standalone adapter API is `runCase(args)`, with the same `taskId`,
`caseSpec`, `native`, `trace`, and `load` inputs as shared adapters. The parent
does not need to add a shared `tasks12_15.cjs` branch when using this installer.

`Task15NativeUiSuite.ets` uses static UiTest imports; the DeviceTestRunner must
lazy-load the generated suite after `onRun`. Original production import is
standard-JS `import(url)` only **after** actual settings root, entry click,
candidate window and visible original password form have been observed:
`@bundle:<candidate bundleName>/entry/ets/features/AccountDeactivationFeature`.
No `../main` import, test-copy fallback, or prelaunch import is allowed.

Startup uses `Task15LaunchNative.js` OS ports and `Task15Launch.js` lifecycle
guards. An actual application lifecycle listener and AbilityMonitor are
registered before `startAbility`. Its returned Promise does not imply window
readiness. A readiness poll stops as soon as all checks pass, with a 6-second
poll budget and at most 40 attempts (up to 150ms between failed observations).
Every attempt/error is retained; no fixed long sleep substitutes for evidence.
Readiness requires original cold-create/foreground callbacks, matching top
ability, observed WindowStage main-window ID equal to `getLastWindow` ID,
matching UIContext host, focused UiTest bundle and main-window geometry, plus
visible Settings/Notifications root and enabled deactivation entry. The case001
diagnostic requires only the root: an absent entry is retained as a native
query result, not misclassified as readiness failure or a negative capability
response. These
main-window checks run again on subsequent UI reads; canonical frames retain
`windowIdentity`. Lifecycle registrations are removed on success or failure.
Missing/foreign environments remain NS without importing production or
performing UI fixture actions. This repairs the first native run's race where
the initial window query threw immediately after `startAbility` returned.

## Runtime Evidence

Case001 launches the unchanged settings page, records a prelaunch boundary
explicitly marked `uiObserved:false`, and reads the actual root/entry controls
and foreground main-window identity after launch. It does not open the form,
import the original class, construct a presenter, or inject a capability.
Only a visible entry may produce partial `deactivateEntryVisible:true`.
Absent entry does not establish that the original capability call settled.
Native destructive styling and the unsupported-server invariant remain
unobserved. Source `.fontColor` is not a native style observation. The adapter
registers source provenance without invoking a test-copy presenter and returns
explicit unsupported evidence regardless of entry presence.

The unchanged page owns `AccountDeactivationPresenter` and `DemoAccountService`.
Pass-through observers capture native callbacks to `setEraseData`,
`setPassword`, and `deactivateAccount` on one actual presenter receiver. They
also observe the original service's `deactivateAccount` method; no replacement
service, scripted response, constructed presenter, or SDK fake is installed.
Original return/Promise identity and throws are preserved; `returned` means
the synchronous call returned, not that its Promise settled.

UI setup toggles erase first, then calls the real password Component's
`inputText('secret')`. Parent has completed Celia Basic IME onboarding on the
device; the probe itself never accepts keyboard privacy dialogs. Loss of the
candidate window, duplicate selectors, input failures and missing observers
stay NS with stage/error/stack/code/receiver diagnostics.

The `task15-first-submit-lifecycle` device run established all three givens on
one original receiver, including actual incremental `setPassword` callbacks
ending in `secret`. Native submit stayed present/visible but `enabled=false`
in both before-event and failure frames. This is not evidence of unfinished
input or an absent control. The source binds enabled to a method on a plain
presenter field, so stale reactive evaluation is a plausible production
cause, not yet a proven diagnosis. No re-render or alternate event is injected.

After input, the probe retains `fixture_after_password` and polls the actual
submit for up to 2 seconds / 10 attempts, stopping early on real readiness.
If it stays disabled, the real before-event frame is retained and the event
remains unexecuted/NS. Diagnostic `submitEnabledRead` calls the original pure
method on the captured receiver and is explicitly separate from native
enabled; it never substitutes for the UI property. Passive `renderCalls`
record only actual page evaluations of that method, not evaluator reads.

Password text can be masked. The canonical password is proven by the exact
native input receipt, completed original `setPassword` call and real receiver
field, not by interpreting asterisks. Erase is checked against the native
toggle and actual receiver. `before_event` must contain every canonical given
on that receiver before an enabled native submit click. `after_event` reads
actual action and `receiver.service.requestCount` and queries the original
confirmation message, Confirm button and Cancel button. No confirm click is
sent. Absence of the queried confirmation controls is observed false, not NS.

The no-destructive-request invariant uses request counts at both checkpoints,
at original method entry/return, and the real service's call log tied to that
receiver's service identity. Full expected fields are `action`, `requestCount`,
and `confirmationVisible`; the shared evaluator retains mismatches as FAIL.
Missing source hashes, given fields, unique receiver, private service field
access or event bindings remain NS, never feature-absence FAIL.

## Verification

```sh
node --test state_tests/runtime/arkts/native/Task15NativeUi.test.cjs
```

Eighteen host scaffold tests execute the unchanged production feature with fake
UiTest transport. They cover full canonical evaluation, masked password,
missing-dialog FAIL, early-service-call mutation FAIL, duplicate ABC class NS,
ignored-input NS, keyboard error diagnostics, source/given/identity guards,
Promise/throw preservation, installer isolation and old-case dispatch. Startup
tests cover delayed foreground/window/root readiness, absent environments,
wrong top ability/window ID/bundle/focus, bounded exhaustion and cleanup.
Submit readiness tests preserve a permanently disabled UI as NS even when
the production method returns true, and permit progress only when the actual
native control eventually reports enabled.
These are not device semantic results. HAP compilation and the actual device
run results are separate from these host tests. The authorized v1/v2 first-submit
device runs passed, without changing the business feature. Case006's real
confirmation diagnostic observes one original request and settled Success,
but no simultaneous natural Loading/modal/input-routing proof: it stays NS.
The diagnostic carries the actually bundled old contract digest, not the
parent-staged traceSchemaVersion2 invariant revision. No loading/failure/retry
PASS is claimed by this slice.

The additional remaining-NS audit is recorded in
`experiment_results/runtime_transition_20261020/task15_repair/remaining_ns_audit/REVIEW.md`.
Its entry HAP is compile-only until the parent allocates the device. The
original page uses a local immediate Demo service, not the Android Matrix
client's external request. No held business Promise, artificial timer,
substituted service, or wrong-password fixture may manufacture the canonical
Loading/Failure givens for cases006/008/009.
