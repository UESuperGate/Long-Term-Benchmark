# Task17 Android MiniMax-M3 Agent Audit

## Benchmark Result

The retained clean-room run used OpenCode 2.0.20 with
`minimax-token-plan/MiniMax-M3` and the configured MiniMax endpoint. The API key
was read from the local OpenCode secret file and is not stored in repository
evidence.

| Metric | Result |
| --- | --- |
| code generation | passed; 15 Kotlin files changed/added |
| application compile | passed (`:app:assembleGplayDebug`) |
| semantic testcases | 0/9 passed, 9/9 failed |
| overall run duration | 1488.650 seconds |
| recursive isolation audit | passed; no violations |

The overall duration includes preparation, the main agent, subagents, model-side
build attempts, independent application build, audit, generic scoring and
cleanup. Subagents are not timed separately.

## Semantic Root Cause

The agent implemented a pinned-list data source, presenter, Compose view, node,
navigation plumbing and tests under the messages feature. It did not expose the
feature through the existing RoomDetails pinned-messages row used by the real
product flow. In every connected testcase the evaluator reached the common
RoomDetails checkpoint through the original room timeline and observed that the
control was absent. The role-independent missing-feature probe therefore
produced a semantic failure for each original transition.

This is a production integration omission by the generated patch. Runtime test
compilation and all nine isolated Gradle/JVM executions passed, so the 0/9 score
is not attributed to adapter, transport, SDK, Gradle or storage availability.

## Evidence

- Agent run: `eval_runs/task17_android_minimax_m3_runtime_20261022_v1/`
- Candidate patch SHA-256:
  `b456e88331bef968da45f1f5d2a407d1f55f04906bd06646a3254ce24e62b7ae`
- Isolation audit SHA-256:
  `a398c11e763334142bcdf4559478fc2357989c337cf47c0c2e897229c0b87ecd`
- Runtime worker:
  `experiment_results/runtime_transition_20261022/task17_android_agent_all_v7_v3/`
- Formal semantic report:
  `experiment_results/runtime_transition_20261022/task17_android_runtime_summary_v1/agent.json`
- Formal report SHA-256:
  `6372f1992b2cbe5c5e92fa788ecc69e829e0beaef8aa32d585ade2f395ef6ecc`

The runner's generic semantic report did not know about connected-v3 and remains
non-publishable. The formal score was independently recomputed from the nine
native JSON files after runtime completion.

## Evaluator Repairs

The first connected attempt stopped before Gradle because the clean-room
candidate intentionally retained Git LFS pointers. The second used an
evaluator-owned, locally hydrated copy but omitted the candidate `.git`
directory; Element X's application Gradle script needs it for version metadata,
so all attempts stopped during configuration. Neither attempt entered the
semantic metric.

The successful third attempt copied the candidate's own clean-room `.git`
metadata, hydrated only locally available LFS objects, and bound the staging
inventory to the archived agent patch. It completed ten owned Gradle processes
(one preparation/compile path plus nine isolated cases), all with exit code 0.

## Storage

`storage_recovery_v9/task17_agent_intermediates_v9` reverified all nine formal
raw hashes before deleting reconstructable hydrated copies, working-tree
archives and repeated per-case LFS guard metadata. It removed 572,504,630
logical bytes without deleting the agent patch, logs, formal reports or native
evidence.
