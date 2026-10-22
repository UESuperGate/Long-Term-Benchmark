# Task17 Android Connected Room Flow V2

Status: offline implementation, not compiled or runtime calibrated. No scoring
authority. The old `calibrated_v1` producer, raw results, patches, and canonical
assertions remain unchanged. Central registration/readiness is coordinator-owned.

The repair must execute the actual chain:

`LoggedInFlowNode -> RoomFlowNode -> JoinedRoomFlowNode ->
JoinedRoomLoadedFlowNode -> DefaultMessagesEntryPoint -> MessagesFlowNode ->
MessagesNode / PinnedMessagesListNode -> original presenter -> original View`.

For view-in-timeline the actual list callback returns through LoggedInFlowNode's
permalink handler. Its replacement target supplies focusedEventId to the new room
flow. Original TimelinePresenter must focus and original TimelineView must render
the target. A callback counter or manually assigned screen is insufficient.

Every UI/effect case needs one episode, actual node-parent links, node-owned
presenter identities, original composition parameter readbacks, full semantics
trees, and external SDK invocation/delivery records. SDK doubles provide only
Matrix inputs; no synthetic presenter, banner state, internal service, or route.
Unknown DI/API/layout is NS pending binding review, not semantic failure.

The prefix uses original room header -> original room-details pinned row. It can
reach the actual list while the SDK response is held. The alternative loading
banner TextButton suppresses onClick while showProgress is true: it cannot be
substituted for the room-details route. The provider starts on the room flow,
before the entry event. Exact canonical effect timing still needs raw review;
no contract correction is made here.

`Task17ProductionBindings.kt` is a fail-closed construction draft, not an already
working DI graph. The original services include FTUE, analytics, permissions,
session storage, formatting, composer and push setup. Their complete provider and
qualified-value bindings have not been established. Missing services throw; they
must not be replaced with success stubs. Do not spend a full runtime calibration
budget before completing this source-level binding review.

`task17_connected_offline_plan.py` accepts an arbitrary standalone `--source`,
explicit `--role`, `--case`, and separate `--owned-root` to emit review-only argv.
It does not run that command. No standalone executable scorer or accepted-control
claim is made yet. `task17_connected_evidence_v2.inspect_episode` checks positive
owner-proof structure only; it is not a semantic scorer and does not replace
per-case canonical assertions or independent compiled/raw admission.

JVM/Gradle/device execution is forbidden until coordinator review and queue release.
Future execution must use one <=3600s overall deadline including shared Android
lock wait and cleanup, >=8 GiB disk guard, arbitrary standalone source arguments,
and hash-delete generated build binaries. An offline source guard is diagnostic,
never evidence that any semantic testcase passed.
