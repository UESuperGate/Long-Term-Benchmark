# Task17 Android calibrated runtime evaluator

This evaluator calibrates all nine canonical `17_pinned_messages` transitions against immutable Element X Android revisions.

## Immutable inputs

- Base commit: `4ecc9f46b6627f89184d66b758094a7c4a24c258`
- Base tree: `6c90042e69580acd06c8d669447c90a4a90ec9e8`
- Final commit: `eff868ddf9e1caef8182e55ac59054e81526a68f`
- Final tree: `0cd8a58632515f8e0f6fb669b02c8b35614d9181`
- Canonical contract SHA-256: `351bacebd24bd1c95707bfea9e5caa8d4813a087f88606a3571d8c73d168fd93`

## Runtime boundaries

The base evaluator renders the immutable production `PinnedMessagesBannerView`, clicks its real `View All` semantics node, dispatches the production `MessagesNode.Callback`, and observes the immutable `MessagesFlowNode` backstack. The list cannot be reached at the base revision, so every canonical case fails at the same real, common operation prefix. A clean JUnit execution is required before any case can be scored as a semantic failure.

The final evaluator compiles a source closure from the immutable final tree and executes the production pinned timeline provider, list presenter, timeline-item factories, action-list presenter, Matrix `Timeline` boundary, and snackbar dispatcher. Each canonical case uses a separate compiler temporary directory and JVM. A separate module probe conjunctively proves that the real banner, production `MessagesNode.Callback`, production `MessagesFlowNode` backstack, and production `PinnedMessagesListNode` perform the `open_loading` navigation transition.

The full Android application build is intentionally not claimed. Base compilation scope is `:features:messages:impl:testDebugUnitTest`; final compilation scope is nine isolated host Robolectric production slices plus one isolated `:features:messages:impl:testDebugUnitTest` navigation conjunct.

## Commands

```bash
python3 state_tests/runtime/android/17_pinned_messages/calibrated_v1/run_base.py \
  --output-dir experiment_results/runtime_transition_20261020/task17_android/base-candidate-v6 \
  --timeout 3600

python3 state_tests/runtime/android/17_pinned_messages/calibrated_v1/run_final.py \
  --output-dir experiment_results/runtime_transition_20261020/task17_android/final-candidate-v2 \
  --timeout 3600

python3 state_tests/runtime/android/17_pinned_messages/calibrated_v1/run_final_navigation.py \
  --output-dir experiment_results/runtime_transition_20261020/task17_android/final-navigation-v1 \
  --timeout 3600

python3 -m unittest -v \
  state_tests/runtime/android/17_pinned_messages/calibrated_v1/test_verify.py

python3 state_tests/runtime/android/17_pinned_messages/calibrated_v1/verify.py \
  --output experiment_results/runtime_transition_20261020/task17_android/verification.json
```

Earlier candidate directories are retained as failure audit. They remain `NOT_SCORED` because repository setup, dependency resolution, evaluator compilation, or value-class ABI errors are not semantic failures.

## Standalone candidate formal scorer

`scripts/runtime_semantics/task17_android_strict_agent.py --source DIR --output REPORT`
executes the actual bytes in an arbitrary standalone Android directory. Final
slice rows retain their production source manifests and checkpoints. The real
navigation conjunct writes actual before/after targets before asserting them.
A failed assertion without those artifacts remains unscored.
The v3 navigation evidence also captures the actual Appyx backstack keys and
asserts that the original room timeline key remains the pinned list's parent.
The active target alone cannot satisfy this invariant.

`scripts/runtime_semantics/task17_android_entry_evidence.py` exports
`validate_entry_failure(row, report, usedids, contract)` for the shared matrix's
Task17 Android entry route. It verifies the executed evaluator, JUnit method,
actual single Banner click, production backstack, source snapshots, artifact
hashes and independent observation IDs. An unreachable operation prefix carries
`observed: null`, empty canonical invariant checks and `transitionExecuted: false`;
the actual runtime checkpoints remain in `actualCheckpoints`.

Run all four evaluator calibration inputs with:

```bash
python3 state_tests/runtime/android/17_pinned_messages/calibrated_v1/run_formal.py \
  --output-dir experiment_results/runtime_transition_20261020/task17_android_formal_source_param_v6
```

The third and fourth inputs are fresh base/final copies, both scored as `agent`,
and are **scorer sanity only**, never MiniMax results. The runner directly calls
the shared `validate_report` through the source-bound entry-policy registry.
`--validate-only` verifies retained reports without
rebuilding. Production slices use the shared runtime `.build.lock`. Every Gradle
module probe first acquires `/tmp/long-term-benchmark-android-full-build.lock`,
then `.build.lock`, with bounded waiting under the same deadline, serial workers
and an 8 GiB free-space guard. The runtime lock is not held while waiting for the
full-build lock. Temporary
sources and build outputs are removed after evidence export.
