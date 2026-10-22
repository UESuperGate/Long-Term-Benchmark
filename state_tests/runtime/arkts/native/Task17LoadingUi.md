# Task17 Natural Loading UI Probe

Scope: only `pm_state_001_open_loading`, canonical digest
`c15a7e08ce803419b47ba43d877c935d394b82405a80803a728ad94df2daeceb`.
No production, contracts, shared packager/executor/Tasks16_18 or reports changed.
No device operation or HAP compilation was performed by this worker.

Parent's first HAP build reached `arkts-no-ns-as-obj` in the `.ets` suite when
passing the Preferences namespace as an object. The evaluator-only repair
moves that import and handoff into `Task17LoadingNativeSdk.js`: it forwards the
exact native SDK object and original probe return, without an API wrapper,
clone, fake or substituted implementation. The `.ets` suite passes no namespace
value. The independent installer includes this JS module and its declaration;
shared packaging remains unchanged. Native rebuild verification is parent-owned.

## Feasibility And Uncertainty

The original `Index.openPinnedMessages` changes its own screen, invokes its
original presenter, synchronizes state immediately, and synchronizes again on
completion. The original presenter sets Loading before awaiting the original
repository. The repository really calls native Preferences get/read and, on
a cold empty store, its original put/flush initialization. There is no API
needed or used to hold a request pending.

This establishes an observable original asynchronous call boundary. It does
**not** guarantee a visible Loading frame. Preferences can finish before a
frame displays loading. The native result remains NS if that happens; source
inspection or a host Promise schedule cannot prove that the device rendered
the canonical state.

## Independent Runtime Path

1. Fresh-install original app, no persistence seed or injected service result.
2. Original AbilityMonitor/ApplicationContext lifecycle and matching main
   window/UIContext/route checks, bounded root readiness, actual Design team
   room, pinned banner and enabled Open, list closed.
3. Only after the real room is ready, import original app exports at
   `@bundle:<bundle>/entry/ets/features/PinnedMessagesFeature`. No static
   test-copy import, second presenter or repository construction in the probe.
4. Install original pass-through `Task17LoadingObserver` on presenter and
   repository, including its original persistence method. Keep original
   receiver, arguments, errors and Promise identities. Do not instrument the
   actual Preferences module or its native Promises. Use the readback proof
   below with the exact original AbilityContext, not ApplicationContext or JSON.
5. Physically click original enabled Open. The optional observer hook registers
   the frame sampler at the original presenter's synchronous return. No business
   state, service method, store result or Promise is replaced.
6. Sample up to eight actual `UIContext.postFrameCallback` callbacks using
   `onFrame` and `onIdle`, scoped original inspector tree and real
   `getComponentUtils().getRectangleById`. Preserve raw trees, geometry,
   current original presenter state, original call records and window/route.
   No held SDK request, scheduling fake, production sleep or layout/state
   forcing is used. Native API frame registration may itself request a frame;
   it does not hold I/O or imply a minimum loading duration.
7. A qualifying frame must simultaneously show visible, positive-sized,
   in-window `pinned_messages_loading` and `pinned_messages_back` nodes, original
   presenter Loading, single original presenter/repository and same window/route.
   Method-return Loading alone, a settled list, hidden node or unobserved
   layout is insufficient. Missing a frame retains all diagnostics as NS.
8. Click actual enabled Back and verify the same room title, banner, Open and
   focus label in the original page/window. This checks the canonical room
   parent through actual UI return; it does not claim a distinct router entry
   or fabricate a navigation-stack object.

`nativePromisePending` remains `unproven`: no callback ordering is used to
claim unresolved native I/O. Existing observer settlement handlers remain
pass-through instrumentation and can add scheduling overhead. A registration
error is recorded without changing the production return. Disposal restores
descriptors and makes outstanding frame callbacks inert.

## Scoring And Evidence

The unchanged expected fields are derived only after all bindings and a
qualifying original frame are observed:

- `screen=pinned_messages`: actual visible Loading and Back branch in the
  original page, not a standalone presenter projection.
- `listState=loading`: actual original presenter's state at that same frame.
- `effects=[open_pinned_timeline]`: the actual single original repository
  operation reached by the physical Open, with the same presenter/Context.
- Invariant: actual Back returns to the original room surface and focus.

If complete loading evidence exists but Back produces a different room/focus,
the invariant is recorded false for the shared evaluator. If the canonical
loading frame cannot be observed, the result is NS rather than a guessed FAIL.
Observer/call/native-frame diagnostics remain in `evidence.nativePageTransition`.
An original successful store read is not mislabeled as Matrix server I/O.

## Parent Build Wiring

Independent installer:
`state_tests/runtime/arkts/native/Task17LoadingUi.install.cjs`.
API: `install(work)`; CLI accepts the generated workspace path. It checks
production hashes before/after, modifies only generated evaluator bundle/suite,
embeds the dependency-free adapter, and preserves shared `evaluateCase`,
`persistRow`, execution nonce and canonical transport.

In the parent-owned task16/17/18 installer selector, add only this selection
before the shared Tasks16_18 fallback:

```javascript
taskId === '17_pinned_messages' && caseId === 'pm_state_001_open_loading'
  ? 'Task17LoadingUi.install.cjs'
  : /* existing selection */ existingInstaller;
```

Do not apply both this installer and Tasks16_18 to the same generated bundle.
No shared-file edit is included in this handoff. After that parent-owned wiring:

```sh
node scripts/runtime_semantics/arkts_native_device.cjs \
  --source final_dev_nodes/17_pinned_messages_final_0_5_3 \
  --task 17_pinned_messages --role final --fixture bundle \
  --case pm_state_001_open_loading --native-ui \
  --output-dir experiment_results/runtime_transition_20261019/device-calibration/task17-natural-loading
```

Parent supplies the existing local signing arguments if required, then uses
the existing fresh-device executor serially. The command builds HAPs but does
not itself run the device. Do not use `--prepare-only` then manually install
into its reported workspace: the shared helper removes that temporary folder.

Bridge: `runTask17LoadingUI(caseSpec)`; core probe:
`runTask17LoadingUi(caseJson,bundleName,driver,ON,launch,preferences)`.
No external CJS require is added to the shared adapter factories.

## Device Audit: JS SDK Build

Parent's `task17-natural-loading-js-sdk` HAP compiled and ran on device. Raw
evidence is retained unchanged at
`experiment_results/runtime_transition_20261019/device-calibration/task17-natural-loading-js-sdk/native-result.json`:
63042 bytes, SHA-256
`c9e6f957bac7537127eb63cb0749bd8bd8c67fcc0a432007978f2ebe9efb12cf`,
matching `device-execution.json`, nonce `87e2cfb2c0e6b6c7b5838b3905d29df8`.
Transport records fresh installation and production unchanged. Result is NS.

Observed, without inference:

- Explicit original module import succeeded after room readiness. One original
  presenter and one original repository are observed, same AbilityContext,
  `singlePresenterCallChainObserved=true`. The real UI Open/Back receipts are
  sequences 2/4; window 135 and `pages/Index` persist throughout.
- Original presenter enters from idle; original repository enters/returns with
  Loading, then fulfills. Presenter later fulfills as filled with `$rules`
  and `$launch`. The actual settled list is visible. Physical Back returns to
  Design team with the same `12 members` focus label. This is genuine original
  entry behavior, not a duplicate-class or wrong-Context failure.
- `bindings.getPreferences.available=false`, reason `Original method descriptor
  is not observable`; there are no intercepted SDK calls. The old evidence
  lacks descriptor attributes, so it cannot distinguish absent, inherited,
  accessor or non-configurable descriptors. Native SDK call interception remains
  unproven, not inferred from successful repository completion.
- The sampler posted one callback but both `onFrame` and `onIdle` failed at
  unconditional `JSON.parse` with `SyntaxError: Unexpected Text in JSON: Invalid
  Token`. It retained zero frames and did not save the raw return. This is a
  transport/diagnostic defect: it proves neither absence nor presence of a
  rendered Loading frame. Native I/O pending state remains unproven.

Evaluator-only repair after audit:

- Preserve each inspector return's exact string or JSON-serializable object,
  `rawType`, parse result and errors. Accept object transport directly; parse
  strings only. Invalid text is not converted into a tree, and errors no longer
  discard available same-frame route, layout or presenter evidence.
- Retain read-only SDK descriptor diagnostics: own configurable/writable/value
  attributes, inherited descriptors, export keys, readable method type and
  default descriptor. No descriptor is made writable, no Proxy/replacement SDK
  is installed and no alternative API is silently selected.
- At that revision, the adapter's native SDK, same-receiver, Context, visible-layout and canonical
  frame requirements remain unchanged. Missing SDK binding still means NS,
  even if the next run successfully transports a Loading inspector frame.

The worker neither changed this raw row/report nor reran the device. Parent
can rebuild the same independent installer to collect the newly retained raw
transport and descriptor evidence. The historical result stays NS.

## Equivalent Native I/O Proof: Readback Revision

Parent's subsequent `task17-natural-loading-raw-frame/native-result.json`
contains six actual frames, with no inspector parse errors. Three samples
(first onIdle, second onFrame/onIdle) simultaneously record original presenter
Loading, visible loading/back nodes, loading size 1308 by 2394 and Back size
238 by 140. The first frame instead still shows the room; the last two show
the original presenter already filled and cannot supply canonical Loading.
Real Back returns to the original room. Thus natural native Loading is now
observed, not hypothesized from method-return timing.

That historical row remains NS: native `getPreferences` has an own function
descriptor with `writable=false`, `configurable=false`. Its 870767 bytes have
SHA-256 `4daaeee8d1a7eac5880a01900d8eba4c3d880730b25c9ebca66ebef7245e4244`,
matching transport nonce `e40edc721f8dc17520f5601e9a9ca2a0`. No raw row or
aggregate was changed, and no readback evidence is retrofitted into that run.

The new isolated evaluator revision replaces unobservable SDK-hook evidence
with a stronger runtime persistence witness, not with source-only inference:

1. Before physical Open, call real Preferences `getPreferences`, `has` and
   `get` with the exact monitored AbilityContext. Require the original
   `element_x_pinned_messages` / `room_design_pinned_events` key to be absent.
   Never clear, seed, put or flush. Existing data is NS. This cold fixture is
   compatible with the unchanged room-timeline/list-closed GIVEN.
2. Click original Open and preserve the same natural-frame requirements. The
   actual repository's empty-store branch initializes its own defaults and
   invokes its original `persistPinnedState`. Pass-through observation records
   exact input rows, same repository/Context, successful completion and the
   original `openPinnedTimeline` resolved rows. No native Promise is intercepted.
3. After original persist, repository open and presenter open have all fulfilled,
   preserve that completed call snapshot. Only then call the real SDK's
   `removePreferencesFromCache`, followed by `getPreferences`, `has` and `get`
   with the identical AbilityContext. This evicts the SDK cache, not stored
   preference data. No original operation is kept pending or retriggered.
4. Require the reopened key to exist and its full ordered eventId/sender/body
   rows to equal the original persistence arguments, original repository return
   and actual presenter collection. Require all seven read/evict/read receipts,
   matching scope/store/key, completed original call ordering, and zero evaluator
   preference-data writes. Cache-only data or missing flush cannot satisfy this
   proof after eviction. SDK failures/missing APIs remain NS, not substitutions.
5. Preserve the actual Back invariant and all native loading/layout/context
   checks. Readback completion never substitutes for the earlier canonical frame.

`Task17LoadingReadback.js` contains only read/has and post-completion cache
eviction. SDK descriptors are not changed, and SDK operations are not wrapped.
Original presenter/repository Promise identities remain unchanged. The pre-read
can warm the Preferences cache and shorten naturally displayed Loading; this
is disclosed measurement overhead, never permission to delay I/O or relax the
required frame. If no qualifying frame is captured, the run still remains NS.

New host negatives cover a preexisting key (no action/clearing), missing durable
flush, wrong reopened contents, wrong Context/scope, omitted cache eviction,
bad operation order, absent pre-eviction completion, different repository,
and mismatched original returned/presenter rows. The independent installer
includes the helper. Parent can use the same existing build command/selector
for a new fresh run; no shared-file change is needed. Device success is not
claimed by these host checks.

## Device Readback Result and Repeat Limitation

The fresh `task17-natural-loading-storage-readback/native-result.json` records
an actual PASS for `pm_state_001_open_loading`: `screen=pinned_messages`,
`listState=loading`, `effects=[open_pinned_timeline]`, and the real Back-to-room
invariant passes. The original same-page presenter, repository and actual
AbilityContext execute the transition. One natural onIdle sample simultaneously
contains presenter Loading, visible loading/back nodes and positive rectangles.
The absent-before/native-cache-reopen proof described above completes with the
original persisted rows, zero evaluator data writes and no SDK interception.
This is real native Preferences/UI evidence, not Matrix network evidence or a
claim that a native I/O Promise was observed pending.

Parent reported strict application of this first result into primary as
9 PASS / 0 FAIL / 0 NS. That retained first-run result is **not stable calibration**:
the independent fresh `task17-natural-loading-storage-readback-repeat` is NS,
not FAIL. Both of its natural samples already have presenter Filled; neither
contains a qualifying same-page Loading frame. Completed persistence and Back
observations cannot fill that missing canonical observation. First PASS remains
a fact, but `reproducibilityIncomplete=true` must accompany its use, with the
repeat NS linked in primary diagnostics by the parent.

See [Task17LoadingUi.reproducibility.md](Task17LoadingUi.reproducibility.md)
for the raw frame comparison, artifact hashes and diagnostic handoff. The older
`task17-natural-loading-js-sdk` and `task17-natural-loading-raw-frame` runs remain
NS without retrospective rescoring or readback evidence backfill. No delay,
I/O gate, relaxed assertion or retry-until-PASS is introduced. This documentation
update changes no original report, code, production source or contract and
starts no new build/device run.

## Current Host Verification

```sh
node --test state_tests/runtime/arkts/native/Task17LoadingObserver.test.cjs \
  state_tests/runtime/arkts/native/Task17LoadingUi.test.cjs \
  state_tests/runtime/arkts/native/Task17PageFixture.test.cjs
```

The original production feature/repository execute with explicitly synthetic
OS/UI/frame transport in these tests. Immediately fulfilled SDK Promises are
used, not held completions. Tests cover an observable synthetic frame, a missed
frame retaining NS, original empty-store initialization/flush, disabled Open,
duplicate classes, wrong route, hidden loading, missing layout/context/source,
wrong parent invariant, unchanged Promise identity, isolated installer and the
unchanged existing Task17 page fixture. Host success is not device calibration.

After the readback revision, all 21 host regressions pass, including actual-object
transport preservation, exact invalid-string retention with NS, immutable
native descriptor diagnostics, equivalent durable I/O proof and unchanged
native loading/visibility requirements.

Files added: `Task17LoadingFrames.js`, `Task17LoadingLaunch.js`,
`Task17LoadingReadback.js`,
`Task17LoadingLaunchNative.js`, `Task17LoadingLaunchNative.d.ts`,
`Task17LoadingNativeSdk.js`, `Task17LoadingNativeSdk.d.ts`,
`Task17LoadingUi.js`, `Task17LoadingUi.d.ts`, `Task17LoadingUiSuite.ets`,
`Task17LoadingUiBridge.js`, `Task17LoadingUiBridge.d.ts`,
`Task17LoadingUi.adapter.cjs`, `Task17LoadingUi.install.cjs`,
`Task17LoadingUi.test.cjs`, this document. Existing Task17LoadingObserver
JS/declaration/test add only current-state observation and an optional isolated
frame-registration hook. Other task fixtures remain frozen.
