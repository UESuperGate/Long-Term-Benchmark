---
name: migration-skill
description: Migrate an Android long-horizon benchmark task to ArkTS while preserving the Android base/final boundary, task behavior, and canonical state-transition semantics. Use to build ArkTS base/final projects, port the task, generate ArkTS semantic adapters from the same contract, calibrate polarity, and evaluate an OpenCode agent result.
---

# Migrate Android Benchmark Tasks To ArkTS

Treat migration as benchmark construction, not as the capability being measured. The ArkTS candidate task must start from a faithful base and target a faithful final; both platforms must bind to the same canonical transitions.

## Inputs

Require the Android `task.json`, public requirement, `transitions.json`, Android base/final refs, calibrated Android results, and ArkTS project/version targets. Read [migration-contract.md](references/migration-contract.md) before implementation.

## Workflow

1. **Freeze source and toolchains.** Record Android and OpenHarmony refs, Android SDK/emulator details, DevEco Studio, OpenHarmony SDK/API, hvigor, ohpm, Node, and JDK versions. Reuse local DevEco/OpenHarmony installations first.
2. **Inventory the complete client boundary.** Map Android modules and dependencies needed by the task: models, reducers/presenters, repositories, SDK calls, persistence, navigation, UI surfaces, resources, and tests. A partial showcase screen is not a migrated base.
3. **Build the ArkTS base.** Port the Android base behavior and surrounding prerequisites while intentionally excluding final-only semantics. Preserve unrelated behavior needed to reach and exercise the task. Build and smoke-test the base.
4. **Build the ArkTS ground-truth final.** Port the Android final delta end to end, including state, events, effects, failure recovery, persistence, navigation, and real rendered surfaces. Do not add semantics absent from Android final.
5. **Bind the shared contract.** Keep every canonical `caseId`, `given`, `event`, `expected`, and digest unchanged. Add only ArkTS fixture, event, and observation bindings. Platform adapters may translate transport and framework details; they may not redefine expected behavior.
6. **Generate ArkTS semantic tests.** Prefer runtime observation of production ArkUI state and effects. Stable component IDs may identify product concepts, but candidate code must not expose testcase switches, semantic-fact projections, or evaluator-only reducers.
7. **Calibrate both platforms.** Require Android base `0/N`, Android final `N/N`, ArkTS base `0/N`, and ArkTS final `N/N`, with identical case IDs/digests and no unscored cases. Run `scripts/validate_transition_parity.py` before accepting the migration.
8. **Prepare the agent task.** Copy the ArkTS base into an isolated workspace. Supply the public requirement and public transition inputs only. Do not expose final source, private selectors, bindings, or semantic feedback.
9. **Run agent_result.** Use OpenCode plus MiniMax-M3 by default, allow subagents within the candidate directory, set the task timeout to 3600 seconds, build with project-local hvigor, and score with the evaluator-owned ArkTS adapter. Use the same one-shot and timing rules as `$testgen-skill`.
10. **Publish benchmark evidence.** Report code generation, compile, and semantic testcase rates for Android and ArkTS. Keep adapter/transport/provider diagnostics separate. Archive version manifests, prompts, diffs, builds, case rows, and overall elapsed time, then clean temporary build and candidate data.

## Correctness Gates

- ArkTS base/final are functional migrations of the matching Android version boundary, not stubs built only for the selected tests.
- Shared transitions are semantically identical across platforms; parity is proved by IDs, normalized clauses, and digests.
- Base/final polarity is valid on both platforms before any agent score is interpreted.
- The ArkTS final passes through production behavior, not evaluator markers or hardcoded case responses.
- The agent sees no external workspace, final implementation, hidden oracle, or semantic failure feedback.

## Repository Integration

In Long-Term-Benchmark, use `state_tests/canonical/cross_platform_contract.json` as the shared truth; regenerate traces/contracts with the repository scripts instead of duplicating them. Use `scripts/assemble_cross_platform_calibration.py` for four-way polarity and `scripts/run_opencode_glm_eval_macos.py` as the current ArkTS runner template, updating its provider to `minimax-token-plan/MiniMax-M3` when necessary. Verify the complete migration with the existing build, equivalence, dynamic UI, and final-migration checks.
