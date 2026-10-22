# ArkTS Common-Entry Projection Withdrawal

Scope: Task16 and Task17 ArkTS runtime evaluators. No production file, canonical
expectation, invariant, case ID, or transition digest is changed by this repair.

## Root Cause

Both old evaluators executed a real common-page positive control but then
projected final-only state that had never been reached:

- Task16 `runBase` used `missingShape(caseSpec.expected)` and marked every
  canonical invariant false after observing that the identity-reset entry was
  absent. Those values were not runtime post-state.
- Task17 `baseObserved(spec)` returned case-dependent idle/list/action values,
  and every later invariant was marked false after a real banner-next click.
  The click proved a working common page, not those later observations.

The generic expected-value comparator accepted these complete-looking rows as
semantic failures. A runtime label and valid device transport were therefore
insufficient integrity gates. Previous base scores are withdrawn, not reused.

## Preserved Evidence

The original reports and native execution artifacts remain unchanged:

| Historical Report | SHA-256 | Disposition |
| --- | --- | --- |
| `experiment_results/runtime_transition_20261020/formal_agent_scorer_audit/task16-arkts-base-as-agent-v5.json` | `6b86daeb99a62b11901041c91abb3917d96635c8af4cd01aa234e6a72faed964` | Former 0P/10F; withdrawn projected post-state |
| `experiment_results/runtime_transition_20261020/formal_agent_scorer_audit/task17-arkts-base-as-agent-v2.json` | `a1fea74961f07eefaafa0061e6e989527415f4d4cd5f7aff5ee3831856aba8cd` | Former 0P/9F; withdrawn projected post-state |

These are evaluator controls, not model results. The public matrix validator
now rejects scored rows that contain these real entry-absence observations but
still claim ordinary post-transition state instead of validated entry evidence.

## Repair And Acceptance

The adapters now leave post-state and canonical invariants unobserved after an
absent entry. Their raw generic result remains `not_scored`. A narrow independent
entry validator may produce an early semantic failure only after checking:

- A fresh installed candidate, exact case/digest, execution nonce, process,
  successful transport, original row bytes, logs, and uninstall completion.
- Actual focused original application windows, ordered before/after frames,
  absent feature controls, and a physically executed positive-control state change.
- Unchanged packaged production, retained production snapshots, and hashes of
  the reviewed evaluator modules that ran.

The normalized early-failure row has `observed: null`, no evaluated canonical
invariants, `transitionExecuted: false`, and explicit unknown expected fields.
It does not claim that the final-only given or event was reached.

Random-directory base/final copies are being executed with the identical
`agent` role. Central readiness remains false until the current complete control
pair passes public validation with no unscored cases. Original final assertions
remain mandatory and unchanged. No new accepted polarity is claimed here.
