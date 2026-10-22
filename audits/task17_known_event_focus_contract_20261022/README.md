# Task17 known-event focus contract audit

## Scope

This audit corrects the Android runtime evaluator implementation for
`pm_state_007_view_in_timeline`. The canonical semantic contract remains
unchanged: selecting a pinned event navigates to the room timeline and focuses
that event while the pinned set remains unchanged.

## Retained pre-change identities

- Evaluator SHA-256: `f9e8a9935027b827125b9baf3785b04b4ce5b2e21ca04126851b536ee2f0a691`
- Offline test SHA-256: `2356de8c004e8993a2bfabd3f74a61c4e657703d4886999b74ac18f760d246ca`
- Canonical transition SHA-256: `351bacebd24bd1c95707bfea9e5caa8d4813a087f88606a3571d8c73d168fd93`
- Failing runtime evidence: `experiment_results/runtime_transition_20261022/task17_android_final_case007_v7_v31/native/view_in_timeline.native.json`

## Upstream evidence

- Android final commit: `eff868ddf9e1caef8182e55ac59054e81526a68f`
- `TimelinePresenter.kt` blob: `9466ac16f5e42dafb6695e80b7225365675be6b5`
- `MessagesFlowNode.kt` blob: `12df0bc0bfd6062e11182095059cf9d113f5f30f`

`MessagesFlowNode` routes the action through a room permalink with the selected
event ID. `MessagesNode` emits `TimelineEvents.FocusOnEvent`. In
`TimelinePresenter`, an event already known by `timelineItemIndexer` transitions
directly to `FocusRequestState.Success`; only an unknown event transitions to
`Loading` and calls `TimelineController.focusOnEvent`, which then invokes
`Room.timelineFocusedOnEvent`.

The canonical fixture contains `$a` in the live timeline before the action.
Requiring `Room.timelineFocusedOnEvent` was therefore incompatible with the
immutable upstream implementation. The revised evaluator strictly requires:

1. the original parent route changes from an unfocused room target;
2. the new route has `trigger=Timeline` and `Messages(focusedEventId=$a)`;
3. the actual target control is rendered with `$a` focused;
4. no detached-timeline SDK call is fabricated for the already-indexed event;
5. the production pinned-event set remains unchanged.

No production logic, canonical expected value, or assertion count is reduced.
