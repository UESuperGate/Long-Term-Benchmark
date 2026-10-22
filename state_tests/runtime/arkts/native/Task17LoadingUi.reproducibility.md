# Task17 Natural Loading Reproducibility Audit

## Scope and Evidence

Read-only audit on 2026-10-19 of final `17_pinned_messages`, canonical case
`pm_state_001_open_loading`, trace digest
`c15a7e08ce803419b47ba43d877c935d394b82405a80803a728ad94df2daeceb`.
All paths below are relative to
`experiment_results/runtime_transition_20261019/device-calibration/`.

| Run | Raw row | Bytes | Result |
| --- | --- | ---: | --- |
| First | `task17-natural-loading-storage-readback/native-result.json` | 823633 | PASS |
| Repeat | `task17-natural-loading-storage-readback-repeat/native-result.json` | 977653 | not_scored |

First raw SHA-256:
`6decb8e1d31d28740735beecaf32250543dcbdacb0533aa7405af778e0dfc185`.
Repeat raw SHA-256:
`2d5bb7b2e140c061af67dd941c61ef9d39f10c2c9746ae9b4f05be4da9fc3428`.
Both hashes and sizes match the respective `device-execution.json` rowArtifact.
Execution nonces are `5cf017a9cd91f00a74164ebf915461d1` (first) and
`b36a7513c6762ef9b00bf23447d3a59c` (repeat). Both executions record
`candidateAbsentBeforeInstall=true` and `productionUnchanged=true`.

## Natural Frame Comparison

Rows below come directly from
`evidence[0].nativePageTransition.loadingFrames.frames`, in recorded order.
Dimensions are actual `rectangles` width x height, not derived visibility.
Node presence/visibility was separately checked in each recorded inspector tree.

| Run / sample | Phase | Presenter | Loading size | Back size | Visible loading/back nodes | Qualifies |
| --- | --- | --- | --- | --- | --- | --- |
| First 1 | onFrame | loading | 0 x 0 | 0 x 0 | neither | no |
| First 2 | onIdle | loading | 1308 x 2394 | 238 x 140 | both | yes |
| First 3 | onFrame | filled | 1308 x 2394 | 238 x 140 | both | no: stale loading UI |
| First 4 | onIdle | filled | 0 x 0 | 238 x 140 | Back only | no |
| Repeat 1 | onFrame | filled | 0 x 0 | 0 x 0 | neither | no |
| Repeat 2 | onIdle | filled | 0 x 0 | 238 x 140 | Back only | no |

The first run uses actual window 137; repeat uses 138. Every sample retains
`pages/Index` and its own original window identity. Inspector transport is an
object in every sample and both samplers have no recorded errors. The first
run posted two callbacks, repeat one; the bounded sampler is not evidence of
every frame the device may have displayed. The repeat does not prove that
Loading never rendered, only that no qualifying frame was captured.

## What Both Runs Prove

Both runs bind one original presenter and one original repository with the
same actual AbilityContext. Original method entry/return records include
Loading before the presenter eventually becomes Filled. The real Preferences
key `room_design_pinned_events` in `element_x_pinned_messages` is absent before
physical Open. Original `persistPinnedState`, `openPinnedTimeline` and
`openPinnedMessages` complete before native cache eviction and reopen. The
reopened key exists and full ordered rows match original persistence arguments,
repository results and presenter contents (`$rules`/Alice and `$launch`/Bob).
All seven native read/evict/read receipts complete; evaluator data writes are
empty. Physical Back executes in both runs.

This is equivalent native persistence proof despite the SDK function's
read-only/non-configurable descriptor. It does not substitute for visible
Loading, prove Matrix network behavior, inspect a separate router-stack object,
or establish that a native I/O Promise was pending. The pre-read may warm the
cache, but these two observations do not establish the cause of the different
sampling outcomes. No SDK descriptor or native Promise is intercepted.

## Classification and Parent Handoff

First PASS is retained with its complete observed fields and true parent
invariant. Repeat remains `not_scored`, with no failed assertions. Its reason is:

> Original Loading call transition observed, but no qualifying natural same-page loading frame; do not substitute settled UI or claim pending native I/O.

The repeat row deliberately leaves canonical observations/invariants unscored;
this audit does not fill them from the first run or from settled state. This is
an unstable observation boundary, not a demonstrated production assertion
failure. Stable calibration is incomplete.

Parent diagnostic handoff (documentation only, not a report mutation):

- `reproducibilityIncomplete: true`
- Case: `pm_state_001_open_loading`; first status: `pass`; repeat status: `not_scored`.
- Link both raw paths and hashes above in primary diagnostics, especially repeat.
- Keep the first-run primary 9/0/0 provenance distinct from the repeat outcome;
  do not present that aggregate as reproducibly complete calibration.
- Preserve older `task17-natural-loading-js-sdk` and
  `task17-natural-loading-raw-frame` NS results; no retrospective rescoring.

No timing adjustment, delayed I/O, assertion change, repeat-until-PASS, new
build or device execution was performed for this audit. Only this diagnostic
document and `Task17LoadingUi.md` were edited; primary/raw reports are unchanged.
