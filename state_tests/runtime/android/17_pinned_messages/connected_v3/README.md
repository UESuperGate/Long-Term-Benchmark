# Task17 Original-App Connected Probe V3

This implementation is the calibrated real-runtime evaluator for Android
Task17. It compiles and executes the original Element X Compose/Appyx/Dagger
flow in isolated JVMs. On the retained immutable boundary it establishes the
required polarity: base 0/9 and final 9/9. A fresh OpenCode + MiniMax-M3
candidate compiled as an application and scored 0/9 because its production
page was not reachable from the RoomDetails entry.

## Actual Production Assembly

The NodeHost contains a DI-owner host without replacement feature UI. Its child
comes from the original generated `SessionComponent.nodeFactories()` map:

```
DaggerAppComponent.factory().create(actual Application)
  -> Element X production InMemorySessionStore / original dispatchers / app scope
  -> original RustMatrixClient constructor
  -> original SessionComponent.Builder.client(actual RustMatrixClient)
  -> original LoggedInFlowNode assisted factory
  -> original RoomFlowNode / JoinedRoomFlowNode
  -> original JoinedRoomLoadedFlowNode
  -> original DefaultRoomComponentFactory / RoomComponent.Builder.room(...)
  -> original MessagesEntryPoint / MessagesFlowNode / page-owned presenter
```

`RustMatrixClient.getRoom()` executes its original `RustRoomFactory` and creates
the original `RustMatrixRoom`. Pinned/focused/live timelines are the original
`RustTimeline`, not `MatrixRoom`/`Timeline` delegates or app SDK fakes. Only
`org.matrix.rustcomponents.sdk` objects and data are controlled. The strict SDK
audit retains unbound calls even when production catches the SDK exception.

The Android SDK artifact contains Android native libraries, not a macOS Matrix
SDK dynamic library. The real `RustRoomFactory` call to
`TimelineEventTypeFilter.exclude` is therefore intercepted at that existing
Rust-SDK leaf boundary and returns a strict audited SDK object. The call and
argument count are recorded; the production factory and its event-filter
decision remain exercised. No host Matrix Rust build is substituted.

Robolectric does not provide the platform `AndroidKeyStore`, so resolving the
default encrypted `DatabaseSessionStore` would fail before any Task17 action.
The fixture therefore supplies Element X's own production
`:libraries:session-storage:impl-memory` implementation to the original
`RustMatrixClient` constructor. The selected class and instance are retained in
raw component evidence. No Task17 state, presenter, bridge, room or timeline is
replaced by this environment input.

The same instance is seeded into the unique generated Dagger provider whose
declared concrete type implements `SessionStore`, before any dependent service
is resolved.
The evaluator rejects a missing, duplicate or non-`DoubleCheck` provider and
verifies readback identity. This keeps production analytics and node bindings
intact while preventing those services from lazily reopening the encrypted
store through a second dependency path.

Source-API constructor compatibility is explicit, role-independent and confined
to `SessionData`, `RustMatrixClient`, and its original optional session delegate.
The final adds a session delegate/cache path; the base does not. SDK session
inputs likewise use the actual SDK constructor metadata (0.2.40 vs 0.2.42).
There is no generic constructor graph, mocked presenter, feature state setter,
patched navigator, or callback-derived screen constant.

The evaluator-only outer Host observes its own Appyx `children` flow and renders
its backstack only after the initial child is attached. This preserves Appyx's
navigation ownership under the deterministic test dispatcher; no production
node or production view is gated by this host-mount condition.

## Changed SDK Boundary

At immutable `4ecc9f46... -> eff868dd...`, `RustMatrixRoom` changes pinned mode
from `isLive=false` to `Timeline.Mode.PINNED_EVENTS`. `RustTimeline` changes its
pagination and postprocessor wiring. The leaf SDK listener supplies actual SDK
timeline items/diffs; original subscribers, mappers and processors execute.
Unpin is held at the lower SDK request before delivering a server-authoritative
diff/room-info callback. Before/pending/after/actual retry checkpoints are kept.

The original provider begins loading in `MessagesFlowNode.onBuilt`, before the
user opens the list. The pending-list entry uses the real room header/details
row, not the disabled loading-banner click. This timing is recorded, never
replaced by an invented second request.

Case007 uses the original callbacks through MessagesFlow/RoomDetailsFlow and
JoinedRoomLoadedFlow into the actual LoggedInFlow parent. The original parent
replaces its room target; the new original TimelinePresenter must focus and
render the target. Snapshots retain actual callback outer-node references,
room-component ownership, source SDK handles, actual Compose arguments, full
node/semantics trees and SDK traces. A legitimate replacement can create a new
RustMatrixRoom scope for the same lower SDK room; no singleton fake room hides
that lifecycle boundary.

## Independent Recompute

`scripts/runtime_semantics/task17_connected_assertions_v3.py:recompute(raw)`
checks all nine original case digests, expected fields and invariant counts.
It computes observations from actual snapshots and SDK windows, never a producer
verdict or a supplied `observed` map. Missing bindings/givens are EvidenceGap,
not semantic failure. A feature that is genuinely absent after the evaluator
reaches the common RoomDetails checkpoint is a role-independent semantic
failure; final and agent candidates are held to the same rule as base.

## Worker

The current worker executes one case or all nine cases with an unchanged 3600
second overall deadline:

```
python3 scripts/task17_connected_worker_v7.py \
  --immutable-source final --role final --case all --run-case --timeout 3600 \
  --output experiment_results/runtime_transition_20261022/task17_android_final_all_v7_v7
```

The immutable-source form creates and removes its own standalone worktree under
the shared Android lock. Preparation, lock waiting, wrapper version, source
retention, compilation, execution and cleanup share one absolute deadline with
cleanup reserve and an unchanged 8 GiB guard. Foreign SIGALRM ownership is
refused. Wrapper <8.11 selects Java17, otherwise Java21.

The Gradle target is `:app:testGplayDebugUnitTest`; every case runs in a separate
Gradle/JVM invocation with the original modules and ABIs intact. No new Rust
build is permitted. `--source /standalone --role agent` uses the same fixture,
scorer and process controls as immutable base/final.

The worker retains original stdout/version, actual raw working-tree input
archive plus bytes/modes/symlinks before/after, producer sources and per-compiler
declared input metadata. Git LFS smudge is explicitly skipped for immutable
preparation; archived bytes are the actual build inputs, not a claim of hydrated
LFS content or clean-filtered Git equivalence. External SDK/Gradle cache closure
is not claimed by the project snapshot. Owned intermediates and source files
are hashed before deletion. Explicit borrowed source directories are never
removed. Full application compile remains `not_run`, regardless of test-source
compile outcome; no model metrics or ready registry are changed.

## Calibrated Results

| Role | Runtime compile | Semantic testcases | Polarity |
| --- | --- | --- | --- |
| base (`4ecc9f46...`) | passed | 0/9 | all fail |
| final (`eff868dd...`) | passed | 9/9 | all pass |
| OpenCode + MiniMax-M3 agent | passed | 0/9 | all fail |

Formal reports are in
`experiment_results/runtime_transition_20261022/task17_android_runtime_summary_v1/`.
The agent application build passed independently; its generation, build,
isolation and patch receipts are under
`eval_runs/task17_android_minimax_m3_runtime_20261022_v1/`. The runner's older
generic semantic report remains non-publishable; only the connected-v3 native
evidence and independent aggregate provide the Task17 semantic metric.
