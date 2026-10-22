# Task17 Open Loading: Read-Only Audit And Isolated Observer

Follow-up: `Task17LoadingUi.md` now describes an independent original-page
device installer and bounded natural-frame sampler. Its host regressions do
not establish device Loading; native replay remains parent-owned. The original
audit below remains the rationale and does not turn source inspection into a
runtime verdict. No shared-file integration or report update was made here.

No shared `Tasks16_18*` implementation, production source, canonical contract,
Android adapter, report, or device was changed for this audit. The only code
addition is the independent `Task17LoadingObserver.js` / `.d.ts` / `.test.cjs`.
It is not installed into the shared runner and produces no canonical verdict.

## Contract And Current Reports

`pm_state_001_open_loading`, trace digest
`c15a7e08ce803419b47ba43d877c935d394b82405a80803a728ad94df2daeceb`:

- GIVEN: `screen=room_timeline`, `pinnedList=closed`.
- EVENT: `open_pinned_messages`.
- EXPECTED: `screen=pinned_messages`, `listState=loading`,
  `effects=[open_pinned_timeline]`.
- INVARIANT: the room timeline remains the navigation parent.

The contract does not explicitly require an unfinished SDK request in GIVEN or
state whether the effect may have started before the click. Do not silently add
a pending requirement, redefine an already-started effect as a new effect, or
change the assertion. Record the actual temporal boundary.

The retained ArkTS final row has domain Loading and a substituted repository
read, but lacks screen and navigation-parent observations. It does not establish
real native I/O. Android's row has no `open_loading` method/evidence; its separate
`load_failure` test has a pending-state checkpoint but cannot supply navigation
evidence for another case. Neither NS is a proven semantic defect.

## ArkTS Production

Final `entry/src/main/ets/features/PinnedMessagesFeature.ets`:

- Lines 106-119: original `openPinnedMessages` assigns Loading synchronously,
  then awaits the original `repository.openPinnedTimeline(context)`.
- Lines 43-63: actual repository awaits Preferences `getPreferences`, then
  `store.get`. An empty store additionally executes original persist/flush.
- There is no production API to hold that native request unresolved. A cold
  store may naturally take longer, but offers no guaranteed visible-frame budget.

Final `entry/src/main/ets/pages/Index.ets`:

- Lines 215-222: original UI callback changes screen, calls the presenter,
  synchronizes its state immediately, and synchronizes again on completion.
- Lines 113-122: the real Loading branch has ID `pinned_messages_loading`.
- Lines 99-103: actual Back returns to `room_timeline`.

Thus a direct observation of the original presenter's method return can capture
Loading without delaying the real SDK. It does not by itself prove a rendered
Loading frame, a native Promise's internal pending status, or the parent UI.
The new observer explicitly preserves these distinctions. Even an already
fulfilled SDK Promise causes an `await` continuation boundary; an unrun `.then`
handler must not be reported as proof of unresolved native I/O.

Original native reference: OpenHarmony Preferences GetPreferences delegates to
`AsyncCall::Call`; neither this API nor its signature promises a minimum latency:
https://github.com/openharmony/distributeddatamgr_preferences/blob/master/frameworks/js/napi/preferences/src/napi_preferences_helper.cpp
The local API23 declaration is `@ohos.data.preferences.d.ts:372`.

## Executable Integration Plan (After Shared-File Release)

1. Fresh install/cold start, no task17 focus seed and no artificial locks, SDK
   gates, sleeps in production calls, large synthetic data, or forced Promises.
2. Capture original AbilityContext. Verify mounted room root, list closed and an
   actual actionable Open control before dispatch. Preserve raw checkpoints.
3. Import original mounted-app exports via its actual OHM URL, not a static
   test-HAP duplicate: `@bundle:<actual-bundle>/<actual-module>/ets/features/PinnedMessagesFeature`.
   Bind the exact exports and SDK Preferences to `observeTask17Loading` below.
   No separately constructed presenter is permitted in the device test.
4. Snapshot observer before the actual UI click and immediately after; it captures
   the synchronous return internally, so remote UiTest IPC latency cannot erase
   the original Loading transition. Persist source/import identity plus all raw
   call records. Zero observed presenter calls remains an identity/binding NS.
5. Capture real loading UI while the operation naturally runs, preferably using
   a bounded original-UIContext frame observer registered before the click.
   API23 `UIContext.postFrameCallback(FrameCallback)` / `onIdle` are available.
   Read the actual inspector node and visible bounds using `runScopedTask`; do
   not force layout/state or keep requests pending to obtain a frame. Bound the
   sampler (for example eight frames), stop on completion/disposal, and retain
   missed-frame diagnostics. Callback records alone cannot fabricate screen state.
6. Use the real Back control and verify the same room root/focus before and after;
   do not infer a navigation stack from a standalone presenter. Preserve the
   original loading evidence separately from the later parent-return evidence.
7. Score only when all unchanged fields/invariant are evidenced. Failure to catch
   a qualifying loading frame is NS, not FAIL. Never merge a mocked pending
   domain run with a separate completed native UI run as one execution.

Evaluator-only binding sketch (original exports supplied by native import):

```js
const observer = observeTask17Loading(original.PinnedMessagesListPresenter,
  original.PinnedMessagesRepository, nativePreferences, actualAbilityContext);
try {
  // Existing native probe performs the actual original-page UI click here.
  // Read observer.snapshot() into before/after/partial diagnostic checkpoints.
} finally {
  observer.dispose();
}
```

The observer wraps descriptors only to forward original receiver, arguments,
throws and exact returned Promise. It never constructs a page/presenter, writes
state, awaits inside the wrapper, substitutes a Promise, or controls I/O timing.
It attaches settlement handlers, which can affect scheduling overhead; no minimum
duration or visual-frame claim is derived from those handlers. Unobservable
descriptors remain unavailable. Disposing avoids overwriting another observer.

Run isolated host regressions (no build/device):

```sh
node --test state_tests/runtime/arkts/native/Task17LoadingObserver.test.cjs
```

Four tests pass, including executing the untouched production presenter and
repository with immediately fulfilled synthetic SDK Promises. These are adapter
regressions, not native-runtime or canonical results.

## Android: Similar Missing Navigation, Different Pending Entry

Immutable final commit: `eff868ddf9e1caef8182e55ac59054e81526a68f` in
`_sources/element-x-android`; inspect with `git show <commit>:<path>`.

- `features/messages/impl/.../MessagesFlowNode.kt:164`: `onBuilt()` starts the
  pinned timeline provider before the list is opened. Lines 224-225 only push
  `NavTarget.PinnedMessagesList` when the actual callback is received.
- `features/messages/impl/.../pinned/PinnedEventsTimelineProvider.kt:75`: only
  Uninitialized/Failure starts a request, emits Loading, then calls
  `room.pinnedEventsTimeline`. Already Loading/Success does not reopen it.
- `libraries/matrix/impl/.../room/RustMatrixRoom.kt:186`: real production delegates
  to `innerRoom.pinnedEventsTimeline`, then creates the real pinned RustTimeline.
- `features/messages/impl/.../pinned/banner/PinnedMessagesBannerView.kt:132`:
  Loading passes `showProgress=true` to the original ViewAll TextButton.
- `libraries/designsystem/.../components/Button.kt:213`: ButtonInternal executes
  `onClick()` only when `!showProgress`. Semantics may still say enabled, so an
  enabled-node check alone does not prove the pending banner dispatches navigation.
- `features/messages/impl/.../pinned/list/PinnedMessagesListPresenter.kt`: initial
  Uninitialized also maps to Loading. A transient composition state is not proof
  that the SDK request remains pending.

Therefore holding a Rust SDK result and directly invoking `onViewAllPinnedEvents`
would bypass a real UI gate. It is not a valid fix. First execute the original
banner/button and FlowNode together, observe whether an eligible click reaches
the callback, and retain the real backstack. If the pending banner consumes the
click, report that reachability constraint as NS rather than forcing navigation.
An already-loaded path may still briefly compose Loading, but cannot be called
an unfinished SDK request or a newly triggered open effect without evidence.

The existing Android `PinnedLoadTest.kt` constructs a separate presenter, while
`MatrixRoom.kt` replaces the application room class with a CompletableDeferred
test implementation. This is not the real Rust pipeline or real room UI entry;
its Loading checkpoint must not be promoted to this canonical case. Full strict
coverage requires real provider/room/node/UI wiring and observation of the
external Rust SDK boundary, not just adding an `open_loading` method name.

## Immutable ArkTS Hashes

- Feature: `c8ddd20bed3eaa79d682462d65ef3ee85f1526243cf8da49e9022d7b1e09c220`
- Page: `2005a02bbd82c52137cf0283d88d11093bde604d04d512f03c50abaabb8f8067`
- Canonical: `351bacebd24bd1c95707bfea9e5caa8d4813a087f88606a3571d8c73d168fd93`

These hashes still match the previously verified task17 source/contract.
