# Task17 Actual Ability Context Fixture

Evaluator-only repair for `pm_state_007_view_in_timeline`. No production or
canonical changes, and no role-dependent decision. This implementation has host
regression coverage; native build/device execution remains pending.

## Execution

- The adapter passes `prepare` and `afterEvent` callbacks as the second in-memory
  argument to `native.runTasks16To18UI`. Neither callbacks nor SDK Context enter
  the serialized request/result.
- The native probe launches the original ability, captures `ability.context`,
  verifies the original room root, and invokes `prepareTasks16To18Page(context)`
  before clicking Open. No page/presenter state is replaced.
- Preparation calls the original repository's `persistPinnedState`, awaiting its
  original flush. Readback uses the real Preferences API for
  `element_x_pinned_messages` / `room_design_pinned_events` and verifies the
  canonical `$a` row. ApplicationContext is not used for this fixture.
- After the original UI event and after-event snapshot,
  `finishTasks16To18Page(context)` invokes `afterEvent` with the identical object.
  Readback calls only `getPreferences` and `get`; it never invokes
  `openPinnedTimeline`, which would initialize defaults for missing data.
- Before/after evidence includes raw persisted values, parsed rows, actual
  `preferencesDir`, area, bundle and module identity. Missing or corrupt data is
  retained, not repaired. Failure to establish the fixture or observation is NS;
  a complete observation still uses unchanged canonical assertions/invariants.
- Callbacks are single-use and task17-focus-only. Cancellation prevents further
  callback dispatch; run completion/disposal releases retained callbacks/Context.
  Existing partial checkpoints and task18 picker observations remain intact.

## Host Verification

```sh
node --test state_tests/runtime/arkts/native/Task17PageFixture.test.cjs \
  state_tests/runtime/arkts/native/Tasks16_18Bindings.test.cjs \
  state_tests/runtime/arkts/native/Tasks16_18TransitionsUI.test.cjs \
  state_tests/runtime/arkts/native/Tasks16_18NativeUi.install.test.cjs
```

These tests use explicitly synthetic external SDK/UI boundaries solely to test
the evaluator. They are not native execution evidence or canonical PASS results.
Coverage includes Context identity/nonserialization, flush ordering, original
production persistence, missing callbacks, wrong context/bundle/module, seed
failure, deleted/corrupt storage without default writes, partial progress and
cancellation, plus unchanged task18 picker/watchdog regressions.

Source audit before handoff: all 20 files comprising task17/task18 production
`entry/src/main` trees and their two canonical transition files retained their
pre-edit SHA-256 values. Task18 native assertions, native UI branch, snapshot and
partial-checkpoint functions, picker observers, same-page sound readback, and
domain/watchdog adapter suffix were byte-identical to the released snapshot.
