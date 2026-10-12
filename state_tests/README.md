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

The full YAML and generated files under `state_tests/bindings` and
`state_tests/traces` are evaluator-private oracle inputs. Coding agents receive
an automatically redacted contract containing only task metadata, `given_state`
fixtures, and transition event names. `expect_ui`, `to_state`, mutation guards,
and parity assertions are never copied into a candidate workspace.

Every trace has one digest and one ordered phase list shared by Android and
ArkTS. Platform adapters may differ only in transport; they may not redefine a
fixture, event, phase, selector, or expected fact.

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

Android's exact-API diagnostic uses evaluator-owned JUnit transition probes
compiled against the candidate's production modules. Methods added or
semantically changed between each official base/final tag form the diagnostic
layer in `state_tests/canonical/official_transition_contract.json`.

1. Candidate integrity is audited before any evaluator source is attached.
2. The evaluator reads the probe from the official final Element X tag into a
   temporary directory outside the candidate.
3. `state_tests/android_observer/init.gradle` replaces the selected module's
   test source set and compiler-task inputs with that external directory. No
   source is copied into or committed in the candidate.
4. Gradle compiles the official probe against candidate production code and
   executes the named JUnit class.
5. A diagnostic testcase passes only when its exact JUnit method appears as
   passed in the new XML result. An assertion failure is behavioral failure; an
   API mismatch identifies upstream-shape incompatibility. SDK/JDK/dependency/
   timeout failures are `not_scored`.
6. Each method has a digest over task, official final tag, class, method, and
   method body. This identifies Android evidence; it is not itself a shared
   cross-platform testcase id.

The benchmark metric uses the 37-case semantic intersection in
`state_tests/canonical/cross_platform_contract.json`. Each case defines one
platform-neutral given/event/expected transition and digest, then binds it to
one or more official Android methods and an ArkTS trace plus phase set.
Platform-only methods and broader unbound YAML cases remain diagnostic coverage
and do not inflate the cross-platform semantic pass rate.

Android benchmark scoring uses
`scripts/run_android_portable_semantic_observer.py`. It checks evaluator-owned,
task-local production clauses for the state model, event/branch, and effect of
each shared transition. Every candidate must first compile successfully. The
observer strips comments, ignores tests and candidate-owned oracle files, and
does not allow evidence from unrelated modules. The same rules must calibrate
to 0/37 on official base tags and 37/37 on official final tags before an agent
result is publishable.

The portable observer is intentionally implementation-tolerant; the official
JUnit observer remains available to explain exact upstream API mismatches. Its
result is diagnostic and is not substituted for the benchmark score.

Three confirmation-number cases were removed from the intersection after audit:
their Android production behavior was identical in task 5's base and final
tags. Their old base failures came from another method in the same JUnit class
failing compilation, so retaining them would violate final-positive polarity.

`scripts/run_android_external_observer.py` runs candidate probes.
`scripts/calibrate_android_external_observer.py` runs the same probes against
official base and final tags using LFS-free temporary worktrees and removes all
worktree/build intermediates afterward.

The Android debug provider, manifest, contract, and `StateTestScenario` are
evaluator-owned protected files. A candidate that modifies them, adds case-id
tables, emits semantic facts, or introduces a production state machine referenced
only by benchmark code is invalid and is not semantically scored. Until an
evaluator-owned instrumentation adapter binds a task to real production state,
Android agent rows are `instrumentationUnbound`, never pass or fail.

For device-only cases, an Android instrumentation adapter writes outside the candidate workspace at
`QINGYU_ANDROID_OBSERVATION_ROOT/<taskId>/<caseId>/capture.json`. Each bundle
must declare `observerOwner: evaluator`, the exact case id and trace digest, and
a phase capture. The target matrix enables `trusted_external_observer` only when
that evaluator-controlled root is configured; mismatched or missing digests are
not scored.

The Android agent workspace is a clean project archive. OpenCode may use one
bounded `explore` subagent, but both parent and child inherit the same
project-only filesystem policy; shell, network, browser, MCP, SDK, JDK, Gradle
cache, temporary-directory, and sibling-repository access are denied to the
agent. The runner performs compilation outside that boundary. Subagent work is
not timed separately: the recorded task duration is one wall-clock interval from
task start through the final generated result.

Agent-result snapshots are not trusted evidence. ArkTS agent results are scored
from independently dumped ArkUI nodes. Android agent results require an external
evaluator observer. Candidate-produced `semanticFacts`, `strict_state_fact`, and
pre-prefixed `transition:N:` facts are ignored in strict mode.

Semantic failures are not returned to the coding agent. Compile diagnostics may
be used for build repair, but expected facts, observed facts, missing facts, and
hidden trace results remain evaluator-private.

The published benchmark metrics are only code generation, compile success, and
semantic testcase pass rate. Adapter readiness, transport failures, agent
timeouts, and compiler diagnostics are retained for debugging and must not be
reported as benchmark metrics.

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
- `bindings/*.binding.json`: evaluator-private selector manifests.
- `traces/*.trace.json`: evaluator-private, platform-neutral phase traces and digests.
- `canonical/official_transition_contract.json`: Android-only executable
  evidence derived from official JUnit transitions.
- `canonical/cross_platform_bindings.json`: audited mappings from shared
  semantics to Android methods and ArkTS traces/phases.
- `canonical/cross_platform_contract.json`: the 37-case benchmark contract
  with platform-neutral case ids and digests.
- `android_observer/probes.json`: official tag/module/class probe manifest.
- `android_observer/init.gradle`: external evaluator source-set injection.
- `scripts/generate_state_transition_traces.py`: deterministic trace generator.
- `scripts/state_test_public_contract.py`: oracle-redacted agent input generator.
- `scripts/semantic_candidate_integrity.py`: candidate oracle/integrity audit.
