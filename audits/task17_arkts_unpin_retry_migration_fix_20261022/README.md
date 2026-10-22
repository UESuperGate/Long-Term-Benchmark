# Task17 ArkTS unpin retry migration repair

The owner-bound API 23 runtime probe for `pm_state_009_unpin_failure_recovery`
confirmed that the migrated final preserved `$a` and `$b` and rendered the real
unpin error, but exposed only Dismiss. The production presenter already retained
the failed event and set `retryEnabled`; the page omitted the matching retry
command.

This repair adds a real Retry button which calls the existing page-owned
`unpin(actionEventId)` path. It does not alter the canonical contract, evaluator
assertions, Matrix room result, agent patch, or presenter outcome.

- Contract SHA-256: `351bacebd24bd1c95707bfea9e5caa8d4813a087f88606a3571d8c73d168fd93`
- Before `Index.ets` SHA-256: `2173ac536265213c8b720d2d1d140cda3ecca958fde9befd3f759ee738ee3e32`
- Failed device execution SHA-256: `5d9e10e1ad4defbac82ec0b7f2308b7b653fb52e24ade2116cab5aa7e0367312`
- Failed evidence: `experiment_results/runtime_transition_20261022/task17_arkts_owner_dev/final-unpin-failure-exec-v1/device-execution.json`

- After `Index.ets` SHA-256: `ccd2fcb903e35412f83405bf7b66d2b7accf1e522d1b09fc79cb970617ee027f`
- Successful device execution SHA-256: `9e81b9516726abb7b6a572d4fbd56001ec9575735cb60e636642d79c56853cf6`
- Successful evidence: `experiment_results/runtime_transition_20261022/task17_arkts_owner_dev/final-unpin-failure-exec-v2/device-execution.json`

The failed probe remains immutable beside the successful rerun.
