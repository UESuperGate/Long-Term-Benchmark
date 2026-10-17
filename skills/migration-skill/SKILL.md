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
4. **Replace copied project identity.** Update package names, bundle IDs, version labels, module descriptions, visible strings, and task metadata so no prior benchmark task identity survives in the new base or final project.
5. **Build the ArkTS ground-truth final.** Port the Android final delta end to end, including state, events, effects, failure recovery, persistence, navigation, and real rendered surfaces. Do not add semantics absent from Android final.
6. **Bind the shared contract.** Keep every canonical `caseId`, `given`, `event`, `expected`, and digest unchanged. Add only ArkTS fixture, event, and observation bindings. Platform adapters may translate transport and framework details; they may not redefine expected behavior.
7. **Generate ArkTS semantic tests.** Prefer runtime observation of production ArkUI state and effects. Require evidence that stores, repositories, presenters, navigation, and rendered controls are connected through the real app entry path; dead or demo-only implementations do not satisfy a transition. Stable component IDs may identify product concepts, but candidate code must not expose testcase switches, semantic-fact projections, or evaluator-only reducers.
   - If only source conformance is feasible, do not bind a case exclusively to the ground-truth final's filenames, classes, methods, component IDs, or page split. Accept structurally different code only after confirming equivalent state mutation, effect/persistence, recovery, and real ArkUI entry-path wiring. Recalibrate all four base/final poles after changing an observer.
8. **Calibrate both platforms.** Require Android base `0/N`, Android final `N/N`, ArkTS base `0/N`, and ArkTS final `N/N`, with identical case IDs/digests and no unscored cases. Run `scripts/validate_transition_parity.py` before accepting the migration.
9. **Prepare the agent task.** Copy the ArkTS base into an isolated workspace. Supply the public requirement and public transition inputs only. Do not expose final source, private selectors, bindings, or semantic feedback.
10. **Run agent_result.** Use OpenCode plus MiniMax-M3 by default, allow subagents within the candidate directory, set the task timeout to 3600 seconds, build with project-local hvigor, and score with the evaluator-owned ArkTS adapter. Use the same one-shot and timing rules as `$testgen-skill`. Export candidate-local `PWD`/`OLDPWD`, deny shell wildcard commands that accept absolute paths, and audit logs for any path outside the candidate before accepting the run.
    Add last-match-wins path rules for OpenCode file tools: relative paths allowed, absolute paths denied, canonical candidate prefix re-allowed. Preflight the exact Android Gradle wrapper/plugin mirrors and ArkTS toolchain outside task timing. Serialize disk-heavy candidates per platform, checkpoint every result, archive untracked production files in binary patches, and make runs resumable. Start a fresh run ID after changing isolation policy so logs, patches, and retained scores cannot refer to different attempts. Provider quota/auth/transport failures are unavailable diagnostics and must not enter benchmark denominators; remove stale agent artifacts from migration bundles for unavailable platforms.
11. **Publish benchmark evidence.** Report code generation, compile, and semantic testcase rates for Android and ArkTS. Keep adapter/transport/provider diagnostics separate. Publish the run manifest, four-way calibration/rescore summaries, reconstructable candidate patches, and per-case reports. Full local logs may remain ignored when bulky, but publish their SHA-256 and byte length to bind each score to its local evidence. Archive versions, prompts, builds, and overall elapsed time, then clean temporary build and candidate data.

## Correctness Gates

- ArkTS base/final are functional migrations of the matching Android version boundary, not stubs built only for the selected tests.
- Shared transitions are semantically identical across platforms; parity is proved by IDs, normalized clauses, and digests.
- Base/final polarity is valid on both platforms before any agent score is interpreted.
- The ArkTS final passes through production behavior, not evaluator markers or hardcoded case responses.
- Effectful semantics are production-wired; providing an unused file-backed store while the page injects an in-memory fake does not pass persistence cases.
- The agent sees no external workspace, final implementation, hidden oracle, or semantic failure feedback.
- Every scored agent patch reconstructs exactly, including new untracked production files; every unavailable provider run remains unscored and resumable.

## Repository Integration

In Long-Term-Benchmark, tasks 01-07 use `state_tests/canonical/cross_platform_contract.json`; tasks 08+ use `state_tests/canonical/new_tasks_cross_platform_contract.json` plus its bindings file. Regenerate contracts instead of duplicating them. For tasks 08+, use `scripts/materialize_new_task_migrations.py`, `scripts/generate_new_tasks_cross_platform_contract.py`, `scripts/calibrate_new_tasks.py`, `scripts/run_new_tasks_opencode_eval_macos.py`, `scripts/rescore_new_tasks_from_patches.py`, and `scripts/assemble_new_tasks_experiment.py`. Verify four-way polarity, contract parity, candidate reconstruction, compile results, semantic rows, and evidence provenance before publishing.
