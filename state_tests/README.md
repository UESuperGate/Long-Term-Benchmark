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
