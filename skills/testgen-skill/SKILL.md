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

## Workflow

1. **Trace behavior before writing tests.** Compare base and final production code and final tests. Identify state holders, events, effects, persistence/SDK calls, rendering, asynchronous completion, and rollback or cleanup.
2. **Define the canonical transitions.** Give each case a stable ID and atomic `given`, `event`, `expected`, plus invariants and evidence. Cover initial state, success, failure, cancellation, retry/timeout, persistence/restoration, and cross-surface propagation when the feature has them.
3. **Separate changed from unchanged semantics.** Every scored case must be final-positive and must fail on base for a semantic reason. Put unchanged regressions in a non-polarity diagnostic suite.
4. **Generate evaluator-owned Android tests.** Prefer runtime state/effect/UI observation through a narrow adapter. Keep fixtures deterministic. Do not let candidate code select outcomes by testcase ID, return oracle facts, or read evaluator files. Compile adapters independently per class or case so one API mismatch cannot hide unrelated results.
5. **Retain exact upstream JUnit only as diagnostics.** It is useful for source fidelity, but an API-shape compile failure is `adapter_failed`, not evidence that the semantic transition failed.
6. **Calibrate on immutable refs.** Run the same case IDs and transition digests against Android base and final. Require base `0/N` and final `N/N`, with no `not_scored`. Repair the contract or adapter when calibration fails; never hardcode tag checks or markers.
7. **Run the agent candidate.** Use OpenCode with `minimax-token-plan/MiniMax-M3`, endpoint `https://api.minimaxi.com/v1`, and a 3600-second task timeout. Keep the API key in the user's OpenCode config or an environment variable, never in the skill, repository, prompt, logs, or result bundle. Allow subagents, constrain all exploration to the copied candidate directory, and provide only the public requirement and public transition inputs.
8. **Score once without semantic feedback.** Build diagnostics may be used for compilation repair. Do not reveal failing semantic cases to the agent or iteratively coach it against the oracle.
9. **Check discrimination and integrity.** Require all semantic cases to be scored and normally require `0 < agent_passed < N`. If an agent gets `0/N` or `N/N`, audit mutations, missing effects, overly weak assertions, leakage, and task completeness. Do not tune expectations merely to force a middle score.
10. **Record and clean up.** Time from overall run start through the last task completion; do not separately add subagent time. Preserve prompts, versions, logs, diffs, build outcome, semantic rows, and digests. Remove build caches, temporary worktrees, unpacked archives, and duplicate candidates after archiving evidence.

Validate normalized results with:

```bash
python3 scripts/validate_result_matrix.py \
  --base base.json --final final.json --agent agent.json \
  --output validation.json
```

## Repository Integration

In Long-Term-Benchmark, reuse `scripts/generate_state_transition_traces.py`, `scripts/generate_cross_platform_contract.py`, `scripts/calibrate_android_external_observer.py`, `scripts/run_android_portable_semantic_observer.py`, and `scripts/run_opencode_glm_android_eval_macos.py`. Set `--agent-timeout 3600`; keep the portable semantic observer authoritative and the exact upstream JUnit observer diagnostic.

Do not report adapter/transport readiness as a benchmark metric. The published metrics are code generation rate, compile pass rate, and semantic testcase pass rate.
