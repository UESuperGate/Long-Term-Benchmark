# Element X Long-Horizon Task Extraction

## 06/07 decision

Tasks 06 and 07 remain separate canonical tasks. Multi-select poll creation/voting and recent-search persistence do not share a user outcome or connected state-transition graph. They are grouped for scheduling and reporting by `suites/06_07_v26_09_release_bundle.json`, without sharing one testcase contract.

## Accepted tasks

| ID | Release boundary | Capability | Long-horizon boundary |
|---|---|---|---|
| 08 | v25.08.3 -> v25.08.4 | Message threads | Navigation, scoped timeline, composer relations, multiple send types, failure recovery |
| 09 | v25.08.4 -> v25.10.0 | Spaces lifecycle | Hierarchy pagination, invites, per-room joins, leave selection, retry |
| 10 | v25.08.2 -> v25.08.3 | Media upload quality | Server limit, metadata, estimation, preference, send gating |
| 11 | v25.06.2 -> v25.06.3 | Room upgrade navigation | SDK mapping, read-only state, predecessor/successor UI and navigation |
| 12 | v25.04.3 -> v25.05.0 | Report room | Form, report, optional leave, partial-failure retry |
| 13 | v25.03.1 -> v25.03.2 | User verification | Request/challenge state machine, cancellation, identity violations |
| 14 | v25.02.0 -> v25.03.0 | Join by address | Validation, asynchronous resolution, stale results, join handoff |
| 15 | v0.6.1 -> v0.6.3 | Account deactivation | Sensitive form, confirmation, destructive request, retry and exit |
| 16 | v0.5.0 -> v0.5.1 | Identity reset | Eligibility, confirmation, reauthentication, SDK handle, cancel/retry |
| 17 | v0.5.1 -> v0.5.3 | Pinned messages | Dedicated timeline, pagination, permissions, unpin and failure state |
| 18 | v26.05.2 -> v26.06.1 | Custom notification sounds | Picker, file copy, persistence, channel update, migration and rollback |

Each accepted directory contains `task.json`, evaluator-private `evidence.json`, public `requirement.md`, and deterministic `raw_release_evidence.json`.

## Rejected examples

- Notification quick actions (`v0.7.5`): the enabling delta is eight files and 58 insertions, too small for parity with the benchmark's existing long-horizon tasks.
- Full Matrix ID on provider screen (`v26.08.3`): useful behavior, but primarily one input-validation path.

## Validation

- All 11 base/final refs resolve to immutable commits and every base is an ancestor of its final.
- Every target feature commit is reachable from final and absent from base history.
- Every declared production and test path exists in the final tree.
- Every task has at least three transitions and an explicit failure, cancellation, retry, or recovery path.
