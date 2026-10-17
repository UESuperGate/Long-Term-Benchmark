---
name: testgen-skill
description: Derive canonical state transitions for an extracted Android long-horizon task, generate evaluator-owned Android semantic testcases, calibrate base-all-fail and final-all-pass polarity, and run an isolated OpenCode plus MiniMax-M3 agent result to verify discrimination. Use after explore-skill or when repairing Android benchmark semantics.
---

# Generate Android State-Transition Tests

Use one canonical transition contract as the semantic truth. Android test code is an adapter to that contract; upstream unit tests and source-pattern observers are supporting diagnostics, not the benchmark definition.

## Inputs And Outputs

Start from `$explore-skill` artifacts plus the Android base/final refs. Read [transition-contract.md](references/transition-contract.md) and [agent-evaluation.md](references/agent-evaluation.md).

Produce:

- `transitions.json`: platform-neutral `given -> event -> expected` cases with evidence and stable digests.
- Android evaluator adapter/tests owned outside the candidate workspace.
- normalized `base.json`, `final.json`, and `agent.json` result files.
- a benchmark summary containing only code generation, compile, and semantic testcase metrics; keep transport, adapter, and provider failures in diagnostics.

Build a canonical contract from a reviewed draft instead of hand-writing digests:

```bash
python3 scripts/build_transition_contract.py \
  --input transitions.draft.json \
  --output transitions.json
```

## Workflow

1. **Trace behavior before writing tests.** Compare base and final production code and final tests. Identify state holders, events, effects, persistence/SDK calls, rendering, asynchronous completion, and rollback or cleanup. Resolve every scored boundary value, enum member, default, and capacity from final production code and corroborate it with an upstream test when one exists; record the source path and symbol in task evidence instead of inferring a plausible value.
2. **Define the canonical transitions.** Give each case a stable ID and atomic `given`, `event`, `expected`, plus invariants and evidence. Cover initial state, success, failure, cancellation, retry/timeout, persistence/restoration, and cross-surface propagation when the feature has them.
3. **Separate changed from unchanged semantics.** Every scored case must be final-positive and must fail on base for a semantic reason. Put unchanged regressions in a non-polarity diagnostic suite.
4. **Generate evaluator-owned Android tests.** Prefer runtime state/effect/UI observation through a narrow adapter. Keep fixtures deterministic. For every effectful transition, verify that the implementation is wired into the production entry path; an unused persistent store, repository, presenter, or UI component is not semantic evidence. Do not let candidate code select outcomes by testcase ID, return oracle facts, or read evaluator files. Compile adapters independently per class or case so one API mismatch cannot hide unrelated results.
   - When runtime execution is unavailable and a source observer is used, label it `source_transition_conformance`. Scan configured production roots plus every changed production file so a valid new module layout cannot disappear from observation. Express each clause as semantic alternatives. An exact filename, class name, method name, component ID, or page decomposition may support evidence but must never be the sole reason an equivalent implementation fails. If no production source is scanned, mark the adapter failed and every case `not_scored`; never turn an empty scan into semantic failures.
   - After the first isolated agent run, reconstruct its candidate from base plus archived patch and audit every `0/N` or `N/N` result. Add an observer alternative only when production state, effect/persistence, failure recovery, and entry-path wiring are all present. Re-run base/final polarity after every observer change.
5. **Retain exact upstream JUnit only as diagnostics.** It is useful for source fidelity, but an API-shape compile failure is `adapter_failed`, not evidence that the semantic transition failed.
6. **Calibrate on immutable refs.** Run the same case IDs and transition digests against Android base and final. Require base `0/N` and final `N/N`, with no `not_scored`. A final failure must first trigger a contract-to-source audit: correct any guessed constants or semantics before changing observer rules or migrated code. Repair the contract or adapter when calibration fails; never hardcode tag checks or markers.
7. **Run the agent candidate.** Use OpenCode with `minimax-token-plan/MiniMax-M3`, endpoint `https://api.minimaxi.com/v1`, and a 3600-second task timeout. Keep the API key in the user's OpenCode config or an environment variable, never in the skill, repository, prompt, logs, or result bundle. Allow subagents, constrain all exploration to the copied candidate directory, and provide only the public requirement and public transition inputs. Set both subprocess `cwd` and exported `PWD`/`OLDPWD` to the candidate. `external_directory: deny` is not sufficient when shell wildcards such as `ls *`, `find *`, or `cat *` permit absolute operands; deny those patterns and allow only fixed project-local commands.
   - Layer path-specific rules onto `read`, `edit`, `glob`, and `list`: allow relative paths, deny `/*`, then allow only the canonical candidate prefix. Audit completed tool inputs structurally; do not count permission-denied attempts as leaks. A completed candidate-external access invalidates that platform-task run.
   - Preflight outside agent timing: install the exact Gradle wrapper, resolve plugin/dependency mirrors, and prove the untouched base builds. Give the agent a candidate-local public init script when a mirror is required. Tell it to run the allowed build command exactly, without pipes or redirection.
   - Keep at most one disk-heavy Android candidate active at a time. Android and ArkTS may run concurrently when storage allows. Check free space before each build and remove only regenerable caches or completed candidates.
8. **Score once without semantic feedback.** Build diagnostics may be used for compilation repair. Do not reveal failing semantic cases to the agent or iteratively coach it against the oracle.
9. **Check discrimination and integrity.** Require all semantic cases to be scored and normally require `0 < agent_passed < N`. If an agent gets `0/N` or `N/N`, audit mutations, missing effects, production wiring, overly weak assertions, leakage, and task completeness. A class that implements the requested behavior but is replaced by an in-memory fake or never instantiated in the app must fail the affected transition. Do not tune expectations merely to force a middle score.
10. **Record and clean up.** Time from overall run start through the last task completion; do not separately add subagent time. Preserve prompts, versions, logs, diffs, build outcome, semantic rows, and digests. Export patches with newly created files included (`git add -N` before `git diff --binary`, or an equivalent method), then verify base plus patch reconstructs the scored candidate. Write a resumable manifest after every platform-task result. Bind each retained score to the matching log and patch; publish the manifest, calibration/rescore summaries, and reconstructable patches with the benchmark bundle. Bulky local logs may remain ignored, but publish their SHA-256 and byte length so the retained score is bound to an immutable local archive. When permissions or isolation policy changes, use a fresh run ID instead of reusing a checkpoint whose evidence was overwritten. Treat provider quota/auth/transport failures as `unavailable` diagnostics, exclude them from benchmark denominators, and resume them under the same model and conditions; never convert them to code-generation, compile, or semantic failures. Remove stale agent files from published bundles when a newer run marks that platform unavailable. Remove build caches, temporary worktrees, unpacked archives, and duplicate candidates after archiving evidence.

Validate normalized results with:

```bash
python3 scripts/validate_result_matrix.py \
  --base base.json --final final.json --agent agent.json \
  --output validation.json
```

## Repository Integration

In Long-Term-Benchmark, tasks 01-07 reuse `scripts/generate_state_transition_traces.py`, `scripts/generate_cross_platform_contract.py`, `scripts/calibrate_android_external_observer.py`, and `scripts/run_android_portable_semantic_observer.py`. Tasks 08+ use `scripts/generate_new_tasks_cross_platform_contract.py`, `scripts/run_task_semantic_observer.py`, `scripts/calibrate_new_tasks.py`, `scripts/run_new_tasks_opencode_eval_macos.py`, `scripts/rescore_new_tasks_from_patches.py`, and `scripts/assemble_new_tasks_experiment.py`. Set `--agent-timeout 3600`; keep the declared semantic observer mode authoritative and exact upstream JUnit or transport checks diagnostic.

Do not report adapter/transport readiness as a benchmark metric. The published metrics are code generation rate, compile pass rate, and semantic testcase pass rate.
