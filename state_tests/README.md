# Element X State-Test Specs

These files define state-level tests for the five long-horizon Element X benchmark tasks.

In this benchmark, `state` means the declarative UI state variables that drive rendering. A state-test does not primarily assert tap sequences or screenshots. It asserts that a semantic state vector produces the expected UI contract, and that events or mocked SDK callbacks move the state to the next semantic state.

## Generator contract

Each YAML file is platform-neutral. A testcase generator should:

- read `state_dimensions` and `cases`;
- instantiate the Android `platform_bindings.android.state_holders` using Compose preview providers, presenter tests, or state fixture helpers;
- instantiate the ArkTS `platform_bindings.arkts.state_holders` using `@State`, view model snapshots, or fixture service state;
- render the target declarative UI;
- assert `expect_ui.visible`, `expect_ui.hidden`, `expect_ui.enabled`, `expect_ui.disabled`, and semantic node properties;
- apply `transitions` by invoking the listed event sink, state mutation, timer, or mocked SDK callback;
- compare final semantic state and UI contracts across Android and ArkTS.

## Production-grade discrimination

The upgraded suite treats each case as a small semantic product requirement, not as a marker check. Every case carries:

- `functional_area`: the product slice protected by the case, such as capability gating, media viewer, active manager, owner gate, timeout retry, or stale event protection;
- `fixture_kind`: the evaluator-owned fixture required to reach the state, such as declarative state injection, SDK callback, timer tick, navigation transition, or permission change;
- `base_failure_signal`: why the base node should fail this final requirement;
- `runtime_oracle`: the minimum runtime signals needed for a pass, including state-vector application, UI-tree token assertions, transition execution, and Android/ArkTS parity;
- `mutation_guards`: implementation shortcuts that this case should reject, especially feature-flag-only completions.

The generator must not collapse all cases for a target into a single `feature_available` boolean. A case is scoreable only when its own `given_state`, `expect_ui`, `transitions`, `properties`, and platform binding manifest are consumed.

## Quality gates

Each YAML file also declares `quality_gates`. A valid production-grade task must satisfy:

- the minimum case count for the task;
- coverage of every required functional area;
- at least one real transition or property assertion for the major flows;
- explicit mutation guards against marker-only, flag-only, first-item-only, always-success, always-hidden, or stale-state implementations;
- final-positive polarity: base mirrors fail because behavior is absent, final mirrors pass because the behavior is actually present.

## Assertion level

Prefer semantic tree assertions over pixel assertions:

- Android: Compose semantics, text matchers, state fixture tests, presenter state transitions.
- ArkTS: ArkUI component tree, text/content descriptions, `@State` values, fixture service snapshot transitions.

Screenshots can be used as a secondary guard, but the primary pass/fail signal is whether the same semantic state produces the same UI behavior on both platforms.

## ArkTS runtime protocol

The device runner uses a public, answer-free transport contract. This contract
may be present in every base project because it only carries test inputs; it does
not contain evaluator selectors or expected facts.

1. The runner starts `EntryAbility` with `caseId` in both the Want parameters and
   the `elementx://state-test` URI.
2. `EntryAbility` stores the id in
   `AppStorage['elementx_state_test_case_id']`. The page applies the matching
   `given_state` fixture to the same state holders used by the real UI.
3. The page publishes `state_test_ready:<caseId>` and a hidden
   `state_probe_snapshot:<json>` node only after that fixture is active.
4. The runner polls `uitest dumpLayout` until the ready marker and matching
   snapshot are both present. A fixed sleep is not a readiness signal.
5. For each declared transition, the runner re-delivers a Want containing
   `stateEvent`. `EntryAbility` stores a nonce-qualified event in
   `AppStorage['elementx_state_test_event']`; the page routes it through the same
   presenter/event sink or mocked SDK callback used by the feature.
6. After every event, the runner captures a new layout. The snapshot should name
   the applied event in `lastEvent` (the nonce may be retained) and expose facts
   derived from the current runtime state. It must not pre-emit future transition
   facts.
7. The evaluator combines independently observed ArkUI node ids, visibility,
   enabled state, and text/property values with runtime state facts, then compares
   that phase against the evaluator-owned binding manifest.

`scripts/run_snapshot_state_matrix.py --transition-mode strict` enforces this
phase protocol for generated candidates. `--transition-mode compatible` still
executes and captures transitions, but may accept aggregate transition facts from
older golden projects so existing benchmark assets can be calibrated while they
are migrated.

## Android runtime protocol

Android uses the same case ids, state vectors, transition events, selectors,
and evaluator-owned binding manifests as ArkTS. Only the transport differs.

1. The evaluator installs the `gplayDebug` APK and queries the exported debug
   provider at `${applicationId}.state-test-probe` with `caseId`.
2. The provider returns a cursor column named `snapshot` containing JSON with a
   matching `caseId`, `ready: true`, and facts derived from the current fixture
   and feature state.
3. The evaluator captures the initial response before sending any event.
4. Each YAML transition is delivered by a new provider query with the same
   `caseId` and one `stateEvent`. The adapter routes that event through its
   deterministic debug fixture and returns the resulting current facts plus
   `lastEvent`.
5. The evaluator records every provider response separately, adds its own
   transition ordinal, and performs the same semantic comparison used for ArkTS.

The golden calibration adapter generated by
`scripts/patch_android_state_phase_harness.py` is evaluator-owned and exists only
under `app/src/debug`. It consumes hidden bindings solely to prove testcase
polarity: all base cases fail and all official final cases pass. Generated agent
candidates receive only the public requirement spec, YAML, schema, and transport
contract; they are always scored with strict phase evidence.

Before candidate scoring, run base and ground-truth-final calibration. Base rows
must observe `fail`, final rows must observe `pass`, and transport failures must
remain distinct from semantic failures.

## Benchmark polarity

Every testcase in this suite is a final-version requirement assertion. The expected benchmark result is:

- Android base mirror: fail every testcase for that task.
- ArkTS base mirror: fail every testcase for that task.
- Android final mirror: pass every testcase for that task.
- ArkTS final mirror: pass every testcase for that task.

Do not add base-negative/control cases that are expected to pass on base. If a base/final contrast is needed, write the case as a final-positive requirement whose missing behavior makes base fail.

## Case selection rules

The suite intentionally avoids overfitted checks. A case should be included only when it protects a real product behavior:

- a user-visible state, action, error, fallback, or navigation result changes;
- an SDK/presenter state transition must be reflected in UI;
- a state must be forbidden because exposing it would be unsafe or functionally wrong;
- base and final behavior intentionally differ;
- state propagation across screens can break independently from the originating screen.

Do not add cases for exact pixels, exact localized prose, private helper call counts, file names, preview-only fixtures, or implementation details that can change while preserving behavior.

## Files

- `elementx-state-test1-user-status.yaml`
- `elementx-state-test2-gallery-messages.yaml`
- `elementx-state-test3-timeline-protection-rich-events.yaml`
- `elementx-state-test4-live-location.yaml`
- `elementx-state-test5-link-new-device.yaml`
